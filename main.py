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
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="API key Anthropic non configurata sul server")

    if request.profile.is_private:
        raise HTTPException(status_code=400, detail="Profilo privato")

    from ai_analyzer import analyze_profile
    result = await asyncio.to_thread(
        analyze_profile,
        request.profile.model_dump(),
        request.tone,
    )
    return result


# ── Static / landing page ─────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
