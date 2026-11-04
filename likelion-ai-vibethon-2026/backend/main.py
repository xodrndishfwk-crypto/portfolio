from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers.answers import router as answers_router
from routers.auth import router as auth_router
from routers.families import router as families_router
from routers.questions import router as questions_router
from routers.system import router as system_router
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent / ".env")

import asyncio
import json
import urllib.request

async def _log_ngrok_url():
    await asyncio.sleep(2)
    for _ in range(6):
        try:
            req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                tunnels = data.get("tunnels", [])
                if tunnels:
                    url = tunnels[0].get("public_url")
                    print("\n" + "=" * 55)
                    print(f" [*] ngrok 외부 접속 주소: {url}")
                    print("=" * 55 + "\n", flush=True)
                    return
        except Exception:
            pass
        await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(_log_ngrok_url())
    yield

app = FastAPI(title="슬쩍 API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?://.*|capacitor://.*|ionic://.*)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(system_router)
app.include_router(auth_router)
app.include_router(families_router)
app.include_router(questions_router)
app.include_router(answers_router)
