"""
Veritabanı katmanı.

İki modda çalışır:
- DATABASE_URL ortam değişkeni tanımlıysa: PostgreSQL (kalıcı bulut veritabanı, ör. Neon)
- Tanımlı değilse: yerel SQLite (data/news_bot.db)

Haber kartı görselleri de PostgreSQL modunda veritabanında saklanır; böylece
Render ücretsiz planında sunucu yeniden başlasa bile haberler ve görseller kaybolmaz.
"""
import sqlite3
import os
import re
import unicodedata
from typing import List, Dict, Optional

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "news_bot.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2
    import psycopg2.extras


class _Conn:
    """sqlite3 / psycopg2 farkını gizleyen küçük sarmalayıcı."""

    def __init__(self):
        if USE_PG:
            self.raw = psycopg2.connect(DATABASE_URL)
        else:
            os.makedirs(DB_DIR, exist_ok=True)
            self.raw = sqlite3.connect(DB_PATH)
            self.raw.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()):
        if USE_PG:
            sql = sql.replace("?", "%s")
            cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()


def get_connection():
    return _Conn()


def _row_to_dict(row) -> Dict:
    d = dict(row)
    # PostgreSQL datetime nesnelerini, SQLite ile aynı metin formatına çevir
    if d.get("created_at") is not None and not isinstance(d["created_at"], str):
        d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S")
    return d


def slugify(text: str) -> str:
    """Türkçe başlığı SEO dostu URL slug'ına dönüştürür."""
    tr_map = {
        'ç': 'c', 'Ç': 'c', 'ğ': 'g', 'Ğ': 'g', 'ı': 'i', 'I': 'i',
        'İ': 'i', 'ö': 'o', 'Ö': 'o', 'ş': 's', 'Ş': 's', 'ü': 'u', 'Ü': 'u'
    }
    for tr, en in tr_map.items():
        text = text.replace(tr, en)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    slug = re.sub(r'[-\s]+', '-', text)
    return slug[:80]


def init_db():
    """Veritabanını ve gerekli tabloları oluşturur."""
    pk = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with get_connection() as conn:
        # 1. Paylaşılan haber kimlikleri
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS posted_news (
                id {pk},
                news_hash TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                source TEXT,
                link TEXT,
                facebook_post_id TEXT,
                instagram_post_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 2. Web sitesi makaleleri tablosu
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS articles (
                id {pk},
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                content TEXT,
                category TEXT DEFAULT 'Gündem',
                image_path TEXT,
                source TEXT,
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # 3. Site ziyaret sayacı tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS site_metrics (
                key TEXT PRIMARY KEY,
                val INTEGER DEFAULT 0
            )
        """)
        # 4. Sistem ayarları ve son paylaşım zamanları tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                val TEXT
            )
        """)
        # 5. Görsel deposu (yalnızca PostgreSQL modunda kullanılır)
        if USE_PG:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    filename TEXT PRIMARY KEY,
                    data BYTEA NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    if USE_PG:
        _migrate_from_sqlite_if_empty()


def _migrate_from_sqlite_if_empty():
    """Bulut veritabanı boşsa, repodaki SQLite dosyasındaki eski haberleri ve görselleri taşır."""
    with get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
    if count > 0 or not os.path.exists(DB_PATH):
        return

    print("📦 Eski SQLite haberleri bulut veritabanına taşınıyor...")
    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    try:
        posted = [dict(r) for r in src.execute("SELECT * FROM posted_news ORDER BY id")]
        articles = [dict(r) for r in src.execute("SELECT * FROM articles ORDER BY id")]
    finally:
        src.close()

    with get_connection() as conn:
        for p in posted:
            conn.execute("""
                INSERT INTO posted_news (news_hash, title, source, link, facebook_post_id, instagram_post_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (news_hash) DO NOTHING
            """, (p["news_hash"], p["title"], p["source"], p["link"],
                  p["facebook_post_id"], p["instagram_post_id"], p["created_at"]))
        for a in articles:
            conn.execute("""
                INSERT INTO articles (slug, title, summary, content, category, image_path, source, views, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (slug) DO NOTHING
            """, (a["slug"], a["title"], a["summary"], a["content"], a["category"],
                  a["image_path"], a["source"], a["views"], a["created_at"]))

    for a in articles:
        if a.get("image_path"):
            local = os.path.join(OUTPUT_DIR, _basename(a["image_path"]))
            if os.path.exists(local):
                save_image_file(local)
    print(f"✅ {len(articles)} haber bulut veritabanına taşındı.")


