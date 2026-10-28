"""
X (Twitter) 7/24 Bağımsız Bulut & Yerel Döngüsü
- Hem GitHub Actions'ta (Bulut) hem yerel PC'de sorunsuz çalışır.
- Canlı sitedeki RSS akışını (https://xn--gndemanalizi-dlb.com.tr/rss.xml) ve yerel veritabanını tarar.
- 45 dakikada 1 adet yüksek değerli, fotoğraflı tweet yayınlar.
- Geceleri (01:30 - 07:30) sessiz moda geçerek hesabı korur.
"""
import os
import sys
import time
import json
import requests
import feedparser

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
import x_poster

BASE_DIR = os.path.dirname(__file__)
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
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Geçmiş kaydedilemedi: {e}")


def get_latest_articles_pool() -> list:
    """Önce canlı sitedeki RSS akışından, alternatif olarak yerel veritabanından haberleri çeker."""
    articles = []

    # 1. Canlı RSS Akışı (Her zaman en güncel ve bulut dostu)
    rss_url = "https://xn--gndemanalizi-dlb.com.tr/rss.xml"
    try:
        feed = feedparser.parse(rss_url)
        if feed.entries:
            for entry in feed.entries:
                img_url = None
                if hasattr(entry, "enclosures") and entry.enclosures:
                    img_url = entry.enclosures[0].href

                slug = entry.link.rstrip("/").split("/")[-1]
                articles.append({
                    "title": entry.title,
                    "summary": entry.description,
                    "category": getattr(entry, "category", "Gündem") or "Gündem",
                    "slug": slug,
                    "site_url": entry.link,
                    "image_url": img_url,
                    "source": "rss"
                })
    except Exception as e:
        print(f"⚠️ Canlı RSS okunamadı ({e}), veritabanına bakılıyor...")

    # 2. Yerel Veritabanı Yedek Kanalı
    if not articles:
        try:
            import database
            db_arts = database.get_articles(limit=15)
            for art in db_arts:
                slug = art.get("slug", "")
                articles.append({
                    "title": art.get("title", ""),
                    "summary": art.get("summary", ""),
                    "category": art.get("category", "Gündem"),
                    "slug": slug,
                    "site_url": f"{config.SITE_URL}/haber/{slug}",
                    "image_path": art.get("image_path", ""),
                    "source": "db"
                })
        except Exception as e:
            print(f"⚠️ Veritabanı sorgulanamadı: {e}")

    return articles


def run_cycle(force: bool = False):
    print("🚀 [X Auto-Poster] Kontrol başlatılıyor...")

    # 1. Zaman ve Sessiz Saat Kontrolü
    allowed, reason = x_poster.can_post_to_x(force=force)
    if not allowed:
        print(f"⏳ [X Auto-Poster] {reason}")
        return False

    # 2. Haber Havuzunu Al
    articles = get_latest_articles_pool()
    if not articles:
        print("ℹ️ Şu an taranacak haber bulunamadı.")
        return False

    history = load_history()
    posted_slugs = {h.get("slug") for h in history if isinstance(h, dict)}
    posted_titles = {h.get("title") for h in history if isinstance(h, dict)}

    for art in articles:
        title = art.get("title", "").strip()
        summary = art.get("summary", "").strip()
        category = art.get("category", "Gündem")
        slug = art.get("slug", "")
        site_url = art.get("site_url", "")

        # Bu haber daha önce atıldı mı?
        if slug in posted_slugs or title in posted_titles:
            continue

        # Kalite Filtresi (Çöp, magazin ve küçük kazaları ele)
        worthy, w_reason = x_poster.is_worthy_for_x(title, summary, category)
        if not worthy:
            history.append({"slug": slug, "title": title, "status": "skipped", "reason": w_reason, "ts": time.time()})
            save_history(history)
            print(f"⏩ [Kalite Filtresi] Atlandı ({title[:35]}...): {w_reason}")
            continue

        # Görseli hazırla
        local_img = art.get("image_path")
        if not local_img and art.get("image_url"):
            # Görseli URL'den indir
            try:
                img_resp = requests.get(art["image_url"], timeout=15)
                if img_resp.status_code == 200:
                    temp_img_path = os.path.join(TEMP_IMG_DIR, f"x_temp_{slug[:20]}.jpg")
                    with open(temp_img_path, "wb") as f:
                        f.write(img_resp.content)
                    local_img = temp_img_path
            except Exception as e:
                print(f"⚠️ Görsel indirilemedi: {e}")

        # Onaylı Aday!
        print(f"🎯 [X Paylaşım Adayı] Kategori: {category} | Başlık: {title}")

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
                "status": "posted",
                "url": res.get("url"),
                "ts": time.time()
            })
            save_history(history)
            print(f"🎉 [X Auto-Poster] Başarıyla tweetlendi: {title}")
            return True
        else:
            print(f"⚠️ Paylaşım sonucu: {res}")
            return False

    print("ℹ️ Şu an paylaşılacak yeni kaliteli haber bulunamadı.")
    return False


if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    run_cycle(force=force_mode)
