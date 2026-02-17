# Project Log

Living document: updated whenever the codebase or project setup changes. (Cursor rule: [.cursor/rules/update-project-log.mdc](../.cursor/rules/update-project-log.mdc) — add a dated entry when you change the project.)

---

## 2026-02-17 (Occupancy by intensity only; edge for piece choice)

- **Changed** `src/agent/vision_template.py` — occupancy now uses **normalized intensity only** when comparing to empty templates; edge/combined score is used **only for piece template choice**. Fixes “all squares labeled empty” when use_edges was True (empty template matched board edges on every square).

---

## 2026-02-17 (Edge/shape matching F + theme-agnostic notebook)

- **Added** `notebooks/theme_agnostic_piece_detection.ipynb` — Jupyter notebook implementing **edge/shape matching (F)** with combined steps: per-square normalization, occupancy-first, two empty templates. Compares three modes (normalized only, edge only, combined), shows edge-map preview and 8×8 labeled boards.
- **Changed** `src/agent/vision_template.py` — **F (edge/shape matching)**: `patch_to_edge_map()` (gradient or Canny), `_match_one_edge()`, optional combined score in `_match_square_to_templates(use_edges, edge_weight, edge_method)`. `image_to_fen_template()` now accepts `use_edges`, `edge_weight`, `edge_method` for combined accuracy.

---

## 2026-02-17 (Edge matching wired in config + notebook)

- **Changed** `main.py` — `--test-vision-template` now reads and passes `use_edges`, `edge_weight`, `edge_method` from `template_fen` config.
- **Changed** `config.example.yaml` — documented `use_edges`, `edge_weight`, `edge_method` for edge-based piece matching.
- **Changed** `notebooks/vision_template_workflow.ipynb` — config cell: `USE_EDGES=True`, `EDGE_WEIGHT=0.5`, `EDGE_METHOD="gradient"`; step-by-step and one-shot calls pass them. Edge matching was already implemented in `vision_template.py` (`patch_to_edge_map`, `_match_one_edge`, combined score in `score_fn`).

---

## 2026-02-17 (Variance-based occupancy)

- **Changed** `src/agent/vision_template.py` — added **variance-based occupancy**: `_variance_in_center(square, center_fraction=0.6)` returns variance of grayscale in central 60% of the square. When `variance_empty_threshold` is set: if variance < threshold → empty (flat); else skip empty-template check and run piece matching only (fixes dark piece on dark square being mislabeled empty). New parameter `variance_empty_threshold` in `_match_square_to_templates` and `image_to_fen_template`; config key `template_fen.variance_empty_threshold` and `main.py` wiring.
- **Changed** `config.example.yaml` — documented `variance_empty_threshold` (e.g. 100).

---

## 2026-02-17 (Vision template workflow notebook)

- **Added** `notebooks/vision_template_workflow.ipynb` — step-by-step Jupyter notebook: load screenshot, detect board corners, warp to 400×400, extract 64 squares, load templates, run occupancy-first + piece matching, display FEN and 8×8 labeled grid. Configurable image path, method (contour/edges), and thresholds.
- **Changed** README — linked the template workflow notebook in the "Template-based FEN pipeline" section.

---

## 2026-02-17 (Theme-agnostic piece detection)

- **Changed** `src/agent/vision_template.py` — theme-agnostic pipeline per plan: **occupancy first** (if max correlation to any empty template ≥ empty_threshold, label square empty; else match only piece templates), **two empty templates** (FEN stems `200_light`, `200_dark` supported), **normalize before matching** (grayscale zero-mean unit-variance), **piece-only masks** (auto-generated from border background when no `*_mask.png` for piece templates). New API: `empty_threshold` (default 0.82), `piece_threshold` (default from match_threshold), `normalize` (default True); `_match_square_to_templates` split into empty vs piece templates and `_match_one` / `_prepare_square` helpers.
- **Changed** `main.py` — `--test-vision-template` reads `template_fen` config (empty_threshold, piece_threshold, normalize, board_extraction) and passes to `image_to_fen_template`.
- **Changed** `config.example.yaml` — `template_fen` section documents empty_threshold, piece_threshold, normalize and optional 200_light/200_dark empty templates.

