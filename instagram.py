import os
import base64
import httpx
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_client = None


def _create_fresh_client():
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 5]
    return cl


def get_client():
    global _client

    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")
    session_file = os.getenv("SESSION_FILE", "session.json")

    if not username or not password:
        raise ValueError("Credenziali Instagram non configurate. Apri le impostazioni.")

    if _client is None:
        cl = _create_fresh_client()

        if Path(session_file).exists():
            try:
                cl.load_settings(session_file)
                cl.login(username, password)
                _client = cl
            except Exception:
                cl = _create_fresh_client()
                cl.login(username, password)
                cl.dump_settings(session_file)
                _client = cl
        else:
            cl.login(username, password)
            cl.dump_settings(session_file)
            _client = cl

    return _client


def _url_to_base64(url: str) -> Optional[str]:
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "image/jpeg")
                if "png" in ct:
                    media_type = "image/png"
                elif "webp" in ct:
                    media_type = "image/webp"
                else:
                    media_type = "image/jpeg"
                return base64.b64encode(resp.content).decode("utf-8"), media_type
    except Exception:
        pass
    return None, None


def get_profile_data(username: str) -> dict:
    from instagrapi.exceptions import UserNotFound, LoginRequired

    cl = get_client()

    try:
        user = cl.user_info_by_username(username)
    except UserNotFound:
        raise ValueError(f"Utente @{username} non trovato")
    except LoginRequired:
        global _client
        _client = None
        cl = get_client()
        user = cl.user_info_by_username(username)

    base = {
        "username": username,
        "full_name": user.full_name or "",
        "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None,
        "follower_count": user.follower_count or 0,
        "following_count": user.following_count or 0,
        "media_count": user.media_count or 0,
        "is_private": user.is_private,
    }

    if user.is_private:
        return base

    posts = []
    try:
        medias = cl.user_medias(user.pk, amount=9)
        for media in medias:
            img_url = None
            if media.media_type == 1 and media.thumbnail_url:
                img_url = str(media.thumbnail_url)
            elif media.media_type == 2 and media.thumbnail_url:
                img_url = str(media.thumbnail_url)
            elif media.media_type == 8 and media.resources:
                img_url = str(media.resources[0].thumbnail_url)

            posts.append({
                "caption": (media.caption_text or "")[:300],
                "image_url": img_url,
            })
    except Exception:
        pass

    highlight_titles = []
    try:
        highlights = cl.user_highlights(user.pk)
        highlight_titles = [h.title for h in highlights]
    except Exception:
        pass

    # Download images for Claude vision
    images = []  # list of {"data": base64str, "media_type": "image/jpeg"}

    if user.profile_pic_url:
        data, mt = _url_to_base64(str(user.profile_pic_url))
        if data:
            images.append({"data": data, "media_type": mt})

    for post in posts:
        if post.get("image_url") and len(images) < 7:
            data, mt = _url_to_base64(post["image_url"])
            if data:
                images.append({"data": data, "media_type": mt})

    return {
        **base,
        "biography": user.biography or "",
        "posts": posts,
        "highlight_titles": highlight_titles,
        "images": images,
    }
