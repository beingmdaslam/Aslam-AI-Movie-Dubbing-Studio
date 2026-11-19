@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Local environment is missing. Run setup-windows.bat first.
  pause
  exit /b 1
)

echo ==========================================
echo ASLAM AI - Local Pipeline Self-Test
echo ==========================================
echo.
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ERROR: FFmpeg is missing from PATH. Install FFmpeg and reopen this window.
  pause
  exit /b 1
)

echo Checking Python and studio files...
".venv\Scripts\python.exe" check-static.py
if errorlevel 1 goto failed

echo.
echo Running local API and synthetic video/audio pipeline test...
".venv\Scripts\python.exe" check-runtime.py
if errorlevel 1 goto failed

echo.
echo SUCCESS: Local API and FFmpeg media pipeline checks passed.
echo NOTE: This self-test uses a synthetic test voice. It does not download or test Whisper, SpeechBrain or XTTS AI models.
pause
exit /b 0

:failed
echo.
echo SELF-TEST FAILED. Read the error above and check README.md.
pause
exit /b 1
