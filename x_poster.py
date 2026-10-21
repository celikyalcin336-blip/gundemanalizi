"""
X (Twitter) Video Paylaşımcısı - Ücretsiz (Free) API paketi ile çalışır.
Gerekli Render Environment değişkenleri:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
"""
import os
import time
import requests
from requests_oauthlib import OAuth1

X_API_KEY = os.getenv("X_API_KEY", "")
X_API_SECRET = os.getenv("X_API_SECRET", "")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET", "")

UPLOAD_V2 = "https://api.x.com/2/media/upload"
TWEET_URL = "https://api.x.com/2/tweets"
CHUNK = 4 * 1024 * 1024


def is_configured() -> bool:
    return all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET])


def _auth():
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)


def _upload_video(video_path: str) -> str:
    """Videoyu X'e parça parça (chunked) yükler ve media_id döner."""
    auth = _auth()
    total = os.path.getsize(video_path)

    init = requests.post(f"{UPLOAD_V2}/initialize", auth=auth, json={
        "media_type": "video/mp4",
        "total_bytes": total,
        "media_category": "tweet_video"
    }, timeout=30).json()
    media_id = (init.get("data") or {}).get("id")
    if not media_id:
        raise RuntimeError(f"X upload init hatası: {init}")

    with open(video_path, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            r = requests.post(f"{UPLOAD_V2}/{media_id}/append", auth=auth,
                              data={"segment_index": idx},
                              files={"media": chunk}, timeout=60)
            if r.status_code >= 300:
                raise RuntimeError(f"X upload append hatası: {r.text[:300]}")
            idx += 1

    fin = requests.post(f"{UPLOAD_V2}/{media_id}/finalize", auth=auth, timeout=30).json()
    info = (fin.get("data") or {}).get("processing_info")
    # X videoyu işleyene kadar bekle
    for _ in range(30):
        if not info or info.get("state") == "succeeded":
            break
        if info.get("state") == "failed":
            raise RuntimeError(f"X video işleme hatası: {info}")
        time.sleep(max(2, int(info.get("check_after_secs", 3))))
        st = requests.get(UPLOAD_V2, auth=auth,
                          params={"command": "STATUS", "media_id": media_id}, timeout=20).json()
        info = (st.get("data") or {}).get("processing_info")
    return media_id


def post_video_to_x(video_path: str, title: str, link: str = "") -> dict:
    """Logolu videoyu kısa başlık + site linki ile X'te paylaşır (280 karakter sınırı)."""
    if not is_configured():
        print("[X] API anahtarları tanımlı değil, atlandı.")
        return {"status": "simulated"}
    try:
        media_id = _upload_video(video_path)
        tags = " #sondakika #gündem"
        room = 280 - 24 - len(tags) - 4  # link X'te 23 karakter sayılır
        text = title.strip()
        if len(text) > room:
            text = text[:room - 1] + "…"
        text = f"🔴 {text}\n{link}{tags}" if link else f"🔴 {text}{tags}"

        r = requests.post(TWEET_URL, auth=_auth(), json={
            "text": text,
            "media": {"media_ids": [str(media_id)]}
        }, timeout=30)
        data = r.json()
        if r.status_code in (200, 201) and data.get("data", {}).get("id"):
            print(f"✅ X paylaşımı başarılı! Tweet ID: {data['data']['id']}")
            return {"status": "success", "tweet_id": data["data"]["id"]}
        print(f"❌ X paylaşım hatası: {data}")
        return {"status": "error", "error": data}
    except Exception as e:
        print(f"❌ X bağlantı hatası: {e}")
        return {"status": "error", "error": str(e)}
