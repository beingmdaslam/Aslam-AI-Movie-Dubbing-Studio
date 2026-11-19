@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Local environment is missing. Run setup-windows.bat first.
  pause
  exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo WARNING: FFmpeg is not on PATH. Video processing will fail until FFmpeg is installed.
)

echo Starting ASLAM AI Local Worker...
echo Keep this window open while processing.
echo API: http://127.0.0.1:8765
echo Health: http://127.0.0.1:8765/health
echo System check: http://127.0.0.1:8765/system/check
echo API docs: http://127.0.0.1:8765/docs
echo.
".venv\Scripts\python.exe" -m uvicorn worker:app --host 127.0.0.1 --port 8765
pause
