"""
YouTube Shorts Otomatik Yükleme Modülü
- Google YouTube Data API v3 (Resmi ve Ücretsiz)
- Shorts etiketleri ve dikey 9:16 video optimizasyonu
- Kalıcı OAuth2 token (youtube_token.json) ile tek seferlik onaydan sonra 7/24 otonom çalışır.
"""

import os
import sys
import json
import time
from typing import Optional, List

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "youtube_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def get_authenticated_service():
    """Kayıtlı token ile veya ilk seferde tarayıcı onayıyla YouTube API servisini başlatır."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception as e:
            print(f"⚠️ Token yüklenemedi: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 YouTube erişim token'ı yenileniyor...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET_FILE):
                raise FileNotFoundError(f"client_secret.json bulunamadı: {CLIENT_SECRET_FILE}")
            print("\n🔑 YouTube ilk yetkilendirme akışı başlatılıyor...")
            print("👉 Tarayıcınızda açılacak ekranda YouTube kanalınızın bağlı olduğu Google hesabını onaylayın.\n")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w", encoding="utf-8") as token_out:
            token_out.write(creds.to_json())
        print("✅ YouTube token'ı başarıyla kaydedildi!")

    return build("youtube", "v3", credentials=creds)

def upload_shorts(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    privacy_status: str = "public"
) -> dict:
    """
    Dikey MP4 videoyu YouTube kanalına 'Shorts' olarak yükler.
    """
    if not os.path.exists(TOKEN_FILE):
        return {"status": "skipped", "reason": "youtube_token.json bulunamadı"}

    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Video dosyası bulunamadı: {video_path}"}

    # YouTube Shorts kuralı: Başlıkta veya açıklamada #Shorts olmalı
    shorts_title = title.strip()
    if "#Shorts" not in shorts_title and "#shorts" not in shorts_title:
        if len(shorts_title) <= 90:
            shorts_title = f"{shorts_title} #Shorts"

    default_tags = ["Shorts", "Gündem Analizi", "Haberler", "Günün Özeti", "SonDakika", "Türkiye"]
    if tags:
        default_tags.extend(tags)
    clean_tags = list(dict.fromkeys(default_tags))[:15]

    try:
        youtube = get_authenticated_service()

        body = {
            "snippet": {
                "title": shorts_title[:100],
                "description": description[:4500],
                "tags": clean_tags,
                "categoryId": "25"  # 25 = Haber ve Politika (News & Politics)
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 2  # 2 MB chunks
        )

        print(f"🎬 YouTube Shorts yükleniyor: {shorts_title}...")
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"⏳ Yükleniyor: %{int(status.progress() * 100)}")

        video_id = response.get("id")
        video_url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ YouTube Shorts yayında! URL: {video_url}")
        return {
            "status": "success",
            "video_id": video_id,
            "url": video_url
        }
    except Exception as e:
        print(f"❌ YouTube Shorts yükleme hatası: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    test_video = r"C:\Users\celik\Desktop\GUNUN_OZETI_58SN_BULTEN.mp4"
    if os.path.exists(test_video):
        res = upload_shorts(
            video_path=test_video,
            title="1 Dakikada Türkiye Gündemi! Günün Özeti",
            description="Türkiye gündeminde son 24 saatte öne çıkan 6 kritik gelişme tek dakikada!\n\nDetaylar: https://www.gundemanalizi.com.tr\n#Shorts #GündemAnalizi #Haberler"
        )
        print("Sonuç:", res)
    else:
        print("Test videosu bulunamadı.")
