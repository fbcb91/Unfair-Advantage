import asyncio
import os
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Unfair Advantage API")

# Allow requests from Chrome extensions and any origin (single-tenant API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────

class ImageData(BaseModel):
    data: str
    media_type: str = "image/jpeg"

class PostData(BaseModel):
    caption: str = ""
    image_url: Optional[str] = None

class ProfileData(BaseModel):
    username: str
    full_name: str = ""
    biography: str = ""
    follower_count: int = 0
    following_count: int = 0
    media_count: int = 0
    is_private: bool = False
    profile_pic_url: str = ""
    posts: List[PostData] = []
    highlight_titles: List[str] = []
    images: List[ImageData] = []

class AnalyzeRequest(BaseModel):
    profile: ProfileData
    tone: str = "curioso"


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    import anthropic as _anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="API key Anthropic non configurata sul server")

    if request.profile.is_private:
        raise HTTPException(status_code=400, detail="Profilo privato")

    try:
        from ai_analyzer import analyze_profile
        result = await asyncio.to_thread(
            analyze_profile,
            request.profile.model_dump(),
            request.tone,
        )
        return result

    except _anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key Anthropic non valida. Controllala nelle impostazioni del server.")
    except _anthropic.PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Accesso negato dall'API Anthropic. Verifica i permessi della tua API key.")
    except _anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Troppe richieste. Riprova tra qualche secondo.")
    except _anthropic.APIStatusError as e:
        msg = getattr(e, "message", str(e))
        if "credit" in msg.lower() or "billing" in msg.lower() or e.status_code in (402, 529):
            raise HTTPException(status_code=402, detail="Crediti Anthropic esauriti. Ricarica su console.anthropic.com → Billing.")
        raise HTTPException(status_code=502, detail=f"Errore API Anthropic: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Static / landing page ─────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
