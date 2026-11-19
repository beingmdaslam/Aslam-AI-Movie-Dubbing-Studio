@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ==========================================
echo ASLAM AI - Local Worker Setup
echo ==========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python Launcher not found. Install Python 3.11 from python.org and enable "Add Python to PATH".
  pause
  exit /b 1
)

py -3.11 --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 is required. Install Python 3.11, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3.11 -m venv .venv
  if errorlevel 1 goto failed
)

echo Updating pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed

echo Installing free local transcription, translation and speaker detection packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo Checking FFmpeg...
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg is required for video processing but was not found.
  where winget >nul 2>nul
  if errorlevel 1 (
    echo Windows Package Manager (winget) is unavailable.
    echo Install FFmpeg manually and add its bin folder to PATH.
  ) else (
    set /p INSTALL_FFMPEG=Try installing free FFmpeg with winget now? (Y/N):
    if /I "!INSTALL_FFMPEG!"=="Y" (
      winget install --id Gyan.FFmpeg --exact --silent --accept-package-agreements --accept-source-agreements
      if errorlevel 1 (
        echo FFmpeg installation did not complete. Install it manually and retry.
      ) else (
        echo FFmpeg installation requested. Close this window and reopen Command Prompt
        echo so the updated PATH is loaded, then run setup-windows.bat again.
      )
    )
  )
) else (
  echo FFmpeg found.
)

echo.
echo Base setup is complete.
echo XTTS voice generation is optional. Read README.md and review the Coqui Public Model License before installing it.
echo To start the worker, double-click start-windows.bat.
pause
exit /b 0

:failed
echo.
echo Setup failed. Read the error above, check internet and available disk space, then retry.
pause
exit /b 1
