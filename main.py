import asyncio
import os
import httpx
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="Unfair Advantage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")


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
    character: str = ""
    user_info: str = ""

class RefineRequest(BaseModel):
    profile: ProfileData
    tone: str = "curioso"
    character: str = ""
    original_message: str
    instruction: str = ""

class AuthRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ResetRequest(BaseModel):
    email: str

class WaitlistRequest(BaseModel):
    email: str

class CheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str


# ── Auth helpers ──────────────────────────────────────────────────────────

from auth_utils import get_current_user_id
from supabase_client import get_user_status, increment_usage, get_admin_client

async def _supabase_post(path: str, payload: dict) -> tuple[dict, int]:
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{SUPABASE_URL}/auth/v1/{path}",
            json=payload,
            headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
            timeout=10.0,
        )
    return res.json(), res.status_code


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"ok": True}


# ── Auth endpoints ─────────────────────────────────────────────────────────

# Signup rate limit: max 3 new accounts per IP per day (in-memory, resets on deploy)
import time
_signup_log: dict = {}
SIGNUP_MAX_PER_DAY = 3

def _check_signup_rate(ip: str):
    now = time.time()
    window_start = now - 86400
    timestamps = [t for t in _signup_log.get(ip, []) if t > window_start]
    if len(timestamps) >= SIGNUP_MAX_PER_DAY:
        raise HTTPException(status_code=429, detail="Troppe registrazioni da questo indirizzo. Riprova domani.")
    timestamps.append(now)
    _signup_log[ip] = timestamps
    # Evita crescita illimitata della mappa
    if len(_signup_log) > 10000:
        cutoff = now - 86400
        for k in list(_signup_log.keys()):
            if all(t <= cutoff for t in _signup_log[k]):
                del _signup_log[k]


@app.post("/api/auth/signup")
async def signup(req: AuthRequest, request: Request):
    client_ip = request.headers.get("Fly-Client-IP") or (request.client.host if request.client else "unknown")
    _check_signup_rate(client_ip)
    data, status = await _supabase_post("signup", {"email": req.email, "password": req.password})
    if status >= 400:
        msg = data.get("msg") or data.get("error_description") or "Errore durante la registrazione."
        raise HTTPException(status_code=400, detail=msg)
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "email": data.get("user", {}).get("email"),
    }

@app.post("/api/auth/login")
async def login(req: AuthRequest):
    data, status = await _supabase_post(
        "token?grant_type=password",
        {"email": req.email, "password": req.password},
    )
    if status >= 400:
        msg = data.get("error_description") or data.get("msg") or "Email o password errati."
        raise HTTPException(status_code=400, detail=msg)
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
        "email": data.get("user", {}).get("email"),
    }

@app.post("/api/auth/refresh")
async def refresh_token(req: RefreshRequest):
    data, status = await _supabase_post(
        "token?grant_type=refresh_token",
        {"refresh_token": req.refresh_token},
    )
    if status >= 400:
        raise HTTPException(status_code=401, detail="Sessione scaduta. Accedi di nuovo.")
    return {
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
    }

@app.get("/api/me")
async def get_me(user_id: str = Depends(get_current_user_id)):
    status = await asyncio.to_thread(get_user_status, user_id)
    return status


