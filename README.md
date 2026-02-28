# Chessist

<div align="center">

**Real-time chess analysis overlay powered by computer vision and Stockfish**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-lightgrey.svg)]()

[Features](#features) • [Quick Start](#quick-start) • [Usage](#usage) • [Configuration](#configuration) • [Building](#building-standalone-executable)

**Project page:** Enable [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) from the **`/docs`** folder to host the landing page at `https://<username>.github.io/<repo-name>`.

</div>

---

## What is this?

Chessist watches your screen, detects the chess board, converts it to FEN using template matching, and shows you the best move via Stockfish — all in a sleek overlay panel. Works with Chess.com, Lichess, or any chess interface.

**No browser extensions. No game integration. Just screen capture + vision + engine.**

```
Screen → Board Detection → Template Matching → FEN → Stockfish → Best Move
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Live Board Detection** | Automatically finds and tracks the chess board on your screen |
| **Template-Based Vision** | Matches pieces using normalized correlation — no ML models needed |
| **Stockfish Integration** | Configurable depth, time, hash, and threads for analysis |
| **Auto-Play Mode** | Optionally execute moves with human-like mouse movements |
| **Modern Overlay** | Clean tkinter UI with dark/light themes |
| **Cross-Platform** | Runs on Linux and Windows (standalone builds available) |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **Stockfish** — [Download](https://stockfishchess.org/download/) or `apt install stockfish`
- **Templates** — Piece images in `templates/` (see [Templates](#templates))

### Install

```bash
git clone https://github.com/Kaleab-Ayenew/chessist.git
cd chessist
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Run

```bash
python main.py
```

The overlay opens. Click **Start Agent**, open your chess game, and watch the magic.

---

## Usage

### Overlay Mode (Default)

```bash
python main.py
# or after install:
auto-chess
```

The control panel provides:

- **We play** — Select White or Black
- **Show move** — Display recommended move
- **Auto-play** — Let the bot play moves (humanized timing)
- **Engine settings** — Adjust time, depth, hash, threads

### Terminal Mode

```bash
python main.py --no-overlay
```

### Test Vision Pipeline

```bash
python main.py --test-vision-template contour
python main.py --test-vision-template edges
```

Uses `sample_screenshot.png` and outputs debug images to temp directory.

---

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

### Engine Settings

| Key | Default | Description |
|-----|---------|-------------|
| `stockfish_path` | `stockfish` | Path to Stockfish binary |
| `engine.time_seconds` | `5.0` | Analysis time limit |
| `engine.depth` | `30` | Search depth |
| `engine.hash_mb` | `512` | Hash table size (MB) |
| `engine.threads` | `4` | CPU threads |

### Vision Settings

| Key | Default | Description |
|-----|---------|-------------|
| `template_fen.board_extraction` | `contour` | Detection method: `contour` or `edges` |
| `template_fen.templates_dir` | `templates` | Piece template directory |
| `template_fen.normalize` | `true` | Normalize templates before matching |

### Humanization (Auto-Play)

| Key | Default | Description |
|-----|---------|-------------|
| `humanization.reaction_time_mean_ms` | `800` | Delay before moving |
| `humanization.move_time_mean_ms` | `250` | Delay between clicks |
| `humanization.click_jitter_std_fraction` | `0.15` | Random click offset |
| `humanization.mouse_speed_px_per_sec` | `800` | Mouse movement speed |

---

## Templates

Place piece images in `templates/`:

```
templates/
├── wp.png  wn.png  wb.png  wr.png  wq.png  wk.png   # White pieces
├── bp.png  bn.png  bb.png  br.png  bq.png  bk.png   # Black pieces
└── 200.png                                           # Empty square
```

Extract templates from your target chess site for best accuracy. Optional `*_mask.png` files for transparency handling.

---

## Building Standalone Executable

### Linux

```bash
./build_linux.sh
# Output: dist/auto_chess
```

### Windows

```batch
build_windows.bat
# Output: dist\auto_chess.exe
```

The executable bundles everything except Stockfish — install it separately and ensure it's in PATH or configure the path in `config.yaml`.

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Screen    │────▶│    Board     │────▶│   Warp to   │
│  Capture    │     │  Detection   │     │   400×400   │
└─────────────┘     └──────────────┘     └─────────────┘
                                                │
                                                ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Stockfish  │◀────│   Generate   │◀────│  Template   │
│  Analysis   │     │     FEN      │     │  Matching   │
└─────────────┘     └──────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│   Overlay   │
│  Best Move  │
└─────────────┘
```

1. **Board Detection** — Canny edges + contour finding (or gradient projection)
2. **Perspective Warp** — Transform to 400×400 square grid
3. **Square Analysis** — Variance check for occupancy, template correlation for piece ID
4. **FEN Generation** — Convert 64 squares to FEN string
5. **Engine Query** — Stockfish analyzes position, returns best move
6. **Display/Execute** — Show in overlay, optionally play with pyautogui

---

## Debug Output

Debug images are written to a temp directory:

| OS | Location |
|----|----------|
| Linux | `/tmp/auto_chess/` |
| macOS | `$TMPDIR/auto_chess/` |
| Windows | `%TEMP%\auto_chess\` |

---

## Disclaimer

MIT License. For educational purposes.

Automated play may violate the Terms of Service of chess platforms. Use responsibly and at your own risk.

---

<div align="center">

**Built with OpenCV, python-chess, and Stockfish**

</div>
