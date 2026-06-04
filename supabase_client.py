import os
from datetime import datetime, timezone
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
FREE_LIMIT = 10

_client: Client = None


def get_admin_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def get_current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_user_status(user_id: str) -> dict:
    try:
        sb = get_admin_client()
    except Exception:
        return {"subscription": "free", "analyses_this_month": 0, "analyses_limit": FREE_LIMIT, "can_analyze": True}

    try:
        res = sb.table("profiles").select("subscription_status, current_period_end").eq("id", user_id).single().execute()
        profile = res.data or {}
    except Exception:
        profile = {}

    status = profile.get("subscription_status", "free")

    if status == "premium" and profile.get("current_period_end"):
        try:
            end = datetime.fromisoformat(profile["current_period_end"].replace("Z", "+00:00"))
            if end < datetime.now(timezone.utc):
                status = "free"
        except Exception:
            pass

    month = get_current_month()
    try:
        res = sb.table("usage").select("analyses_count").eq("user_id", user_id).eq("month", month).execute()
        count = res.data[0]["analyses_count"] if res.data else 0
    except Exception:
        count = 0

    return {
        "subscription": status,
        "analyses_this_month": count,
        "analyses_limit": None if status == "premium" else FREE_LIMIT,
        "can_analyze": status == "premium" or count < FREE_LIMIT,
    }


def increment_usage(user_id: str) -> int:
    sb = get_admin_client()
    month = get_current_month()
    res = sb.rpc("increment_usage", {"p_user_id": user_id, "p_month": month}).execute()
    return res.data or 0
