@echo off
title SEUL-JJEOCK FRONTEND
cd /d "%~dp0frontend"

:: 1. Clear Frontend Ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5174 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: 2. Check node_modules
if not exist "node_modules" (
    echo [*] Installing frontend packages...
    call npm.cmd install
)

:: 3. Run Dev Server and Open Browser
echo [*] Starting Frontend Server...
start http://localhost:5173
call npm.cmd run dev -- --port 5173

if %errorlevel% neq 0 (
    echo.
    echo [*] Server exited with error.
)
pause