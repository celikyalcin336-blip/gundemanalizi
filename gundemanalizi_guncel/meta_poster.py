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

def post_to_facebook(caption: str, image_path: str) -> dict:
    """
    Facebook Sayfasına görsel ve açıklama metnini yayınlar.
    """
    if config.DRY_RUN:
        print("\n[DRY RUN - FACEBOOK SİMÜLASYONU]")
        print(f"Sayfa ID: {config.FACEBOOK_PAGE_ID or 'Tanımlanmadı (Simülasyon)'}")
        print(f"Görsel Dosyası: {image_path}")
        print(f"Açıklama:\n{caption[:120]}...\n")
        return {"status": "simulated", "post_id": f"fb_mock_{int(time.time())}"}

    if not config.META_PAGE_ACCESS_TOKEN or not config.FACEBOOK_PAGE_ID:
        raise ValueError("META_PAGE_ACCESS_TOKEN veya FACEBOOK_PAGE_ID ayarlanmamış!")

    url = f"https://graph.facebook.com/v21.0/{config.FACEBOOK_PAGE_ID}/photos"
    payload = {
        "caption": caption,
        "access_token": config.META_PAGE_ACCESS_TOKEN
    }

    with open(image_path, "rb") as img_file:
        files = {"source": img_file}
        resp = requests.post(url, data=payload, files=files, timeout=30)
        data = resp.json()

        if resp.status_code == 200 and "id" in data:
            print(f"✅ Facebook paylaşımı başarılı! Post ID: {data.get('post_id', data['id'])}")
            return {"status": "success", "post_id": data.get("post_id", data["id"])}
        else:
            print(f"❌ Facebook paylaşım hatası: {data}")
            return {"status": "error", "error": data}

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

if __name__ == "__main__":
    test_img = os.path.join(os.path.dirname(__file__), "output", "test_card.jpg")
    if os.path.exists(test_img):
        fb_res = post_to_facebook("Test Başlığı - Açıklaması", test_img)
        ig_res = post_to_instagram("Test Başlığı - Açıklaması #gündem", test_img)
        print("Facebook Sonucu:", fb_res)
        print("Instagram Sonucu:", ig_res)
    else:
        print("Önce test_card.jpg oluşturulmalı.")
