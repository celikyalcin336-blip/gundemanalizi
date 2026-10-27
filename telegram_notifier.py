import os
import sys
import requests
import json

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config

BASE_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

def to_ascii_url(url: str) -> str:
    if not url:
        return "https://xn--gndemanalizi-dlb.com.tr"
    u = url.replace("https://www.gündemanalizi.com.tr", "https://xn--gndemanalizi-dlb.com.tr")
    u = u.replace("http://www.gündemanalizi.com.tr", "https://xn--gndemanalizi-dlb.com.tr")
    u = u.replace("https://gündemanalizi.com.tr", "https://xn--gndemanalizi-dlb.com.tr")
    u = u.replace("http://gündemanalizi.com.tr", "https://xn--gndemanalizi-dlb.com.tr")
    u = u.replace("www.gündemanalizi.com.tr", "xn--gndemanalizi-dlb.com.tr")
    u = u.replace("gündemanalizi.com.tr", "xn--gndemanalizi-dlb.com.tr")
    return u

def clean_news_link(url: str) -> str:
    """
    Punycode (xn--gndemanalizi-dlb.com.tr) adreslerini kullanıcı dostu
    ve güven veren 'https://www.gündemanalizi.com.tr' adresine dönüştürür.
    """
    if not url:
        return ""
    clean = url.replace("https://xn--gndemanalizi-dlb.com.tr", "https://www.gündemanalizi.com.tr")
    clean = clean.replace("http://xn--gndemanalizi-dlb.com.tr", "https://www.gündemanalizi.com.tr")
    clean = clean.replace("https://xn--gndemanali-dlb.com.tr", "https://www.gündemanalizi.com.tr")
    clean = clean.replace("http://xn--gndemanali-dlb.com.tr", "https://www.gündemanalizi.com.tr")
    clean = clean.replace("xn--gndemanalizi-dlb.com.tr", "www.gündemanalizi.com.tr")
    clean = clean.replace("xn--gndemanali-dlb.com.tr", "www.gündemanalizi.com.tr")
    # Eğer doğrudan www olmadan gündemanalizi varsa www ekle
    clean = clean.replace("https://gündemanalizi.com.tr", "https://www.gündemanalizi.com.tr")
    clean = clean.replace("http://gündemanalizi.com.tr", "https://www.gündemanalizi.com.tr")
    return clean


def send_telegram_message(text: str) -> bool:
    """Telegram'a salt metin mesajı gönderir."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanımlı değil.")
        return False

    clean_text = clean_news_link(text)
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": clean_text,
        "parse_mode": "HTML"
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        return data.get("ok", False)
    except Exception as e:
        print(f"Telegram mesaj gönderme hatası: {e}")
        return False

def send_telegram_news(image_path: str, caption: str, news_link: str = "") -> bool:
    """
    Telegram'a haber kartı görselini ve açıklamasını tek bir post halinde gönderir.
    Altına tertemiz ve güvenilir 'www.gündemanalizi.com.tr' linkini ve tek tıkla açılan butonu ekler.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanımlı değil.")
        return False

    if not os.path.exists(image_path):
        print(f"Görsel bulunamadı: {image_path}")
        return False

    display_link = clean_news_link(news_link)
    # Kaynak parantezlerini (örn: (Motor1 Otomobil), (Habertürk Spor) vb.) kesinlikle kaldır
    clean_caption = re.sub(r'\s*\([A-Za-z0-9\sğüşıöçĞÜŞİÖÇ\.\'\-]{3,40}\)\s*$', '', caption)
    full_caption = clean_caption
    if display_link:
        full_caption += f"\n\n🔗 Haberin Detayı: {display_link}"

    if len(full_caption) > 1020:
        full_caption = full_caption[:1015] + "..."

    url = f"{BASE_URL}/sendPhoto"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "caption": full_caption
    }
    if display_link:
        btn_target_url = to_ascii_url(news_link or display_link)
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [
                [
                    {
                        "text": "📖 Haberi Oku: www.gündemanalizi.com.tr",
                        "url": btn_target_url
                    }
                ]
            ]
        })

    try:
        with open(image_path, "rb") as img:
            files = {"photo": img}
            resp = requests.post(url, data=payload, files=files, timeout=30)
            data = resp.json()
            if not data.get("ok") and "reply_markup" in payload:
                print(f"⚠️ Telegram reply_markup reddedildi ({data.get('description')}), butonsuz gonderiliyor...")
                del payload["reply_markup"]
                with open(image_path, "rb") as retry_img:
                    resp = requests.post(url, data=payload, files={"photo": retry_img}, timeout=30)
                    data = resp.json()
            if data.get("ok"):
                print("📲 Haber başarıyla Telegram'a gönderildi!")
                return True
            else:
                print(f"Telegram API hatası: {data}")
                return False
    except Exception as e:
        print(f"Telegram görsel gönderme hatası: {e}")
        return False

