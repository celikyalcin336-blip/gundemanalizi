import os
import json
import time
import requests
from typing import Optional

_cached_access_token = None
_token_expiry = 0

def get_credentials() -> Optional[dict]:
    """Google Indexing API kimlik bilgilerini env veya dosyadan yukler."""
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
            # 50 dakika boyunca onbellekte tut (Google token omru 60 dakikadir)
            _token_expiry = now + int(data.get("expires_in", 3600)) - 600
            return _cached_access_token
        else:
            print(f"[!] [Google Indexer] Token yenilenemedi ({resp.status_code}): {resp.text[:100]}")
    except Exception as e:
        print(f"[!] [Google Indexer] Token baglanti hatasi: {e}")

    return None

def notify_google_indexing(url: str) -> bool:
    """
    Google Indexing API'ye 'URL_UPDATED' bildirimi gonderir.
    Googlebot bu bildirim sonrasinda sayfayi 1-3 dakika icinde taramaya gelir.
    Sifir risk: Tum hatalar yakalanir, sitenin calismasina asla zarar vermez.
    """
    if not url or not url.startswith("http"):
        return False

    token = get_access_token()
    if not token:
        # Anahtar henuz yapilandirilmadiysa sessizce gec
        return False

    try:
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "type": "URL_UPDATED"
        }
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f" [Google Indexing API] Bildirim basariyla iletildi: {url}")
            return True
        else:
            print(f"[!] [Google Indexing API] Bildirim yaniti ({resp.status_code}): {resp.text[:120]}")
            return False
    except Exception as e:
        print(f"[!] [Google Indexing API] Istek hatasi (guvenli atlandi): {e}")
        return False

if __name__ == "__main__":
    test_url = "https://xn--gndemanalizi-dlb.com.tr/"
    print(f"Testing Google Indexing API with: {test_url}")
    success = notify_google_indexing(test_url)
    print(f"Result: {success}")
