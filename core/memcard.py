"""
core/memcard.py — PS1 memory-card (.mcd/.mcr/.srm/raw 128K) reader/writer.

Presents a card as a directory of save files. Decodes each save's standard PS1
icon (palette@0x60, 16x16 4bpp@0x80, BGR555) so the browser can show a thumbnail.
Identifies Armored Core 1 saves (product code SCUS-94182 / SLUS-01323, title
"ARMOREDCORE01") — only those are openable for emblem editing; everything else is
listed read-only / out of scope.

Card layout (standard 128 KiB, 16 blocks × 8192 B):
  block 0 = directory. Frame 0 (128 B) = 'MC' header.
            Frames 1..15 (128 B each) = directory entry for blocks 1..15:
              +0x00 u32 state  (0x51 first/in-use, 0x52 mid-link, 0x53 end-link,
                                0xA0 free)
              +0x04 u32 file size (bytes; in the first-block entry)
              +0x08 u16 next-block link (0xFFFF = none)
              +0x0A filename  ASCII, NUL-terminated (e.g. "BASCUS-94182A")
              +0x7F u8 XOR checksum of bytes 0x00..0x7E
  blocks 1..15 = save data (8192 B). First block begins with the title frame:
              +0x00 'SC'; +0x02 icon flag (0x11/12/13 = 1/2/3 frames);
              +0x04 title Shift-JIS (64 B); +0x60 icon CLUT (16×u16 BGR555);
              +0x80.. icon frame(s), 16x16 4bpp = 128 B each.
"""
from __future__ import annotations
import struct
from dataclasses import dataclass, field
from pathlib import Path

BLOCK = 8192
FRAME = 128
N_BLOCKS = 16

# AC1 (USA) save signatures. The on-card product code is fixed by the game
# regardless of disc reprint; we also accept the title string as a fallback.
AC1_CODES = ("SCUS-94182", "SLUS-01323", "SCUS94182", "SLUS01323")
AC1_TITLES = ("ARMOREDCORE01", "ARMOREDCORE")


def _bgr555(w: int):
    if w == 0:
        return (0, 0, 0, 0)            # 0x0000 = transparent on PS1 icons
    r = (w & 0x1F) << 3
    g = ((w >> 5) & 0x1F) << 3
    b = ((w >> 10) & 0x1F) << 3
    return (r, g, b, 255)


@dataclass
class SaveFile:
    slot: int                  # directory frame / first block index (1..15)
    code: str                  # raw filename / product code
    title: str                 # decoded Shift-JIS title
    size_blocks: int
    block_indices: list[int]   # data blocks making up this file (in link order)
    icon_frames: int
    is_ac1: bool
    data_offset: int           # byte offset of the first data block in the card

    @property
    def label(self) -> str:
        return self.title or self.code


