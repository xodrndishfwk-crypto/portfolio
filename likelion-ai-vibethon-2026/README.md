# 슬쩍

**2026 멋쟁이 사자처럼 AI바이브톤 · 4팀**

> 말하기 어려운 자녀의 고민을 자연스러운 질문으로 바꾸고, 부모의 경험이 담긴 답변을 가족에게 전하기 좋은 문장으로 다듬는 가족 대화 프로토타입

슬쩍은 자녀가 입력한 고민의 핵심 의도를 익명화한 뒤 네 개의 일상 질문 사이에 섞어 보여줍니다. 부모는 질문 하나를 골라 자신의 경험을 답하고, 답변을 부드럽게 다듬어 지혜 서재에 보관할 수 있습니다.

## 주요 기능

- 두 배경 이미지가 시간에 따라 교차하는 감성적인 로그인·회원가입 홈
- 자녀의 감정과 고민 입력
- `슬쩍 모드`와 `살짝 모드` 선택
- 자녀의 고민을 부모의 과거 경험을 묻는 질문으로 변환
- 변환된 질문 한 개를 네 개의 일상 질문과 섞어서 제공
- 질문 내용에 맞는 답변 시작 문구 제공
- 부모 답변을 질문 의도에 맞게 다듬기
- 감정, 날짜, 질문, 원문, 다듬은 답변을 지혜 서재에 표시
- 회원가입과 로그인, 부모·자녀 역할 구분
- 가족 생성, 초대 코드 참여, 질문·답변의 SQLite 저장
- OpenAI 또는 Gemini API를 사용할 수 없을 때 로컬 질문·답변 규칙으로 대체

## 현재 구현 범위

현재 버전은 로컬 FastAPI 서버를 중심으로 자녀와 부모의 질문·답변 흐름을 시연하는 프로토타입입니다.

- 사용자, 가족, 질문 전달 상태, 답변과 반응은 `backend/seuljjeock.db`에 저장됩니다.
- 로그인 토큰과 현재 가족 선택 정보는 브라우저 `localStorage`에 저장됩니다.
- 음성 녹음 버튼은 Web Speech API 기반의 실시간 음성 인식(STT)으로 부모님의 조언을 음성으로 받아 적습니다.
- 서버가 접근 가능한 환경에서는 서로 다른 브라우저에서도 같은 가족 데이터를 조회할 수 있습니다.
- 질문은 `pending`, 답변 후에는 `answered` 상태로 관리됩니다.

실제 가족 간 서비스로 확장하려면 인증, 가족 멤버십, 질문 전달 상태, 답변 저장을 담당하는 데이터베이스가 필요합니다.

## 기술 구성

| 영역 | 기술 |
| --- | --- |
| Frontend | React 19, Vite 8, JavaScript, CSS |
| Backend | Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy, SQLite |
| AI | OpenAI Responses API 우선, 선택적 Gemini 장애 대비 |
| Quality data | JSON 질문 라이브러리와 말투별 답변 품질 예시 |
| Local fallback | API를 모두 사용할 수 없을 때만 쓰는 로컬 질문·답변 규칙 |
| 현재 저장소 | SQLite 및 브라우저 로그인 상태 |

## 실행 요구사항

- Python 3.10 이상
- Node.js `^20.19.0` 또는 `>=22.12.0`
- npm
- 최초 패키지 설치를 위한 인터넷 연결
- AI 기능 사용 시 OpenAI 또는 Gemini API 키

## 빠른 실행

### Windows

- **로컬 실행**: `START.bat`을 더블 클릭하면 백엔드와 프런트엔드를 실행합니다. (`http://localhost:5173`)
- **외부/모바일 접속 실행**: `START_NGROK.bat`을 더블 클릭하면 백엔드, 프런트엔드, ngrok을 한 번에 실행하고 백엔드 CLI와 콘솔에 임의의 ngrok 접속 주소를 출력하며 클립보드에 자동 복사합니다.