---

## 2026-02-16 (Template-based screenshot-to-FEN pipeline)

- **Added** `src/agent/vision_template.py` — custom pipeline: board extraction via **contour detection** or **1D edge projection**, perspective warp, 64-square split, masked template matching against ground-truth images, FEN output. Supports Chess.com-style template names (wp, bk, 200, etc.).
- **Added** `templates/` — Chess.com piece images downloaded from `assets-themes.chess.com/image/ejgfv/150/` (wp, wn, wb, wr, wq, wk, bp, bn, bb, br, bq, bk; 200.png is optional empty square).
- **Added** `--test-vision-template [contour|edges]` in `main.py` — runs template pipeline on `sample_screenshot.png` so you can compare extraction methods.
- **Added** `config.example.yaml` — commented `template_fen` section (templates_dir, board_extraction, template_match_threshold).
- **Added** `tests/test_vision_sample.py` — `TestVisionTemplatePipeline`: tests contour/edges corner detection and that `image_to_fen_template` returns valid FEN when sample + templates exist.
- **Changed** `vision_template.py` — added `save_marked_board_image()` and `save_marked_path` to `image_to_fen_template`; when running `--test-vision-template`, saves the detected board quad (green outline + corners) to `last_contour_marked.png` or `last_edges_marked.png` for debugging.
- **Changed** `.gitignore` — added `last_contour_marked.png`, `last_edges_marked.png`.

---

## 2026-02-16 (chesscog CLI test on 2D screenshot via ovh)

- **Tested** chesscog on ovh: copied `sample_screenshot_1.png`, built CPU Docker image, downloaded occupancy and piece models, ran `python -m chesscog.recognition.recognition ... --white`. Recognition failed with empty occupancy (no squares classified as occupied); pipeline is tuned for photos/3D boards, not 2D screenshots.

---

## 2025-02-16 (Test vision with sample screenshot)

- **Added** `tests/test_vision_sample.py` — unittest that uses `sample_screenshot.png` in project root: tests board corner detection and (when ONNX models exist) full FEN extraction; skipped if file or models missing.
- **Added** `--test-vision` in `main.py` — runs vision on `sample_screenshot.png` and prints FEN (or "No board detected") for quick manual testing.
- **Changed** `.gitignore` — added `sample_screenshot.png` (optional user-provided fixture).
- **Changed** README — "Testing computer vision" subsection: how to use `sample_screenshot.png` with `--test-vision` and `python -m unittest tests.test_vision_sample`.

---

## 2025-02-13 (GUI to set assist region)

- **Added** `--assist-set-region` — one-shot GUI: overlay assistant waits for user click, then captures primary screen; user drags a rectangle around the board, Save writes `assist_region` to `config.yaml`.
- **Added** `src/agent/assist_region_picker.py` — overlay "Position the board, then click to capture"; after click, capture and tkinter window with scaled screenshot, click-drag rect, coordinate conversion, Save/Cancel.
- **Added** `save_assist_region(left, top, width, height)` in `src/agent/config.py` — merge and write to `config.yaml`.
- **Changed** README — documented `python main.py --assist-set-region`.

---

## 2025-02-13 (vision: board detection on green/low-contrast boards)

- **Changed** `src/agent/vision_onnx.py` — `find_board_corners()` now tries multiple OpenCV flags (default, CALIB_CB_ADAPTIVE_THRESH, CALIB_CB_NORMALIZE_IMAGE, both) so boards with green or low-contrast squares (e.g. Chess.com themes) are detected.

---

## 2025-02-13 (assist: save last screenshot)

- **Changed** `src/agent/assist_loop.py` — save the last captured image to `last_assist_screenshot.png` in the project root each poll so you can inspect it when vision fails; log the path once at start.
- **Changed** `.gitignore` — added `last_assist_screenshot.png`.

---

## 2025-02-13 (assist loop logging)

- **Changed** `src/agent/assist_loop.py` — log every screenshot (size + region/full screen), vision result (FEN obtained or no board detected), and engine result (no move or recommended move).

