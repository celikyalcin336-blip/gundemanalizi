"""
Gündem Analizi - Viral Video Radarı (Video Scout)
X (Twitter) ve Telegram üzerindeki yeni, özgün, logosuz sokak, asayiş ve trafik videolarını
otomatik tarar ve doğrudan Yalçın Bey'in şahsi Telegram'ına bildirir.
"""
import os
import sys
import time
import json
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from typing import List, Dict

import config
import telegram_notifier

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "scout_cache.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_scout_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS seen_videos (
            url_hash TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def is_seen(url: str) -> bool:
    import hashlib
    h = hashlib.md5(url.strip().encode("utf-8")).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM seen_videos WHERE url_hash = ?", (h,))
    row = c.fetchone()
    conn.close()
    return bool(row)


def mark_seen(url: str, title: str = "", source: str = ""):
    import hashlib
    h = hashlib.md5(url.strip().encode("utf-8")).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO seen_videos (url_hash, url, title, source) VALUES (?, ?, ?, ?)",
              (h, url, title, source))
    conn.commit()
    conn.close()


def verify_x_video_with_ytdlp(x_url: str) -> dict:
    """yt-dlp ile X tweet'inde video olup olmadığını ve süresini doğrular."""
    import subprocess
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
        x_url
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            dur = data.get("duration", 0)
            title = data.get("title", "") or data.get("description", "")
            return {
                "has_video": True,
                "duration": int(dur or 0),
                "title": title.strip()
            }
    except Exception as e:
        print(f"yt-dlp kontrol hatası ({x_url}): {e}")
    return {"has_video": False, "duration": 0, "title": ""}


