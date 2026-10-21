import os
import sys
import time
import requests
import config

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def upload_image_to_imgur(image_path: str) -> str:
    """
    Yerel görseli Imgur'a yükleyerek Instagram API'nin gerektirdiği public HTTPS linki döner.
    IMGUR_CLIENT_ID boşsa basit dosya yükleme servislerini veya doğrudan URL'i dener.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")

    # 1. Imgur API varsa
    if config.IMGUR_CLIENT_ID:
        headers = {"Authorization": f"Client-ID {config.IMGUR_CLIENT_ID}"}
        with open(image_path, "rb") as f:
            resp = requests.post(
                "https://api.imgur.com/3/image",
                headers=headers,
                files={"image": f},
                timeout=20
            )
        data = resp.json()
        if data.get("success"):
            return data["data"]["link"]
        else:
            print(f"Imgur yükleme hatası: {data}")

    # 2. Ücretsiz/Geçici dosya barındırma (tmpfiles.org) fallback
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=15)
            if resp.status_code == 200:
                res = resp.json()
                if "data" in res and "url" in res["data"]:
                    # tmpfiles url'si: https://tmpfiles.org/12345/image.jpg -> doğrudan indirme linki: https://tmpfiles.org/dl/12345/image.jpg
                    raw_url = res["data"]["url"]
                    direct_url = raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    return direct_url
    except Exception as e:
        print(f"Geçici görsel sunucusuna yüklenemedi: {e}")

    return ""

# Son otomatik Facebook paylaşım zamanını takip eder (Anti-Spam & Algoritma Koruması)
_LAST_FB_AUTO_POST_TIME = 0.0
FB_MIN_INTERVAL_SECONDS = int(os.getenv("FB_MIN_INTERVAL_SECONDS", str(3 * 3600)))  # Varsayılan: 3 saatte 1


def _can_auto_post_to_facebook() -> bool:
    """
    Facebook Algoritma & Anti-Spam Kalkanı:
    1. Gece 01:00 - 08:00 (TSİ) arasında otomatik paylaşım yapmaz (gerçek insan editör davranışı).
    2. Otomatik haber kartlarını en sık 3 saatte 1 paylaşır (günde 5-6 kaliteli post),
       böylece sayfa spama düşmez ve organik erişim (keşfet) maksimumda kalır.
    """
    global _LAST_FB_AUTO_POST_TIME
    from datetime import datetime, timezone, timedelta
    tr_now = datetime.now(timezone(timedelta(hours=3)))
    if 1 <= tr_now.hour < 8:
        print(f"🌙 [Facebook Koruma Kalkanı] Gece uyku modu ({tr_now.strftime('%H:%M')}) - Facebook spama düşmesin diye yalnızca Site ve Telegram'a atıldı.")
        return False

    now_ts = time.time()
    if _LAST_FB_AUTO_POST_TIME > 0 and (now_ts - _LAST_FB_AUTO_POST_TIME) < FB_MIN_INTERVAL_SECONDS:
        rem_min = int((FB_MIN_INTERVAL_SECONDS - (now_ts - _LAST_FB_AUTO_POST_TIME)) / 60)
        print(f"🛡️ [Facebook Koruma Kalkanı] Son paylaşımdan bu yana 3 saat geçmedi ({rem_min} dk kaldı). Sadece Site ve Telegram'a atıldı.")
        return False

    return True


def _post_first_comment(object_id: str, news_link: str):
    """
    Facebook algoritmasının dış link içeren gönderilerin erişimini düşürmemesi için
    haber linkini ana metne değil, gönderinin altına İLK YORUM olarak bırakır.
    """
    if not object_id or not news_link:
        return
    try:
        time.sleep(2)
        c_url = f"https://graph.facebook.com/v21.0/{object_id}/comments"
        c_payload = {
            "message": f"📰 Haberin tüm detayları ve gelişmeler için tıklayın:\n👉 {news_link}",
            "access_token": config.META_PAGE_ACCESS_TOKEN
        }
        requests.post(c_url, data=c_payload, timeout=15)
    except Exception:
        pass


def post_to_facebook(caption: str, image_path: str, news_link: str = None, is_manual: bool = False) -> dict:
    """
    Facebook Sayfasına görsel ve açıklama metnini yayınlar.
    - Otomatik paylaşımlarda 3 saat kuralı ve gece uyku modunu uygular.
    - Erişim düşmemesi için linki ana açıklamaya değil, otomatik İLK YORUMA ekler.
    """
    global _LAST_FB_AUTO_POST_TIME
    if not config.META_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        print("\n[FACEBOOK SİMÜLASYONU - Token/Page ID henüz girilmedi]")
        return {"status": "simulated", "post_id": f"fb_mock_{int(time.time())}"}

    if not is_manual and not _can_auto_post_to_facebook():
        return {"status": "skipped_by_shield", "post_id": None}

    url = f"https://graph.facebook.com/v21.0/{config.FACEBOOK_PAGE_ID}/photos"
    payload = {
        "caption": caption,
        "access_token": config.META_PAGE_ACCESS_TOKEN
    }

    try:
        with open(image_path, "rb") as img_file:
            files = {"source": img_file}
            resp = requests.post(url, data=payload, files=files, timeout=35)
            data = resp.json()

            if resp.status_code == 200 and "id" in data:
                post_id = data.get("post_id", data["id"])
                if not is_manual:
                    _LAST_FB_AUTO_POST_TIME = time.time()
                print(f"✅ Facebook fotoğraf paylaşımı başarılı! Post ID: {post_id}")
                if news_link:
                    _post_first_comment(post_id, news_link)
                return {"status": "success", "post_id": post_id}
            else:
                print(f"❌ Facebook paylaşım hatası: {data}")
                return {"status": "error", "error": data}
    except Exception as e:
        print(f"❌ Facebook bağlantı hatası: {e}")
        return {"status": "error", "error": str(e)}


def post_video_to_facebook(video_path: str, caption: str, news_link: str = None) -> dict:
    """
    Facebook Sayfasına doğrudan MP4/Reels video yayınlar ve linki ilk yoruma bırakır.
    """
    if not config.META_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        return {"status": "simulated"}

    url = f"https://graph-video.facebook.com/v21.0/{config.FACEBOOK_PAGE_ID}/videos"
    payload = {
        "description": caption,
        "access_token": config.META_PAGE_ACCESS_TOKEN
    }

    try:
        with open(video_path, "rb") as vf:
            files = {"source": vf}
            resp = requests.post(url, data=payload, files=files, timeout=90)
            data = resp.json()
            if resp.status_code == 200 and "id" in data:
                vid_id = data["id"]
                print(f"✅ Facebook video paylaşımı başarılı! Video ID: {vid_id}")
                if news_link:
                    _post_first_comment(vid_id, news_link)
                return {"status": "success", "video_id": vid_id}
            else:
                print(f"❌ Facebook video hatası: {data}")
                return {"status": "error", "error": data}
    except Exception as e:
        print(f"❌ Facebook video bağlantı hatası: {e}")
        return {"status": "error", "error": str(e)}

def post_to_instagram(caption: str, image_path: str) -> dict:
    """
    Instagram Profesyonel Hesabına görseli 2 adımlı Graph API ile yayınlar:
    1. Container oluşturma (image_url ile)
    2. Container'ı yayınlama (media_publish)
    """
    if config.DRY_RUN:
        print("\n[DRY RUN - INSTAGRAM SİMÜLASYONU]")
        print(f"Instagram Hesap ID: {config.INSTAGRAM_ACCOUNT_ID or 'Tanımlanmadı (Simülasyon)'}")
        print(f"Görsel Dosyası: {image_path}")
        print(f"Açıklama:\n{caption[:120]}...\n")
        return {"status": "simulated", "media_id": f"ig_mock_{int(time.time())}"}

    if not config.META_PAGE_ACCESS_TOKEN or not config.INSTAGRAM_ACCOUNT_ID:
        raise ValueError("META_PAGE_ACCESS_TOKEN veya INSTAGRAM_ACCOUNT_ID ayarlanmamış!")

    # Instagram API yerel dosyayı doğrudan alamaz, internete açık bir HTTPS adresi ister
    image_url = upload_image_to_imgur(image_path)
    if not image_url:
        return {"status": "error", "error": "Instagram için görsel public URL'ye yüklenemedi."}

    # Adım 1: Media Container Oluşturma
    create_url = f"https://graph.facebook.com/v21.0/{config.INSTAGRAM_ACCOUNT_ID}/media"
    create_payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": config.META_PAGE_ACCESS_TOKEN
    }
    create_resp = requests.post(create_url, data=create_payload, timeout=30)
    create_data = create_resp.json()

    if "id" not in create_data:
        print(f"❌ Instagram container oluşturma hatası: {create_data}")
        return {"status": "error", "error": create_data}

    creation_id = create_data["id"]
    time.sleep(3)  # Instagram'ın görseli işlemesi için kısa bir bekleme

    # Adım 2: Yayınlama
    publish_url = f"https://graph.facebook.com/v21.0/{config.INSTAGRAM_ACCOUNT_ID}/media_publish"
    publish_payload = {
        "creation_id": creation_id,
        "access_token": config.META_PAGE_ACCESS_TOKEN
    }
    publish_resp = requests.post(publish_url, data=publish_payload, timeout=30)
    publish_data = publish_resp.json()

    if "id" in publish_data:
        print(f"✅ Instagram paylaşımı başarılı! Media ID: {publish_data['id']}")
        return {"status": "success", "media_id": publish_data["id"]}
    else:
        print(f"❌ Instagram yayınlama hatası: {publish_data}")
        return {"status": "error", "error": publish_data}

def post_reel_to_instagram(video_public_url: str, caption: str) -> dict:
    """
    Instagram Profesyonel hesabına Reels video yayınlar (Meta Graph API - ücretsiz).
    1. REELS container oluşturur (Instagram videoyu bizim sitemizdeki public URL'den kendisi indirir)
    2. Instagram videoyu işleyene kadar bekler (status_code == FINISHED)
    3. Yayınlar (media_publish)
    """
    if not config.META_PAGE_ACCESS_TOKEN or not config.INSTAGRAM_ACCOUNT_ID:
        print("[INSTAGRAM] INSTAGRAM_ACCOUNT_ID henüz tanımlı değil, atlandı.")
        return {"status": "simulated"}

    base = "https://graph.facebook.com/v21.0"
    tok = config.META_PAGE_ACCESS_TOKEN
    try:
        cr = requests.post(f"{base}/{config.INSTAGRAM_ACCOUNT_ID}/media", data={
            "media_type": "REELS",
            "video_url": video_public_url,
            "caption": caption[:2150],
            "share_to_feed": "true",
            "access_token": tok
        }, timeout=30).json()
        if "id" not in cr:
            print(f"❌ Instagram Reels container hatası: {cr}")
            return {"status": "error", "error": cr}

        creation_id = cr["id"]
        # Instagram videoyu indirip işlesin diye en fazla ~3 dakika bekle
        for _ in range(36):
            time.sleep(5)
            st = requests.get(f"{base}/{creation_id}", params={
                "fields": "status_code,status", "access_token": tok
            }, timeout=15).json()
            code = st.get("status_code")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                print(f"❌ Instagram video işleme hatası: {st}")
                return {"status": "error", "error": st}

        pub = requests.post(f"{base}/{config.INSTAGRAM_ACCOUNT_ID}/media_publish", data={
            "creation_id": creation_id, "access_token": tok
        }, timeout=30).json()
        if "id" in pub:
            print(f"✅ Instagram Reels yayınlandı! Media ID: {pub['id']}")
            return {"status": "success", "media_id": pub["id"]}
        print(f"❌ Instagram yayınlama hatası: {pub}")
        return {"status": "error", "error": pub}
    except Exception as e:
        print(f"❌ Instagram bağlantı hatası: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    test_img = os.path.join(os.path.dirname(__file__), "output", "test_card.jpg")
    if os.path.exists(test_img):
        fb_res = post_to_facebook("Test Başlığı - Açıklaması", test_img)
        ig_res = post_to_instagram("Test Başlığı - Açıklaması #gündem", test_img)
        print("Facebook Sonucu:", fb_res)
        print("Instagram Sonucu:", ig_res)
    else:
        print("Önce test_card.jpg oluşturulmalı.")
