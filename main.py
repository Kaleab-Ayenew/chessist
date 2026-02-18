#!/usr/bin/env python3
"""
Chess assist: screen capture -> template vision (board + FEN) -> Stockfish -> overlay + terminal.
Run from project root: python main.py [--no-overlay] [--test-vision-template contour|edges]
"""
import sys
from pathlib import Path

if __name__ == "__main__":
    # Ensure project root is on path when running from source
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from src.agent.__main__ import _main
    _main()
