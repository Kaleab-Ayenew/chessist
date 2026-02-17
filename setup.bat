@echo off
REM Run full setup from project root. Use: setup.bat  or  .\setup.bat
REM Vision requires Python 3.10. Create venv with: py -3.10 -m venv .venv
cd /d "%~dp0"
if not exist .venv (
  if defined py py -3.10 -m venv .venv 2>nul
  if not exist .venv python -m venv .venv
)
call .venv\Scripts\activate.bat
python scripts\setup.py
echo.
echo Activate the venv and run the agent:
echo   .venv\Scripts\activate.bat
echo   python main.py
