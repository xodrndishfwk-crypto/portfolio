@echo off
chcp 65001 >nul
title SEUL-JJEOCK RUNNER (WITH NGROK)
cd /d "%~dp0"

echo ===================================================
echo   [슬쩍] 백엔드, 프론트엔드 및 ngrok 실행 준비 중...
echo ===================================================

:: 1. 기존 프로세스 및 포트 정리
echo [*] 기존 포트(8000, 5173) 및 ngrok 프로세스 정리...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
powershell -NoProfile -Command "Get-Process -Name 'ngrok' -ErrorAction SilentlyContinue | Stop-Process -Force"

:: 2. Backend venv 확인
cd /d "%~dp0backend"
if not exist ".venv" (
    echo [*] 백엔드 가상환경 생성 중...
    python -m venv .venv
)
call .venv\Scripts\activate.bat
echo [*] 백엔드 의존성 패키지 확인...
python -m pip install -q -r requirements.txt

:: 3. Frontend 패키지 확인
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo [*] 프론트엔드 패키지 설치 중...
    call npm.cmd install
)

:: 4. 백엔드, 프론트엔드, ngrok 실행
echo [*] 백엔드, 프론트엔드, ngrok을 실행합니다...
start "BACKEND_SERVER" cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && python -m uvicorn main:app --port 8000"
start "FRONTEND_SERVER" cmd /k "cd /d %~dp0frontend && call npm.cmd run dev"
start "NGROK_SERVER" cmd /k "ngrok http 5173 --log=stdout"

:: 5. ngrok 공용 URL 가져오기 및 클립보드 복사 (최대 10초 대기)
echo [*] ngrok 외부 주소 연결 대기 중...
set "NGROK_URL="
for /f "usebackq delims=" %%U in (`powershell -NoProfile -Command "$url=''; for($i=0;$i -lt 20;$i++){ try { $r = Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -ErrorAction Stop; if($r.tunnels.Length -gt 0){ $url = $r.tunnels[0].public_url; break; } } catch {}; Start-Sleep -Milliseconds 500 }; $url"`) do set "NGROK_URL=%%U"

if defined NGROK_URL (
    powershell -NoProfile -Command "Set-Clipboard -Value '%NGROK_URL%'"
)

echo.
echo ===================================================
echo   [슬쩍] 모든 서버와 ngrok이 성공적으로 실행되었습니다!
echo ===================================================
echo   - 내 컴퓨터 접속:   http://localhost:5173
if defined NGROK_URL (
    echo   - 모바일/외부 접속: %NGROK_URL%
    echo.
    echo   * 위 외부 접속 주소가 클립보드에 자동 복사되었습니다!
    echo   * 스마트폰 카톡 등에 바로 붙여넣기[Ctrl+V] 하세요.
) else (
    echo   - 외부 접속 주소 확인 중... [잠시 후 NGROK_SERVER 창 확인]
)
echo ===================================================
echo   * 이 창을 닫아도 서버는 계속 동작합니다.
echo ===================================================
echo.
pause