---

## 2025-02-13 (assist: ONNX-only fallback, Ctrl+C)

- **Changed** `src/agent/orient.py` — when ONNX models are present, do not fall back to chesscog on failure; return None so assist mode does not spam "No module named 'chesscog'" when ONNX fails or board not detected.
- **Changed** `main.py` — in assist mode with overlay, register SIGINT handler so Ctrl+C closes the overlay and exits.

---

## 2025-02-13 (assist mode: screen capture, no browser)

- **Added** `--assist` mode — no Playwright; you open Chess.com in your own browser. App captures screen (mss), runs vision (FEN) + Stockfish, prints recommended move in terminal and shows it in an optional overlay window; you make the move yourself.
- **Added** `src/agent/screen_capture.py` — `capture_region()` and `capture_full_screen()` (RGB numpy).
- **Added** `src/agent/assist_loop.py` — poll loop: capture -> image_to_fen_cv -> best_move -> on_move callback; optional config `assist_region` and `assist_poll_seconds`.
- **Changed** `main.py` — assist path with optional tkinter overlay; `--no-overlay` for terminal-only.
- **Changed** `requirements.txt` — added mss. **Changed** config defaults and `config.example.yaml` — assist_poll_seconds, assist_region (commented).

---

## 2025-02-13 (rebrowser-playwright + Chrome automation bar fix)

- **Changed** `requirements.txt` — replaced playwright with rebrowser-playwright (patched Playwright that fixes CDP Runtime.Enable leak used by Cloudflare/DataDome).
- **Changed** `main.py` — added `ignore_default_args=["--enable-automation"]` to Chromium launch so Chrome no longer shows "Chrome is being controlled by automated test software".
- **Changed** README — noted use of rebrowser-playwright and optional REBROWSER_PATCHES env vars.

---

## 2025-02-13 (anti-detection / bot bypass)

- **Changed** `main.py` — applied multiple bot-evasion mechanisms: Chromium launch args (`--disable-blink-features=AutomationControlled`, etc.), realistic context (user-agent, viewport, locale, timezone, Accept-Language), and `playwright-stealth` applied to context; added `--chrome` (use installed Chrome) and `--user-data-dir PATH` (persistent profile to reuse login).
- **Changed** `requirements.txt` — added playwright-stealth>=2.0.0.

---

## 2025-02-13 (wait before starting game loop)

- **Changed** `main.py` — default: wait for Enter in terminal before starting the game loop so user can log in and open a game; added `--no-wait` (start immediately) and `--wait-for-board[=SECS]` (poll until board appears, optional timeout).
- **Added** `src/agent/loop.py` — `wait_for_board(page, timeout_seconds=None)` to poll for board every 1.5 s until found or timeout.

---

## 2025-02-13 (ONNX vision path)

- **Added** `scripts/export_chesscog_to_onnx.py` — export chesscog occupancy and piece classifiers to ONNX (run on a machine with PyTorch + chesscog, e.g. `ssh ovh`).
- **Added** `src/agent/vision_onnx.py` — vision pipeline using only onnxruntime and OpenCV (board corners via `cv2.findChessboardCorners`, warp/crop matching chesscog, run ONNX models).
- **Changed** `src/agent/orient.py` — vision order: try ONNX first when `onnx_models/metadata.json` exists, then fall back to chesscog.
- **Changed** `scripts/setup.py` — if `onnx_models/` (metadata.json + occupancy.onnx + piece.onnx) is present, skip installing PyTorch and chesscog; install only onnxruntime for vision.
- **Changed** `requirements.txt` — added onnxruntime.
- **Added** `scripts/run_export_on_ovh.sh` — sync project to ovh, run export, sync `onnx_models/` back for local ONNX-only setup.

---

## 2025-02-13 (chesscog install fix)

- **Changed** `scripts/setup.py`: Install PyTorch and torchvision first (unpinned, so pip picks versions with wheels). Then install chesscog with `--no-deps` to avoid its unsatisfiable `torchvision<0.11` constraint. Then install chesscog runtime deps (recap, googledrivedownloader, osfclient, matplotlib, pandas, scikit-learn, tqdm, tensorboard) manually.

