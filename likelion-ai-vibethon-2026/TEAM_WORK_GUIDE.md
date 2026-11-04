# 슬쩍 백엔드 분리본 — 팀 작업 안내

기존 `main.py`의 동작과 API 주소를 유지하면서, 여러 명이 동시에 작업하기 쉽도록 기능별로 분리한 버전입니다.

## 폴더 구조

```text
backend/
├─ main.py                         # 앱 생성·라우터 등록만 담당
├─ routers/
│  ├─ system.py                    # 루트·상태 확인 API
│  ├─ questions.py                 # 질문 API 연결부
│  └─ answers.py                   # 답변 API 연결부
├─ schemas/
│  ├─ question.py                  # 질문 입력 형식
│  └─ answer.py                    # 답변 입력 형식
├─ services/
│  ├─ question_service.py          # 질문 변환·질문 섞기
│  ├─ answer_service.py            # 부모 답변 순화
│  └─ openai_client.py             # 공통 OpenAI 요청
├─ data/
│  └─ question_bank.py             # 로컬 질문·키워드 데이터
├─ requirements.txt
└─ .env.example
```

## 추천 역할 분담

| 담당 | 주로 수정할 파일 | 역할 |
| --- | --- | --- |
| 질문 기능 | `services/question_service.py`, `data/question_bank.py` | 자녀 고민을 질문으로 변환하고 익명 질문 사이에 섞기 |
| 답변 기능 | `services/answer_service.py` | 부모 답변을 부드럽게 다듬기 |
| API 연결 | `routers/questions.py`, `routers/answers.py`, `main.py` | 요청·응답 연결 및 새 라우터 등록 |
| 데이터 형식 | `schemas/question.py`, `schemas/answer.py` | 입력값 검증 규칙 관리 |

질문 담당과 답변 담당은 서로 다른 파일만 수정하므로 대부분의 작업에서 충돌하지 않습니다.

## 기존 프론트와의 연결

프론트가 호출하던 주소는 바뀌지 않았습니다.

```text
POST /api/questions/transform
POST /api/answers/polish
```

요청 필드와 응답 필드도 기존과 같습니다.

## 실행

```bash
cd backend
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

API 문서는 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

## 합치는 순서

1. 질문 기능 브랜치와 답변 기능 브랜치를 먼저 각각 완성합니다.
2. 각 브랜치에서 자기 API를 단독 확인합니다.
3. `develop`에 질문·답변 기능을 차례로 병합합니다.
4. 마지막에 API 연결 담당자가 `main.py`의 라우터 등록과 전체 프론트 연결만 확인합니다.

`main.py`와 공통 `services/openai_client.py`는 여러 명이 동시에 수정하지 않는 편이 안전합니다.
