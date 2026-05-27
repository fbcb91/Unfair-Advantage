import asyncio
import os
import uuid
from typing import List

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Unfair Advantage")

jobs: dict = {}


# ── Models ──────────────────────────────────────────────────────────────────

class SetupRequest(BaseModel):
    anthropic_api_key: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TwoFARequest(BaseModel):
    code: str

class AnalyzeRequest(BaseModel):
    usernames: List[str]
    tone: str = "curioso"


# ── Setup / Auth ─────────────────────────────────────────────────────────────

@app.get("/api/setup")
async def check_setup():
    from instagram import is_logged_in
    logged_in = await is_logged_in()
    return {
        "api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "logged_in": logged_in,
    }


@app.post("/api/setup")
async def save_api_key(data: SetupRequest):
    os.environ["ANTHROPIC_API_KEY"] = data.anthropic_api_key
    try:
        _write_env()
    except OSError:
        pass
    return {"success": True}


@app.post("/api/login")
async def do_login(data: LoginRequest):
    from instagram import start_login
    result = await start_login(data.username, data.password)
    if result.get("success"):
        os.environ["INSTAGRAM_USERNAME"] = data.username
        os.environ["INSTAGRAM_PASSWORD"] = data.password
        try:
            _write_env()
        except OSError:
            pass
    return result


@app.post("/api/login/verify")
async def do_2fa(data: TwoFARequest):
    from instagram import submit_2fa
    return await submit_2fa(data.code)


@app.post("/api/logout")
async def do_logout():
    global _context
    from pathlib import Path
    import instagram
    instagram._context = None
    instagram._browser = None
    instagram._login_page = None
    try:
        Path(instagram.COOKIES_FILE).unlink(missing_ok=True)
    except Exception:
        pass
    return {"success": True}


# ── Analysis ──────────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def start_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    from instagram import is_logged_in
    if not await is_logged_in():
        raise HTTPException(status_code=401, detail="Non sei loggato su Instagram")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=400, detail="API key Anthropic non configurata")

    usernames = [u.strip().lstrip("@") for u in request.usernames if u.strip()]
    if not usernames:
        raise HTTPException(status_code=400, detail="Nessun username fornito")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "processing",
        "total": len(usernames),
        "completed": 0,
        "current": usernames[0],
        "results": [],
    }

    background_tasks.add_task(_process_batch, job_id, usernames, request.tone)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job non trovato")
    return jobs[job_id]


async def _process_batch(job_id: str, usernames: List[str], tone: str):
    from ai_analyzer import analyze_profile
    from instagram import get_profile_data

    for i, username in enumerate(usernames):
        jobs[job_id]["current"] = username
        try:
            profile = await get_profile_data(username)

            if profile.get("is_private"):
                result = {
                    "username": username,
                    "full_name": profile.get("full_name", ""),
                    "profile_pic_url": profile.get("profile_pic_url"),
                    "follower_count": profile.get("follower_count", 0),
                    "status": "private",
                }
            else:
                analysis = await asyncio.to_thread(analyze_profile, profile, tone)
                result = {"username": username, "status": "done", **analysis}

        except Exception as e:
            result = {"username": username, "status": "error", "error": str(e)}

        jobs[job_id]["results"].append(result)
        jobs[job_id]["completed"] += 1

        if i < len(usernames) - 1:
            await asyncio.sleep(3)

    jobs[job_id]["status"] = "done"
    jobs[job_id]["current"] = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _write_env():
    lines = {
        "INSTAGRAM_USERNAME": os.getenv("INSTAGRAM_USERNAME", ""),
        "INSTAGRAM_PASSWORD": os.getenv("INSTAGRAM_PASSWORD", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "SESSION_FILE": os.getenv("SESSION_FILE", "session.json"),
    }
    with open(".env", "w") as f:
        f.write("\n".join(f"{k}={v}" for k, v in lines.items()) + "\n")


# ── Static ────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
