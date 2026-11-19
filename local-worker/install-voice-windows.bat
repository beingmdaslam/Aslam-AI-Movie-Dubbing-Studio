@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run setup-windows.bat first.
  pause
  exit /b 1
)

echo WARNING: XTTS-v2 is governed by the Coqui Public Model License.
echo Review its terms before installation or commercial use.
echo The model download is free but can be several gigabytes and CPU generation is slow.
echo.
set /p CONFIRM=Continue installing optional XTTS voice generation? (Y/N):
if /I not "%CONFIRM%"=="Y" exit /b 0

".venv\Scripts\python.exe" -m pip install -r requirements-voice.txt
if errorlevel 1 (
  echo.
  echo Voice dependency installation failed. Check the error above.
  pause
  exit /b 1
)

echo.
echo Optional XTTS dependency installation finished.
echo The first voice-generation request downloads the model weights.
pause
