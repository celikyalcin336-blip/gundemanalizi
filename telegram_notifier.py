import os
import sys
import re
import requests
import json
import urllib.parse

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config

BASE_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

def to_ascii_url(url: str) -> str:
    """
    Herhangi bir Turkce karakterli URL'i Telegram Bot API'nin
    100% sorunsuz kabul edecegi standart ASCII Punycode formatina cevirir.
    Ornek: https://www.gundemanalizi.com.tr -> https://www.xn--gndemanalizi-dlb.com.tr
    """
    if not url:
        return "https://xn--gndemanalizi-dlb.com.tr"
    try:
        parts = urllib.parse.urlsplit(url)
        hostname = parts.hostname or ""
        encoded_host = hostname.encode("idna").decode("ascii")
        netloc = encoded_host
        if parts.port:
            netloc += f":{parts.port}"
        path = urllib.parse.quote(parts.path, safe="/:@!$&'()*+,;=-_.~")
        query = urllib.parse.quote(parts.query, safe="=&?/:@!$'()*+,;=-_.~")
        return urllib.parse.urlunsplit((parts.scheme or "https", netloc, path, query, parts.fragment))
    except Exception:
        # Yedek guvenli cevirici
        u = re.sub(r'https?://(www\.)?g[^\.]+\.com\.tr', r'https://\1xn--gndemanalizi-dlb.com.tr', url, flags=re.IGNORECASE)
        return u

def clean_news_link(url: str) -> str:
    """
    Punycode adresleri telegram metninde veya tarayicida temiz linke cevirir.
    """
    if not url:
        return ""
    clean = url.replace("https://xn--gndemanalizi-dlb.com.tr", "https://www.gundemanalizi.com.tr")
    clean = clean.replace("http://xn--gndemanalizi-dlb.com.tr", "https://www.gundemanalizi.com.tr")
    clean = clean.replace("xn--gndemanalizi-dlb.com.tr", "www.gundemanalizi.com.tr")
    return clean

def send_telegram_message(text: str) -> bool:
    """Telegram'a salt metin mesaji gonderir."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanimli degil.")
        return False

    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        data = resp.json()
        if data.get("ok"):
            print("Telegram metin bildirimi basariyla iletildi.")
            return True
        else:
            print(f"Telegram sendMessage hatasi: {data}")
            return False
    except Exception as e:
        print(f"Telegram mesaj gonderme hatasi: {e}")
        return False

def send_telegram_news(image_path: str, caption: str, news_link: str = "") -> bool:
    """
    Telegram'a haber karti gorselini ve aciklamasini tek bir post halinde gonderir.
    1. Gorselli + Butonlu gondermeyi dener.
    2. Buton reddedilirse butonsuz gorsel dener.
    3. Gorsel dosya yoksa veya gorsel API tarafindan reddedilirse
       ASLA HABERI DUSURMEZ -> Hemen metin olarak Telegram'a iletir!
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanimli degil.")
        return False

    ascii_link = to_ascii_url(news_link) if news_link else ""
    # Kaynak parantezlerini temizle
    clean_caption = re.sub(r'\s*\([A-Za-z0-9\sçğıöşüÇĞİÖŞÜ\.\'\-]{3,40}\)\s*$', '', caption)
    
    full_caption = clean_caption
    if ascii_link:
        full_caption += f"\n\n📖 Haberin Detayi: {ascii_link}"

    if len(full_caption) > 1020:
        full_caption = full_caption[:1015] + "..."

    url = f"{BASE_URL}/sendPhoto"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "caption": full_caption
    }
    if ascii_link:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [
                [
                    {
                        "text": "📖 Haberi Oku: www.gundemanalizi.com.tr",
                        "url": ascii_link
                    }
                ]
            ]
        })

    # 1. Gorsel ile gonderme denemesi
    if image_path and os.path.exists(image_path):
        try:
            with open(image_path, "rb") as img:
                files = {"photo": img}
                resp = requests.post(url, data=payload, files=files, timeout=30)
                data = resp.json()
                if data.get("ok"):
                    print("📢 Haber basariyla Telegram'a gorselle gonderildi!")
                    return True
                
                # Buton kaynakli hata varsa butonsuz dene
                if "reply_markup" in payload:
                    print(f"⚠️ Telegram buton reddi ({data.get('description')}), butonsuz deneniyor...")
                    del payload["reply_markup"]
                    with open(image_path, "rb") as retry_img:
                        resp = requests.post(url, data=payload, files={"photo": retry_img}, timeout=30)
                        data = resp.json()
                        if data.get("ok"):
                            print("📢 Haber basariyla Telegram'a butonsuz gorselle gonderildi!")
                            return True
                print(f"Telegram sendPhoto basarisiz: {data}")
        except Exception as e:
            print(f"Telegram gorsel gonderme hatasi: {e}")

    # 2. Guvenlik Agi (Fallback): Gorsel yoksa veya reddedildiyse haberi salt metin olarak kesinlikle ilet!
    print("⚠️ Gorselli bildirim yapilamadi, haber Telegram'a metin olarak iletiliyor...")
    text_fallback = f"{clean_caption}\n\n📖 Haberin Detayi: {ascii_link}"
    return send_telegram_message(text_fallback)

