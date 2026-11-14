@echo off
cd /d "%~dp0"
if not exist ".venv314\Scripts\python.exe" (
  echo Chua co .venv314. Doc BAT_DAU_SPARK.md.
  pause
  exit /b 1
)
".venv314\Scripts\python.exe" "pc\app.py" %*
pause
