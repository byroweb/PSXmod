# AC1mod

A desktop tool for browsing, previewing, annotating and modding the assets of the
PlayStation game **Armored Core** (1997, `SLUS-01323`). Evolved from **PSXmod**
(a general PSX BIN asset browser) into an AC1-specific toolkit, built on
[jPSXdec](https://github.com/m35/jpsxdec).

> **No game data is included or distributed.** You must supply your own legally
> obtained disc image. The tool reads assets from *your* copy, on *your* machine;
> the repository ships only source code.

## Features
- Browse the disc's file index (via jPSXdec); preview **TIM** images, **text**, and
  raw **hex** per entry; import replacement images/audio.
- **PA##.T 3D model viewer** — the stage/object geometry packs decode into an
  orbitable, software-rendered mesh (drag = orbit, wheel = zoom). Each PA file is a
  container of many low-poly objects (stage pieces, MTs, ACs, props).
- **Per-PA notes** saved in the `.ac1mod` project file — annotate what each PA file
  contains.
- **Headless CLI** (`ac1mod_cli.py`) — `list / info / note / obj / render`: browse,
  annotate, export OBJ, and render PNG previews without the GUI.

## Run
```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./run_ac1mod.sh            # or: .venv/bin/python main.py
```
CLI examples:
```sh
.venv/bin/python ac1mod_cli.py list
.venv/bin/python ac1mod_cli.py render GG/P0/PA00.T -o /tmp/pa00.png
.venv/bin/python ac1mod_cli.py note set GG/P0/PA00.T "PA00 = ..."
```

## How the PA geometry was reverse-engineered
The PA##.T container + custom (non-TMD) primitive format were reverse-engineered
separately; see the companion notes in the `AC_1_USA_RE` project
(`docs/PA_FORMAT.md`). `core/pa_parser.py` vendors that validated decoder.

## Legal
Unofficial, non-commercial fan tooling for interoperability and preservation. Not
affiliated with or endorsed by FromSoftware or Agetec. *Armored Core* and all
related assets are property of their respective owners. This repository contains
**only original source code** — no game executable, ROM, disc image, textures, or
audio.
