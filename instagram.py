import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional

import httpx
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

_playwright_inst = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None
_login_page: Optional[Page] = None

COOKIES_FILE = "ig_cookies.json"


async def _ensure_browser() -> Browser:
    global _playwright_inst, _browser
    if _browser is None or not _browser.is_connected():
        if _playwright_inst:
            try:
                await _playwright_inst.stop()
            except Exception:
                pass
        _playwright_inst = await async_playwright().start()
        _browser = await _playwright_inst.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
            ],
        )
    return _browser


async def _get_context() -> BrowserContext:
    global _context
    if _context is None:
        browser = await _ensure_browser()
        _context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
            locale="it-IT",
        )
        cookies = _load_cookies()
        if cookies:
            await _context.add_cookies(cookies)
    return _context


def _load_cookies() -> Optional[list]:
    b64 = os.getenv("IG_COOKIES_B64", "")
    if b64:
        try:
            return json.loads(base64.b64decode(b64))
        except Exception:
            pass
    if Path(COOKIES_FILE).exists():
        try:
            return json.loads(Path(COOKIES_FILE).read_text())
        except Exception:
            pass
    return None


async def _save_cookies():
    ctx = await _get_context()
    cookies = await ctx.cookies()
    try:
        Path(COOKIES_FILE).write_text(json.dumps(cookies))
    except Exception:
        pass


async def is_logged_in() -> bool:
    ctx = await _get_context()
    cookies = await ctx.cookies("https://www.instagram.com")
    return any(c["name"] == "sessionid" for c in cookies)


