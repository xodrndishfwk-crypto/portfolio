#!/bin/bash

# Finder에서 더블 클릭해 백엔드와 프런트엔드를 함께 실행합니다.
set -u

# Finder에서 실행할 때도 Homebrew 및 공식 설치 프로그램의 명령을 찾습니다.
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_PID=""
FRONTEND_PID=""

pause_before_exit() {
  printf '\nEnter 키를 누르면 창을 닫습니다.'
  read -r _
}

fail() {
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  printf '\n[오류] %s\n' "$1"
  pause_before_exit
  exit 1
}

cleanup() {
  trap - EXIT INT TERM
  printf '\n[*] 서버를 종료합니다...\n'
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 130' INT TERM

command -v node >/dev/null 2>&1 || fail "Node.js가 필요합니다. https://nodejs.org/ 에서 LTS 버전을 설치해 주세요."
command -v npm >/dev/null 2>&1 || fail "npm을 찾을 수 없습니다. Node.js LTS 버전을 다시 설치해 주세요."

if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON="$BACKEND_DIR/.venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
  PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || fail "Python 3.10 이상이 필요합니다."
  PYTHON="$(command -v python3)"
else
  fail "Python 3.10 이상이 필요합니다."
fi

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
NODE_MINOR="$(node -p 'process.versions.node.split(".")[1]')"
if ! { [ "$NODE_MAJOR" -eq 20 ] && [ "$NODE_MINOR" -ge 19 ]; } && \
   ! { [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -ge 12 ]; } && \
   ! [ "$NODE_MAJOR" -gt 22 ]; then
  fail "Node.js 20.19 이상 또는 22.12 이상이 필요합니다."
fi

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  fail "8000 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료한 뒤 다시 실행해 주세요."
fi
if lsof -nP -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  fail "5173 포트를 다른 프로그램이 사용 중입니다. 해당 프로그램을 종료한 뒤 다시 실행해 주세요."
fi

printf '[1/4] 백엔드 환경을 준비합니다...\n'
if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
  "$PYTHON" -m venv "$BACKEND_DIR/.venv" || fail "Python 가상환경을 만들지 못했습니다."
fi
"$BACKEND_DIR/.venv/bin/python" -m pip install -q -r "$BACKEND_DIR/requirements.txt" || fail "백엔드 패키지 설치에 실패했습니다. 인터넷 연결을 확인해 주세요."

printf '[2/4] 프런트엔드 환경을 준비합니다...\n'
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  (cd "$FRONTEND_DIR" && npm install) || fail "프런트엔드 패키지 설치에 실패했습니다. 인터넷 연결을 확인해 주세요."
fi

printf '[3/4] 백엔드를 시작합니다...\n'
(cd "$BACKEND_DIR" && exec "$BACKEND_DIR/.venv/bin/python" -m uvicorn main:app --port 8000) &
BACKEND_PID=$!

printf '[4/4] 프런트엔드를 시작합니다...\n'
(cd "$FRONTEND_DIR" && exec "$FRONTEND_DIR/node_modules/.bin/vite" --host 127.0.0.1 --port 5173 --strictPort) &
FRONTEND_PID=$!

READY=0
COUNT=0
while [ "$COUNT" -lt 30 ]; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:5173 >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null || ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    break
  fi
  sleep 1
  COUNT=$((COUNT + 1))
done

if [ "$READY" -ne 1 ]; then
  fail "서버가 정상적으로 시작되지 않았습니다. 위 로그를 확인해 주세요."
fi

open http://localhost:5173
printf '\n[완료] 슬쩍이 실행 중입니다: http://localhost:5173\n'
printf '이 창을 닫거나 Control+C를 누르면 서버가 종료됩니다.\n'

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

fail "서버 중 하나가 예기치 않게 종료되었습니다. 위 로그를 확인해 주세요."