def send_telegram_video(video_path: str, caption: str, news_link: str = "") -> bool:
    """Telegram kanalına doğrudan video (Reels / MP4) gönderir."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanımlı değil.")
        return False

    if not os.path.exists(video_path):
        print(f"Video bulunamadı: {video_path}")
        return False

    display_link = clean_news_link(news_link)
    # Kaynak parantezlerini (örn: (Motor1 Otomobil), (Habertürk Spor) vb.) kesinlikle kaldır
    clean_caption = re.sub(r'\s*\([A-Za-z0-9\sğüşıöçĞÜŞİÖÇ\.\'\-]{3,40}\)\s*$', '', caption)
    full_caption = clean_caption
    if display_link:
        full_caption += f"\n\n🔗 Haberin Detayı: {display_link}"

    url = f"{BASE_URL}/sendVideo"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "caption": full_caption[:1020],
        "supports_streaming": "true"
    }
    if display_link:
        btn_target_url = to_ascii_url(news_link or display_link)
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [
                [
                    {
                        "text": "📖 Haberi Oku: www.gündemanalizi.com.tr",
                        "url": btn_target_url
                    }
                ]
            ]
        })

    try:
        with open(video_path, "rb") as vid:
            files = {"video": vid}
            resp = requests.post(url, data=payload, files=files, timeout=60)
            data = resp.json()
            if data.get("ok"):
                print("🎥 Video başarıyla Telegram'a gönderildi!")
                return True
            else:
                print(f"Telegram video gönderme hatası: {data}")
                return False
    except Exception as e:
        print(f"Telegram video hatası: {e}")
        return False

def send_admin_ihbar(message_text: str, media_path: str = "", media_type: str = "") -> bool:
    """
    Sitedeki '7/24 İhbar Hattı'ndan gelen mesaj, fotoğraf veya videoyu
    doğrudan Yalçın Bey'in özel Telegram hesabına (TELEGRAM_ADMIN_ID) iletir.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    admin_chat = getattr(config, "TELEGRAM_ADMIN_ID", "") or config.TELEGRAM_CHAT_ID
    try:
        if media_path and os.path.exists(media_path):
            if media_type == "video":
                with open(media_path, "rb") as vf:
                    r = requests.post(
                        f"{BASE_URL}/sendVideo",
                        data={"chat_id": admin_chat, "caption": message_text[:1020], "supports_streaming": "true"},
                        files={"video": vf},
                        timeout=60
                    )
                    if r.json().get("ok"):
                        return True
            elif media_type == "photo":
                with open(media_path, "rb") as pf:
                    r = requests.post(
                        f"{BASE_URL}/sendPhoto",
                        data={"chat_id": admin_chat, "caption": message_text[:1020]},
                        files={"photo": pf},
                        timeout=45
                    )
                    if r.json().get("ok"):
                        return True

        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": admin_chat, "text": message_text[:4000]},
            timeout=15
        )
        return r.json().get("ok", False)
    except Exception as e:
        print(f"İhbar gönderim hatası: {e}")
        return False

def send_admin_alert(subject: str, message: str, is_resolved: bool = False) -> bool:
    """
    Sitede kritik bir kesinti, veritabanı kopması veya aksaklık olduğunda
    Yalçın Bey'in şahsi Telegram'ına anında acil durum uyarısı atar.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    admin_chat = getattr(config, "TELEGRAM_ADMIN_ID", "") or config.TELEGRAM_CHAT_ID
    icon = "✅ [SİSTEM NORMALE DÖNDÜ]" if is_resolved else "🚨 [ACİL DURUM UYARISI]"
    from datetime import datetime
    full_text = (
        f"<b>{icon}</b>\n"
        f"<b>Konu:</b> {subject}\n\n"
        f"{message}\n\n"
        f"⏰ <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (TSİ)</i>"
    )
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": admin_chat, "text": full_text, "parse_mode": "HTML"},
            timeout=15
        )
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Admin uyarı mesajı gönderme hatası: {e}")
        return False

if __name__ == "__main__":
    send_telegram_message("👋 Merhaba Yalçın Bey! Gündem Analizi botu başarıyla bağlandı. Test haberiniz birazdan geliyor...")
    test_img = os.path.join(os.path.dirname(__file__), "output", "test_card.jpg")
    if os.path.exists(test_img):
        send_telegram_news(
            test_img,
            "🇹🇷 [TEST HABERİ] Gündem Analizi Sistemi Başarıyla Çalışıyor!\n\nArtık Türkiye gündemindeki tüm son dakika gelişmeleri otomatik olarak hazırlanıp buraya iletilecektir.",
            "https://www.google.com"
        )
