#!/bin/bash
set -e

echo "=== Auto Chess Linux Build ==="
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: No virtual environment detected."
    echo "It's recommended to run this in a venv to avoid dependency conflicts."
    echo ""
fi

# Install PyInstaller if not present
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf build/ dist/

# Run PyInstaller
echo "Building executable..."
pyinstaller --clean auto_chess.spec

echo ""
echo "=== Build Complete ==="
echo "Executable: dist/auto_chess"
echo ""
echo "To run: ./dist/auto_chess"
echo ""
echo "Requirements for users:"
echo "  - Linux with X11 (Wayland may work with XWayland)"
echo "  - Stockfish installed (apt install stockfish) or set STOCKFISH_PATH"