---

## 2025-02-13 (vision primary, DOM fallback)

- **Changed** Observation order: **vision (chesscog) is primary**, DOM is fallback. `obtain_fen` in `loop.py` now tries screenshot → chesscog first, then DOM move list / FEN only if vision fails.
- **Changed** Config: replaced `prefer_dom` with `prefer_vision` (default `true` = vision first). `config.example.yaml` and `config.py` updated.
- **Changed** `orient.py`: vision is the primary path; removed “optional” wording; `image_to_fen_cv` no longer catches `ImportError` (vision is required at setup).
- **Changed** Setup: **Python 3.10 required** for vision (chesscog supports only &lt;3.11). Setup exits with clear instructions if run with 3.11+. Chesscog install and model download are **required** (setup fails if they fail); post-setup check verifies `import chesscog`.
- **Changed** README, SETUP.md: vision primary, Python 3.10 requirement, launchers prefer python3.10.

---

## 2025-02-13 (setup fixes)

- **Changed** `scripts/setup.py` — Skip chesscog model download when chesscog is not installed (avoids ModuleNotFoundError after failed chesscog install). Stockfish: more robust download (size check, retry on incomplete), use `tarfile.extractall(..., filter='data')` on Python 3.12+ to fix deprecation and extraction errors, remove partial archive on extract failure so re-run re-downloads.
- **Changed** `docs/SETUP.md` — Troubleshooting for chesscog on Python 3.13+ and Stockfish extract failures.

---

## 2025-02-13 (setup script)

- **Added** `scripts/setup.py` — full cross-platform setup: venv, pip deps, chesscog + model download, Playwright Chromium, Stockfish download (GitHub release for Linux/Windows/macOS), `.env` and `config.yaml`.
- **Added** `setup.sh` and `setup.bat` — one-command launchers for Linux/macOS and Windows.
- **Changed** `README.md` — setup section now documents one-command setup and manual steps.

---

## 2025-02-13 (later)

- **Added** `docs/` and `docs/PROJECT_LOG.md` — living project log.
- **Added** `.cursor/rules/update-project-log.mdc` — rule to update this log whenever the codebase changes.
- **Changed** `docs/PROJECT_LOG.md` — linked to the rule in the header.

---

## 2025-02-13

### Project bootstrap and agent implementation

- **Added** project structure and autonomous Chess.com agent (OODA loop).
- **Added** `main.py` — entry point; launches Playwright browser, runs game loop.
- **Added** `config.example.yaml` — engine limits, humanization, `prefer_dom`, chess.com base URL.
- **Added** `requirements.txt` — playwright, python-chess, numpy, Pillow, opencv-python-headless, python-dotenv, pyyaml; chesscog optional (commented).
- **Added** `src/agent/config.py` — load config from `config.yaml` / `.env` (e.g. `STOCKFISH_PATH`).
- **Added** `src/agent/observer.py` — board bounding box, DOM move list / FEN, board screenshot, square coordinates.
- **Added** `src/agent/orient.py` — DOM moves → FEN; optional chesscog image → FEN (lazy import).
- **Added** `src/agent/decider.py` — Stockfish via python-chess; `best_move(fen, white_to_move=...)`.
- **Added** `src/agent/humanize.py` — Gaussian reaction/move delays and click jitter from config.
- **Added** `src/agent/actuator.py` — click-click move execution with jitter.
- **Added** `src/agent/turn_detection.py` — our turn (clock), game over, we-play-white detection.
- **Added** `src/agent/loop.py` — OODA loop: observe → FEN (DOM then vision) → decide → act; runs until game over.
- **Added** `scripts/download_chesscog_models.py` — download chesscog models after installing chesscog.
- **Added** `README.md` — setup, run, optional chesscog instructions.
- **Added** `docs/` and this `docs/PROJECT_LOG.md` — project log to be updated with every change.

---

*When you change the project, append a dated entry above describing what was added, changed, or removed.*
