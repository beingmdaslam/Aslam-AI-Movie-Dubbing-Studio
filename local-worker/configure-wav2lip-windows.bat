@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo ASLAM AI - Configure Local Wav2Lip
echo ==========================================
echo.
echo This helper does not download Wav2Lip or its checkpoint.
echo First obtain a compatible local Wav2Lip checkout and checkpoint,
echo and review their licenses and usage restrictions.
echo.

set /p WAV2LIP_DIR=Full path to Wav2Lip folder (contains inference.py):
if not exist "%WAV2LIP_DIR%\inference.py" (
  echo ERROR: inference.py was not found in that folder.
  pause
  exit /b 1
)

set /p WAV2LIP_CHECKPOINT=Full path to the Wav2Lip checkpoint file:
if not exist "%WAV2LIP_CHECKPOINT%" (
  echo ERROR: The checkpoint file was not found.
  pause
  exit /b 1
)

setx WAV2LIP_DIR "%WAV2LIP_DIR%" >nul
if errorlevel 1 (
  echo ERROR: Could not save WAV2LIP_DIR.
  pause
  exit /b 1
)
setx WAV2LIP_CHECKPOINT "%WAV2LIP_CHECKPOINT%" >nul
if errorlevel 1 (
  echo ERROR: Could not save WAV2LIP_CHECKPOINT.
  pause
  exit /b 1
)

echo.
echo Wav2Lip paths saved for your Windows user account.
echo Close the worker terminal and open a NEW Command Prompt.
echo Then start the worker again and visit /lip-sync/status.
pause
