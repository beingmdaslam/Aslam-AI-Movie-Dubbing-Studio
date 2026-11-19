@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run setup-windows.bat first.
  pause
  exit /b 1
)

echo Installing optional Demucs speech/music separation...
echo This downloads large packages and model files. Processing remains local and uses no paid API.
".venv\Scripts\python.exe" -m pip install -r requirements-audio.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check the error and package compatibility.
  pause
  exit /b 1
)

echo.
echo Optional Demucs installation complete.
echo The first dubbing run downloads the htdemucs model if needed.
pause