def send_telegram_video(video_path: str, caption: str, news_link: str = "") -> bool:
    """Telegram kanalina dogrudan video (Reels / MP4) gonderir."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram bot token veya chat ID tanimli degil.")
        return False

    if not os.path.exists(video_path):
        print(f"Video bulunamadi: {video_path}")
        return False

    ascii_link = to_ascii_url(news_link) if news_link else ""
    clean_caption = re.sub(r'\s*\([A-Za-z0-9\sçğıöşüÇĞİÖŞÜ\.\'\-]{3,40}\)\s*$', '', caption)
    full_caption = clean_caption
    if ascii_link:
        full_caption += f"\n\n📖 Haberin Detayi: {ascii_link}"

    url = f"{BASE_URL}/sendVideo"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "caption": full_caption[:1020]
    }
    if ascii_link:
        payload["reply_markup"] = json.dumps({
            "inline_keyboard": [
                [
                    {
                        "text": "📖 Haberi Oku: www.gundemanalizi.com.tr",
                        "url": ascii_link
                    }
                ]
            ]
        })

    try:
        with open(video_path, "rb") as vid:
            files = {"video": vid}
            resp = requests.post(url, data=payload, files=files, timeout=90)
            data = resp.json()
            if data.get("ok"):
                print("📢 Video basariyla Telegram'a gonderildi!")
                return True
            if "reply_markup" in payload:
                del payload["reply_markup"]
                with open(video_path, "rb") as retry_vid:
                    resp = requests.post(url, data=payload, files={"video": retry_vid}, timeout=90)
                    data = resp.json()
                    if data.get("ok"):
                        print("📢 Video butonsuz olarak Telegram'a gonderildi!")
                        return True
            print(f"Telegram Video API hatasi: {data}")
            return False
    except Exception as e:
        print(f"Telegram video gonderme hatasi: {e}")
        return False

def send_admin_ihbar(message_text: str, media_path: str = None, media_type: str = "none") -> bool:
    """Okuyucudan gelen ihbarlari Yalcin Bey'in Telegram'ina iletir."""
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    admin_chat = getattr(config, "TELEGRAM_ADMIN_ID", "") or config.TELEGRAM_CHAT_ID
    try:
        if media_path and os.path.exists(media_path):
            if media_type == "video":
                with open(media_path, "rb") as vf:
                    r = requests.post(
                        f"{BASE_URL}/sendVideo",
                        data={"chat_id": admin_chat, "caption": message_text[:1020]},
                        files={"video": vf},
                        timeout=90
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
        print(f"Ihbar gonderim hatasi: {e}")
        return False

def send_admin_alert(subject: str, message: str, is_resolved: bool = False) -> bool:
    """Sistem kesintisi veya aksaklik uyarisi."""
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    admin_chat = getattr(config, "TELEGRAM_ADMIN_ID", "") or config.TELEGRAM_CHAT_ID
    icon = "✅ [SISTEM NORMALE DONDU]" if is_resolved else "🚨 [ACIL DURUM UYARISI]"
    from datetime import datetime
    full_text = (
        f"<b>{icon}</b>\n"
        f"<b>Konu:</b> {subject}\n\n"
        f"{message}\n\n"
        f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (TSI)</i>"
    )
    try:
        r = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": admin_chat, "text": full_text, "parse_mode": "HTML"},
            timeout=15
        )
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Admin uyari mesaji gonderme hatasi: {e}")
        return False


def send_admin_whatsapp_prompt(image_path: str, title: str, summary: str, site_url: str, category: str = "Gündem") -> bool:
    """
    VIP Editör Modu:
    Haber yayınlandığında Yalçın Bey'in özel Telegram hesabına (TELEGRAM_ADMIN_ID):
    - Hazır formatlanmış WhatsApp bülten metni
    - Tek tıkla "📲 WhatsApp Kanalında Paylaş" butonu gönderir.
    Telefondan butona tek bir tıkla basıldığında resmi WhatsApp açılır ve kanal seçilerek 1 saniyede paylaşılır!
    """
    if not config.TELEGRAM_BOT_TOKEN:
        return False

    admin_chat = getattr(config, "TELEGRAM_ADMIN_ID", "") or config.TELEGRAM_CHAT_ID
    if not admin_chat:
        return False

    category_emojis = {
        "Ekonomi": "📊",
        "Gündem": "🚨",
        "Teknoloji": "🚀",
        "Otomobil": "🚗",
        "Dünya": "🌍",
        "Sağlık": "🩺",
        "Spor": "⚽",
        "Eğitim": "🎓"
    }
    emoji = category_emojis.get(category, "🔴")
    clean_title = title.strip()

    # WhatsApp için optimize edilmiş bülten metni
    wp_text = f"*{emoji} {clean_title}*\n\n"
    if summary:
        first_sentence = summary.split('.')[0].strip()
        if first_sentence:
            wp_text += f"📌 {first_sentence}.\n\n"
    wp_text += f"🔗 *Detaylar:* {site_url}\n\n#GündemAnalizi #{category}"

    encoded_text = urllib.parse.quote(wp_text)
    wa_share_url = f"https://api.whatsapp.com/send?text={encoded_text}"

    caption = (
        f"👑 <b>[YALÇIN BEY - WHATSAPP KANAL ÖNERİSİ]</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>Bu haber çok tıklandı / öne çıktı:</b>\n"
        f"<b>{clean_title}</b>\n\n"
        f"💡 Aşağıdaki butona tek tıkla basarak doğrudan <b>WhatsApp Kanalında</b> paylaşabilirsiniz:"
    )

    url = f"{BASE_URL}/sendPhoto"
    payload = {
        "chat_id": admin_chat,
        "caption": caption[:1020],
        "parse_mode": "HTML",
        "reply_markup": json.dumps({
            "inline_keyboard": [
                [
                    {
                        "text": "📲 WhatsApp Kanalında Paylaş (Tek Tık)",
                        "url": wa_share_url
                    }
                ],
                [
                    {
                        "text": "🌐 Haberi Sitede Gör",
                        "url": site_url
                    }
                ]
            ]
        })
    }

    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img:
                resp = requests.post(url, data=payload, files={"photo": img}, timeout=30)
                data = resp.json()
                if data.get("ok"):
                    print("📲 [VIP WhatsApp] Paylaşım önerisi Telegram yöneticisine iletildi.")
                    return True

        # Görüntü yoksa düz mesaj olarak ilet
        msg_url = f"{BASE_URL}/sendMessage"
        resp = requests.post(msg_url, json={
            "chat_id": admin_chat,
            "text": caption,
            "parse_mode": "HTML",
            "reply_markup": json.loads(payload["reply_markup"])
        }, timeout=20)
        data = resp.json()
        if data.get("ok"):
            print("📲 [VIP WhatsApp] Paylaşım önerisi metin olarak iletildi.")
            return True
        print(f"⚠️ VIP WhatsApp önerisi hatası: {data}")
        return False
    except Exception as e:
        print(f"⚠️ VIP WhatsApp önerisi istisnası: {e}")
        return False
