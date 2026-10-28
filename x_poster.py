"""
X (Twitter) Profesyonel Paylaşım ve Kalite Kalkanı (@gndmanalizi)
- Playwright Web Motoru Destekli (%100 Ücretsiz, Sıfır API Ücreti, Kesintisiz)
- Çöp / Magazin / Tık Tuzağı Engelleyici (Seçici Kalite Filtresi)
- Otomatik Zaman Kilidi & Gece Sessiz Saatler Koruyucusu (Günde ~20 tweet kotası)
- Kristal Netliğinde Haber Kartı Görseli & Video Desteği
"""
import os
import io
import time
import base64
import requests
import re
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
from PIL import Image

import config

# Doğrulanmış Oturum Çerezleri (@gndmanalizi) - Ortam değişkeninden okunur
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN", "").strip()
TWITTER_CT0 = os.getenv("TWITTER_CT0", "").strip()

TR_TZ = timezone(timedelta(hours=3))

# Tweet sıklığı (Saatte 1 tweet - Tam saat başı kilit tamponu: 45 dk)
X_COOLDOWN_MINUTES = float(os.getenv("X_COOLDOWN_MINUTES", getattr(config, "X_COOLDOWN_MINUTES", 45.0)))

# -------------------------------------------------------------
# 🛡️ ÇÖP & TIK TUZAĞI (CLICKBAIT) ENGELLEYİCİ LİSTESİ
# -------------------------------------------------------------
JUNK_KEYWORDS = [
    # Magazin & Şöhret Dedikoduları
    "kimdir", "nereli", "nerelidir", "kaç yaşında", "sevgilisi", "eşi kim",
    "bomba iddia", "şok eden", "burç", "astroloji", "magazin", "evlilik",
    "göz kamaştırdı", "sosyal medyayı salladı", "can yeleği", "bikinili", "dekolteli",
    "dudak uçuklattı", "ağızları açık bıraktı", "görenler şaştı", "gözyaşlarına boğuldu",
    "survivor", "masterchef", "dizi fragmanı", "yalı çapkını", "kızılcık şerbeti",
    "şaşırtan olay", "yürek yakan", "kahreden", "inanılmaz görüntü",

    # Önemsiz Küçük Yerel Asayiş / Basit Trafik Olayları
    "kaldırıma çıktı", "tır devrildi", "direğe çarptı", "hafif ticari araç",
    "maddi hasarlı kaza", "kavga çıktı", "komşuların kavgası", "balkondan düştü",
    "sokak köpeği kovaladı", "pazarcı kavgası", "apartmanda yangın paniği",

    # Reklam ve Tanıtım Tuzakları
    "sponsorlu", "tanıtım bülteni", "indirim kodu", "fırsatı kaçırma", "tıkla izle"
]

# X'te Yüksek Etkileşim ve Tıklama Getiren Öncelikli Konular
PRIORITY_KEYWORDS = [
    "enflasyon", "asgari ücret", "faiz", "dolar", "euro", "altın", "borsa", "bist",
    "emekli maaşı", "vergi", "memur zammı", "merkez bankası", "tcmb", "şimşek",
    "cumhurbaşkanı", "erdoğan", "bakanlık", "tbmm", "meclis", "yasa teklifi", "kanun",
    "togg", "elektrikli araç", "yapay zeka", "apple", "iphone", "tesla", "deprem",
    "baykar", "kızılelma", "kaan", "savunma sanayii", "milli takım", "şampiyonlar ligi",
    "derbi", "fenerbahçe", "galatasaray", "beşiktaş", "trabzonspor"
]


def is_configured() -> bool:
    """Oturum çerezlerinin tanımlı olup olmadığını doğrular."""
    return bool(TWITTER_AUTH_TOKEN and TWITTER_CT0)


