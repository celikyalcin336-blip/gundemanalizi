"""
Gündem Analizi - Bağımsız 15 Dakikalık Haber Botu (news_bot.py)
=================================================================
Görev: Siteye ve Telegram kanalına TAM 15 DAKİKADA BİR güncel, tekrarsız haber basmak.

Temel kurallar:
1. Zamanlama "slot" (yuva) mantığıyla çalışır: Her yayın, bir önceki yayının PLANLANAN
   saatine +900 sn eklenerek hesaplanır. Böylece süre asla kaymaz (16, 17, 24 dk olmaz).
2. Botun saati veritabanındaki kendi anahtarında (system_settings: newsbot_last_slot) tutulur.
   - Yalçın Bey'in panelden attığı manuel haber/videolar bu sayacı ETKİLEMEZ.
   - Render yeniden başlasa/deploy olsa bile saat veritabanında kaldığı için kaybolmaz.
3. Erken hazırlık: Haber (kaynak tarama + AI metin + görsel) yayın saatinden 3 dk önce
   hazırlanır, tam yayın saniyesinde siteye ve Telegram'a basılır.
4. Çift yayın kilidi: Deploy sırasında 2 sunucu kısa süre aynı anda açık kalsa bile
   veritabanı üzerinde "compare-and-swap" kilidiyle o slotu yalnızca BİR sunucu yayınlar.
5. Tazelik: Önce son 6 saatin haberleri; havuz boşsa 24 saate genişler.
6. Tekrarsızlık: Hash + link + başlık + slug + benzerlik (%80) + kelime kökü örtüşmesi.
   Kontroller tek seferde belleğe alınan geçmiş üzerinde yapılır (hızlı), yayından hemen
   önce bir kez de veritabanında son kontrol yapılır.
"""

import os
import re
import sys
import time
import difflib
import threading
from calendar import timegm
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

import requests
import feedparser

import config
import database
import news_fetcher
import ai_writer
import image_generator
import telegram_notifier

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ----------------------------------------------------------------------------
# AYARLAR
# ----------------------------------------------------------------------------
INTERVAL_SEC = 900          # Tam 15 dakika
PREP_LEAD_SEC = 180         # Yayın saatinden 3 dk önce hazırlığa başla
LATE_TOLERANCE_SEC = 60     # Bu kadar gecikirse yeni yayın saati baz alınır
FEED_TIMEOUT_SEC = 10       # Her RSS kaynağı için en fazla bekleme
FRESH_HOURS_PRIMARY = 6     # Öncelikli tazelik penceresi
FRESH_HOURS_FALLBACK = 24   # Havuz boşsa genişletilmiş pencere
MAX_PREP_ATTEMPTS = 5       # Hazırlanamayan haber olursa sıradaki adaya geç

SLOT_KEY = "newsbot_last_slot"
LAST_CAT_KEY = "newsbot_last_cat"
LAST_TITLE_KEY = "newsbot_last_title"

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

_STOPWORDS = {
    've', 'ile', 'bir', 'bu', 'da', 'de', 'ta', 'te', 'icin', 'için', 'yeni', 'son', 'dakika',
    'gore', 'göre', 'kadar', 'olan', 'olarak', 'eden', 'etti', 'yaptı', 'oldu', 'belli',
    'işte', 'iste', 'hakkında', 'neden', 'hangi', 'kimdir', 'nereli', 'kaç'
}

_started = False
_start_lock = threading.Lock()


def log(msg: str):
    ts = datetime.now(database.TR_TZ).strftime("%H:%M:%S")
    print(f"[NewsBot {ts}] {msg}", flush=True)


# ----------------------------------------------------------------------------
# ZAMAN KİLİDİ (Veritabanında kalıcı, manuel paylaşımlardan bağımsız)
# ----------------------------------------------------------------------------
def _ensure_slot_row():
    with database.get_connection() as conn:
        if conn.is_pg:
            conn.execute(
                "INSERT INTO system_settings (key, val) VALUES (?, ?) ON CONFLICT (key) DO NOTHING",
                (SLOT_KEY, "0"))
        else:
            conn.execute("INSERT OR IGNORE INTO system_settings (key, val) VALUES (?, ?)", (SLOT_KEY, "0"))


def _read_slot_raw() -> str:
    return database.get_setting(SLOT_KEY, "")