각 실행 파일은 처음 실행할 때 필요한 가상환경 또는 npm 패키지를 준비합니다.

### macOS / Linux

#### macOS 원터치 실행

프로젝트 루트의 `START.command`를 더블 클릭합니다. 처음 실행할 때 Python 가상환경과 npm 패키지를 자동으로 준비하고, 백엔드와 프런트엔드를 함께 시작한 뒤 브라우저를 엽니다.

- macOS가 실행을 막으면 `START.command`를 Control-클릭한 뒤 **열기**를 한 번 선택합니다.
- 실행 중 표시되는 터미널 창을 닫거나 `Control+C`를 누르면 두 서버가 함께 종료됩니다.
- OpenAI API 키가 없어도 로컬 대체 기능으로 실행됩니다.

Linux 또는 터미널에서 각각 실행하려면 아래 방법을 사용합니다.

터미널 1에서 백엔드를 실행합니다.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

터미널 2에서 프런트엔드를 실행합니다.

```bash
cd frontend
npm install
npm run dev
```

## 수동 실행

### Backend

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Backend URL:

- API: `http://127.0.0.1:8000`
- 상태 확인: `http://127.0.0.1:8000/api/health`
- Swagger 문서: `http://127.0.0.1:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

프런트엔드는 기본적으로 `http://127.0.0.1:8000`을 호출합니다. 다른 백엔드 주소를 사용할 때는 프런트엔드 환경변수 `VITE_API_URL`을 설정합니다.

## AI 및 인증 설정

1. `backend/.env.example`을 `backend/.env`로 복사합니다.
2. 실제 API 키를 입력합니다.

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-5.6
OPENAI_TIMEOUT_SECONDS=30
OPENAI_MAX_ATTEMPTS=2
ENABLE_GEMINI_FALLBACK=true
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-latest
SECRET_KEY=충분히-긴-무작위-문자열
```

`backend/.env`는 Git에 포함하지 않습니다. OpenAI가 항상 첫 번째 제공자이며, OpenAI 호출이 실패한 경우에만 `ENABLE_GEMINI_FALLBACK=true`일 때 Gemini를 시도합니다. 두 API를 모두 사용할 수 없을 때에만 로컬 질문·답변 로직을 사용합니다. `backend/data/question_library.json`과 `backend/data/answer_style_examples.json`은 AI 프롬프트의 품질 참고 자료이자 최종 로컬 대체 데이터입니다. 상태 확인 API의 `provider`와 `providers` 값으로 인식된 제공자와 우선순위를 확인할 수 있습니다.

```json
{
  "status": "ok",
  "ai": true,
  "provider": "openai",
  "providers": ["openai", "gemini"],
  "openai_model": "gpt-5.6"
}
```

## API

### 상태 확인

`GET /api/health`

### 질문 변환

`POST /api/questions/transform`

요청 예시:

```json
{
  "worry": "면접에서 계속 떨어져서 자신감이 없어졌어요.",
  "emotion": "지침",
  "mode": "stealth"
}
```

`mode`는 `stealth` 또는 `direct`입니다. `stealth`는 다섯 개의 질문을, `direct`는 익명화한 회고 질문 하나를 반환합니다.

### 부모 답변 다듬기

`POST /api/answers/polish`

요청 예시:

```json
{
  "question": "실패가 계속될 때 어떻게 다시 움직일 힘을 얻었나요?",
  "answer": "나도 처음에는 막막했지만 그냥 하루씩 버텼어."
}
```

응답에는 부모 원문, 다듬은 답변, AI·로컬 처리 출처가 포함됩니다.

## 프로젝트 구조

```text
LikeLion/
├─ backend/
│  ├─ main.py                    # FastAPI 앱 조립과 라우터 등록
│  ├─ routers/                   # 시스템·질문·답변 API
│  ├─ schemas/                   # Pydantic 요청 형식
│  ├─ services/                  # 질문 변환·답변 다듬기·OpenAI 통신
│  ├─ data/                      # JSON 질문 라이브러리와 답변 품질 예시
│  ├─ tests/                     # API 계약·AI 우선순위·로컬 대체 테스트
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  ├─ public/
│  ├─ src/
│  │  ├─ App.jsx                 # 화면 상태와 사용자 흐름
│  │  ├─ App.css
│  │  ├─ QuestionOptions.css
│  │  └─ FeatureUpdates.css
│  ├─ package.json
│  └─ vite.config.js
├─ START.bat                     # Windows 백엔드 실행
├─ START2.bat                    # Windows 프런트엔드 실행
├─ TEAM_WORK_GUIDE.md            # 백엔드 분리 구조와 팀 작업 안내
└─ README.md
```

## 검사 명령

백엔드 계약 테스트:

```bash
cd backend
python -m unittest discover -s tests -v
```

프런트엔드 검사 및 빌드:

```bash
cd frontend
npm run lint
npm run build
```

## 다음 개발 우선순위

1. 답변 완료 후 질문·입력 상태 초기화
2. 사용자 로그인과 인증
3. 가족 생성, 초대 코드, 부모·자녀 역할 관리
4. 질문·답변 데이터베이스 저장
5. 질문의 `pending`, `viewed`, `answered` 상태 관리
6. 자녀 기기에서 부모 기기로 질문 전달
7. 답변 도착 알림과 기기 간 동기화
8. 실제 음성 인식 연결

권장 전달 흐름은 다음과 같습니다.

```text
자녀 질문 등록
  → AI 질문 변환
  → DB에 pending 상태로 저장
  → 부모가 미답변 질문 조회
  → 부모 답변 저장
  → 질문을 answered 상태로 변경
  → 자녀가 답변 확인
