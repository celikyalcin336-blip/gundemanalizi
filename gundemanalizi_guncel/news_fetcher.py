import feedparser
import hashlib
import re
from typing import List, Dict, Optional
import config
import database

def get_news_hash(title: str, link: str) -> str:
    """Haber için benzersiz bir MD5 özeti üretir."""
    normalized = f"{title.strip().lower()}_{link.strip()}"
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def extract_image_url(entry) -> Optional[str]:
    """RSS girdisinden haber görseli URL'sini çıkarmaya çalışır."""
    # 1. media_content kontrolü
    if "media_content" in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get("url")

    # 2. enclosures kontrolü
    if "enclosures" in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href")

    # 3. description veya summary içindeki <img> etiketini arama
    content = entry.get("summary", "") or entry.get("description", "")
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)

    return None

def clean_html(text: str) -> str:
    """HTML etiketlerini temizler."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def fetch_latest_news(limit_per_feed: int = 5) -> List[Dict]:
    """
    Tanımlı RSS kaynaklarını tarar ve daha önce paylaşılmamış en yeni haberleri döner.
    """
    database.init_db()
    unposted_news = []

    for feed_info in config.RSS_FEEDS:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]

        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit_per_feed]:
                title = clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
                image_url = extract_image_url(entry)
                published = entry.get("published", "")

                if not title or not link:
                    continue

                news_hash = get_news_hash(title, link)

                # Daha önce paylaşılmış mı kontrol et
                if not database.is_already_posted(news_hash):
                    unposted_news.append({
                        "hash": news_hash,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "image_url": image_url,
                        "source": feed_name,
                        "published": published
                    })
        except Exception as e:
            print(f"[{feed_name}] RSS okunurken hata oluştu: {e}")

    return unposted_news

if __name__ == "__main__":
    news = fetch_latest_news(limit_per_feed=2)
    print(f"Bulunan yeni haber sayısı: {len(news)}")
    for n in news[:3]:
        print(f"- [{n['source']}] {n['title']} (Görsel: {n['image_url']})")
