"""
TikTok Oturum Kaydedici (One-Time Login Assistant)
- Görünür bir Chromium penceresi açar.
- Kullanıcı TikTok hesabına (QR kod veya şifre ile) giriş yapar.
- Giriş yapıldığı an çerezleri tiktok_cookies.json dosyasına kaydeder.
"""

import os
import sys
import json
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIE_FILE = os.path.join(BASE_DIR, "tiktok_cookies.json")

def capture_tiktok_session():
    print("🚀 TikTok Oturum Yardımcısı başlatılıyor...")
    print("👉 Açılan pencerede TikTok (@gundemanalizi) hesabınıza giriş yapın (QR kod en hızlısıdır).")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # Kullanıcının görebilmesi için açık pencere
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            viewport=None,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com/login", timeout=60000)

        print("\n⏳ Giriş yapmanız bekleniyor (QR kod veya şifre ile giriş yapın)...")

        # Giriş yapılıp yapılmadığını periyodik kontrol et (maksimum 5 dakika bekle)
        logged_in = False
        for _ in range(150):  # 150 * 2sn = 300sn (5 dakika)
            time.sleep(2)
            cookies = context.cookies()
            # sessionid çerezi giriş yapıldığında oluşur
            has_session = any(c.get("name") in ("sessionid", "sessionid_ss") and c.get("value") for c in cookies)
            
            # Veya URL kontrolü
            current_url = page.url
            if has_session or "login" not in current_url.lower():
                # Doğrulamak için upload sayfasına bak
                if has_session:
                    logged_in = True
                    break

        if logged_in:
            print("\n🎉 GİRİŞ BAŞARILI! Çerezler kaydediliyor...")
            cookies = context.cookies()
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"✅ Çerezler kaydedildi: {COOKIE_FILE}")
            time.sleep(2)
            browser.close()
            return True
        else:
            print("\n⚠️ Süre doldu, giriş algılanamadı.")
            browser.close()
            return False

if __name__ == "__main__":
    capture_tiktok_session()
