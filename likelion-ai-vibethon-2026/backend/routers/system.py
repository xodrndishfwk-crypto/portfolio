import os
from fastapi import APIRouter

router = APIRouter(tags=["system"])

@router.get("/")
def root(): return {"message": "슬쩍 API가 마음을 잇고 있어요."}

@router.get("/api/health")
def health():
    gk = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    ok = bool(os.getenv("OPENAI_API_KEY"))
    providers = [name for name, enabled in (("openai", ok), ("gemini", gk)) if enabled]
    return {
        "status": "ok",
        "ai": bool(providers),
        "provider": providers[0] if providers else "local",
        "providers": providers,
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.6") if ok else None,
    }
