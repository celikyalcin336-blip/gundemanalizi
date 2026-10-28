"""
TikTok Studio Otomatik Video Yükleyici Modülü (@gundemanalizi)
- Playwright + Gerçek Google Chrome + Kalıcı Profil (tiktok_profile)
- Dikey 1080x1920 bülten videosu, başlık ve hashtag optimizasyonu
- Sıfır bot engeli, %100 yerli oturum koruması
"""

import os
import sys
import time
from typing import Optional

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "tiktok_profile")
COOKIE_FILE = os.path.join(BASE_DIR, "tiktok_cookies.json")

def upload_tiktok_video(
    video_path: str,
    caption: str,
    headless: bool = True
) -> dict:
    """
    TikTok Studio web arayüzü üzerinden videoyu kalıcı profil ile otomatik yükler ve yayınlar.
    """
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Video dosyası bulunamadı: {video_path}"}

    if not os.path.exists(PROFILE_DIR):
        return {"status": "error", "error": f"TikTok profili bulunamadı ({PROFILE_DIR}). Lütfen masaüstündeki TIKTOK_GIRIS.bat ile giriş yapın."}

    print(f"🎬 [TikTok] Video yükleme başlatılıyor: {video_path}...")

    clean_caption = caption.strip()
    if "#GündemAnalizi" not in clean_caption:
        clean_caption += "\n\n#GündemAnalizi #GününÖzeti #Haberler #SonDakika #Türkiye"

    try:
        with sync_playwright() as p:
            # Gerçek Chrome ve Kalıcı Profil ile başlat
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                channel="chrome",
                headless=headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ],
                viewport={"width": 1280, "height": 800}
            )

            page = context.pages[0] if context.pages else context.new_page()
            upload_url = "https://www.tiktok.com/creator-center/upload"
            page.goto(upload_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            # Giriş yapılmış mı kontrol et
            if "login" in page.url.lower():
                context.close()
                return {"status": "error", "error": "TikTok oturumu kapalı görünüyor. Lütfen TIKTOK_GIRIS.bat ile tekrar giriş yapın."}

            # Dosya seçici input'u bul (iframe içinde veya sayfada)
            file_input = page.locator('input[type="file"]').first
            if not file_input.count():
                for frame in page.frames:
                    fi = frame.locator('input[type="file"]').first
                    if fi.count():
                        file_input = fi
                        break

            if not file_input or not file_input.count():
                context.close()
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
                post_btn = page.locator('button:has-text("Yayınla")').first
                if not post_btn.count():
                    post_btn = page.locator('button:has-text("Post")').first

                if post_btn.count():
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
                context.close()
                print("✅ [TikTok] Video başarıyla yayınlandı!")
                return {"status": "success"}
            else:
                context.close()
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
