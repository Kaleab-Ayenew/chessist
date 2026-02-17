# Autonomous Chess.com Agent

An autonomous agent that plays chess on Chess.com using an OODA loop: **Observe** (vision primary, DOM fallback), **Orient** (FEN), **Decide** (Stockfish), **Act** (Playwright click-click). Runs 100% locally.

## Requirements

- **Python 3.10** (3.11+ is not supported: chesscog/vision requires 3.10 or earlier)
- Stockfish is installed automatically. **Vision** uses either **ONNX** (if `onnx_models/` is present) or **chesscog + PyTorch** (installed by setup when ONNX is not present).

## Setup (one command)

**Linux / macOS** (use Python 3.10)

```bash
cd /path/to/auto_chess
python3.10 -m venv .venv
source .venv/bin/activate
python scripts/setup.py
# or: chmod +x setup.sh && ./setup.sh  (ensure python3.10 is used for the venv)
```

**Windows** (use Python 3.10)

```cmd
cd path\to\auto_chess
py -3.10 -m venv .venv
.venv\Scripts\activate
python scripts\setup.py
REM or: setup.bat
```

The setup script will:

- **Enforce Python 3.10** (exits with instructions if you use 3.11+)
- Create a virtual environment (`.venv`) if missing
- Install dependencies from `requirements.txt`
- Install **vision**: if `onnx_models/` (from export) is present, only **onnxruntime** is installed; otherwise **chesscog** + PyTorch and model download (required)
- Install **rebrowser-playwright** (Playwright with anti-detection patches) and Chromium
- Download **Stockfish** from the official GitHub release (Linux/Windows/macOS) if not in `PATH`, and write `STOCKFISH_PATH` to `.env`
- Copy `config.example.yaml` to `config.yaml` if missing

Then activate the venv and run:

```bash
# Linux/macOS
source .venv/bin/activate
python main.py

# Windows
.venv\Scripts\activate
python main.py
```

### Manual setup (optional)

