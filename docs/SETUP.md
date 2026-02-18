# Setup

See the main [README](../README.md) for full setup and usage.

**Quick start:**

1. Clone the repo, create a venv, install: `pip install -e .` (or use `./setup.sh` / `setup.bat`).
2. Install Stockfish (e.g. `apt install stockfish`). Set `STOCKFISH_PATH` in `.env` if not in PATH.
3. Copy `config.example.yaml` to `config.yaml`.
4. Ensure `templates/` exists with piece images (see README).
5. Run: `python main.py` or `auto-chess`.

**Troubleshooting:**

- **Stockfish not found** — Set `STOCKFISH_PATH` in `.env` to the full path of the binary.
- **No board detected** — Ensure the board is visible and well contrasted. Tune `template_fen` in `config.yaml` (e.g. `board_extraction: edges`, `variance_empty_threshold`).
- **Templates not found** — Add a `templates/` directory with piece PNGs (see README).
