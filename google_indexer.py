import os
import json
import time
import base64
import requests
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from typing import Optional

_cached_access_token = None
_token_expiry = 0

_DEFAULT_B64_CREDS = (
    "eyJjbGllbnRfaWQiOiAiMzA4ODM4NDExMzY0LXU3NXE2Mm91bG9qcTYxNDdtYm00cTNwODk5ZjNpODlhLmFwcHMuZ29vZ2xldXNlcmNvbnRlbnQuY29tIiwg"
    "ImNsaWVudF9zZWNyZXQiOiAiR09DU1BYLThzdWpSTkdiY2RPc3FOdUhkS0Nfam9hZS1fQ2giLCAicmVmcmVzaF90b2tlbiI6ICIxLy8wM1NDc0JGZ1Zuak50"
    "Q2dZSUFSQUFHQU1TTndGLUw5SXJQZ0tCSWVEeXBFeW1uZFFOeWVQdlp1dEUxNTVEMVpHdmszb0VmT25vd0VBSF9oRHRUdUttYW1qZDZacXdNUG9lZzRrIn0="
)

def get_credentials() -> Optional[dict]:
    """Google Indexing API kimlik bilgilerini env, dosya veya kalici cloud yedeğinden yukler."""
    env_token = os.getenv("GOOGLE_INDEXING_TOKEN", "").strip()
    if env_token:
        try:
            return json.loads(env_token)
        except Exception:
            pass

    token_file = os.path.join(os.path.dirname(__file__), "google_indexing_token.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    try:
        return json.loads(base64.b64decode(_DEFAULT_B64_CREDS).decode("utf-8"))
    except Exception:
        return None

def get_access_token() -> Optional[str]:
    """Gerektiginde kalici refresh_token kullanarak 1 saatlik taze access_token uretir."""
    global _cached_access_token, _token_expiry
    now = time.time()
    if _cached_access_token and now < _token_expiry:
        return _cached_access_token

    creds = get_credentials()
    if not creds:
        return None

    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    refresh_token = creds.get("refresh_token")

    if not (client_id and client_secret and refresh_token):
        return None

    try:
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            _cached_access_token = data.get("access_token")
            # 55 dakika boyunca onbellekte tut (Google access token 1 saat gecerlidir)
            _token_expiry = now + 3300
            return _cached_access_token
        else:
            print(f"⚠️ [Google Indexing] Token yenileme basarisiz ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"⚠️ [Google Indexing] Token istegi hatasi: {e}")

    return None

def notify_google_indexing(url: str, action: str = "URL_UPDATED") -> bool:
    """
    Google Indexing API'ye anlik indeksleme cagrisi gonderir.
    action: URL_UPDATED veya URL_DELETED
    """
    access_token = get_access_token()
    if not access_token:
        print(f"⚠️ [Google Indexing API] Token alinamadigi icin atlandi: {url}")
        return False

    api_endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "url": url,
        "type": action
    }

    try:
        resp = requests.post(api_endpoint, headers=headers, json=payload, timeout=12)
        if resp.status_code in (200, 201):
            print(f"🚀 [Google Indexing API] Bildirim basariyla iletildi: {url}")
            return True
        else:
            print(f"⚠️ [Google Indexing API] Yanit ({resp.status_code}): {resp.text}")
            return False
    except Exception as e:
        print(f"⚠️ [Google Indexing API] Baglanti hatasi: {e}")
        return False

if __name__ == "__main__":
    test_url = "https://xn--gndemanalizi-dlb.com.tr/"
    print(f"Testing Google Indexing API with: {test_url}")
    res = notify_google_indexing(test_url)
    print(f"Result: {res}")
