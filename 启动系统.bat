@echo off
setlocal
cd /d "%~dp0"
title City Short-term Rental Decision Support System

if not exist ".venv\Scripts\streamlit.exe" (
    echo.
    echo [ERROR] Python environment not found.
    echo Please run the environment setup described in README.md.
    echo.
    pause
    exit /b 1
)

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8501' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { Start-Process 'http://localhost:8501'; exit 0 } } catch {}; exit 1"
if %errorlevel% equ 0 (
    echo The system is already running. Opening the browser...
    timeout /t 2 >nul
    exit /b 0
)

echo Starting the system...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://localhost:8501'"
".venv\Scripts\streamlit.exe" run app.py --server.port 8501

echo.
echo The system has stopped. Press any key to close this window.
pause >nul
