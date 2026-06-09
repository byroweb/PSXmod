"""
core/mis.py — extract every embedded TIM image from MIS.T (mission previews).

MIS.T is the mission-text container. Besides its text corpus it embeds a run of
~194 small TIM images (100x100, 8bpp): the mission-preview pictures shown to the
player on the briefing screen. jPSXdec indexes them as MIS.T[0]..MIS.T[n], but
AC1mod historically surfaced only the first. This module scans the raw container
for TIM file headers and slices each one out so they can all be shown nested
under MIS.T (and exported), independent of jPSXdec at runtime.

A PS1 TIM file:
  0x00  u32 0x00000010              magic (id=0x10, ver=0)
  0x04  u32 flag                    bits0-2 = pmode, bit3 = has CLUT
  if CLUT: u32 len; u16 x,y,w,h; w*h*2 bytes  (len counts the whole block)
  image:  u32 len; u16 x,y,w,h;  data           (len counts the whole block)
Total length = 8 + (clut block) + (image block).
"""
from __future__ import annotations
import struct
from pathlib import Path
from core import pa_parser as PP

MIS_SECTORS = (101920, 103449)
TIM_MAGIC = b"\x10\x00\x00\x00"


def _tim_length(buf: bytes, off: int) -> int | None:
    """Return total byte length of the TIM starting at `off`, or None if invalid."""
    if buf[off:off + 4] != TIM_MAGIC:
        return None
    if off + 8 > len(buf):
        return None
    flag = struct.unpack_from("<I", buf, off + 4)[0]
    pmode = flag & 0x07
    has_clut = bool(flag & 0x08)
    if pmode > 4:
        return None
    p = off + 8
    if has_clut:
        if p + 4 > len(buf):
            return None
        clut_len = struct.unpack_from("<I", buf, p)[0]
        if clut_len < 12 or p + clut_len > len(buf):
            return None
        p += clut_len
    if p + 4 > len(buf):
        return None
    img_len = struct.unpack_from("<I", buf, p)[0]
    if img_len < 12 or p + img_len > len(buf):
        return None
    p += img_len
    return p - off


def mis_blob(bin_path) -> bytes:
    """The whole MIS.T container as one contiguous byte blob (user data only)."""
    return PP._read_sectors(bin_path, *MIS_SECTORS) if hasattr(PP, "_read_sectors") \
        else _read_sectors(bin_path)


def _read_sectors(bin_path) -> bytes:
    RAW, OFF, DATA = 2352, 24, 2048
    s0, s1 = MIS_SECTORS
    out = bytearray()
    with open(bin_path, "rb") as f:
        for s in range(s0, s1 + 1):
            f.seek(s * RAW + OFF)
            out += f.read(DATA)
    return bytes(out)


def find_tims(bin_path) -> list[tuple[int, int, bytes]]:
    """Scan MIS.T for TIMs. Returns [(index, blob_offset, tim_bytes)]."""
    buf = _read_sectors(bin_path)
    out = []
    off = 0
    idx = 0
    n = len(buf)
    while off < n - 8:
        if buf[off:off + 4] == TIM_MAGIC:
            ln = _tim_length(buf, off)
            if ln:
                out.append((idx, off, buf[off:off + ln]))
                idx += 1
                off += ln
                continue
        off += 4          # TIMs are word/sector aligned; step by 4 is safe + fast
    return out


def extract_tims(bin_path, out_dir) -> list[Path]:
    """Write every MIS.T TIM to out_dir/MIS.T[i].tim; return the paths in order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for idx, _off, data in find_tims(bin_path):
        p = out_dir / f"MIS.T[{idx}].tim"
        p.write_bytes(data)
        paths.append(p)
    return paths