async def start_login(username: str, password: str) -> dict:
    global _login_page
    ctx = await _get_context()

    if _login_page:
        try:
            await _login_page.close()
        except Exception:
            pass
        _login_page = None

    _login_page = await ctx.new_page()

    try:
        from playwright_stealth import stealth_async
        await stealth_async(_login_page)
    except ImportError:
        pass

    try:
        await _login_page.goto(
            "https://www.instagram.com/accounts/login/",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        await _login_page.wait_for_timeout(2000)

        # Dismiss cookie consent if present
        for selector in [
            "text=Allow all cookies",
            "text=Consenti tutti i cookie",
            "text=Accept all",
        ]:
            try:
                await _login_page.click(selector, timeout=2000)
                await _login_page.wait_for_timeout(600)
                break
            except Exception:
                pass

        await _login_page.fill('input[name="username"]', username)
        await _login_page.wait_for_timeout(400)
        await _login_page.fill('input[name="password"]', password)
        await _login_page.wait_for_timeout(400)
        await _login_page.click('button[type="submit"]')
        await _login_page.wait_for_timeout(5000)

        url = _login_page.url

        if "two_factor" in url or await _login_page.query_selector('input[name="verificationCode"]'):
            return {"success": False, "needs_2fa": True}

        if "challenge" in url:
            return {"success": False, "needs_challenge": True}

        if "accounts/login" in url:
            return {"success": False, "error": "Credenziali non valide"}

        await _save_cookies()
        await _login_page.close()
        _login_page = None
        return {"success": True}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def submit_2fa(code: str) -> dict:
    global _login_page
    if not _login_page:
        return {"success": False, "error": "Sessione scaduta, riprova il login"}
    try:
        await _login_page.fill('input[name="verificationCode"]', code)
        await _login_page.wait_for_timeout(400)
        await _login_page.click('button[type="submit"]')
        await _login_page.wait_for_timeout(4000)

        url = _login_page.url
        if "accounts/login" not in url and "two_factor" not in url:
            await _save_cookies()
            await _login_page.close()
            _login_page = None
            return {"success": True}

        return {"success": False, "error": "Codice non valido, riprova"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_profile_data(username: str) -> dict:
    ctx = await _get_context()
    page = await ctx.new_page()

    try:
        from playwright_stealth import stealth_async
        await stealth_async(page)
    except ImportError:
        pass

    profile_user: dict = {}
    posts_edges: list = []

    async def on_response(response):
        url = response.url
        try:
            if "web_profile_info" in url:
                data = await response.json()
                user = data.get("data", {}).get("user") or data.get("graphql", {}).get("user", {})
                if user:
                    profile_user.update(user)
            elif "edge_owner_to_timeline_media" in url or (
                "graphql/query" in url and not posts_edges
            ):
                data = await response.json()
                edges = (
                    data.get("data", {})
                    .get("user", {})
                    .get("edge_owner_to_timeline_media", {})
                    .get("edges", [])
                )
                if edges:
                    posts_edges.extend(edges)
        except Exception:
            pass

    page.on("response", on_response)

    try:
        await page.goto(
            f"https://www.instagram.com/{username}/",
            wait_until="networkidle",
            timeout=20000,
        )
        await page.wait_for_timeout(2000)

        # If we got redirected to login, session is expired
        if "accounts/login" in page.url:
            raise ValueError("Sessione Instagram scaduta. Fai di nuovo il login.")

        if not profile_user:
            content = await page.content()
            if "Page Not Found" in content or "Sorry, this page" in content:
                raise ValueError(f"Utente @{username} non trovato")
            raise ValueError(
                f"Impossibile leggere il profilo di @{username}. "
                "Instagram potrebbe aver bloccato la richiesta temporaneamente."
            )

        is_private = profile_user.get("is_private", False)
        follower_count = (
            profile_user.get("edge_followed_by", {}).get("count")
            or profile_user.get("follower_count", 0)
        )
        following_count = (
            profile_user.get("edge_follow", {}).get("count")
            or profile_user.get("following_count", 0)
        )
        media_count = (
            profile_user.get("edge_owner_to_timeline_media", {}).get("count")
            or profile_user.get("media_count", 0)
        )

        base = {
            "username": username,
            "full_name": profile_user.get("full_name", ""),
            "biography": profile_user.get("biography", ""),
            "follower_count": follower_count,
            "following_count": following_count,
            "media_count": media_count,
            "is_private": is_private,
            "profile_pic_url": (
                profile_user.get("profile_pic_url_hd")
                or profile_user.get("profile_pic_url", "")
            ),
        }

        if is_private:
            return base

        # Extract posts
        if not posts_edges:
            posts_edges.extend(
                profile_user.get("edge_owner_to_timeline_media", {}).get("edges", [])
            )

        posts = []
        for edge in posts_edges[:9]:
            node = edge.get("node", {})
            caption_edges = node.get("edge_media_to_caption", {}).get("edges", [])
            caption = caption_edges[0]["node"]["text"] if caption_edges else ""
            img_url = node.get("thumbnail_src") or node.get("display_url", "")
            posts.append({"caption": caption[:300], "image_url": img_url})

        # Story highlight titles from page DOM
        highlight_titles = []
        try:
            els = await page.query_selector_all(
                'div[class*="highlight"] span, [data-testid="highlight-reel-title"]'
            )
            for el in els[:10]:
                text = (await el.inner_text()).strip()
                if text and len(text) < 30:
                    highlight_titles.append(text)
            highlight_titles = list(dict.fromkeys(highlight_titles))  # dedupe
        except Exception:
            pass

        # Download images using session cookies
        cookies = await ctx.cookies("https://www.instagram.com")
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        images = await _download_images(base["profile_pic_url"], posts, cookie_header)

        return {**base, "posts": posts, "highlight_titles": highlight_titles, "images": images}

    finally:
        await page.close()


async def _download_images(profile_pic_url: str, posts: list, cookie_header: str) -> list:
    headers = {
        "Cookie": cookie_header,
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://www.instagram.com/",
    }
    urls = []
    if profile_pic_url:
        urls.append(profile_pic_url)
    for post in posts[:6]:
        if post.get("image_url"):
            urls.append(post["image_url"])

    images = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in urls[:7]:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    ct = resp.headers.get("content-type", "image/jpeg")
                    mt = (
                        "image/png" if "png" in ct
                        else ("image/webp" if "webp" in ct else "image/jpeg")
                    )
                    images.append({
                        "data": base64.b64encode(resp.content).decode("utf-8"),
                        "media_type": mt,
                    })
            except Exception:
                pass

    return images
