"""
TikTok Studio Otomatik Video Yükleyici Modülü (@gundemanalizi)
- Playwright + Gerçek Google Chrome + Kalıcı Profil (tiktok_profile)
- Dikey 1080x1920 bülten videosu, başlık ve hashtag optimizasyonu
- Yükleme sonrası çıkan 'Anladım' popup'ını otomatik kapatır ve 'Herkes' (Public) olarak yayınlar.
"""

import os
import sys
import time
from typing import Optional

if sys.stdout and getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(BASE_DIR, "tiktok_profile")

def _dismiss_popups(page):
    """TikTok Studio'daki tanıtım / önizleme ('Anladım' vb.) pencerelerini kapatır."""
    for sel in [
        'button:has-text("Anladım")',
        'button:has-text("Got it")',
        'button:has-text("Tamam")',
        'button:has-text("Kapat")',
        'button:has-text("Skip")',
        '[aria-label="Close"]',
    ]:
        try:
            el = page.locator(sel)
            if el.count():
                el.first.click(force=True, timeout=2000)
                print(f"🛡️ Popup kapatıldı: {sel}")
                page.wait_for_timeout(800)
        except Exception:
            pass

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
        clean_caption += " #GündemAnalizi #GününÖzeti #Haberler #SonDakika #Türkiye"

    try:
        with sync_playwright() as p:
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
                viewport={"width": 1280, "height": 950}
            )

            page = context.pages[0] if context.pages else context.new_page()
            upload_url = "https://www.tiktok.com/creator-center/upload"
            page.goto(upload_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)

            if "login" in page.url.lower():
                context.close()
                return {"status": "error", "error": "TikTok oturumu kapalı görünüyor. Lütfen TIKTOK_GIRIS.bat ile tekrar giriş yapın."}

            _dismiss_popups(page)

            # Dosya seçici input'u bul
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

            # Dosyayı yükle ve yüklemenin tamamlanmasını + 'Anladım' popup'ının çıkmasını bekle
            file_input.set_input_files(video_path)
            print("⏳ Video TikTok'a aktarılıyor (12 sn)...")
            page.wait_for_timeout(12000)

            # Yükleme sonrası çıkan 'Videonuzu telefonunuzda ön izleyin -> Anladım' popup'ını kapat
            _dismiss_popups(page)

            # Başlık / Açıklama editörünü bul ve doldur
            try:
                caption_box = page.locator('div[contenteditable="true"]').first
                if caption_box.count():
                    caption_box.click(force=True, timeout=3000)
                    page.keyboard.press("Control+A")
                    page.keyboard.press("Backspace")
                    page.wait_for_timeout(300)
                    page.keyboard.insert_text(clean_caption[:200])
                    page.wait_for_timeout(800)
                    print("✍️ TikTok açıklaması yazıldı.")
            except Exception as e:
                print(f"⚠️ Açıklama yazma uyarısı: {e}")

            # Sayfayı ve iç konteynerleri aşağı kaydır
            page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight);
                document.querySelectorAll('div').forEach(d => {
                    if (d.scrollHeight > d.clientHeight + 100) {
                        d.scrollTop = d.scrollHeight;
                    }
                });
            }""")
            page.wait_for_timeout(2000)
            _dismiss_popups(page)

            # Gizlilik ayarını 'Herkes' yapmaya çalış (Eğer Sadece ben/sen seçiliyse)
            try:
                priv_trigger = page.locator('button.Select__trigger, div.Select__trigger').first
                if priv_trigger.count():
                    trig_txt = priv_trigger.inner_text().strip()
                    if "Herkes" not in trig_txt and "Everyone" not in trig_txt and "Public" not in trig_txt:
                        priv_trigger.click(force=True)
                        page.wait_for_timeout(600)
                        herkes_opt = page.locator('div[role="option"]:has-text("Herkes"), span:has-text("Herkes")').first
                        if herkes_opt.count():
                            herkes_opt.click(force=True)
                            print("👁️ Gizlilik 'Herkes' olarak değiştirildi.")
                            page.wait_for_timeout(600)
            except Exception as e:
                print(f"⚠️ Gizlilik kontrol uyarısı: {e}")

            # Yayınla / Paylaş / Post butonunu bul
            publish_btn = None
            for _ in range(15):
                _dismiss_popups(page)
                for sel in [
                    'button[data-e2e="post_video_button"]',
                    'button:has-text("Yayınla")',
                    'button:has-text("Paylaş")',
                    'button:has-text("Post")',
                ]:
                    loc = page.locator(sel).first
                    if loc.count():
                        publish_btn = loc
                        break
                if publish_btn:
                    break
                page.wait_for_timeout(2000)

            if publish_btn and publish_btn.count():
                print("🚀 'Paylaş / Yayınla' butonu bulundu, tıklanıyor...")
                publish_btn.click(force=True)
                page.wait_for_timeout(2500)

                # 'Paylaşmaya devam edilsin mi? -> Hemen paylaş' onay penceresi çıkarsa tıkla!
                for confirm_sel in [
                    'button:has-text("Hemen paylaş")',
                    'button:has-text("Şimdi paylaş")',
                    'button:has-text("Post now")',
                    'button:has-text("Continue to post")',
                ]:
                    try:
                        c_btn = page.locator(confirm_sel).first
                        if c_btn.count():
                            c_btn.click(force=True)
                            print(f"🔥 Onay penceresinde '{confirm_sel}' tıklandı!")
                            break
                    except Exception:
                        pass

                page.wait_for_timeout(8000)

                screenshot_path = os.path.join(BASE_DIR, "output", "tiktok_last_publish.png")
                try:
                    page.screenshot(path=screenshot_path)
                except Exception:
                    pass

                context.close()
                print("✅ [TikTok] Video başarıyla yayınlandı!")
                return {"status": "success"}
            else:
                btns = []
                for b in page.locator('button').all():
                    try:
                        t = b.inner_text().strip()
                        if t:
                            btns.append(t)
                    except Exception:
                        pass
                print("Mevcut butonlar:", btns)
                context.close()
                return {"status": "error", "error": f"Yayınla butonu bulunamadı. Butonlar: {btns[:10]}"}

    except Exception as e:
        print(f"❌ TikTok yükleme istisnası: {e}")
        return {"status": "error", "error": str(e)}

if __name__ == "__main__":
    from datetime import datetime
    today_str = datetime.now().strftime("%d.%m.%Y")
    video_file = os.path.join(BASE_DIR, "output", "bulletin_20261029_1334.mp4")
    res = upload_tiktok_video(
        video_path=video_file,
        caption=f"🔴 GÜNÜN ÖZETİ ({today_str}) | 1 Dakikada Türkiye Gündemi! 🌐 gundemanalizi.com.tr"
    )
    print("Sonuç:", res)
