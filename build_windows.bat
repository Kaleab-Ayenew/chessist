@echo off
setlocal

echo === Auto Chess Windows Build ===
echo.

:: Check if we're in a virtual environment
if "%VIRTUAL_ENV%"=="" (
    echo Warning: No virtual environment detected.
    echo It's recommended to run this in a venv to avoid dependency conflicts.
    echo.
)

:: Install dependencies if not present
echo Checking dependencies...
pip install -r requirements.txt >nul 2>&1

:: Install PyInstaller if not present
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

:: Run PyInstaller
echo Building executable...
pyinstaller --clean auto_chess.spec

if errorlevel 1 (
    echo.
    echo === Build FAILED ===
    echo Check the output above for errors.
    echo Common fix: make sure all dependencies are installed: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo === Build Complete ===
echo Executable: dist\auto_chess.exe
echo.
echo To run: dist\auto_chess.exe
echo.
echo Requirements for users:
echo   - Stockfish installed and in PATH, or set STOCKFISH_PATH in config.yaml
echo     Download from https://stockfishchess.org/download/
echo.
pause
