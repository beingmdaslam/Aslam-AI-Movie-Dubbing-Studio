@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==========================================================
echo ASLAM AI - Separate Wav2Lip Environment Setup (CPU)
echo ==========================================================
echo.
echo This installs a separate Wav2Lip environment. It does NOT
echo install voice cloning, use paid APIs, or change the main worker.
echo The upstream Wav2Lip open-source model is restricted to
echo personal/research/non-commercial use. Read its license first.
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python Launcher not found. Install Python 3.8 x64 and enable the Python Launcher.
  pause
  exit /b 1
)
py -3.8 --version >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.8 was not found.
  echo This isolated setup targets Python 3.8 for the legacy Wav2Lip code.
  echo Install Python 3.8 x64, then run this file again.
  pause
  exit /b 1
)

where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git was not found. Install Git for Windows, reopen this window and retry.
  pause
  exit /b 1
)

set "WAV2LIP_DIR=%~dp0wav2lip"
set "WAV2LIP_ENV=%~dp0.wav2lip-venv"
set "WAV2LIP_PYTHON=%WAV2LIP_ENV%\Scripts\python.exe"
set "S3FD_DIR=%WAV2LIP_DIR%\face_detection\detection\sfd"
set "S3FD_FILE=%S3FD_DIR%\s3fd.pth"

if not exist "%WAV2LIP_DIR%\inference.py" (
  echo Downloading the official Wav2Lip source code from GitHub...
  git clone --depth 1 https://github.com/Rudrabha/Wav2Lip.git "%WAV2LIP_DIR%"
  if errorlevel 1 goto failed
) else (
  echo Existing Wav2Lip source found.
)

if not exist "%WAV2LIP_ENV%\Scripts\python.exe" (
  echo Creating isolated Python 3.8 environment...
  py -3.8 -m venv "%WAV2LIP_ENV%"
  if errorlevel 1 goto failed
)

echo.
echo Installing a CPU-only PyTorch build in the separate environment...
"%WAV2LIP_PYTHON%" -m pip install --upgrade "pip<25"
if errorlevel 1 goto failed
"%WAV2LIP_PYTHON%" -m pip install torch==1.13.1+cpu torchvision==0.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed

echo.
echo Installing compatible Wav2Lip inference dependencies...
"%WAV2LIP_PYTHON%" -m pip install numpy==1.23.5 scipy==1.10.1 numba==0.57.1 librosa==0.9.2 opencv-contrib-python==4.8.1.78 tqdm==4.66.4
if errorlevel 1 goto failed

echo.
echo Downloading the S3FD face detector weights...
if not exist "%S3FD_DIR%" mkdir "%S3FD_DIR%"
if not exist "%S3FD_FILE%" (
  where curl.exe >nul 2>nul
  if errorlevel 1 (
    echo ERROR: curl.exe was not found. Download the S3FD file manually.
    echo URL: https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth
    echo Save it as: %S3FD_FILE%
    pause
    exit /b 1
  )
  curl.exe -L --fail --retry 3 --output "%S3FD_FILE%" "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"
  if errorlevel 1 goto failed
)
if not exist "%S3FD_FILE%" goto failed

echo.
echo Download the official Wav2Lip checkpoint from the official weights folder:
echo https://drive.google.com/drive/folders/153HLrqlBNxzZcHi17PEvP09kkAfzRshM
echo Save it as: %WAV2LIP_DIR%\checkpoints\wav2lip.pth
echo Use only a checkpoint whose license and source you have checked.
echo.
if not exist "%WAV2LIP_DIR%\checkpoints" mkdir "%WAV2LIP_DIR%\checkpoints"
set "WAV2LIP_CHECKPOINT=%WAV2LIP_DIR%\checkpoints\wav2lip.pth"
if not exist "%WAV2LIP_CHECKPOINT%" (
  set /p WAV2LIP_CHECKPOINT=Paste the full path to your downloaded Wav2Lip checkpoint:
)
if not exist "%WAV2LIP_CHECKPOINT%" (
  echo ERROR: Checkpoint file not found. Download it and rerun this setup.
  pause
  exit /b 1
)

echo.
echo Checking separate Wav2Lip Python imports...
"%WAV2LIP_PYTHON%" -c "import torch, torchvision, cv2, librosa, numpy; print('torch',torch.__version__,'CUDA',torch.cuda.is_available()); print('opencv',cv2.__version__,'librosa',librosa.__version__,'numpy',numpy.__version__)"
if errorlevel 1 goto failed

echo.
echo Saving isolated Wav2Lip settings...
setx WAV2LIP_DIR "%WAV2LIP_DIR%" >nul
if errorlevel 1 goto failed
setx WAV2LIP_CHECKPOINT "%WAV2LIP_CHECKPOINT%" >nul
if errorlevel 1 goto failed
setx WAV2LIP_PYTHON "%WAV2LIP_PYTHON%" >nul
if errorlevel 1 goto failed

echo.
echo SUCCESS: Wav2Lip source, CPU environment and S3FD are configured.
echo Close this window and the ASLAM AI worker terminal.
echo Open a NEW Command Prompt, start ASLAM AI again, then open:
echo http://127.0.0.1:8765/lip-sync/status
echo.
echo NOTE: This setup prepares dependencies; it does not prove real lip-sync inference.
echo CPU processing can be very slow. Use a short test clip first.
pause
exit /b 0

:failed
echo.
echo SETUP FAILED. Read the error above. Your main ASLAM AI environment was not modified.
echo Check internet access, disk space, Python 3.8 x64 and Git, then retry.
pause
exit /b 1
