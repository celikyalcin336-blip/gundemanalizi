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

    # 3. DİĞER SOSYAL MEDYA KANALLARI (Instagram, Facebook, YouTube, TikTok, X)
    # Kullanıcı stratejisi: Sayfa cezası / spam filtresini önlemek ve organik kitleyi korumak için
    # otomatik bot video yüklemeleri devre dışı bırakılmıştır.
    # Video doğrudan Telegram kanalına iletilir; kullanıcı oradan seçerek manuel olarak paylaşır.
    print("\n🛡️ [Sosyal Medya Koruma Modu] Facebook, Instagram, YouTube, TikTok ve X otomatik video yüklemeleri devre dışı.")
    print("📲 Bülten videosu Telegram kanalına eksiksiz iletildi. Manuel paylaşım için Telegram'dan alabilirsiniz.")
    report["platforms"]["instagram"] = {"status": "disabled_by_user", "reason": "Manuel mod aktif"}
    report["platforms"]["facebook"] = {"status": "disabled_by_user", "reason": "Manuel mod aktif"}
    report["platforms"]["youtube"] = {"status": "disabled_by_user", "reason": "Manuel mod aktif"}
    report["platforms"]["tiktok"] = {"status": "disabled_by_user", "reason": "Manuel mod aktif"}
    report["platforms"]["x"] = {"status": "disabled_by_user", "reason": "Manuel mod aktif"}

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
