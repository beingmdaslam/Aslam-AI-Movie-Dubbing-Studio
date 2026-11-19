@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================
echo ASLAM AI - Configure Local Wav2Lip
echo ==========================================
echo.
echo This helper does not download Wav2Lip or its checkpoint.
echo Use a SEPARATE compatible Python environment for Wav2Lip; do not install its old requirements into the ASLAM AI worker environment.
echo The upstream open-source model is for personal/research use only, not commercial use.
echo Obtain a compatible checkout and checkpoint, and review their licenses.
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

if not exist "%WAV2LIP_DIR%\face_detection\detection\sfd\s3fd.pth" (
  echo ERROR: S3FD face-detection weights are missing.
  echo Place s3fd.pth at face_detection\detection\sfd\s3fd.pth inside the Wav2Lip folder.
  pause
  exit /b 1
)

set /p WAV2LIP_PYTHON=Optional full path to Wav2Lip environment python.exe (leave blank to use current worker Python):
if not "%WAV2LIP_PYTHON%"=="" if not exist "%WAV2LIP_PYTHON%" (
  echo ERROR: The selected Wav2Lip Python executable was not found.
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

if not "%WAV2LIP_PYTHON%"=="" (
  setx PYTHON "%WAV2LIP_PYTHON%" >nul
  if errorlevel 1 (
    echo ERROR: Could not save PYTHON.
    pause
    exit /b 1
  )
)

echo.
echo Wav2Lip paths saved for your Windows user account.
echo Close the worker terminal and open a NEW Command Prompt.
echo Then start the worker again and visit /lip-sync/status.
echo If you supplied a separate Python executable, Wav2Lip will run inside that environment.
pause