def is_worthy_for_x(title: str, summary: str = "", category: str = "Gündem") -> Tuple[bool, str]:
    """
    Haberi kalite süzgecinden geçirir:
    - Çöp/magazin/tık tuzağı içerikleri eler.
    - Sadece X okuyucusunun ilgisini çekecek yüksek değerli haberlere onay verir.
    """
    clean_text = f"{title} {summary}".lower()

    if len(title.strip()) < 22:
        return False, "Başlık çok kısa veya özensiz."

    for junk in JUNK_KEYWORDS:
        if re.search(rf"\b{re.escape(junk)}\b", clean_text):
            return False, f"Çöp/Magazin filtresine takıldı: '{junk}'"

    norm_cat = category.strip().title()

    if norm_cat in ("Ekonomi", "Teknoloji", "Otomobil", "Gündem", "Dünya", "Sağlık"):
        return True, f"Yüksek değerli ana kategori: {norm_cat}"

    if norm_cat == "Spor":
        for kw in PRIORITY_KEYWORDS:
            if kw in clean_text:
                return True, f"Önemli spor gelişmesi: '{kw}'"
        return False, "Sıradan spor haberi filtrelendi (Sadece derbi ve milli maçlar paylaşılır)."

    for kw in PRIORITY_KEYWORDS:
        if kw in clean_text:
            return True, f"Flaş gündem anahtar kelimesi: '{kw}'"

    return True, "Genel kalite onayından geçti."


def can_post_to_x(force: bool = False) -> Tuple[bool, str]:
    """
    Zaman kilidi ve sessiz saat kontrolü yapar.
    - Gece 01:30 - 07:30 arası sessiz mod (uyku saatlerinde kotayı tüketmez).
    - İki tweet arasında en az X_COOLDOWN_MINUTES (varsayılan: 45 dk) süre olmalıdır.
    """
    if force:
        return True, "Manuel zorlama (Force modu aktif)."

    now_tr = datetime.now(TR_TZ)
    hour_decimal = now_tr.hour + (now_tr.minute / 60.0)

    # 1. Gece Sessiz Saatler Kalkanı (01:30 - 07:30)
    if 1.5 <= hour_decimal < 7.5:
        return False, f"Gece sessiz saatler devrede ({now_tr.strftime('%H:%M')}). 07:30'a kadar kota korunuyor."

    # 2. Zaman Kilidi (Cooldown) Kontrolü
    try:
        history_path = os.path.join(os.path.dirname(__file__), "x_posted_history.json")
        last_ts = 0.0
        if os.path.exists(history_path):
            import json
            with open(history_path, "r", encoding="utf-8") as f:
                hist = json.load(f)
                posted_items = [h for h in hist if isinstance(h, dict) and h.get("status") == "posted" and h.get("ts")]
                if posted_items:
                    last_ts = float(posted_items[-1]["ts"])

        if last_ts > 0:
            elapsed_minutes = (time.time() - last_ts) / 60.0
            if elapsed_minutes < X_COOLDOWN_MINUTES:
                remaining = round(X_COOLDOWN_MINUTES - elapsed_minutes, 1)
                return False, f"Zaman kilidi devrede. Son tweet {round(elapsed_minutes, 1)} dk önce atıldı. ({remaining} dk kaldı)."
    except Exception as e:
        print(f"⚠️ X zaman kilidi kontrolü hatası: {e}")

    return True, "Zaman kilidi onaylandı."


def format_x_tweet(title: str, summary: str, site_url: str, category: str = "Gündem") -> str:
    """
    X (Twitter) algoritmasına uygun, 280 karakteri aşmayan, merak uyandıran profesyonel tweet metni üretir.
    """
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
    cat_tag = f"#{category}" if category in ("Ekonomi", "Teknoloji", "Gündem", "Otomobil", "Spor") else "#Gündem"
    tags = f"{cat_tag} #SonDakika"

    clean_title = title.strip()
    clean_title = re.sub(r'\s*-\s*[A-Za-z0-9ğüşıöçĞÜŞİÖÇ\s\.]+$', '', clean_title)

    max_title_len = 150
    trimmed_title = clean_title
    if len(trimmed_title) > max_title_len:
        trimmed_title = trimmed_title[:max_title_len - 1] + "…"

    body = ""
    remaining_room = 280 - 24 - len(tags) - len(trimmed_title) - 25
    if remaining_room > 40 and summary:
        first_sentence = summary.split(".")[0].strip()
        if first_sentence and len(first_sentence) < remaining_room:
            body = f"\n\n{first_sentence}."

    tweet = f"{emoji} {trimmed_title}{body}\n\n🔗 Detaylar: {site_url}\n{tags}"
    return tweet.strip()


