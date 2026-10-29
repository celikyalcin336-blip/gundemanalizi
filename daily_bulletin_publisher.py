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

if sys.stdout and getattr(sys.stdout, 'encoding', '') != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

import config
import telegram_notifier
import meta_poster
import youtube_uploader
import tiktok_uploader
import x_poster
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
    stories = []
    if not video_path or not os.path.exists(video_path):
        print("🎬 1/4 - Video motoru tetikleniyor (taze haberlerle sıfırdan render)...")
        video_path, stories = daily_bulletin_engine.render_bulletin_video()
    else:
        print(f"🎬 1/4 - Belirtilen video kullanılıyor: {video_path}")

    report["video_path"] = video_path

    # Dinamik başlık listesi (Asla eski haberleri tekrar paylaşma)
    num_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
    if stories:
        story_lines = []
        for idx, s in enumerate(stories[:6]):
            emoji = num_emojis[idx] if idx < len(num_emojis) else f"{idx+1}️⃣"
            cat = s.get("category", "").upper()
            hl = s.get("headline", "")
            story_lines.append(f"{emoji} {cat}: {hl}")
        story_text = "\n".join(story_lines)
    else:
        story_text = (
            "1️⃣ GÜNDEM | 2️⃣ EKONOMİ | 3️⃣ DÜNYA\n"
            "4️⃣ SAĞLIK | 5️⃣ TEKNOLOJİ | 6️⃣ SPOR"
        )

    caption = (
        f"🔴 GÜNÜN ÖZETİ ({today_str})\n"
        f"Türkiye gündeminde son 24 saatte öne çıkan 6 kritik gelişme tek dakikada!\n\n"
        f"{story_text}\n\n"
        f"🌐 Tüm detaylar ve tarafsız analizler: https://gundemanalizi.com.tr\n"
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
    print("\n🎬 5/6 - YouTube Shorts Kanalına Yükleniyor...")
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

    # Platformlar arası 3 saniye nefes payı
    time.sleep(3)

    # 6. ADIM: TIKTOK
    print("\n🎵 6/7 - TikTok Kanalına Yükleniyor...")
    try:
        tt_res = tiktok_uploader.upload_tiktok_video(
            video_path=video_path,
            caption=f"1 Dakikada Türkiye Gündemi! ({today_str}) #GününÖzeti",
            headless=True
        )
        report["platforms"]["tiktok"] = tt_res
        if tt_res.get("status") == "success":
            print("✅ TikTok video paylaşımı başarılı!")
        else:
            print(f"⚠️ TikTok sonucu: {tt_res}")
    except Exception as e:
        print(f"❌ TikTok istisnası: {e}")
        report["platforms"]["tiktok"] = {"status": "error", "error": str(e)}

    # Platformlar arası 3 saniye nefes payı
    time.sleep(3)

    # 7. ADIM: TWITTER / X
    print("\n🐦 7/7 - Twitter / X (@gndmanalizi) Video Paylaşılıyor...")
    try:
        if stories:
            x_items = [f"{num_emojis[idx]} {s.get('category','').upper()}" for idx, s in enumerate(stories[:6])]
            x_cat_lines = " | ".join(x_items[:3]) + "\n" + " | ".join(x_items[3:6])
        else:
            x_cat_lines = "1️⃣ EKONOMİ | 2️⃣ SAĞLIK | 3️⃣ SPOR\n4️⃣ EĞİTİM | 5️⃣ OTOMOBİL | 6️⃣ TEKNOLOJİ"

        x_tweet_text = (
            f"🔴 GÜNÜN ÖZETİ ({today_str})\n"
            f"Türkiye gündeminde son 24 saatte öne çıkan 6 kritik gelişme tek dakikada!\n\n"
            f"{x_cat_lines}\n\n"
            f"🌐 Detaylar: https://gundemanalizi.com.tr\n"
            f"#GündemAnalizi #GününÖzeti #Haberler #SonDakika"
        )
        x_res = x_poster.post_tweet_playwright(text=x_tweet_text, media_path=video_path)
        report["platforms"]["x"] = x_res
        if x_res.get("status") == "success":
            print("✅ Twitter / X video paylaşımı başarılı!")
        else:
            print(f"⚠️ Twitter / X sonucu: {x_res}")
    except Exception as e:
        print(f"❌ Twitter / X istisnası: {e}")
        report["platforms"]["x"] = {"status": "error", "error": str(e)}

    append_log(report)
    print("\n🎉 [TAMAMLANDI] Dağıtım özeti kaydedildi.")
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gündem Analizi Günlük Bülten Dağıtıcı")
    parser.add_argument("--video", type=str, default=None, help="Özel bir video yolu vermek için (varsayılan: taze render)")
    args = parser.parse_args()

    # Altın kural: Asla eski bülten videosu varsayılan olarak paylaşılmaz, her zaman taze haberlerle sıfırdan render edilir!
    if args.video and os.path.exists(args.video):
        print(f"🎬 Manuel video belirtildi: {args.video}")
        run_bulletin_cycle(video_path=args.video)
    else:
        print("🎬 Otomatik mod: Canlı ve taze haberlerle bülten sıfırdan üretilip dağıtılacak...")
        run_bulletin_cycle(video_path=None)
