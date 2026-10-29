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
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history[-200:], f, ensure_ascii=False, indent=2)
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


def run_cycle(force: bool = False) -> bool:
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

    history = load_history()
    posted_slugs = {h.get("slug") for h in history if isinstance(h, dict)}
    posted_titles = {h.get("title") for h in history if isinstance(h, dict)}

    for art in articles:
        title = art.get("title", "").strip()
        summary = art.get("summary", "").strip()
        category = art.get("category", "Gündem")
        slug = art.get("slug", "")
        site_url = art.get("site_url", "")

        if not title or slug in posted_slugs or title in posted_titles:
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
            print(f"⚠️ Paylaşım hatası ({res}), sıradaki haber deneniyor...")
            continue

    print("ℹ️ Şu an paylaşılacak yeni kaliteli haber bulunamadı.")
    return False


if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    run_cycle(force=force_mode)
