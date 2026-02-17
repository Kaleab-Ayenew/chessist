# Setup Guide

**Vision is required** (chesscog). It is the primary observation path; DOM is only a fallback. Setup **requires Python 3.10** (chesscog does not support 3.11+).

## One-command setup (all platforms)

From the project root, **use Python 3.10** to create the venv, then run setup:

| Platform | Command |
|----------|---------|
| **Linux / macOS** | `python3.10 -m venv .venv && source .venv/bin/activate && python scripts/setup.py` or `./setup.sh` (setup.sh tries `python3.10` first) |
| **Windows** | `py -3.10 -m venv .venv` then `.venv\Scripts\activate` then `python scripts\setup.py` or `setup.bat` |

The script will:

1. **Check Python version** — Exit with instructions if Python 3.11+ (vision requires 3.10).
2. **Virtual environment** — Create `.venv` if it doesn’t exist.
3. **Python dependencies** — Install from `requirements.txt`.
4. **Chesscog (vision)** — **Required.** Install from GitHub and download models; setup fails if this fails.
5. **Playwright** — Install Chromium for browser automation.
6. **Stockfish** — Download from GitHub if not in PATH; write `STOCKFISH_PATH` to `.env`.
7. **Config** — Copy `config.example.yaml` to `config.yaml` if missing.

## After setup

Activate the venv and run the agent:

- **Linux / macOS:** `source .venv/bin/activate` then `python main.py`
- **Windows:** `.venv\Scripts\activate` then `python main.py`

## Platform notes

- **Linux:** Prefers `ubuntu-x86-64-avx2` Stockfish build; falls back to older CPU builds if needed. Uses `tar` extraction.
- **macOS:** Apple Silicon (M1/M2) gets `macos-m1-apple-silicon`; Intel gets `macos-x86-64-avx2`. Uses `tar` extraction.
- **Windows:** Uses the `windows-x86-64-avx2` (or similar) asset; supports `.zip` or `.tar` extraction. Binary is `stockfish.exe`; path is written to `.env` as `STOCKFISH_PATH`.

If Stockfish is already installed (e.g. `apt install stockfish` or from the official site), the script skips the download and does not overwrite `STOCKFISH_PATH` in `.env`.

## Troubleshooting

- **"Vision requires Python 3.10 or earlier"** — Create a new venv with Python 3.10: `python3.10 -m venv .venv`, activate it, then run `python scripts/setup.py` again.
- **Chesscog install fails** (e.g. Pillow build errors) — Ensure you are using **Python 3.10** (not 3.11 or 3.12). Chesscog’s dependencies do not support newer Python.
- **Stockfish extract failed / unexpected end of data** — Delete `.stockfish/` and run setup again to re-download.
- **Stockfish not found** — Set `STOCKFISH_PATH` in `.env` to the full path of the `stockfish` (or `stockfish.exe`) binary.
- **Playwright browser missing** — Run `python -m playwright install chromium` with the venv activated.