# ── Analysis endpoints ─────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest, user_id: str = Depends(get_current_user_id)):
    import anthropic as _anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="API key Anthropic non configurata sul server")

    if request.profile.is_private:
        raise HTTPException(status_code=400, detail="Profilo privato")

    user_status = await asyncio.to_thread(get_user_status, user_id)
    if not user_status["can_analyze"]:
        raise HTTPException(
            status_code=402,
            detail=f"Hai raggiunto il limite di {user_status['analyses_limit']} analisi gratuite questo mese. Passa a Premium per continuare.",
        )
    if request.character and user_status["subscription"] != "premium":
        raise HTTPException(
            status_code=402,
            detail="I personaggi sono riservati agli utenti Premium. Passa a Premium per scrivere come Chuck Bass.",
        )

    try:
        from ai_analyzer import analyze_profile
        result = await asyncio.to_thread(
            analyze_profile,
            request.profile.model_dump(),
            request.tone,
            request.character,
            request.user_info,
            user_status["subscription"] == "premium",
        )
        await asyncio.to_thread(increment_usage, user_id)
        result["_usage"] = {
            "analyses_this_month": user_status["analyses_this_month"] + 1,
            "analyses_limit": user_status["analyses_limit"],
            "subscription": user_status["subscription"],
        }
        return result

    except _anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key Anthropic non valida.")
    except _anthropic.PermissionDeniedError:
        raise HTTPException(status_code=403, detail="Accesso negato dall'API Anthropic.")
    except _anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Troppe richieste. Riprova tra qualche secondo.")
    except _anthropic.APIStatusError as e:
        msg = getattr(e, "message", str(e))
        if "credit" in msg.lower() or "billing" in msg.lower() or e.status_code in (402, 529):
            raise HTTPException(status_code=402, detail="Crediti Anthropic esauriti.")
        raise HTTPException(status_code=502, detail=f"Errore API Anthropic: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refine")
async def refine(request: RefineRequest, user_id: str = Depends(get_current_user_id)):
    import anthropic as _anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="API key Anthropic non configurata sul server")

    user_status = await asyncio.to_thread(get_user_status, user_id)
    is_premium = user_status["subscription"] == "premium"
    if not is_premium and not user_status["can_analyze"]:
        raise HTTPException(
            status_code=402,
            detail="Hai esaurito le analisi gratuite di questo mese. Passa a Premium per continuare.",
        )

    try:
        from ai_analyzer import refine_message
        alternatives = await asyncio.to_thread(
            refine_message,
            request.profile.model_dump(),
            request.tone,
            request.character,
            request.original_message,
            request.instruction,
            is_premium,
        )
        if not is_premium:
            await asyncio.to_thread(increment_usage, user_id)
        return {"alternatives": alternatives}

    except _anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key Anthropic non valida.")
    except _anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Troppe richieste. Riprova tra qualche secondo.")
    except _anthropic.APIStatusError as e:
        msg = getattr(e, "message", str(e))
        if "credit" in msg.lower() or "billing" in msg.lower() or e.status_code in (402, 529):
            raise HTTPException(status_code=402, detail="Crediti Anthropic esauriti.")
        raise HTTPException(status_code=502, detail=f"Errore API Anthropic: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Stripe endpoints ───────────────────────────────────────────────────────

@app.post("/api/checkout")
async def create_checkout(req: CheckoutRequest, user_id: str = Depends(get_current_user_id)):
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        raise HTTPException(status_code=503, detail="Pagamenti non ancora configurati.")
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    sb = get_admin_client()
    profile_res = sb.table("profiles").select("stripe_customer_id").eq("id", user_id).single().execute()
    customer_id = profile_res.data.get("stripe_customer_id") if profile_res.data else None

    session = stripe.checkout.Session.create(
        customer=customer_id or None,
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        success_url=req.success_url,
        cancel_url=req.cancel_url,
        metadata={"user_id": user_id},
        allow_promotion_codes=True,
    )
    return {"url": session.url}


@app.post("/api/regen")
async def regen(request: AnalyzeRequest, user_id: str = Depends(get_current_user_id)):
    import anthropic as _anthropic

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="API key Anthropic non configurata sul server")
    if request.profile.is_private:
        raise HTTPException(status_code=400, detail="Profilo privato")

    user_status = await asyncio.to_thread(get_user_status, user_id)
    is_premium = user_status["subscription"] == "premium"
    if request.character and not is_premium:
        raise HTTPException(status_code=402, detail="I personaggi sono riservati agli utenti Premium.")

    try:
        from ai_analyzer import analyze_profile
        result = await asyncio.to_thread(
            analyze_profile,
            request.profile.model_dump(),
            request.tone,
            request.character,
            request.user_info,
            is_premium,
        )
        return result
    except _anthropic.AuthenticationError:
        raise HTTPException(status_code=401, detail="API key Anthropic non valida.")
    except _anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Troppe richieste. Riprova tra qualche secondo.")
    except _anthropic.APIStatusError as e:
        msg = getattr(e, "message", str(e))
        raise HTTPException(status_code=502, detail=f"Errore API Anthropic: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/reset-password")
