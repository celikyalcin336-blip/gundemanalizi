"""
X (Twitter) Video Paylaşımcısı (@gndmanalizi) - OAuth 1.0a ve OAuth 2.0 User Context destekli.
"""
import os
import time
import base64
import requests
from requests_oauthlib import OAuth1

_DEF_K = base64.b64decode("M05uNWVaMmlnY1NyMXpJbG9oVUQ0QkhqOQ==").decode("utf-8")
_DEF_S = base64.b64decode("WGd3U3dseEFqdHdXakpDZHd5eVlHUTRpU0loc3lxeWlvSVlCZVpCWXhGVnpmNnJyOFU=").decode("utf-8")
_DEF_AT = base64.b64decode(
    "Y1dkc1JYaFZTVVJtVTI4MU9FTndibE95ZGxFdFVtSnJheTFyVlRscUxWUnFlazhZY2tOdVdtZHNaV2RIT2pFM09USTFPRGN5TWpJd09ESTZNVG94T21GME9qRQ=="
).decode("utf-8")

X_API_KEY = os.getenv("X_API_KEY", "").strip() or _DEF_K
X_API_SECRET = os.getenv("X_API_SECRET", "").strip() or _DEF_S
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip() or _DEF_AT
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "").strip()

UPLOAD_V2 = "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"
CHUNK = 4 * 1024 * 1024


def is_configured() -> bool:
    return bool(X_ACCESS_TOKEN)


def _req_kwargs():
    """OAuth 1.0a (tireli token) veya OAuth 2.0 User Context Bearer token seçer."""
    if "-" in X_ACCESS_TOKEN and X_API_KEY and X_API_SECRET and X_ACCESS_SECRET:
        return {"auth": OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)}
    return {"headers": {"Authorization": f"Bearer {X_ACCESS_TOKEN}"}}


def _upload_video(video_path: str) -> str:
    """Videoyu X'e parça parça (chunked) yükler ve media_id döner."""
    kw = _req_kwargs()
    total = os.path.getsize(video_path)

    init = requests.post(f"{UPLOAD_V2}/initialize", json={
        "media_type": "video/mp4",
        "total_bytes": total,
        "media_category": "tweet_video"
    }, timeout=30, **kw).json()
    media_id = (init.get("data") or {}).get("id")
    if not media_id:
        raise RuntimeError(f"X upload init hatası: {init}")

    with open(video_path, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            r = requests.post(f"{UPLOAD_V2}/{media_id}/append",
                              data={"segment_index": idx},
                              files={"media": chunk}, timeout=60, **kw)
            if r.status_code >= 300:
                raise RuntimeError(f"X upload append hatası: {r.text[:300]}")
            idx += 1

    fin = requests.post(f"{UPLOAD_V2}/{media_id}/finalize", timeout=30, **kw).json()
    info = (fin.get("data") or {}).get("processing_info")
    for _ in range(30):
        if not info or info.get("state") == "succeeded":
            break
        if info.get("state") == "failed":
            raise RuntimeError(f"X video işleme hatası: {info}")
        time.sleep(max(2, int(info.get("check_after_secs", 3))))
        st = requests.get(UPLOAD_V2,
                          params={"command": "STATUS", "media_id": media_id}, timeout=20, **kw).json()
        info = (st.get("data") or {}).get("processing_info")
    return media_id


def post_video_to_x(video_path: str, title: str, link: str = "") -> dict:
    """Logolu videoyu kısa başlık + site linki ile X'te paylaşır (280 karakter sınırı)."""
    if not is_configured():
        print("[X] API anahtarları tanımlı değil, atlandı.")
        return {"status": "simulated"}
    tags = " #sondakika #gündem"
    room = 280 - 24 - len(tags) - 4
    text = title.strip()
    if len(text) > room:
        text = text[:room - 1] + "…"
    text = f"🔴 {text}\n{link}{tags}" if link else f"🔴 {text}{tags}"
    kw = _req_kwargs()
    try:
        media_id = _upload_video(video_path)
        r = requests.post(TWEET_URL, json={
            "text": text,
            "media": {"media_ids": [str(media_id)]}
        }, timeout=30, **kw)
        data = r.json()
        if r.status_code in (200, 201) and data.get("data", {}).get("id"):
            print(f"✅ X paylaşımı başarılı! Tweet ID: {data['data']['id']}")
            return {"status": "success", "tweet_id": data["data"]["id"]}
        return {"status": "intent_ready", "error": data}
    except Exception as e:
        # Eğer video yükleme paketi (Free tier) kısıtlıysa sadece metin+link tweeti dene
        try:
            r2 = requests.post(TWEET_URL, json={"text": text}, timeout=20, **kw)
            d2 = r2.json()
            if r2.status_code in (200, 201) and d2.get("data", {}).get("id"):
                return {"status": "success", "tweet_id": d2["data"]["id"]}
        except Exception:
            pass
        print(f"ℹ️ X API uyarısı (Panelden Tek Tık Paylaşım aktif): {e}")
        return {"status": "intent_ready", "error": str(e)}
