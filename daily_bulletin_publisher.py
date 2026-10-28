"""
Gündem Analizi - 6 Kanallı Günlük Bülten Otomasyon Dağıtıcısı
Hedef Platformlar:
1. Telegram Kanalı (@gundemanalizi)
2. Instagram Reels (@gundem_analiz)
3. Facebook Reels & Video (Gündem analizi)
(YouTube Shorts, TikTok ve Twitter aşamalı olarak eklenecektir)

Güvenlik ve İzolasyon:
- Sıfır veritabanı riski.
- Platformlar birbirinden bağımsız çalışır (Biri aksasa diğeri etkilenmez).
- Detaylı yayın raporu (bulletin_publish_log.json) tutar.
"""

import os
import sys
import time
import json
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
import telegram_notifier
import meta_poster
import youtube_uploader
import daily_bulletin_engine

LOG_FILE = os.path.join(BASE_DIR, "bulletin_publish_log.json")

def load_logs() -> list:
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def append_log(entry: dict):
    logs = load_logs()
    logs.append(entry)
    # Son 100 kaydı sakla
    logs = logs[-100:]
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Log kaydedilemedi: {e}")

def run_bulletin_cycle(video_path: str = None) -> dict:
    """
    Günlük bülteni hazırlar ve aktif platformlara sırayla dağıtır.
    """
    today_str = datetime.now().strftime("%d.%m.%Y")
    now_time_str = datetime.now().strftime("%H:%M")
    report = {
        "timestamp": time.time(),
        "date": today_str,
        "time": now_time_str,
        "video_path": None,
        "platforms": {}
    }

    print(f"\n========================================================")
    print(f"🚀 [GÜNDEM ANALİZİ] Günlük Bülten Dağıtım Döngüsü Başladı ({today_str} {now_time_str})")
    print(f"========================================================\n")

    # 1. ADIM: Video Hazırlığı (Yoksa Renderla)
    if not video_path or not os.path.exists(video_path):
        print("🎬 1/4 - Video motoru tetikleniyor...")
        video_path = daily_bulletin_engine.render_bulletin_video()
    else:
        print(f"🎬 1/4 - Mevcut video kullanılıyor: {video_path}")

    report["video_path"] = video_path

    caption = (
        f"🔴 GÜNÜN ÖZETİ ({today_str})\n"
        f"Türkiye gündeminde son 24 saatte öne çıkan 6 kritik gelişme tek dakikada!\n\n"
        f"1️⃣ Ekonomi: Kasım İndirimlerine Sıkı Denetim\n"
        f"2️⃣ Sağlık: Yerli Kalp-Akciğer Cihazı\n"
        f"3️⃣ Spor: Zirve Yarışında Sıcak Kararlar\n"
        f"4️⃣ Eğitim: 2027 YKS Sınav Takvimi\n"
        f"5️⃣ Otomobil: Togg'dan 126 Bin Araç Rekoru\n"
        f"6️⃣ Teknoloji: Huawei Pura 90 Plus\n\n"
        f"🌐 Tüm detaylar ve tarafsız analizler: www.gundemanalizi.com.tr\n"
        f"#GündemAnalizi #GününÖzeti #Haberler #SonDakika #Türkiye #Ekonomi #Teknoloji #Otomobil"
    )

    # 2. ADIM: TELEGRAM KANALI
    print("\n📢 2/4 - Telegram Kanalına Gönderiliyor...")
    try:
        tg_ok = telegram_notifier.send_telegram_video(
            video_path=video_path,
            caption=caption,
            news_link="https://xn--gndemanalizi-dlb.com.tr"
        )
        report["platforms"]["telegram"] = {"status": "success" if tg_ok else "failed"}
        if tg_ok:
            print("✅ Telegram paylaşımı tamamlandı!")
        else:
            print("⚠️ Telegram gönderimi başarısız oldu.")
    except Exception as e:
        print(f"❌ Telegram istisnası: {e}")
        report["platforms"]["telegram"] = {"status": "error", "error": str(e)}

    # Platformlar arası 3 saniye nefes payı
    time.sleep(3)

    # 3. ADIM: INSTAGRAM REELS
    print("\n📸 3/4 - Instagram (@gundem_analiz) Reels Olarak Yayınlanıyor...")
    try:
        ig_res = meta_poster.post_reel_to_instagram(
            video_path_or_url=video_path,
            caption=caption
        )
        report["platforms"]["instagram"] = ig_res
        if ig_res.get("status") == "success":
            print(f"✅ Instagram Reels başarıyla yayında! (Media ID: {ig_res.get('media_id')})")
        else:
            print(f"⚠️ Instagram sonucu: {ig_res}")
    except Exception as e:
        print(f"❌ Instagram istisnası: {e}")
        report["platforms"]["instagram"] = {"status": "error", "error": str(e)}

    # Platformlar arası 3 saniye nefes payı
    time.sleep(3)

    # 4. ADIM: FACEBOOK REELS & VİDEO
    print("\n📘 4/5 - Facebook Sayfasına Video/Reels Olarak Yayınlanıyor...")
    try:
        fb_res = meta_poster.post_video_to_facebook(
            video_path=video_path,
            caption=caption,
            news_link="https://xn--gndemanalizi-dlb.com.tr"
        )
        report["platforms"]["facebook"] = fb_res
        if fb_res.get("status") == "success":
            print(f"✅ Facebook video paylaşımı başarılı! (Video ID: {fb_res.get('video_id')})")
        else:
            print(f"⚠️ Facebook sonucu: {fb_res}")
    except Exception as e:
        print(f"❌ Facebook istisnası: {e}")
        report["platforms"]["facebook"] = {"status": "error", "error": str(e)}

    # Platformlar arası 3 saniye nefes payı
    time.sleep(3)

    # 5. ADIM: YOUTUBE SHORTS
    print("\n🎬 5/5 - YouTube Shorts Kanalına Yükleniyor...")
    try:
        yt_res = youtube_uploader.upload_shorts(
            video_path=video_path,
            title=f"1 Dakikada Türkiye Gündemi! ({today_str}) #Shorts",
            description=caption
        )
        report["platforms"]["youtube"] = yt_res
        if yt_res.get("status") == "success":
            print(f"✅ YouTube Shorts yayında! URL: {yt_res.get('url')}")
        else:
            print(f"⚠️ YouTube sonucu: {yt_res}")
    except Exception as e:
        print(f"❌ YouTube Shorts istisnası: {e}")
        report["platforms"]["youtube"] = {"status": "error", "error": str(e)}

    append_log(report)
    print("\n🎉 [TAMAMLANDI] Dağıtım özeti kaydedildi.")
    return report

if __name__ == "__main__":
    # Test için daha önce masaüstüne çıkardığımız onaylı videoyu verebiliriz
    custom_video = r"C:\Users\celik\Desktop\GUNUN_OZETI_58SN_BULTEN.mp4"
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        custom_video = sys.argv[1]
    
    if os.path.exists(custom_video):
        print(f"Test için masaüstündeki video kullanılıyor: {custom_video}")
        run_bulletin_cycle(video_path=custom_video)
    else:
        run_bulletin_cycle()
