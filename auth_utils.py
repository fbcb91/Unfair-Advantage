import os
import httpx
from fastapi import Header, HTTPException

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


async def get_current_user_id(authorization: str = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Non autenticato. Accedi dall'estensione.")
    token = authorization.split(" ", 1)[1]
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
                timeout=8.0,
            )
        if res.status_code == 401:
            raise HTTPException(status_code=401, detail="Sessione scaduta. Accedi di nuovo.")
        if res.status_code != 200:
            raise HTTPException(status_code=401, detail="Token non valido.")
        return res.json()["id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Errore di autenticazione.")
