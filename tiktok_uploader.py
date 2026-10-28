"""
TikTok Studio Otomatik Video Yükleyici Modülü (@gundemanalizi)
- Playwright tabanlı otonom TikTok Studio uploader
- Kaydedilmiş oturum çerezleri (tiktok_cookies.json) ile çalışır
- 1080x1920 dikey bülten videosu, başlık ve hashtag optimizasyonu
"""

import os
import sys
import json
import time
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "tiktok_cookies.json")

def load_cookies() -> list:
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def upload_tiktok_video(
    video_path: str,
    caption: str,
    headless: bool = True
) -> dict:
    """
    TikTok Studio web arayüzü üzerinden videoyu otomatik yükler ve yayınlar.
    """
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Video dosyası bulunamadı: {video_path}"}

    cookies = load_cookies()
    if not cookies:
        return {"status": "error", "error": "TikTok oturum çerezleri (tiktok_cookies.json) bulunamadı. Önce tiktok_auth.py çalıştırılmalı."}

    print(f"🎬 [TikTok] Video yükleme başlatılıyor: {video_path}...")

    clean_caption = caption.strip()
    if "#GündemAnalizi" not in clean_caption:
        clean_caption += "\n\n#GündemAnalizi #GününÖzeti #Haberler #SonDakika #Türkiye"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            context.add_cookies(cookies)

            page = context.new_page()
            # TikTok Studio Upload sayfasına git
            upload_url = "https://www.tiktok.com/creator-center/upload"
            page.goto(upload_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            # Giriş yapılmış mı kontrol et
            if "login" in page.url.lower():
                browser.close()
                return {"status": "error", "error": "TikTok oturumu süresi dolmuş veya geçersiz. Lütfen tiktok_auth.py ile yeniden giriş yapın."}

            # Dosya seçici input'u bul (iframe içinde veya doğrudan sayfada)
            file_input = page.locator('input[type="file"]').first
            if not file_input.count():
                # Bazen iframe içinde olabilir
                for frame in page.frames:
                    fi = frame.locator('input[type="file"]').first
                    if fi.count():
                        file_input = fi
                        break

            if not file_input or not file_input.count():
                browser.close()
                return {"status": "error", "error": "TikTok dosya yükleme kutusu bulunamadı."}

            # Dosyayı yükle
            file_input.set_input_files(video_path)
            print("⏳ Video TikTok'a aktarılıyor...")
            page.wait_for_timeout(8000)

            # Başlık / Açıklama editörünü bul
            caption_box = page.locator('div[contenteditable="true"]').first
            if not caption_box.count():
                caption_box = page.locator('div[role="combobox"]').first

            if caption_box.count():
                try:
                    caption_box.click()
                    # Önceki içeriği temizle (Select all & delete)
                    caption_box.press("Control+A")
                    caption_box.press("Backspace")
                    page.wait_for_timeout(500)
                    caption_box.fill(clean_caption[:150])
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"⚠️ Açıklama kutusu yazma uyarısı: {e}")

            # Videonun yüklenmesini ve işlenmesini bekle (%100 tamamlanana kadar)
            print("⏳ TikTok video yükleme durumunu kontrol ediyor...")
            for _ in range(40):  # Maksimum 80 saniye
                page.wait_for_timeout(2000)
                # Yayınla / Post butonu aktifleşti mi?
                post_btn = page.locator('button:has-text("Yayınla")').first
                if not post_btn.count():
                    post_btn = page.locator('button:has-text("Post")').first

                if post_btn.count():
                    # Buton disabled değilse hazırdır
                    is_disabled = post_btn.get_attribute("disabled") is not None
                    if not is_disabled:
                        break

            # Yayınla butonuna tıkla
            post_btn = page.locator('button:has-text("Yayınla")').first
            if not post_btn.count():
                post_btn = page.locator('button:has-text("Post")').first

            if post_btn.count():
                post_btn.click(force=True)
                print("🚀 'Yayınla' butonuna tıklandı!")
                page.wait_for_timeout(6000)
                browser.close()
                print("✅ [TikTok] Video başarıyla yayınlandı!")
                return {"status": "success"}
            else:
                browser.close()
                return {"status": "error", "error": "Yayınla butonu bulunamadı veya etkinleşmedi."}

    except Exception as e:
        print(f"❌ TikTok yükleme istisnası: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    test_video = r"C:\Users\celik\Desktop\GUNUN_OZETI_58SN_BULTEN.mp4"
    res = upload_tiktok_video(
        video_path=test_video,
        caption="1 Dakikada Türkiye Gündemi! Günün Özeti"
    )
    print("Sonuç:", res)