class MemoryCard:
    def __init__(self, path):
        self.path = Path(path)
        self.raw = bytearray(self.path.read_bytes())
        if len(self.raw) < BLOCK * N_BLOCKS:
            raise ValueError(f"not a 128K PS1 card: {len(self.raw)} bytes")
        self.saves: list[SaveFile] = []
        self._parse_directory()

    # ---- directory ---------------------------------------------------------
    def _dir_frame(self, i: int) -> bytes:
        return bytes(self.raw[i * FRAME:(i + 1) * FRAME])

    def _parse_directory(self):
        self.saves.clear()
        for slot in range(1, N_BLOCKS):
            fr = self._dir_frame(slot)
            state = struct.unpack_from("<I", fr, 0)[0]
            if state != 0x51:                      # only first-block entries
                continue
            size = struct.unpack_from("<I", fr, 4)[0]
            code = fr[0x0A:0x0A + 20].split(b"\x00")[0].decode("ascii", "replace")
            # follow the link chain for multi-block saves
            blocks = [slot]
            link = struct.unpack_from("<h", fr, 8)[0]
            guard = 0
            while link != -1 and 1 <= link + 1 < N_BLOCKS and guard < N_BLOCKS:
                b = link + 1
                blocks.append(b)
                lf = self._dir_frame(b)
                link = struct.unpack_from("<h", lf, 8)[0]
                guard += 1
            data_off = slot * BLOCK
            title, frames = self._read_title(data_off)
            code_u = code.upper()
            is_ac1 = (any(c in code_u for c in AC1_CODES) or
                      any(t in title.upper().replace(" ", "") for t in AC1_TITLES))
            self.saves.append(SaveFile(
                slot=slot, code=code, title=title,
                size_blocks=max(1, size // BLOCK), block_indices=blocks,
                icon_frames=frames, is_ac1=is_ac1, data_offset=data_off,
            ))

    def _read_title(self, off: int):
        blk = self.raw[off:off + BLOCK]
        if blk[0:2] != b"SC":
            return "", 0
        frames = {0x11: 1, 0x12: 2, 0x13: 3}.get(blk[2], 1)
        raw = bytes(blk[0x04:0x04 + 64]).split(b"\x00")[0]
        try:
            title = raw.decode("shift_jis").strip()
        except Exception:
            title = raw.decode("ascii", "replace")
        # PS1 titles use full-width chars; normalise to ASCII where possible
        title = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E
                        else (" " if c == "　" else c) for c in title).strip()
        return title, frames

    # ---- icon --------------------------------------------------------------
    def icon_rgba(self, save: SaveFile, frame: int = 0):
        """Return (w, h, rgba_bytes) for an icon frame, or None."""
        off = save.data_offset
        blk = self.raw[off:off + BLOCK]
        if blk[0:2] != b"SC":
            return None
        pal = [_bgr555(struct.unpack_from("<H", blk, 0x60 + i * 2)[0]) for i in range(16)]
        ic = 0x80 + frame * 0x80
        out = bytearray()
        for i in range(16 * 16):
            b = blk[ic + i // 2]
            idx = (b & 0x0F) if i % 2 == 0 else (b >> 4)
            out += bytes(pal[idx])
        return 16, 16, bytes(out)

    # ---- raw block access (for emblem read/write) --------------------------
    def block_bytes(self, slot: int) -> bytes:
        return bytes(self.raw[slot * BLOCK:(slot + 1) * BLOCK])

    def write_block(self, slot: int, data: bytes):
        if len(data) != BLOCK:
            raise ValueError("block must be 8192 bytes")
        self.raw[slot * BLOCK:(slot + 1) * BLOCK] = data

    def patch(self, slot: int, offset: int, data: bytes):
        """Write `data` at `offset` within block `slot`'s data."""
        base = slot * BLOCK + offset
        self.raw[base:base + len(data)] = data

    def _fix_dir_checksum(self, slot: int):
        base = slot * FRAME
        x = 0
        for i in range(0x7F):
            x ^= self.raw[base + i]
        self.raw[base + 0x7F] = x

    def save(self, path=None):
        """Recompute directory checksums and write the card back to disk."""
        for slot in range(1, N_BLOCKS):
            self._fix_dir_checksum(slot)
        Path(path or self.path).write_bytes(bytes(self.raw))


# ---------------------------------------------------------------------------
# Armored Core 1 emblem (player-drawn decal)
# ---------------------------------------------------------------------------
# Confirmed statically (see docs): the emblem is 64x64, 4bpp (16 colours), using
# a fixed rainbow BGR555 palette (the in-game colour picker) stored in the save
# block at 0x0C3A. The pixel data is RAW (not an embedded TIM) and lives in the
# block's tail region (default-blank = 0xFF). The exact pixel offset + whether
# there are multiple emblems are pending a DuckStation byte-diff (draw + save +
# diff the card) — see docs/AC1_EMBLEM.md. Both are exposed as parameters so the
# decoder/encoder is correct the moment the offset is confirmed.
EMBLEM_W = EMBLEM_H = 64
EMBLEM_BPP = 4
EMBLEM_PAL_OFF = 0x0C3A          # 16 x u16 BGR555, in block data
EMBLEM_PIX_OFF = 0x0E80          # best-guess; 2048 B (64x64 4bpp). DuckStation-confirm.
EMBLEM_BYTES = EMBLEM_W * EMBLEM_H // 2   # 2048


def emblem_palette(block: bytes):
    """16 (r,g,b) tuples from the fixed emblem colour picker @0x0C3A."""
    return [_bgr555(struct.unpack_from("<H", block, EMBLEM_PAL_OFF + i * 2)[0])[:3]
            for i in range(16)]


def decode_emblem(block: bytes, pix_off: int = EMBLEM_PIX_OFF):
    """Decode one 64x64 4bpp emblem to (w, h, rgba_bytes)."""
    pal = emblem_palette(block)
    out = bytearray()
    for i in range(EMBLEM_W * EMBLEM_H):
        b = block[pix_off + i // 2]
        idx = (b & 0x0F) if i % 2 == 0 else (b >> 4)
        r, g, b3 = pal[idx]
        out += bytes((r, g, b3, 255))
    return EMBLEM_W, EMBLEM_H, bytes(out)


def is_emblem_blank(block: bytes, pix_off: int = EMBLEM_PIX_OFF) -> bool:
    seg = block[pix_off:pix_off + EMBLEM_BYTES]
    return all(b == 0xFF for b in seg) or all(b == 0x00 for b in seg)


def _nearest(rgb, palette):
    r, g, b = rgb
    best_i, best_d = 0, 1 << 30
    for i, (pr, pg, pb) in enumerate(palette):
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def encode_emblem(image_path, block: bytes) -> bytes:
    """Match an image (GIF/PNG, any size) to the save's fixed 16-colour emblem
    palette and pack it as 64x64 4bpp -> EMBLEM_BYTES bytes ready to write back."""
    from PIL import Image
    pal = emblem_palette(block)
    img = Image.open(image_path)
    try:
        img.seek(0)                       # first frame of an animated GIF
    except Exception:
        pass
    img = img.convert("RGB").resize((EMBLEM_W, EMBLEM_H), Image.NEAREST)
    px = list(img.getdata())
    idx = [_nearest(p, pal) for p in px]
    out = bytearray(EMBLEM_BYTES)
    for i in range(EMBLEM_W * EMBLEM_H):
        lo = i % 2 == 0
        out[i // 2] |= idx[i] if lo else (idx[i] << 4)
    return bytes(out)


def read_card(path) -> MemoryCard:
    return MemoryCard(path)
