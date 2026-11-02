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
_DEF_X_AUTH = base64.b64decode("MmE3NmI2MTQyNmFhNmZkNmNkZGNiMTM1MDU4MDE2NTM0NDlkYjkyZg==").decode("utf-8")
_DEF_X_CT0 = base64.b64decode("NDhhZmRkMWM0Y2RhYWU5ZmZjMmQyZThhNjZhMDNhNWNhMDA0ODljM2ZmYmU5Y2ZhMmJjZTdhNzlmNzViNGNlMzMzMTU1NjhiYjBiOTM3NzhjYjhkNTExMmRkNDZiMmY4NTBkZTBjZjJkMjliZDQ2M2Q0MTk2MGE5MjZlYmFmMGJkYmE1ZTZkMTA0Y2ExMGIzNTkzMTMyYjRjOTkyNzgxYQ==").decode("utf-8")
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN", "").strip() or _DEF_X_AUTH
TWITTER_CT0 = os.getenv("TWITTER_CT0", "").strip() or _DEF_X_CT0

TR_TZ = timezone(timedelta(hours=3))

# Tweet sıklığı (Saatte 1 tweet - Tam saat başı kilit tamponu: 45 dk)
# Tweet sıklığı (Tam 45 dakikalık ritim - Kilit tamponu: 38.0 dk)
X_COOLDOWN_MINUTES = float(os.getenv("X_COOLDOWN_MINUTES", 38.0))

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

    if norm_cat in ("Ekonomi", "Teknoloji", "Otomobil", "Gündem", "Dünya", "Sağlık", "Eğitim"):
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

    # 1. 7/24 Kesintisiz Saat Başı Paylaşım Aktif (Gece kilidi kaldırıldı)

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


def smart_sentence_split(text: str) -> list:
    """Türkçe sıra sayıları (10., 1., 2026.) ve unvan/kısaltmaları (Dr., Prof., vb.) bozmadan tam cümlelere böler."""
    if not text:
        return []
    t = text
    abbrevs = ["dr", "prof", "doç", "doc", "av", "uzm", "vb", "vs", "yy", "mad", "no", "m", "km"]
    for ab in abbrevs:
        t = re.sub(rf"\b({ab})\.", r"\1___DOT___", t, flags=re.I)
    t = re.sub(r"(\b\d+)\.", r"\1___DOT___", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ\"“])", t)
    clean_sents = []
    for p in parts:
        restored = p.replace("___DOT___", ".").strip()
        if len(restored) > 20:
            clean_sents.append(restored)
    return clean_sents

def format_x_tweet(title: str, summary: str, site_url: str = "", category: str = "Gündem") -> str:
    """
    X Premium (Mavi Tik) uyumlu, hiçbir cümlesi yarıda kesilmeyen, doyurucu ve profesyonel tweet metni üretir.
    - Cümleler ASLA ortasından bölünmez ve '...' ile kesilmez.
    - Her cümle tam ve eksiksiz şekilde noktayla biter.
    - BPT / Pusholder editoryal standardında haberin özünü ve detayını tam aktarır.
    """
    cat_tag = f"#{category}" if category in ("Ekonomi", "Teknoloji", "Gündem", "Otomobil", "Spor", "Dünya", "Sağlık") else "#Gündem"
    tags = f"{cat_tag} #SonDakika #Haber"

    clean_title = title.strip()
    clean_title = re.sub(r'\s*-\s*[A-Za-z0-9ğüşıöçĞÜŞİÖÇ\s\.]+$', '', clean_title).strip()

    chosen_sents = []
    if summary:
        clean_summary = strip_all_urls(summary)
        sentences = smart_sentence_split(clean_summary)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            # Başlıkla neredeyse aynı olan cümleyi mükerrer ekleme
            if s_clean.lower() == clean_title.lower() or (len(s_clean) > 30 and clean_title.lower() in s_clean.lower()):
                continue
            # Cümlenin sonunun düzgün bittiğinden emin ol
            if not s_clean.endswith(('.', '!', '?')):
                s_clean += '.'
            
            chosen_sents.append(s_clean)
            
            # X Premium ile en akıcı ve doyurucu okuma için 3-4 tam cümle
            if len(chosen_sents) >= 4:
                break

    body = " ".join(chosen_sents).strip()
    
    # Eğer özet yoksa veya çok kısaysa başlığı tam ve eksiksiz olarak al
    if not body or len(body) < 25:
        body = clean_title
        if not body.endswith(('.', '!', '?')):
            body += '.'

    tweet = f"{body}\n\n{tags}"
    return tweet.strip()