```

## 보안 및 개인정보

- `.env`, API 키, 가상환경, `node_modules`는 Git에 올리지 않습니다.
- 자녀가 입력한 원래 고민은 부모 화면에 그대로 노출하지 않습니다.
- 데이터베이스 도입 시 원문 고민의 저장 기간과 삭제 정책을 먼저 정해야 합니다.
- 가족과 사용자 기능을 추가할 때 모든 질문·답변 API에 가족 소속 및 역할 권한 검사를 적용해야 합니다.

## 협업

백엔드의 기능별 역할 분담과 병합 순서는 `TEAM_WORK_GUIDE.md`를 참고하세요.

커밋 메시지 예시:

```text
feat: 가족 초대 API 추가
fix: 답변 완료 후 질문 상태 초기화
docs: 현재 구현 범위와 실행법 정리
test: 질문 전달 상태 계약 테스트 추가
```


## 대회 발표 및 시연 자료

- [최종 발표자료 (PDF)](슬쩍발표최종본ppt.pdf)
- [서비스 소개 영상](t소개.mp4)
- [PC 회원가입·로그인 시연](1%20pc%20회원가입%20로그인%20등.mp4)
- [모바일 회원가입·로그인 시연](2%20모바일%20회원가입%20로그인%20등.mp4)
- [PC 슬쩍 마음 보내기](3%20pc%20슬쩍%20마음%20보내기.mp4)
- [모바일 슬쩍 답변](4%20모바일%20슬쩍%20답변.mp4)
- [PC 살짝 마음 보내기](5%20pc%20살짝%20마음%20보내기.mp4)
- [모바일 살짝 답변](6%20모바일%20살짝%20답변.mp4)
- [PC 지혜의 서재 확인](7%20pc%20지혜의%20서재%20확인.mp4)
- [Android 시연용 APK](슬쩍_debug.apk)

공개본에는 기존 실행 데이터베이스와 개인 환경 파일을 포함하지 않습니다. 실행에 필요한 환경 변수는 `backend/.env.example`을 참고하세요.
