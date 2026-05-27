import os
import uuid
import asyncio
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Unfair Advantage")

jobs: dict = {}


class AnalyzeRequest(BaseModel):
    usernames: List[str]
    tone: str = "curioso"


class SetupRequest(BaseModel):
    instagram_username: str
    instagram_password: str
    anthropic_api_key: str


@app.get("/api/setup")
async def check_setup():
    return {
        "configured": bool(
            os.getenv("INSTAGRAM_USERNAME") and os.getenv("ANTHROPIC_API_KEY")
        )
    }


@app.post("/api/setup")
async def save_setup(data: SetupRequest):
    # Set in-process env vars immediately (works on any platform)
    os.environ["INSTAGRAM_USERNAME"] = data.instagram_username
    os.environ["INSTAGRAM_PASSWORD"] = data.instagram_password
    os.environ["ANTHROPIC_API_KEY"] = data.anthropic_api_key
    os.environ.setdefault("SESSION_FILE", "session.json")

    # Also persist to .env for local use (no-op if filesystem is read-only)
    try:
        env_lines = [
            f"INSTAGRAM_USERNAME={data.instagram_username}",
            f"INSTAGRAM_PASSWORD={data.instagram_password}",
            f"ANTHROPIC_API_KEY={data.anthropic_api_key}",
            "SESSION_FILE=session.json",
        ]
        with open(".env", "w") as f:
            f.write("\n".join(env_lines) + "\n")
    except OSError:
        pass

    import instagram
    instagram._client = None

    return {"success": True}


@app.post("/api/analyze")
async def start_analysis(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    if not os.getenv("INSTAGRAM_USERNAME"):
        raise HTTPException(status_code=400, detail="Credenziali non configurate")

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
    from instagram import get_profile_data
    from ai_analyzer import analyze_profile

    for i, username in enumerate(usernames):
        jobs[job_id]["current"] = username

        try:
            profile = await asyncio.to_thread(get_profile_data, username)

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


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


app.mount("/static", StaticFiles(directory="static"), name="static")
