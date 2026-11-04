@echo off
title SEUL-JJEOCK RUNNER
cd /d "%~dp0"

echo ===================================================
echo   Starting SEUL-JJEOCK Full-Stack Service...
echo ===================================================

:: 1. Backend port 8000 cleanup
powershell -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

:: 2. Frontend port 5173 cleanup
powershell -Command "Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

:: 3. Setup Python venv and install packages
cd /d "%~dp0backend"
if not exist ".venv" (
    echo [*] Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo [*] Checking backend packages...
python -m pip install -q fastapi uvicorn pydantic python-dotenv google-generativeai sqlalchemy "python-jose[cryptography]" "pydantic[email]"

:: 4. Setup Frontend packages
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [*] Installing frontend packages...
    call npm install
)

:: 5. Launch Backend and Frontend in separate windows
echo [*] Launching Servers...

start "BACKEND_SERVER" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && python -m uvicorn main:app --port 8000"

start "FRONTEND_SERVER" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ===================================================
echo   Running! Access: http://localhost:5173
echo ===================================================
timeout /t 5 >nul