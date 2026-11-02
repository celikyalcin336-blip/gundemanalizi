"""
X (Twitter) 7/24 Bağımsız Bulut & Yerel Döngüsü (@gndmanalizi)
- Canlı sitedeki /api/articles ve /rss.xml akışını tarar.
- Saat başı (55 dk kilit tamponuyla) 1 adet yüksek değerli, fotoğraflı tweet yayınlar.
"""
import json
import os
import sys
import time
import urllib.request
import feedparser
import requests
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_PATH = os.path.join(BASE_DIR, "x_daemon.log")
if sys.stdout is None or sys.stderr is None:
    _log_f = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log_f
    sys.stderr = _log_f
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

import config
import x_poster

HISTORY_FILE = os.path.join(BASE_DIR, "x_posted_history.json")
TEMP_IMG_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(TEMP_IMG_DIR, exist_ok=True)


def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history: list):
    """Paylaşılan (posted) kayıtlar ASLA atlanan kayıtlar yüzünden silinmez.
    Son 400 paylaşım + son 150 atlama kaydı tutulur (mükerrer kalkanı hafızası)."""
    try:
        posted = [h for h in history if isinstance(h, dict) and h.get("status") == "posted"][-400:]
        others = [h for h in history if isinstance(h, dict) and h.get("status") != "posted"][-150:]
        merged = sorted(posted + others, key=lambda h: float(h.get("ts", 0) or 0))
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Geçmiş kaydedilemedi: {e}")