async def reset_password(req: ResetRequest):
    data, status = await _supabase_post("recover", {"email": req.email})
    if status >= 400:
        msg = data.get("msg") or data.get("error_description") or "Errore durante il reset."
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True}


@app.post("/api/portal")
async def stripe_portal(request: Request, user_id: str = Depends(get_current_user_id)):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Pagamenti non configurati.")
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    sb = get_admin_client()
    profile_res = sb.table("profiles").select("stripe_customer_id").eq("id", user_id).single().execute()
    customer_id = profile_res.data.get("stripe_customer_id") if profile_res.data else None
    if not customer_id:
        raise HTTPException(status_code=404, detail="Nessun abbonamento attivo trovato.")

    origin = request.headers.get("origin", "https://unfair-advantage.fly.dev")
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{origin}/success",
    )
    return {"url": session.url}


@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe non configurato.")
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Webhook signature non valida.")

    sb = get_admin_client()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session["metadata"].get("user_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        if user_id:
            period_end_iso = None
            if subscription_id:
                try:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    import datetime
                    period_end_iso = datetime.datetime.fromtimestamp(
                        sub["current_period_end"], tz=datetime.timezone.utc
                    ).isoformat()
                except Exception:
                    pass
            sb.table("profiles").update({
                "stripe_customer_id": customer_id,
                "subscription_id": subscription_id,
                "subscription_status": "premium",
                "current_period_end": period_end_iso,
            }).eq("id", user_id).execute()

    elif event["type"] in ("customer.subscription.deleted", "customer.subscription.updated"):
        sub = event["data"]["object"]
        status = sub.get("status")
        subscription_id = sub.get("id")
        current_period_end = sub.get("current_period_end")
        is_active = status in ("active", "trialing")

        import datetime
        period_end_iso = datetime.datetime.fromtimestamp(
            current_period_end, tz=datetime.timezone.utc
        ).isoformat() if current_period_end else None

        sb.table("profiles").update({
            "subscription_status": "premium" if is_active else "free",
            "current_period_end": period_end_iso,
        }).eq("subscription_id", subscription_id).execute()

    return {"ok": True}


@app.post("/api/waitlist")
async def waitlist(req: WaitlistRequest):
    try:
        sb = get_admin_client()
        sb.table("waitlist").upsert({"email": req.email}, on_conflict="email").execute()
    except Exception:
        pass  # Fail silently — table might not exist yet
    return {"ok": True}


@app.get("/pricing")
async def pricing_page():
    return FileResponse("static/pricing.html")

@app.get("/success")
async def success_page():
    return FileResponse("static/success.html")

@app.get("/privacy")
async def privacy_page():
    return FileResponse("static/privacy.html")

@app.get("/reset")
async def reset_page():
    return FileResponse("static/reset.html")

class UpdatePasswordRequest(BaseModel):
    password: str

@app.post("/api/auth/update-password")
async def update_password(req: UpdatePasswordRequest, authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token mancante.")
    token = authorization.split(" ", 1)[1]
    async with httpx.AsyncClient() as client:
        res = await client.put(
            f"{SUPABASE_URL}/auth/v1/user",
            json={"password": req.password},
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
    if res.status_code >= 400:
        raise HTTPException(status_code=400, detail="Errore aggiornamento password.")
    return {"ok": True}


# ── Static / landing page ─────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
