# Auto Chess

**Chess assist:** screen capture → template-based vision (board → FEN) → Stockfish → recommended move on a **CustomTkinter control panel** and in the terminal. Optional **auto-play**: the bot can play moves itself with pyautogui (humanized clicks). No browser automation: you open Chess.com (or any board) and play; the app shows the move and can execute it.

**Pipeline:** Screenshot (full screen) → detect board (contour or edge projection) → warp → 64 squares → template matching → FEN → Stockfish → overlay + optional screen clicks.

---

## Requirements

- **Python 3.10+**
- **Stockfish** (e.g. `apt install stockfish`, or [stockfishchess.org](https://stockfishchess.org/download/))
- **Templates:** a `templates/` directory with piece images (e.g. `wp.png`, `bk.png`, `200.png`) — see [Templates](#templates-folder-templates) below.

---

## Setup

### From source (recommended for development)

```bash
git clone https://github.com/your-org/auto_chess.git
cd auto_chess
python3 -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
pip install -e .
```

Or use the setup script (creates venv, installs deps, optionally downloads Stockfish):

```bash
# Linux/macOS
./setup.sh
# Windows
setup.bat
```

### Install from PyPI (when published)

```bash
pip install auto-chess
```

- **Stockfish:** Install separately. If not in PATH, set `STOCKFISH_PATH` in `.env` or `config.yaml`.
- **Config:** Copy `config.example.yaml` to `config.yaml` and adjust (e.g. `template_fen`).
- **Templates:** Put a `templates/` folder with piece images in your working directory (or project root when running from source). The repo includes `sample_screenshot.png` for tests and the vision notebook.

---

## Usage

Run from the project root (or any directory that has `config.yaml` and `templates/`).

### 1. Assist with control panel (default)

```bash
python main.py
# or, after pip install:
auto-chess
```

A **CustomTkinter overlay** opens with:
- **We play:** White or Black (dropdown).
- **Show move recommendation:** toggle to show or hide the recommended move.
- **Auto-play moves:** toggle to let the bot play moves on screen (pyautogui; humanized timing and jitter).
- **Start / Stop agent:** start or stop the vision + Stockfish loop (move display and/or auto-play).

Open your board (e.g. Chess.com), click **Start agent**, and optionally enable **Auto-play**. When the game ends, the overlay shows the result (e.g. "White wins by checkmate").

### 2. Terminal only (no overlay)

```bash
python main.py --no-overlay
# or: auto-chess --no-overlay
```

### 3. Test vision on a screenshot

Uses `sample_screenshot.png` (in current directory or project root) and writes debug images to the system temp directory (cross-platform).

```bash
python main.py --test-vision-template contour
python main.py --test-vision-template edges
```

### 4. Default color (overlay can override)

```bash
python main.py --we-play black
```

You can also set **We play** in the overlay after starting.

---

## Config

| Key | Default | Description |
|-----|---------|-------------|
| `stockfish_path` | `stockfish` | Engine binary (or set `STOCKFISH_PATH` in `.env`) |
| `assist_poll_seconds` | `2.0` | Poll interval (seconds) |
| `template_fen.templates_dir` | `templates` | Folder with piece/empty images |
| `template_fen.board_extraction` | `contour` | `contour` or `edges` |
| `template_fen.empty_threshold` | — | Max correlation to empty template → empty square |
| `template_fen.piece_threshold` | — | Min correlation for piece match |
| `template_fen.variance_empty_threshold` | — | Center variance below this → empty |
| `template_fen.normalize` | `true` | Zero-mean unit-variance before matching |
| `template_fen.use_edges` | `false` | Combine intensity + edge score for pieces |
| `template_fen.edge_weight` | `0.5` | Weight for edge score |
| `template_fen.edge_method` | `gradient` | `gradient` or `canny` |
| `humanization.reaction_time_mean_ms` | `800` | Delay before acting (mean ms) |
| `humanization.move_time_mean_ms` | `250` | Delay between from/to click (mean ms) |
| `humanization.click_jitter_std_fraction` | `0.15` | Click jitter as fraction of square size |

See `config.example.yaml` for full comments.

---

## Templates folder (`templates/`)

- **Pieces:** `wp.png`, `wn.png`, `wb.png`, `wr.png`, `wq.png`, `wk.png`, `bp.png`, `bn.png`, `bb.png`, `br.png`, `bq.png`, `bk.png` (Chess.com-style). Optional `*_mask.png` per piece.
- **Empty:** `200.png` and/or `200_light.png`, `200_dark.png`.

---

## Vision pipeline

1. **Board detection** — Contour (Canny + largest quad) or edges (1D gradient projection).
2. **Warp** — Perspective warp to 400×400; 64 squares (50×50).
3. **Occupancy** — Variance in center of each square: low → empty; high → piece matching only. Optional empty-template correlation.
4. **Piece matching** — Normalized (and optionally edge) correlation to 12 piece templates.

**Notebook:** `notebooks/vision_template_workflow.ipynb` runs the pipeline step-by-step (screenshot → FEN).

---

## Debug images

Assist and test-vision write debug images (last screenshot, marked board, warped board, edges) to a **temporary directory** so the project directory stays clean and works on all OSes:

- **Linux:** `$TMPDIR/auto_chess/` or `/tmp/auto_chess/`
- **macOS:** `/var/folders/.../T/auto_chess/` or `$TMPDIR/auto_chess/`
- **Windows:** `%TEMP%\auto_chess\`

---

## Tests

```bash
python -m pytest tests/
# or
python -m unittest tests.test_vision_sample
```

Requires `sample_screenshot.png` and `templates/` in project root (or current directory).

---

## License and disclaimer

MIT. For educational use. Automated play may violate Chess.com’s Terms of Service; use at your own risk.
