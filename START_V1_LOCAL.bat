@echo off
REM ========================================
REM FAMILY FEUD V1 - LOCAL TESTING
REM ========================================

echo.
echo ╔════════════════════════════════════════╗
echo ║   FAMILY FEUD V1 - LOCAL TEST MODE    ║
echo ╚════════════════════════════════════════╝
echo.

REM Change to this directory (in case you double-clicked from Explorer)
cd /d "%~dp0"

echo [1/3] Checking dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies!
    echo Please run manually: python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo Dependencies OK!
echo.

echo [2/3] Starting Family Feud V1...
echo Server will be at: http://localhost:5000
echo Press Ctrl+C to stop
echo.

REM Start the Flask application
python app.py

REM If the server crashes, pause to see the error
pause