Use **Python 3.10**. Create a venv with `python3.10 -m venv .venv`, activate it, then: `pip install -r requirements.txt`, `pip install "chesscog @ git+https://github.com/georg-wolflein/chesscog.git"`, run the chesscog model download scripts, `playwright install chromium`, install Stockfish (e.g. `apt install stockfish` or from [stockfishchess.org](https://stockfishchess.org/download/)), set `STOCKFISH_PATH` in `.env` if needed. Copy `config.example.yaml` to `config.yaml` and edit if desired.

## Run

1. Start the agent (browser opens):

   ```bash
   python main.py
   ```

2. In the browser, log in to Chess.com and start a game (e.g. Play → Play Computer or Live Chess).

3. When the game board is visible, the agent will detect your turn and play moves (click-click with humanized delays).

**Options**

- `--url https://www.chess.com/play/computer` — open a specific URL.
- `--headless` — run browser headless (harder to debug).
- `--we-play white|black|auto` — force color or auto-detect.
- `--chrome` — use installed Google Chrome instead of bundled Chromium (better fingerprint).
- `--user-data-dir PATH` — use a persistent browser profile (log in once, reuse cookies).
- `--no-wait` / `--wait-for-board[=SECS]` — start immediately or poll until a board appears.

The project uses **rebrowser-playwright** for better anti-detection (CDP Runtime.Enable fix). You can tune it with env vars, e.g. `REBROWSER_PATCHES_RUNTIME_FIX_MODE=addBinding` (default), `alwaysIsolated`, or `enableDisable`. See [rebrowser-patches](https://github.com/rebrowser/rebrowser-patches).

### Assist mode (no browser, no Cloudflare)

If the browser path is blocked by Cloudflare (or you prefer not to automate the browser), use **assist mode**:

1. Open Chess.com in your **own** browser and start a game.
2. Run:
   ```bash
   python main.py --assist
   ```
3. The app captures your screen (full screen or a region set in `config.yaml` as `assist_region`), runs vision + Stockfish, and shows the **recommended move** in the terminal and in a small always-on-top overlay window. You make the move yourself.

Options: `--we-play white|black` (default white), `--no-overlay` (terminal only). In `config.yaml` you can set `assist_poll_seconds` (default 2) and optionally `assist_region: {left, top, width, height}` to capture only the board area; if omitted, the full screen is captured and vision finds the board. To set the board region with a GUI, run `python main.py --assist-set-region` once: drag a rectangle around the board and click Save.

### Testing computer vision

To verify vision without running the assist loop: copy a board screenshot to `sample_screenshot.png` in the project root (e.g. from `last_assist_screenshot.png` after one assist poll), then run:

```bash
python main.py --test-vision
```

This prints the detected FEN or "No board detected." You can also run the unit test (requires `sample_screenshot.png`):

```bash
python -m unittest tests.test_vision_sample
```

### Template-based FEN pipeline (theme-agnostic, no neural nets)

An alternative pipeline uses **contour detection** or **1D edge projection** to find the board, then **template matching** with theme-agnostic occupancy and piece recognition. It works across board themes (green, blue, wood, etc.) and avoids the “only white pieces detected” problem.

**Quick test**

```bash
python main.py --test-vision-template contour
python main.py --test-vision-template edges
```

Requires `sample_screenshot.png` in the project root and a `templates/` folder (see below). Optional settings go under `template_fen` in `config.yaml` (see `config.example.yaml`).

**Pipeline overview**

1. **Board detection** — Find the 4 corners of the board: `contour` (Canny + largest quad) or `edges` (1D gradient projection).
2. **Warp** — Perspective warp to 400×400; split into 64 squares (50×50 each).
3. **Occupancy** — For each square, decide *empty* vs *occupied*:
   - **Variance (recommended):** Center 60% of the square: variance of grayscale. **Flat squares → low variance → empty.** High variance → run piece matching (no empty-template check), so dark pieces on dark squares are not mislabeled empty.
   - **Optional fallback:** If variance is not used, max correlation to *empty* templates (e.g. `200.png`, `200_light.png`, `200_dark.png`) above `empty_threshold` → empty.
4. **Piece matching** — For occupied squares only: compare to 12 piece templates. Score = normalized (grayscale zero-mean unit-variance) and optionally **edge (shape)** correlation. Piece-only masks (auto-generated or `*_mask.png`) limit correlation to the piece, not the square background.

**Templates folder (`templates/`)**

- **Pieces:** `wp.png`, `wn.png`, `wb.png`, `wr.png`, `wq.png`, `wk.png`, `bp.png`, `bn.png`, `bb.png`, `br.png`, `bq.png`, `bk.png` (Chess.com-style names). Add `piece_mask.png` (e.g. `wp_mask.png`) per piece if you have them; otherwise a mask is auto-generated from the template border.
- **Empty:** `200.png` and/or `200_light.png`, `200_dark.png` (only used when variance occupancy is off). One or two empty templates improve empty detection on light/dark squares.

**Config (`template_fen` in `config.yaml`)**

| Key | Default | Description |
|-----|---------|--------------|
| `board_extraction` | `"contour"` | `"contour"` or `"edges"` |
| `template_match_threshold` | `0.5` | Fallback piece threshold if `piece_threshold` not set |
| `empty_threshold` | `0.82` | Max correlation to empty template → empty (when variance not used) |
| `piece_threshold` | `0.45` | Min correlation to assign a piece (lower = more permissive) |
| `variance_empty_threshold` | — | If set (e.g. `100`): center variance &lt; this → empty; high variance → piece matching only. **Use this to fix dark-on-dark mislabels.** |
| `normalize` | `true` | Grayscale zero-mean unit-variance before matching |
| `use_edges` | `false` | Combine normalized + edge (shape) score for piece choice; helps dark pieces |
| `edge_weight` | `0.5` | Weight for edge score (0 = normalized only, 1 = edge only) |
| `edge_method` | `"gradient"` | `"gradient"` (Sobel magnitude) or `"canny"` |

**Jupyter notebook**

To run the pipeline step-by-step and inspect variance / FEN per square:

```bash
pip install notebook
jupyter notebook notebooks/vision_template_workflow.ipynb
```

In the notebook you can change the screenshot path, method, thresholds, variance, and edge settings, then re-run from the config cell.

## Vision: ONNX (lightweight, no PyTorch)

To avoid installing PyTorch locally, export the vision models on a machine that has it (e.g. your server), then use the ONNX files locally:

1. **On the server** (e.g. `ssh ovh`): sync the project and run the export (or run the helper script from your machine):
   ```bash
   ./scripts/run_export_on_ovh.sh
   ```
   This rsyncs the project to `ovh:~/auto_chess_export`, runs `scripts/export_chesscog_to_onnx.py` there (installs torch + chesscog, downloads models, exports to ONNX), then rsyncs `onnx_models/` back.

2. **Locally**: after `onnx_models/` is in the project root, run `python scripts/setup.py` again. Setup will skip PyTorch and chesscog and use **onnxruntime** only for vision. You can then package the app with just the `onnx_models/` folder and no torch dependency.

## How it works

- **Observe:** Playwright captures a screenshot of the board; **vision (ONNX or chesscog)** is the **primary** path to FEN. If vision fails, **DOM** (move list / page state) is used as fallback.
- **Orient:** Builds FEN from the board image via ONNX or chesscog, or from the DOM move list when vision is unavailable.
- **Decide:** Stockfish returns the best move (UCI).
- **Act:** The agent clicks the source square, then the destination square, with Gaussian jitter on timing and position (humanization).

Turn detection uses the active clock on the page. Game-over is detected by text/overlays so the loop stops at the end of a game.

## Disclaimer

This is for **educational use** on your own account. Automated play may violate Chess.com’s Terms of Service. Use at your own risk.
