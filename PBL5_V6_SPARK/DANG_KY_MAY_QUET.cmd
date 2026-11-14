@echo off
cd /d "%~dp0"
if not exist ".venv314\Scripts\python.exe" (
  echo Chua co .venv314. Chay: py -3.14 -m venv .venv314
  pause
  exit /b 1
)
".venv314\Scripts\python.exe" "pc\register_scanner.py"
pause