def scout_x_videos(limit: int = 5) -> List[Dict]:
    """X (Twitter) üzerinde son 24 saatte paylaşılan ham asayiş/sokak/trafik videolarını yakalar."""
    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        print("googlenewsdecoder yüklü değil!")
        return []

    # Türk halkının en çok izlediği viral sokak olayı anahtar kelimeleri
    queries = [
        'site:x.com ("trafikte" OR "kavga" OR "kamerada" OR "pes dedirtti" OR "o anlar") when:24h',
        'site:x.com ("yumruklu kavga" OR "dehşet anları" OR "yol verme kavgası") when:24h'
    ]

    found = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for q in queries:
        encoded_q = urllib.parse.quote(q)
        rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=tr&gl=TR&ceid=TR:tr"
        req = urllib.request.Request(rss_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                root = ET.fromstring(resp.read())
                items = root.findall(".//item")
                for it in items:
                    raw_title = it.find("title").text if it.find("title") is not None else ""
                    raw_link = it.find("link").text if it.find("link") is not None else ""
                    if not raw_link:
                        continue

                    # Google News URL'sini gerçek X linkine çöz
                    try:
                        dec = gnewsdecoder(raw_link)
                        x_url = dec.get("decoded_url", "")
                    except Exception:
                        x_url = ""

                    if not x_url or "x.com" not in x_url:
                        continue

                    # /status/ içermeli
                    if "/status/" not in x_url:
                        continue

                    clean_x_url = x_url.split("?")[0].split("/video/")[0]
                    if is_seen(clean_x_url):
                        continue

                    # yt-dlp ile videoyu doğrula
                    v_info = verify_x_video_with_ytdlp(clean_x_url)
                    if v_info["has_video"]:
                        dur = v_info["duration"]
                        # 4 saniye ile 180 saniye arası ideal viral kısa videolar
                        if 4 <= dur <= 180:
                            item_obj = {
                                "source": "X (Twitter)",
                                "url": clean_x_url,
                                "title": v_info["title"] or raw_title.replace(" - X", "").strip(),
                                "duration": dur
                            }
                            found.append(item_obj)
                            mark_seen(clean_x_url, item_obj["title"], "X (Twitter)")
                            if len(found) >= limit:
                                return found
        except Exception as e:
            print(f"X tarama hatası ({q}): {e}")

    return found


def scout_telegram_channels(limit: int = 5) -> List[Dict]:
    """Halka açık Türk asayiş ve sokak haber kanallarından ham videoları yakalar."""
    channels = ["asayisberkemal", "bpthaber"]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    found = []

    for ch in channels:
        url = f"https://t.me/s/{ch}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                soup = BeautifulSoup(resp.read(), "html.parser")
                msgs = soup.find_all("div", class_="tgme_widget_message")
                for m in reversed(msgs):
                    video = m.find("video")
                    if not video:
                        continue
                    post_id = m.get("data-post")  # Örn: asayisberkemal/3960
                    if not post_id:
                        continue
                    post_url = f"https://t.me/{post_id}"
                    if is_seen(post_url):
                        continue

                    text_el = m.find("div", class_="tgme_widget_message_text")
                    caption = text_el.get_text(separator=" ", strip=True) if text_el else "Yeni Sokak/Asayiş Videosu"

                    # İlgi çekici kelime filtresi
                    lower_cap = caption.lower()
                    viral_keys = ["kavga", "trafik", "kamerada", "o anlar", "pes dedirtti", "dehşet", "yaral", "kaza", "polis", "jandarma", "yakalandı", "tartışma"]
                    if not any(k in lower_cap for k in viral_keys):
                        continue

                    item_obj = {
                        "source": f"Telegram (@{ch})",
                        "url": post_url,
                        "title": caption[:160],
                        "duration": 0
                    }
                    found.append(item_obj)
                    mark_seen(post_url, caption[:160], f"Telegram (@{ch})")
                    if len(found) >= limit:
                        return found
        except Exception as e:
            print(f"Telegram tarama hatası (@{ch}): {e}")

    return found


def send_scout_alert_to_admin(item: dict) -> bool:
    """Yakalanan viral videoyu doğrudan Yalçın Bey'in şahsi Telegram'ına bildirir."""
    title = item.get("title", "Yeni Sokak / Asayiş Videosu")
    url = item.get("url", "")
    source = item.get("source", "X (Twitter)")
    duration = item.get("duration", 0)

    dur_str = f"\n⏱️ <b>Süre:</b> {duration} saniye" if duration > 0 else ""

    text = f"""🚨 <b>VİRAL VİDEO RADARI YAKALADI!</b>

📌 <b>Kaynak:</b> {source}
📝 <b>Konu:</b> {title}{dur_str}

🔗 <b>Videonun Linki:</b>
{url}

💡 <i>İzlemek için linke tıkla. Beğendiysen linki panelindeki Video Stüdyosuna yapıştırıp 1-tıkla logolu olarak yayınla!</i>"""

    # Admin'e özel mesaj
    admin_id = getattr(config, "TELEGRAM_ADMIN_ID", "1934709259")
    bot_token = config.TELEGRAM_BOT_TOKEN
    if not bot_token:
        bot_token = os.getenv("TELEGRAM_SCOUT_BOT_TOKEN", "").strip()
    if not bot_token:
        print("Bot token tanımlı değil.")
        return False

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        import requests
        r = requests.post(api_url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Admin bildirim hatası: {e}")
        return False


def run_scout_cycle() -> int:
    """Tek bir radar taraması yapar ve bulunan yeni videoları gönderir."""
    init_scout_db()
    print("📡 Viral Video Radarı taranıyor...")

    # 1. X (Twitter) videoları
    x_items = scout_x_videos(limit=3)
    # 2. Telegram Asayiş/Sokak kanalları
    tg_items = scout_telegram_channels(limit=2)

    all_items = x_items + tg_items
    sent_count = 0
    for it in all_items:
        print(f"✨ Yeni Video: [{it['source']}] {it['title'][:50]}... ({it['url']})")
        ok = send_scout_alert_to_admin(it)
        if ok:
            sent_count += 1
            time.sleep(1.5)  # Telegram spam koruması

    print(f"🏁 Tarama tamamlandı. Toplam {sent_count} adet yeni viral video Telegram'ına iletildi.")
    return sent_count


if __name__ == "__main__":
    run_scout_cycle()