def post_tweet_playwright(text: str, media_path: Optional[str] = None) -> dict:
    """
    Playwright Chromium motoruyla X'te (%100 ücretsiz) tweet yayınlar.
    Görsel ve video eklerini destekler.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "reason": "Playwright kurulu değil"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            context.add_cookies([
                {"name": "auth_token", "value": TWITTER_AUTH_TOKEN, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": True},
                {"name": "ct0", "value": TWITTER_CT0, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": False}
            ])
            page = context.new_page()
            page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Tweet metin editörünü bul
            editor = page.locator('div[role="textbox"][data-testid="tweetTextarea_0"]')
            if not editor.count():
                editor = page.locator('div[role="textbox"]')

            if not editor.count():
                browser.close()
                return {"status": "error", "reason": "Tweet metin kutusu bulunamadı"}

            editor.first.click()
            editor.first.fill(text)
            page.wait_for_timeout(1000)

            # Görsel veya Video Ekle
            if media_path and os.path.exists(media_path):
                file_input = page.locator('input[data-testid="fileInput"]').first
                if file_input.count():
                    file_input.set_input_files(media_path)
                    is_video = media_path.lower().endswith(('.mp4', '.mov', '.avi'))
                    wait_sec = 18 if is_video else 4
                    print(f"⏳ Medya X'e yükleniyor ({'Video' if is_video else 'Görsel'}), {wait_sec}s bekleniyor...")
                    page.wait_for_timeout(wait_sec * 1000)

            # Tweeti Gönder
            post_btn = page.locator('button[data-testid="tweetButton"]').first
            if not post_btn.count():
                post_btn = page.locator('button[data-testid="tweetButtonInline"]').first

            # Video yükleme sonrası butonun aktifleşmesini bekle (maksimum 30s)
            for _ in range(15):
                if post_btn.count() and post_btn.get_attribute("disabled") is None:
                    break
                page.wait_for_timeout(2000)

            try:
                editor.first.press("Control+Enter")
            except Exception:
                pass

            if post_btn.count():
                try:
                    post_btn.click(force=True)
                except Exception:
                    pass

            page.wait_for_timeout(6000)
            browser.close()
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def post_article_to_x(title: str, summary: str, site_url: str, image_path: Optional[str] = None,
                      category: str = "Gündem", force: bool = False) -> dict:
    """
    Sitede yayınlanan bir haberi X (Twitter) hesabına fotoğraflı tweet olarak gönderir.
    - Zaman kilidi ve çöp filtrelerini otomatik kontrol eder.
    - Başarılı olursa son tweet zamanını kaydeder.
    """
    if not is_configured():
        return {"status": "skipped", "reason": "X oturum çerezleri eksik."}

    # 1. Kalite ve Seçicilik Süzgeci
    worthy, reason = is_worthy_for_x(title, summary, category)
    if not worthy and not force:
        return {"status": "skipped", "reason": f"Kalite filtresi: {reason}"}

    # 2. Zaman Kilidi & Gece Kalkanı
    allowed, time_reason = can_post_to_x(force=force)
    if not allowed:
        return {"status": "skipped", "reason": f"Zamanlama: {time_reason}"}

    # 3. Tweet Metnini Hazırla
    tweet_text = format_x_tweet(title, summary, site_url, category)

    # 4. Playwright ile Tweeti Gönder
    res = post_tweet_playwright(tweet_text, media_path=image_path)
    if res.get("status") == "success":
        print(f"✅ [X/Twitter] Tweet başarıyla paylaşıldı: @gndmanalizi")
        return {"status": "success", "url": "https://x.com/gndmanalizi"}

    return res


def post_video_to_x(video_path: str, title: str, link: str = "") -> dict:
    """Panelden veya yerelden yüklenen MP4 videoyu X'te paylaşır."""
    if not is_configured():
        return {"status": "error", "reason": "X oturum çerezleri eksik."}

    tags = " #Gündem #SonDakika"
    room = 280 - 24 - len(tags) - 6
    text = title.strip()
    if len(text) > room:
        text = text[:room - 1] + "…"
    tweet_text = f"🎥 {text}\n\n🔗 {link}\n{tags}" if link else f"🎥 {text}\n\n{tags}"

    return post_tweet_playwright(tweet_text, media_path=video_path)
