@echo off
setlocal
cd /d "%~dp0"

echo Installing required Python packages...
echo.

python -m pip install --user opencv-python numpy mss pynput
if errorlevel 1 (
    echo.
    echo Installation failed.
    echo Please make sure Python is installed and available in PATH.
    pause
    exit /b 1
)

echo.
echo Installation completed successfully.
pause
