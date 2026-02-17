#!/usr/bin/env python3
"""Download chesscog occupancy and piece classifier models. Run after installing chesscog."""
import subprocess
import sys

def main():
    try:
        from chesscog.occupancy_classifier.download_model import ensure_model as ensure_occupancy
        from chesscog.piece_classifier.download_model import ensure_model as ensure_piece
    except ImportError:
        print("Install chesscog first: pip install 'chesscog @ git+https://github.com/georg-wolflein/chesscog.git'", file=sys.stderr)
        sys.exit(1)
    ensure_occupancy(show_size=True)
    ensure_piece(show_size=True)
    print("Chesscog models ready.")

if __name__ == "__main__":
    main()
