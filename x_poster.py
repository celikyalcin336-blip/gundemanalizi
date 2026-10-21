"""
X (Twitter) Video Paylaşımcısı (@gndmanalizi) - OAuth 1.0a destekli.
"""
import os
import time
import base64
import requests
from requests_oauthlib import OAuth1

_DEF_K = base64.b64decode("M05uNWVaMmlnY1NyMXpJbG9oVUQ0QkhqOQ==").decode("utf-8")
_DEF_S = base64.b64decode("WGd3U3dseEFqdHdXakpDZHV5eVlHUTRpU0loc3lxeWlvSVlCZVpCWXhGVnpmNnJyOFU=").decode("utf-8")
_DEF_AT = base64.b64decode("MjA2MTAyMTg3MDUyMzEwMTE4Ni0wcG9RNm5WWFNzbWRUNFFlMzBXRWRadzFPNXJpZ1I=").decode("utf-8")
_DEF_ATS = base64.b64decode("SGZYOXdWVVU5dE1nWkxQUEZIemxldFR3MGUzR1JLcHh1c1g1YmtCSE1FRnQz").decode("utf-8")

X_API_KEY = os.getenv("X_API_KEY", "").strip() or _DEF_K
X_API_SECRET = os.getenv("X_API_SECRET", "").strip() or _DEF_S
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip() or _DEF_AT
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "").strip() or _DEF_ATS

UPLOAD_V1 = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_URL = "https://api.x.com/2/tweets"
CHUNK = 4 * 1024 * 1024


def is_configured() -> bool:
    return all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET])


def _auth():
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)


def _upload_video(video_path: str) -> str:
    """Videoyu X v1.1 Chunked Upload ile yükler ve media_id döner."""
    auth = _auth()
    total = os.path.getsize(video_path)

    init = requests.post(UPLOAD_V1, auth=auth, data={
        "command": "INIT",
        "total_bytes": str(total),
        "media_type": "video/mp4",
        "media_category": "tweet_video"
    }, timeout=30).json()
    media_id = str(init.get("media_id") or init.get("media_id_string") or "")
    if not media_id:
        raise RuntimeError(f"X upload init hatası: {init}")

    with open(video_path, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            r = requests.post(UPLOAD_V1, auth=auth,
                              data={"command": "APPEND", "media_id": media_id, "segment_index": str(idx)},
                              files={"media": chunk}, timeout=60)
            if r.status_code >= 300:
                raise RuntimeError(f"X upload append hatası: {r.text[:300]}")
            idx += 1

    fin = requests.post(UPLOAD_V1, auth=auth, data={"command": "FINALIZE", "media_id": media_id}, timeout=30).json()
    info = fin.get("processing_info")
    for _ in range(30):
        if not info or info.get("state") == "succeeded":
            break
        if info.get("state") == "failed":
            raise RuntimeError(f"X video işleme hatası: {info}")
        time.sleep(max(2, int(info.get("check_after_secs", 2))))
        st = requests.get(UPLOAD_V1, auth=auth,
                          params={"command": "STATUS", "media_id": media_id}, timeout=20).json()
        info = st.get("processing_info")
    return media_id


def post_video_to_x(video_path: str, title: str, link: str = "") -> dict:
    """Logolu videoyu kısa başlık + site linki ile X'te paylaşır (280 karakter sınırı)."""
    if not is_configured():
        return {"status": "intent_ready"}
    tags = " #sondakika #gündem"
    room = 280 - 24 - len(tags) - 4
    text = title.strip()
    if len(text) > room:
        text = text[:room - 1] + "…"
    text = f"🔴 {text}\n{link}{tags}" if link else f"🔴 {text}{tags}"
    auth = _auth()
    try:
        media_id = _upload_video(video_path)
        r = requests.post(TWEET_URL, auth=auth, json={
            "text": text,
            "media": {"media_ids": [media_id]}
        }, timeout=30)
        data = r.json()
        if r.status_code in (200, 201) and data.get("data", {}).get("id"):
            print(f"✅ X paylaşımı başarılı! Tweet ID: {data['data']['id']}")
            return {"status": "success", "tweet_id": data["data"]["id"]}
        # X 402 Credits Depleted dönerse tek tıkla paylaşımı öner
        print(f"ℹ️ X API yanıtı ({r.status_code}): {data}")
        return {"status": "intent_ready", "error": data}
    except Exception as e:
        print(f"ℹ️ X video paylaşımı uyarısı: {e}")
        return {"status": "intent_ready", "error": str(e)}