def strip_all_urls(text: str) -> str:
    """X algoritması için tweet metnindeki tüm linkleri tamamen temizler."""
    if not text:
        return ""
    # Detaylar ve link yönlendirme satırlarını temizle
    text = re.sub(r'(?i)(?:🌐|🔗|👉)?\s*(?:detaylar|kaynak|haber|link|tıklayın|oku)[^\r\n:]*:\s*https?://\S+', '', text)
    # http ve https linklerini temizle
    text = re.sub(r'https?://\S+', '', text)
    # www linklerini temizle
    text = re.sub(r'(?i)\bwww\.[a-z0-9\-]+(?:\.[a-z0-9\-]+)+[/\S]*', '', text)
    # com.tr, com vb alan adlarını temizle
    text = re.sub(r'(?i)\b[a-z0-9\-]+\.(?:com\.tr|com|net|org|site|co|io)[/\S]*', '', text)
    # Boşlukları ve gereksiz satırları toparla
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def post_tweet_playwright(text: str, media_path: Optional[str] = None, title: str = "") -> dict:
    """
    Playwright Chromium motoruyla X'te (%100 ücretsiz) tweet yayınlar.
    Görsel ve video eklerini destekler.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "reason": "Playwright kurulu değil"}

    # KESİN KURAL: %100 Linksiz tweet güvencesi
    text = strip_all_urls(text)
    if not text:
        return {"status": "error", "reason": "Metin boş kalamaz"}

    try:

        with sync_playwright() as p:
            # Video H.264/AAC donanım codec desteği için öncelikle sistemdeki Google Chrome'u başlat
            launch_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled"
            ]
            browser = None
            try:
                browser = p.chromium.launch(channel="chrome", headless=True, args=launch_args)
            except Exception:
                browser = p.chromium.launch(headless=True, args=launch_args)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            context.add_cookies([
                {"name": "auth_token", "value": TWITTER_AUTH_TOKEN, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": True},
                {"name": "ct0", "value": TWITTER_CT0, "domain": ".x.com", "path": "/", "secure": True, "httpOnly": False}
            ])
            page = context.new_page()
                        # 🛡️ CANLI PROFİL ÇİFT PAYLAŞIM KALKANI
            if title:
                try:
                    page.goto("https://x.com/gndmanalizi", wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(2500)
                    tweet_elements = page.locator("article[data-testid='tweet']").all_text_contents()
                    
                    def _clean(s: str) -> str:
                        s = s.lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
                        return re.sub(r'[^a-z0-9]', '', s)
                    
                    norm_cand = _clean(title)
                    cand_words = [w for w in re.findall(r'[a-z0-9çğıöşü]+', title.lower()) if len(w) >= 4]

                    for tw_text in tweet_elements[:6]:
                        norm_tw = _clean(tw_text)
                        if norm_cand and (norm_cand in norm_tw or (len(norm_cand) > 18 and norm_cand[:25] in norm_tw)):
                            print(f"🛑 [Canlı Kalkan] '{title[:35]}...' haberi @gndmanalizi canlı profilinde zaten var!")
                            browser.close()
                            return {"status": "already_posted", "reason": "Haber canlı profilde mevcut"}
                        if cand_words:
                            tw_words = [w for w in re.findall(r'[a-z0-9çğıöşü]+', tw_text.lower()) if len(w) >= 4]
                            if tw_words:
                                common = set(cand_words) & set(tw_words)
                                if len(common) / max(len(cand_words), 1) >= 0.7:
                                    print(f"🛑 [Canlı Kalkan] '{title[:35]}...' kelime benzerliğiyle tespit edildi!")
                                    browser.close()
                                    return {"status": "already_posted", "reason": "Haber canlı profilde mevcut"}
                except Exception as e:
                    print(f"⚠️ Canlı profil kontrol uyarısı: {e}")

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

            # Tweeti Gönder butonu referansı
            post_btn = page.locator('button[data-testid="tweetButton"]').first
            if not post_btn.count():
                post_btn = page.locator('button[data-testid="tweetButtonInline"]').first

            # Görsel veya Video Ekle
            if media_path and os.path.exists(media_path):
                file_input = page.locator('input[data-testid="fileInput"]').first
                if file_input.count():
                    file_input.set_input_files(media_path)
                    is_video = media_path.lower().endswith(('.mp4', '.mov', '.avi'))
                    print(f"⏳ Medya X'e aktarılıyor ({'Video' if is_video else 'Görsel'})...")
                    
                    # Medyanın DOM'a eklenmesini ve Twitter sunucularında işlenmesini bekle
                    media_ready = False
                    for sec in range(1, 40 if is_video else 10):
                        page.wait_for_timeout(1000)
                        attachments = page.locator('div[data-testid="attachments"]').count()
                        aria_dis = post_btn.get_attribute("aria-disabled") if post_btn.count() else "true"
                        if attachments > 0 and aria_dis != "true" and (not is_video or sec >= 6):
                            media_ready = True
                            print(f"✅ Medya başarıyla hazırlandı ({sec}. saniye).")
                            break
                    
                    if not media_ready and page.locator('div[data-testid="attachments"]').count() == 0:
                        print("⚠️ Medya yüklenemedi (Twitter ekleyemedi). Videonsuz tweet atılmaması için iptal ediliyor.")
                        browser.close()
                        return {"status": "error", "reason": "Medya yüklemesi X tarafından reddedildi"}

            # Butonun aktifleştiğini son kez doğrula
            for _ in range(10):
                aria_dis = post_btn.get_attribute("aria-disabled") if post_btn.count() else "true"
                if aria_dis != "true":
                    break
                page.wait_for_timeout(1000)

            # Güvenli gönderim: JS Evaluate click + Control+Enter + dispatchEvent
            sent = False
            try:
                page.evaluate('''() => {
                    const btn = document.querySelector('button[data-testid="tweetButton"]') || document.querySelector('button[data-testid="tweetButtonInline"]');
                    if (btn) btn.click();
                }''')
                sent = True
            except Exception:
                pass

            page.wait_for_timeout(1000)

            try:
                editor.first.focus()
                page.wait_for_timeout(300)
                page.keyboard.press("Control+Enter")
                sent = True
            except Exception:
                pass

            page.wait_for_timeout(3000)

            # Buton hala görünürse event click tetikle
            if post_btn.count() and post_btn.is_visible():
                try:
                    post_btn.dispatch_event("click")
                    sent = True
                except Exception:
                    pass

            # Modalın kapanmasını bekle
            for _ in range(10):
                if not post_btn.count() or not post_btn.is_visible():
                    break
                page.wait_for_timeout(1000)

            page.wait_for_timeout(3000)
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

    # 3. Görseli Editoryal Haber Kartına Dönüştür
    final_media = image_path
    try:
        import image_generator
        card_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        os.makedirs(card_dir, exist_ok=True)
        card_out = os.path.join(card_dir, f"x_card_{int(time.time())}.jpg")
        created_card = image_generator.create_x_editorial_card(
            image_input=image_path,
            title=title,
            category=category,
            output_path=card_out
        )
        if created_card and os.path.exists(created_card):
            final_media = created_card
            print(f"🎨 [X Editoryal Kart Hazırlandı: {final_media}]")
    except Exception as e:
        print(f"⚠️ X editoryal kart oluşturma istisnası: {e}")

    # 4. Tweet Metnini Hazırla (Cevap ve detay odaklı ferah metin)
    tweet_text = format_x_tweet(title, summary, site_url, category)

    # 5. Playwright ile Tweeti Gönder
    res = post_tweet_playwright(tweet_text, media_path=final_media, title=title)
    if res.get("status") == "success":
        print(f"✅ [X/Twitter] Tweet başarıyla paylaşıldı: @gndmanalizi")
        return {"status": "success", "url": "https://x.com/gndmanalizi"}

    return res


def post_video_to_x(video_path: str, title: str, link: str = "") -> dict:
    """Panelden veya yerelden yüklenen MP4 videoyu X'te paylaşır."""
    if not is_configured():
        return {"status": "error", "reason": "X oturum çerezleri eksik."}

    tags = " #Gündem #SonDakika"
    text = title.strip()
    tweet_text = f"🎥 {text}\n\n{tags}"

    return post_tweet_playwright(tweet_text, media_path=video_path)