def _claim_slot(prev_raw: str, new_slot: int) -> bool:
    """Compare-and-swap: Slot değeri hâlâ prev_raw ise new_slot yazar. Başka sunucu kaptıysa False."""
    try:
        with database.get_connection() as conn:
            cur = conn.execute(
                "UPDATE system_settings SET val = ? WHERE key = ? AND val = ?",
                (str(int(new_slot)), SLOT_KEY, prev_raw))
            return (cur.rowcount or 0) == 1
    except Exception as e:
        log(f"Slot kilidi hatası: {e}")
        return False


def _bootstrap_last_slot() -> int:
    """İlk çalıştırmada (anahtar yoksa) botun son yayınından başlat; yoksa hemen yayınla."""
    now = int(time.time())
    try:
        with database.get_connection() as conn:
            row = conn.execute("SELECT MAX(created_at) AS m FROM posted_news").fetchone()
            val = row["m"] if row else None
        if val:
            if isinstance(val, datetime):
                dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.strptime(str(val).split(".")[0].replace("T", " ")[:19],
                                       "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            ts = int(dt.timestamp())
            if 0 < now - ts < 24 * 3600:
                return ts
    except Exception as e:
        log(f"Başlangıç zamanı okunamadı: {e}")
    return now - INTERVAL_SEC


def _get_last_slot() -> (str, int):
    raw = _read_slot_raw()
    if not raw or raw == "0":
        _ensure_slot_row()
        raw = _read_slot_raw() or "0"
        if raw == "0":
            boot = _bootstrap_last_slot()
            if _claim_slot("0", boot):
                raw = str(boot)
            else:
                raw = _read_slot_raw()
    try:
        return raw, int(float(raw))
    except Exception:
        return raw, int(time.time()) - INTERVAL_SEC


# ----------------------------------------------------------------------------
# TEKRAR KONTROLÜ (Bellekte, tek veritabanı okumasıyla)
# ----------------------------------------------------------------------------
def _stems(text: str) -> set:
    out = set()
    for w in re.findall(r"\w+", (text or "").lower()):
        if len(w) >= 3 and w not in _STOPWORDS:
            out.add(w[:5])
    return out


class _History:
    def __init__(self):
        self.hashes, self.links, self.titles, self.slugs = set(), set(), [], set()
        try:
            with database.get_connection() as conn:
                for r in conn.execute(
                        "SELECT news_hash, link, title FROM posted_news ORDER BY id DESC LIMIT 3000").fetchall():
                    if r["news_hash"]:
                        self.hashes.add(r["news_hash"])
                    if r["link"]:
                        self.links.add(r["link"].strip())
                    if r["title"]:
                        self.titles.append(r["title"].strip().lower())
                for r in conn.execute(
                        "SELECT title, slug FROM articles ORDER BY id DESC LIMIT 400").fetchall():
                    if r["title"]:
                        self.titles.append(r["title"].strip().lower())
                    if r["slug"]:
                        self.slugs.add(re.sub(r"-\d+$", "", r["slug"].strip().lower()))
        except Exception as e:
            log(f"Geçmiş okunamadı: {e}")
        # Benzerlik kontrolü için son 400 başlık yeterli (performans)
        self.recent_titles = self.titles[:400]
        self.recent_stems = [_stems(t) for t in self.recent_titles]

    def is_dup(self, news_hash: str, link: str, title: str) -> bool:
        if news_hash in self.hashes or (link and link.strip() in self.links):
            return True
        t = title.strip().lower()
        slug = re.sub(r"-\d+$", "", database.slugify(title))
        if slug in self.slugs:
            return True
        st = _stems(t)
        for prev, prev_st in zip(self.recent_titles, self.recent_stems):
            if difflib.SequenceMatcher(None, t, prev).ratio() > 0.80:
                return True
            if len(st) >= 4 and len(prev_st) >= 4:
                if len(st & prev_st) / min(len(st), len(prev_st)) >= 0.80:
                    return True
        return False

    def add(self, title: str):
        t = title.strip().lower()
        self.recent_titles.insert(0, t)
        self.recent_stems.insert(0, _stems(t))


# ----------------------------------------------------------------------------
# KAYNAK TARAMA (Paralel + zaman aşımlı: Asla takılıp kalmaz)
# ----------------------------------------------------------------------------
def _fetch_feed(feed_info: dict) -> list:
    try:
        r = requests.get(feed_info["url"], headers=_UA, timeout=FEED_TIMEOUT_SEC)
        if r.status_code != 200:
            return []
        parsed = feedparser.parse(r.content)
        return [(feed_info, e) for e in parsed.entries[:15]]
    except Exception:
        return []


def _collect_candidates() -> list:
    feeds = list(getattr(config, "RSS_FEEDS", []))
    raw = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(_fetch_feed, feeds):
            raw.extend(res)

    history = _History()
    now = time.time()
    items, batch_titles = [], []

    for feed_info, entry in raw:
        try:
            title = news_fetcher.sanitize_news_text(news_fetcher.clean_html(entry.get("title", "")))
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            # Canlı maç anlatım sayfaları haber değildir
            if re.search(r"\|\s*CANLI|canlı izle|canlı anlatım", title, flags=re.I):
                continue
            summary = news_fetcher.sanitize_news_text(
                news_fetcher.clean_html(entry.get("summary", "") or entry.get("description", "")))

            pub_ts = None
            if entry.get("published_parsed"):
                try:
                    pub_ts = timegm(entry.published_parsed)  # RSS zamanları UTC'dir
                except Exception:
                    pub_ts = None
            age_h = (now - pub_ts) / 3600.0 if pub_ts else None
            if age_h is not None and age_h > FRESH_HOURS_FALLBACK:
                continue

            try:
                if news_fetcher.is_valueless_clickbait(title, summary):
                    continue
            except Exception:
                pass

            news_hash = news_fetcher.get_news_hash(title, link)
            if history.is_dup(news_hash, link, title):
                continue

            # Aynı taramada farklı kaynaklardan gelen aynı haber
            tl = title.lower()
            if any(difflib.SequenceMatcher(None, tl, p).ratio() > 0.75 for p in batch_titles):
                continue
            batch_titles.append(tl)

            feed_cat = feed_info.get("category", "Gündem")
            try:
                category = ai_writer.classify_article(title, summary, feed_cat)
            except Exception:
                category = feed_cat

            items.append({
                "hash": news_hash,
                "title": title,
                "summary": summary,
                "link": link,
                "image_url": news_fetcher.extract_image_url(entry),
                "source": feed_info.get("name", ""),
                "category": category or feed_cat,
                "pub_ts": pub_ts or 0,
                "age_h": age_h if age_h is not None else 99.0,
            })
        except Exception:
            continue

    log(f"Tarama bitti: {len(raw)} girdi, {len(items)} taze & tekrarsız aday.")
    return items


def _slot_categories() -> list:
    h = datetime.now(database.TR_TZ)
    h = h.hour + h.minute / 60.0
    if 7.0 <= h < 10.5:
        return ["Ekonomi", "Gündem", "Otomobil"]
    if 10.5 <= h < 16.5:
        return ["Teknoloji", "Otomobil", "Gündem", "Sağlık", "Eğitim"]
    if 16.5 <= h < 23.0:
        return ["Spor", "Gündem", "Ekonomi"]
    return ["Dünya", "Teknoloji", "Otomobil", "Gündem"]


def _rank(items: list) -> list:
    """Önce tazelik penceresi, sonra kuşak kategorisi rotasyonu, sonra en yeni haber."""
    fresh = [i for i in items if i["age_h"] <= FRESH_HOURS_PRIMARY] or items
    cats = _slot_categories()
    last_cat = database.get_setting(LAST_CAT_KEY, "")
    if last_cat in cats:
        idx = (cats.index(last_cat) + 1) % len(cats)
        cats = cats[idx:] + cats[:idx]

    def key(i):
        cat_rank = cats.index(i["category"]) if i["category"] in cats else len(cats)
        has_img = 0 if i.get("image_url") else 1
        return (cat_rank, has_img, -i["pub_ts"])

    return sorted(fresh, key=key)


# ----------------------------------------------------------------------------
# HAZIRLIK ve YAYIN
# ----------------------------------------------------------------------------
def _prepare(item: dict) -> dict:
    """Haberin tüm içeriğini (metin + görsel) yayın öncesi hazırlar. Siteye/Telegram'a henüz basmaz."""
    title, source, link = item["title"], item["source"], item["link"]
    details = news_fetcher.fetch_article_details(link) or {}
    body = details.get("body", "") or ""
    summary = body if len(body) > len(item.get("summary", "")) else item.get("summary", "")

    telegram_caption = ai_writer.generate_telegram_post(title, summary, source)
    article = ai_writer.generate_full_article(title, summary, source, force_category=item.get("category"))
    category = article.get("category") or item.get("category") or "Gündem"

    images = list(details.get("images", []) or [])
    if item.get("image_url") and item["image_url"] not in images:
        images.append(item["image_url"])
    visual_path = image_generator.create_news_visual(
        candidate_urls=images,
        output_filename=f"post_{item['hash'][:10]}.jpg",
        title=title,
        category=category,
    )
    return {"item": item, "article": article, "category": category,
            "telegram_caption": telegram_caption, "visual_path": visual_path}


def _prepare_next() -> dict:
    candidates = _rank(_collect_candidates())
    for item in candidates[:MAX_PREP_ATTEMPTS]:
        try:
            prep = _prepare(item)
            log(f"Hazır: [{prep['category']}] {item['title'][:70]}")
            return prep
        except Exception as e:
            log(f"Hazırlanamadı ({item['title'][:40]}): {e} -> sıradaki aday")
    return None


def _publish(prep: dict) -> bool:
    item, article = prep["item"], prep["article"]
    # Son saniye tekrar kontrolü (veritabanında)
    if database.is_already_posted(item["hash"], title=item["title"], link=item["link"]):
        log("Son kontrolde tekrar tespit edildi, yayınlanmadı.")
        return False

    slug = database.save_article(
        title=article["title"], summary=article["summary"], content=article["content"],
        image_path=prep["visual_path"], source=item["source"], category=prep["category"])
    database.mark_as_posted(news_hash=item["hash"], title=item["title"],
                            source=item["source"], link=item["link"])
    site_url = f"{config.SITE_URL}/haber/{slug}"
    log(f"🌐 SİTEDE YAYINDA: {site_url}")

    try:
        ok = telegram_notifier.send_telegram_news(prep["visual_path"], prep["telegram_caption"], site_url)
        log("📲 Telegram'a gönderildi." if ok else "⚠️ Telegram gönderimi başarısız.")
    except Exception as e:
        log(f"⚠️ Telegram hatası: {e}")

    database.set_setting(LAST_CAT_KEY, prep["category"])
    database.set_setting(LAST_TITLE_KEY, item["title"][:200])

    def _index():
        try:
            import google_indexer
            google_indexer.notify_google_indexing(site_url)
        except Exception:
            pass
    threading.Thread(target=_index, daemon=True).start()
    return True


# ----------------------------------------------------------------------------
# ANA DÖNGÜ
# ----------------------------------------------------------------------------
def _sleep_until(ts: float):
    while True:
        rem = ts - time.time()
        if rem <= 0:
            return
        time.sleep(min(rem, 20))


def run_forever():
    time.sleep(8)
    log("🚀 15 dakikalık haber botu devrede (site + Telegram).")
    while True:
        try:
            prev_raw, last_slot = _get_last_slot()
            now = time.time()
            target = last_slot + INTERVAL_SEC
            if now > target + LATE_TOLERANCE_SEC:
                target = int(now)  # Sunucu kapalıyken slot kaçtıysa: hemen yayınla, yeni saat bu olsun
            log(f"Sıradaki yayın: {datetime.fromtimestamp(target, database.TR_TZ).strftime('%H:%M:%S')}")

            _sleep_until(target - PREP_LEAD_SEC)

            # Başka sunucu (deploy sırasında) bu arada yayın yaptıysa baştan hesapla
            if _read_slot_raw() != prev_raw:
                continue

            prep = None
            while prep is None:
                prep = _prepare_next()
                if prep is None:
                    log("Uygun taze haber bulunamadı, 30 sn sonra tekrar taranacak.")
                    time.sleep(30)
                    if _read_slot_raw() != prev_raw:
                        break
            if prep is None:
                continue

            _sleep_until(target)

            now = time.time()
            new_slot = int(now) if now - target > LATE_TOLERANCE_SEC else int(target)
            if not _claim_slot(prev_raw, new_slot):
                log("Bu slot başka bir sunucu tarafından yayınlandı, atlanıyor.")
                continue

            if not _publish(prep):
                # Yayın olmadıysa slotu geri al ki hemen yeni haberle denensin
                _claim_slot(str(new_slot), new_slot - INTERVAL_SEC)
        except Exception as e:
            log(f"Döngü hatası: {e}")
            time.sleep(20)


def start_in_background():
    """web_server açılışında bir kez çağrılır."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
    threading.Thread(target=run_forever, name="NewsBot15", daemon=True).start()


def status() -> dict:
    raw = _read_slot_raw()
    try:
        last = int(float(raw))
    except Exception:
        last = 0
    fmt = lambda t: datetime.fromtimestamp(t, database.TR_TZ).strftime("%Y-%m-%d %H:%M:%S") if t else "-"
    return {
        "son_yayin": fmt(last),
        "siradaki_yayin": fmt(last + INTERVAL_SEC) if last else "-",
        "son_baslik": database.get_setting(LAST_TITLE_KEY, ""),
        "son_kategori": database.get_setting(LAST_CAT_KEY, ""),
        "aralik_sn": INTERVAL_SEC,
    }