def _basename(path: str) -> str:
    return path.replace("\\", "/").split("/")[-1]


def _compress_image(path: str) -> bytes:
    """
    Görseli web için küçültüp sıkıştırır (800px, JPEG kalite 72).
    1080px ~250 KB'lık kart, gözle fark edilmeyecek şekilde ~60-90 KB'a iner.
    Telegram'a giden orijinal dosya etkilenmez.
    """
    from io import BytesIO
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((800, 800), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=72, optimize=True, progressive=True)
        return buf.getvalue()


def save_image_file(path: str):
    """Görsel dosyasını sıkıştırıp kalıcı veritabanına yazar (yalnızca PostgreSQL modunda)."""
    if not USE_PG or not path or not os.path.exists(path):
        return
    try:
        data = _compress_image(path)
    except Exception as e:
        print(f"⚠️ Görsel sıkıştırılamadı, orijinali kaydediliyor: {e}")
        with open(path, "rb") as f:
            data = f.read()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO images (filename, data) VALUES (?, ?)
            ON CONFLICT (filename) DO UPDATE SET data = EXCLUDED.data
        """, (_basename(path), psycopg2.Binary(data)))


def cleanup_old_images(days: int = 180) -> int:
    """
    Belirtilen günden eski haber görsellerini siler (haber metinleri kalır).
    Böylece ücretsiz 1 GB'lık veritabanı hiçbir zaman dolmaz.
    """
    if not USE_PG:
        return 0
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM images WHERE created_at < NOW() - (? * INTERVAL '1 day')", (days,)
        )
        return cur.rowcount or 0


def get_storage_stats() -> Dict:
    """Veritabanı doluluk bilgisini döner (izleme için)."""
    stats = {"articles": 0, "images": 0, "db_size_mb": None}
    with get_connection() as conn:
        stats["articles"] = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
        if USE_PG:
            stats["images"] = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
            size = conn.execute("SELECT pg_database_size(current_database()) AS s").fetchone()["s"]
            stats["db_size_mb"] = round(size / 1024 / 1024, 1)
    return stats


def get_image(filename: str) -> Optional[bytes]:
    if not USE_PG:
        return None
    with get_connection() as conn:
        row = conn.execute("SELECT data FROM images WHERE filename = ?", (filename,)).fetchone()
    return bytes(row["data"]) if row else None


def is_already_posted(news_hash: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM posted_news WHERE news_hash = ?", (news_hash,)).fetchone()
        return row is not None


def mark_as_posted(news_hash: str, title: str, source: str = "", link: str = "", fb_id: str = None, ig_id: str = None):
    with get_connection() as conn:
        if USE_PG:
            conn.execute("""
                INSERT INTO posted_news (news_hash, title, source, link, facebook_post_id, instagram_post_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (news_hash) DO UPDATE SET
                    title = EXCLUDED.title, source = EXCLUDED.source, link = EXCLUDED.link,
                    facebook_post_id = EXCLUDED.facebook_post_id, instagram_post_id = EXCLUDED.instagram_post_id
            """, (news_hash, title, source, link, fb_id, ig_id))
        else:
            conn.execute("""
                INSERT OR REPLACE INTO posted_news 
                (news_hash, title, source, link, facebook_post_id, instagram_post_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (news_hash, title, source, link, fb_id, ig_id))


def save_article(title: str, summary: str, content: str, image_path: str, source: str, category: str = "Gündem") -> str:
    """Makaleyi web sitesi veritabanına kaydeder ve SEO URL slug'ını döner."""
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "haber"

    # Görseli kalıcı depoya da yaz (PostgreSQL modunda)
    save_image_file(image_path)

    slug = base_slug
    with get_connection() as conn:
        # Slug benzersizliği sağla
        counter = 1
        while conn.execute("SELECT 1 FROM articles WHERE slug = ?", (slug,)).fetchone():
            slug = f"{base_slug}-{counter}"
            counter += 1

        conn.execute("""
            INSERT INTO articles (slug, title, summary, content, category, image_path, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (slug, title, summary, content, category, image_path, source))
    return slug


def get_articles(limit: int = 20, category: str = None) -> List[Dict]:
    """Son yayınlanan makaleleri listeler."""
    with get_connection() as conn:
        if category:
            cur = conn.execute("SELECT * FROM articles WHERE category = ? ORDER BY id DESC LIMIT ?", (category, limit))
        else:
            cur = conn.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,))
        return [_row_to_dict(row) for row in cur.fetchall()]


def get_article_by_slug(slug: str) -> Optional[Dict]:
    """Slug'a göre makale detayını çeker ve okunma sayısını 1 artırır."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
        if row:
            conn.execute("UPDATE articles SET views = views + 1 WHERE id = ?", (row["id"],))
            return _row_to_dict(row)
        return None


def delete_article(article_id: int) -> bool:
    """Belirtilen ID'li makaleyi siler."""
    with get_connection() as conn:
        cur = conn.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        return (cur.rowcount or 0) > 0


def get_article_by_id(article_id: int) -> Optional[Dict]:
    """ID'ye göre makaleyi döner."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
        return _row_to_dict(row) if row else None


def update_article(article_id: int, title: str, summary: str, content: str, category: str) -> bool:
    """Belirtilen ID'li makalenin başlık, özet, içerik ve kategorisini günceller."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE articles SET title = ?, summary = ?, content = ?, category = ? WHERE id = ?",
            (title, summary, content, category, article_id)
        )
        return (cur.rowcount or 0) > 0


def record_visit(key: str = "home_visits"):
    """Genel sayfa ziyaret sayacını 1 artırır."""
    try:
        with get_connection() as conn:
            if USE_PG:
                conn.execute("""
                    INSERT INTO site_metrics (key, val) VALUES (?, 1)
                    ON CONFLICT (key) DO UPDATE SET val = site_metrics.val + 1
                """, (key,))
            else:
                row = conn.execute("SELECT val FROM site_metrics WHERE key = ?", (key,)).fetchone()
                new_val = (row["val"] + 1) if row else 1
                conn.execute("INSERT OR REPLACE INTO site_metrics (key, val) VALUES (?, ?)", (key, new_val))
    except Exception:
        pass


def get_setting(key: str, default: str = "") -> str:
    """Kalıcı sistem ayarını okur."""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT val FROM system_settings WHERE key = ?", (key,)).fetchone()
            return str(row["val"]) if row and row["val"] is not None else default
    except Exception:
        return default


def set_setting(key: str, val: str):
    """Kalıcı sistem ayarını kaydeder/günceller."""
    try:
        with get_connection() as conn:
            if USE_PG:
                conn.execute("""
                    INSERT INTO system_settings (key, val) VALUES (?, ?)
                    ON CONFLICT (key) DO UPDATE SET val = EXCLUDED.val
                """, (key, str(val)))
            else:
                conn.execute("INSERT OR REPLACE INTO system_settings (key, val) VALUES (?, ?)", (key, str(val)))
    except Exception as e:
        print(f"⚠️ Ayar kaydedilemedi ({key}): {e}")


def get_dashboard_summary() -> Dict:
    """Yönetim paneli (/panel) için tüm ayrıntılı istatistikleri döner."""
    with get_connection() as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS total_views FROM articles"
        ).fetchone()
        total_articles = totals["cnt"] if totals else 0
        total_views = totals["total_views"] if totals else 0

        home_row = conn.execute(
            "SELECT val FROM site_metrics WHERE key = ?", ("home_visits",)
        ).fetchone()
        home_visits = home_row["val"] if home_row else 0

        top_rows = conn.execute(
            "SELECT * FROM articles ORDER BY views DESC, id DESC LIMIT 10"
        ).fetchall()
        recent_rows = conn.execute(
            "SELECT * FROM articles ORDER BY id DESC LIMIT 30"
        ).fetchall()

        cat_rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS views FROM articles GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
        src_rows = conn.execute(
            "SELECT source, COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS views FROM articles GROUP BY source ORDER BY cnt DESC"
        ).fetchall()

        images_count = 0
        db_size_mb = 0.0
        if USE_PG:
            images_count = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
            size = conn.execute("SELECT pg_database_size(current_database()) AS s").fetchone()["s"]
            db_size_mb = round(size / 1024 / 1024, 1)

    recent_list = [_row_to_dict(r) for r in recent_rows]
    top_list = [_row_to_dict(r) for r in top_rows]
    return {
        "total_articles": total_articles,
        "total_views": total_views,
        "home_visits": home_visits,
        "total_all_hits": total_views + home_visits,
        "avg_views": round(total_views / total_articles, 1) if total_articles > 0 else 0,
        "images_count": images_count,
        "db_size_mb": db_size_mb,
        "use_pg": USE_PG,
        "last_article_time": recent_list[0]["created_at"] if recent_list else "-",
        "top_articles": top_list,
        "recent_articles": recent_list,
        "categories": [dict(r) for r in cat_rows],
        "sources": [dict(r) for r in src_rows],
    }