def get_latest_articles_pool() -> list:
    """Önce canlı sitedeki /api/articles uç noktasından (gerçek kategorileriyle), yedek olarak RSS'ten çeker."""
    articles = []
    try:
        req = urllib.request.Request(
            "https://xn--gndemanalizi-dlb.com.tr/api/articles?limit=40",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for a in data:
            slug = (a.get("slug") or "").strip()
            img_p = (a.get("image_path") or "").strip()
            safe_img = os.path.basename(img_p.replace("\\", "/")).split("?")[0] if img_p else ""
            img_url = f"https://xn--gndemanalizi-dlb.com.tr/images/{safe_img}?v=3" if safe_img else ""
            articles.append({
                "title": (a.get("title") or "").strip(),
                "summary": (a.get("summary") or "").strip(),
                "category": (a.get("category") or "Gündem").strip(),
                "slug": slug,
                "site_url": f"https://xn--gndemanalizi-dlb.com.tr/haber/{slug}",
                "image_url": img_url,
                "source": "api"
            })
    except Exception as e:
        print(f"⚠️ Canlı API okunamadı ({e}), RSS deneniyor...")

    if not articles:
        rss_url = "https://xn--gndemanalizi-dlb.com.tr/rss.xml"
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                img_url = entry.enclosures[0].href if (hasattr(entry, "enclosures") and entry.enclosures) else None
                slug = entry.link.rstrip("/").split("/")[-1]
                articles.append({
                    "title": entry.title,
                    "summary": getattr(entry, "description", ""),
                    "category": getattr(entry, "category", "Gündem") or "Gündem",
                    "slug": slug,
                    "site_url": entry.link,
                    "image_url": img_url,
                    "source": "rss"
                })
        except Exception as e:
            print(f"⚠️ RSS okunamadı: {e}")

    return articles


def normalize_text_loose(t: str) -> str:
    if not t:
        return ""
    t = t.lower().replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return re.sub(r'[^a-z0-9\s]', ' ', t)


def extract_key_entities(text: str) -> set:
    """Metindeki özel isimleri ve kilit kurum/kişi adlarını çıkarır."""
    if not text:
        return set()
    proper_nouns = re.findall(r'\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]{3,}\b', text)
    acronyms = re.findall(r'\b[A-ZÇĞİÖŞÜ]{2,}\b', text)
    res = set(p.lower() for p in proper_nouns + acronyms)
    common_stops = {"turkiye", "bakan", "baskani", "haber", "bugun", "resmi", "karar", "sayisi", "yeni", "donem"}
    return res - common_stops


def is_duplicate_story(candidate_title: str, candidate_summary: str, candidate_slug: str, history: list) -> tuple:
    """
    Haberin başlığı tamamen farklı olsa bile; içerik, özet, kişi ve kurum adlarını
    tarayarak aynı olayın ikinci kez paylaşılmasını %100 engeller.
    """
    cand_norm_title = normalize_text_loose(candidate_title)
    cand_title_words = set(w for w in cand_norm_title.split() if len(w) >= 4)
    cand_entities = extract_key_entities(candidate_title + " " + candidate_summary)
    cand_norm_summary = normalize_text_loose(candidate_summary)[:200]
    cand_sum_words = set(w for w in cand_norm_summary.split() if len(w) >= 4)

    for h in history:
        if not isinstance(h, dict):
            continue
        h_slug = h.get("slug", "")
        h_title = h.get("title", "")
        h_summary = h.get("summary", "")

        # 1. Birebir Slug veya Başlık Eşleşmesi
        if candidate_slug and candidate_slug == h_slug:
            return True, f"Birebir slug eşleşmesi: {h_slug}"

        # Aşağıdaki benzerlik kontrolleri yalnızca GERÇEKTEN paylaşılmış haberlerle yapılır
        if h.get("status") != "posted":
            continue
        
        h_norm_title = normalize_text_loose(h_title)
        if cand_norm_title and h_norm_title:
            if cand_norm_title == h_norm_title:
                return True, f"Birebir başlık eşleşmesi: {h_title[:35]}"
            if len(cand_norm_title) > 20 and cand_norm_title in h_norm_title:
                return True, f"Başlık içerme: {h_title[:35]}"
            if len(h_norm_title) > 20 and h_norm_title in cand_norm_title:
                return True, f"Başlık içerme: {h_title[:35]}"

        # 2. Başlık Kelime Benzerliği (%70+)
        if cand_title_words:
            h_title_words = set(w for w in h_norm_title.split() if len(w) >= 4)
            if h_title_words:
                common = cand_title_words & h_title_words
                if len(common) / max(len(cand_title_words), 1) >= 0.7:
                    return True, f"Başlık kelime benzerliği ({len(common)} kelime): {h_title[:35]}"

        # 3. İÇERİK & ÖZET BENZERLİĞİ (Farklı başlıkla aynı haber tekrar gelirse!)
        if h_summary and candidate_summary:
            import difflib
            h_norm_summary = normalize_text_loose(h_summary)[:200]
            ratio = difflib.SequenceMatcher(None, cand_norm_summary, h_norm_summary).ratio()
            if ratio >= 0.45:
                return True, f"Özet/İçerik benzerliği (%{int(ratio*100)} aynı metin): {h_title[:35]}"

            h_sum_words = set(w for w in h_norm_summary.split() if len(w) >= 4)
            if cand_sum_words and h_sum_words:
                sum_common = cand_sum_words & h_sum_words
                if len(sum_common) >= 7 and len(sum_common) / max(len(cand_sum_words), 1) >= 0.45:
                    return True, f"Özet ortak terimleri ({len(sum_common)} kelime): {h_title[:35]}"

        # 4. KİŞİ / KURUM / OLAY VARLIK EŞLEŞMESİ (Örn: Muhsin Atcı + SPK veya Conceiçao + Fenerbahçe)
        h_entities = extract_key_entities(h_title + " " + h_summary)
        if cand_entities and h_entities:
            common_ent = cand_entities & h_entities
            if len(common_ent) >= 2:
                return True, f"Ortak varlıklar ({', '.join(list(common_ent)[:2])}): {h_title[:35]}"

        # 5. SPOR KULÜBÜ KORUMASI: Son 6 saatte aynı kulüp hakkında haber paylaşıldıysa mükerrer say
        MAJOR_CLUBS = ["fenerbahce", "galatasaray", "besiktas", "trabzonspor"]
        cand_lower = cand_norm_title.lower()
        h_lower = h_norm_title.lower()
        for club in MAJOR_CLUBS:
            if club in cand_lower and club in h_lower:
                try:
                    h_ts = float(h.get("ts", 0))
                    if time.time() - h_ts < 21600:  # 6 saat kilit
                        return True, f"Aynı kulüp ({club.title()}) son 6 saatte paylaşıldı: {h_title[:35]}"
                except Exception:
                    pass

    return False, ""


def run_cycle(force: bool = False, max_attempts: int = 3) -> bool:
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] 🚀 [X Auto-Poster] Kontrol başlatılıyor...")

    allowed, reason = x_poster.can_post_to_x(force=force)
    if not allowed:
        print(f"⏳ [X Auto-Poster] {reason}")
        return False

    articles = get_latest_articles_pool()
    if not articles:
        print("ℹ️ Şu an taranacak haber bulunamadı.")
        return False

    # 🚀 VİRALLİK SIRALAMASI: En yüksek etkileşim, son dakika ve halkın ilgisini çeken haberi en başa al
    try:
        import news_fetcher
        for art in articles:
            art["virality_score"] = news_fetcher.calculate_virality_score(
                art.get("title", ""),
                art.get("summary", ""),
                art.get("category", "")
            )
        articles.sort(key=lambda x: x.get("virality_score", 0), reverse=True)
    except Exception as e:
        print(f"⚠️ Virallik puanı sıralama uyarısı: {e}")

    history = load_history()
    posted_slugs = {h.get("slug") for h in history if isinstance(h, dict)}
    posted_titles = {h.get("title") for h in history if isinstance(h, dict)}

    attempts = 0
    for art in articles:
        if attempts >= max_attempts:
            print(f"⚠️ {max_attempts} paylaşım denemesi başarısız oldu, bu tur sonlandırılıyor.")
            break
        title = art.get("title", "").strip()
        summary = art.get("summary", "").strip()
        category = art.get("category", "Gündem")
        slug = art.get("slug", "")
        site_url = art.get("site_url", "")

        dup, dup_reason = is_duplicate_story(title, summary, slug, history)
        if not title or dup:
            if dup:
                print(f"⏩ [Mükerrer Haber Kalkanı] Atlandı: {title[:35]}... ({dup_reason})")
            continue

        worthy, w_reason = x_poster.is_worthy_for_x(title, summary, category)
        if not worthy:
            history.append({"slug": slug, "title": title, "status": "skipped", "reason": w_reason, "ts": time.time()})
            save_history(history)
            print(f"⏩ [Kalite Filtresi] Atlandı ({title[:35]}...): {w_reason}")
            continue

        local_img = art.get("image_path")
        if not local_img and art.get("image_url"):
            try:
                img_resp = requests.get(art["image_url"], timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if img_resp.status_code == 200 and len(img_resp.content) > 4000:
                    temp_img_path = os.path.join(TEMP_IMG_DIR, f"x_temp_{slug[:20]}.jpg")
                    with open(temp_img_path, "wb") as f:
                        f.write(img_resp.content)
                    local_img = temp_img_path
            except Exception as e:
                print(f"⚠️ Görsel indirilemedi: {e}")

        if not local_img or not os.path.exists(local_img):
            print(f"⏩ [Görsel Zorunlu] Görseli olmayan haber atlandı: {title[:40]}")
            continue

        attempts += 1
        print(f"🎯 [X Paylaşım Adayı] Kategori: {category} | Virallik/Duygu Skoru: {art.get('virality_score', 0)} | Başlık: {title}")

        res = x_poster.post_article_to_x(
            title=title,
            summary=summary,
            site_url=site_url,
            image_path=local_img,
            category=category,
            force=force
        )

        if res.get("status") == "success":
            history.append({
                "slug": slug,
                "title": title,
                "summary": summary[:250],
                "status": "posted",
                "url": res.get("url"),
                "ts": time.time()
            })
            save_history(history)
            print(f"🎉 [X Auto-Poster] Başarıyla tweetlendi: {title}")
            return True
        elif res.get("status") == "already_posted":
            history.append({
                "slug": slug,
                "title": title,
                "status": "posted",
                "url": res.get("url", "https://x.com/gndmanalizi"),
                "ts": time.time()
            })
            save_history(history)
            print(f"🛡️ [X Auto-Poster] Canlı profilde zaten tespit edildi, mükerrer önlendi: {title}")
            continue
        elif res.get("status") == "uncertain":
            history.append({
                "slug": slug,
                "title": title,
                "summary": summary[:250],
                "status": "posted",
                "url": "https://x.com/gndmanalizi",
                "note": "uncertain",
                "ts": time.time()
            })
            save_history(history)
            print(f"⚠️ [X Auto-Poster] Gönderim sonucu belirsiz; mükerrer riskine karşı paylaşıldı sayıldı: {title}")
            return True
        else:
            print(f"⚠️ Paylaşım hatası ({res}), sıradaki haber deneniyor...")
            continue

    print("ℹ️ Şu an paylaşılacak yeni kaliteli haber bulunamadı.")
    return False


if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    run_cycle(force=force_mode)
