# PSXmod

A desktop GUI for modding PlayStation 1 disc images. Open a `.bin`/`.cue`,
browse the files inside, **preview and replace TIM images and audio**, then
rebuild the disc. PSXmod expands on — and currently depends on —
[jPSXdec](https://github.com/m35/jpsxdec) for indexing and asset extraction.

> **Bring your own disc.** No game data is included. You need a legally-owned
> copy of the game you want to mod, dumped to `.bin`/`.cue`.

## Features

- Index a disc image with jPSXdec and browse its contents in a tree.
- Preview TIM textures (with CLUT handling) and listen to audio tracks.
- Import replacement images (PNG / GIF / TIM) and audio (WAV), with
  validation against the original format/dimensions/bit-depth.
- Save your work as a `.psxmod` project file and rebuild the modified disc.

## Requirements

- **Python 3.10+**
- **Java 8+** (jPSXdec is a Java tool)
- Python packages: PyQt6, Pillow, pygame (see `requirements.txt`)

## Install

```bash
git clone https://github.com/byroweb/PSXmod.git
cd PSXmod
./INSTALL.sh
```

`INSTALL.sh` checks for Java, installs the Python dependencies, and downloads
jPSXdec into `jpsxdec/`. To do it manually instead:

```bash
pip install -r requirements.txt
# then place jpsxdec.jar in ./jpsxdec/ (https://github.com/m35/jpsxdec/releases)
```

## Run

```bash
python3 main.py
```

## Project layout

```
main.py            PyQt6 application / main window
core/
  jpsxdec.py       jPSXdec wrapper: indexing, TIM parse/encode, audio
  project.py       .psxmod project (JSON) load/save
  workers.py       background threads (index / build / extract)
INSTALL.sh         dependency + jPSXdec setup
```

At runtime PSXmod creates working directories (`EXISTING_FILES/`,
`NEW_FILES/`, `NEW_AUDIO/`) and index files; these are git-ignored.

## Credits & licensing

PSXmod is released under the [MIT License](LICENSE).

It depends on **[jPSXdec](https://github.com/m35/jpsxdec)** by Michael Sabin,
which is **not bundled** here — `INSTALL.sh` downloads it from its official
release page. jPSXdec is distributed under its own (non-commercial) license;
see its repository for terms.
