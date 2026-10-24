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
import sys
import re
import unicodedata
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

TR_TZ = timezone(timedelta(hours=3))

def tr_now_str() -> str:
    """Türkiye yerel saatini (TSİ, UTC+3) string formatında döner."""
    return datetime.now(TR_TZ).strftime("%Y-%m-%d %H:%M:%S")

def tr_today_str() -> str:
    """Türkiye bugünün tarihini döner (YYYY-MM-DD)."""
    return datetime.now(TR_TZ).strftime("%Y-%m-%d")

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
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
        else:
            cur = self.raw.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
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
    # created_at zaman damgasını daima Türkiye Yerel Saatine (TSİ, UTC+3) dönüştür
    if d.get("created_at") is not None:
        val = d["created_at"]
        if isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc).astimezone(TR_TZ)
            else:
                val = val.astimezone(TR_TZ)
            d["created_at"] = val.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(val, str) and val.strip():
            try:
                clean_str = val.split(".")[0].replace("T", " ")
                dt = datetime.strptime(clean_str[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).astimezone(TR_TZ)
                d["created_at"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                d["created_at"] = str(val)
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
        # 5. Canlı Ziyaretçi ve Trafik Analitiği Tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visitor_logs (
                id SERIAL PRIMARY KEY if_pg,
                visitor_hash TEXT NOT NULL,
                is_first_visit INTEGER DEFAULT 1,
                page TEXT,
                referrer TEXT,
                device TEXT,
                country TEXT,
                city TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """.replace("SERIAL PRIMARY KEY if_pg", "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"))
        # 6. Gelir ve Para Kazanma (AdSense & Sponsorluk) Tablosu
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revenue_records (
                id SERIAL PRIMARY KEY if_pg,
                source TEXT NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """.replace("SERIAL PRIMARY KEY if_pg", "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"))
        # 7. Görsel deposu (yalnızca PostgreSQL modunda kullanılır)
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

    # Arka plan API sorgu kayıtlarını (döviz kurları vb.) ziyaretçi geçmişinden temizle
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM visitor_logs WHERE page LIKE ?", ('/api/%',))
    except Exception:
        pass
    cleanup_corrupted_articles()


def cleanup_corrupted_articles():
    """
    Veritabanındaki makaleleri tarayarak:
    1. 'Favorilerime ekle', borsa canlı bantları, editör imzaları ve telif çöplerini temizler.
    2. 'Gelişmenin Ayrıntıları' altında giriş cümlesinin birebir tekrarlandığı makaleleri düzeltir.
    3. Başlıklardaki kaynak uzantılarını (- Hürriyet vb.) ayıklar.
    """
    import news_fetcher
    try:
        with get_connection() as conn:
            cur = conn.execute("SELECT id, slug, title, summary, content, category FROM articles")
            rows = cur.fetchall()
            updated_count = 0
            for r in rows:
                aid = r["id"]
                orig_title = r["title"] or ""
                orig_summary = r["summary"] or ""
                orig_content = r["content"] or ""
                category = r["category"] or "Gündem"

                # 1. Başlık temizliği
                clean_title = news_fetcher.sanitize_news_text(orig_title)
                clean_title = re.sub(r'\s*-\s*(?:Hürriyet|Mynet|Milliyet|Sabah|Habertürk|Ensonhaber|NTV|Bloomberg HT).*$', '', clean_title, flags=re.I).strip()

                # 2. Özet temizliği
                clean_summary = news_fetcher.sanitize_news_text(orig_summary)

                # 3. İçerik temizliği
                clean_content = orig_content
                if "favorilerime ekle" in clean_content.lower():
                    clean_content = re.sub(r'<p class="lead[^>]*>.*?favorilerime ekle.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)

                clean_content = news_fetcher.sanitize_news_text(clean_content)

                # Tekrarlayan lead paragrafı kontrolü
                lead_match = re.search(r'<p class="lead[^>]*>(.*?)</p>', clean_content, re.DOTALL | re.IGNORECASE)
                if lead_match:
                    lead_txt = lead_match.group(1).strip()
                    detail_match = re.search(r'<h3[^>]*>Gelişmenin Ayrıntıları</h3>\s*<p[^>]*>(.*?)</p>', clean_content, re.DOTALL | re.IGNORECASE)
                    if detail_match:
                        detail_txt = detail_match.group(1).strip()
                        if lead_txt == detail_txt or (len(lead_txt) > 25 and lead_txt in detail_txt) or (len(detail_txt) > 25 and detail_txt in lead_txt):
                            if category == "Ekonomi":
                                new_body = '<p class="text-slate-300 leading-relaxed mb-4">Piyasalarda ve ekonomi çevrelerinde geniş yankı uyandıran gelişmeyle ilgili uzmanlar, fiyatlama dinamikleri ve tüketiciye etkilerinin önümüzdeki günlerde netleşeceğini vurguluyor.</p>'
                            elif category == "Spor":
                                new_body = '<p class="text-slate-300 leading-relaxed mb-4">Spor kamuoyunun yakından takip ettiği gelişmeyle ilgili resmi açıklamaların ardından tarafların önümüzdeki süreçte atacağı adımlar merakla bekleniyor.</p>'
                            else:
                                new_body = '<p class="text-slate-300 leading-relaxed mb-4">Konuyla ilgili resmi mercilerin ve ilgili kurumların değerlendirmeleri sürerken, sürecin kamuoyundaki yansımaları dikkatle takip ediliyor.</p>'
                            clean_content = clean_content.replace(detail_match.group(0), f'<h3 class="text-xl font-bold text-white mt-6 mb-3">Gelişmenin Ayrıntıları</h3>\n{new_body}')

                # Eğer lead paragrafı boşalmışsa (silindiği için)
                if '<p class="lead' not in clean_content:
                    first_p_match = re.search(r'<p class="text-slate-300[^>]*>(.*?)</p>', clean_content, re.DOTALL | re.IGNORECASE)
                    if first_p_match:
                        new_lead = first_p_match.group(1).strip()
                        clean_content = f'<p class="lead font-medium text-lg text-slate-200 mb-6">{new_lead}</p>\n' + clean_content.replace(first_p_match.group(0), '', 1)
                    else:
                        clean_content = f'<p class="lead font-medium text-lg text-slate-200 mb-6">{clean_summary or clean_title}</p>\n' + clean_content

                # Boş başlık kalmışsa başlığı tamamla
                clean_content = re.sub(r'<h3 class="text-xl font-bold text-white mt-6 mb-3">\s*</h3>', '<h3 class="text-xl font-bold text-white mt-6 mb-3">Gelişmenin Ayrıntıları</h3>', clean_content)

                if clean_title != orig_title or clean_summary != orig_summary or clean_content != orig_content:
                    conn.execute(
                        "UPDATE articles SET title = ?, summary = ?, content = ? WHERE id = ?",
                        (clean_title, clean_summary, clean_content, aid)
                    )
                    updated_count += 1
            if updated_count > 0:
                print(f"🧹 [Veritabanı Temizliği] {updated_count} adet makale başarıyla temizlendi ve güncellendi.")
    except Exception as e:
        print(f"Veritabanı Temizliği Hatası: {e}")


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


def normalize_category_name(cat: Optional[str]) -> Optional[str]:
    """Kategori isimlerini ve takma adlarını standartlaştırır."""
    if not cat:
        return None
    c = cat.strip().lower()
    mapping = {
                "egitim": "Eğitim",
        "eğitim": "Eğitim",
        "meb": "Eğitim",
        "osym": "Eğitim",
        "ösym": "Eğitim",
        "sinav": "Eğitim",
        "sınav": "Eğitim",
        "yks": "Eğitim",
        "lgs": "Eğitim",
        "kpss": "Eğitim",
        "saglik": "Sağlık",
        "sağlık": "Sağlık",
        "ekonomi": "Ekonomi",
        "otomobil": "Otomobil",
        "oto": "Otomobil",
        "araba": "Otomobil",
        "teknoloji": "Teknoloji",
        "tekno": "Teknoloji",
        "bilim": "Teknoloji",
        "spor": "Spor",
        "futbol": "Spor",
        "dunya": "Dünya",
        "dünya": "Dünya",
        "gundem": "Gündem",
        "gündem": "Gündem",
        "son-dakika": "Son Dakika",
        "sondakika": "Son Dakika",
        "son dakika": "Son Dakika",
        "asayis": "Asayiş",
        "asayiş": "Asayiş",
        "magazin": "Magazin",
        "yasam": "Yaşam",
        "yaşam": "Yaşam"
    }
    return mapping.get(c, cat.strip())


def get_articles(limit: int = 20, category: str = None, offset: int = 0) -> List[Dict]:
    """Son yayınlanan makaleleri listeler."""
    with get_connection() as conn:
        if category:
            cat_norm = normalize_category_name(category) or category
            cur = conn.execute(
                """SELECT * FROM articles 
                   WHERE category = ? OR LOWER(category) = LOWER(?) OR category = ?
                   ORDER BY id DESC LIMIT ? OFFSET ?""",
                (cat_norm, cat_norm, category.strip(), limit, offset)
            )
            rows = [_row_to_dict(row) for row in cur.fetchall()]
            if not rows and offset == 0:
                kw = cat_norm.lower()
                cur = conn.execute(
                    """SELECT * FROM articles 
                       WHERE title LIKE ? OR summary LIKE ? OR category LIKE ?
                       ORDER BY id DESC LIMIT ? OFFSET ?""",
                    (f"%{kw}%", f"%{kw}%", f"%{kw}%", limit, offset)
                )
                rows = [_row_to_dict(row) for row in cur.fetchall()]
            return rows
        else:
            cur = conn.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
            return [_row_to_dict(row) for row in cur.fetchall()]


def get_articles_total_count(category: str = None) -> int:
    """Toplam yayınlanmış haber sayısını döner."""
    try:
        with get_connection() as conn:
            if category:
                cat_norm = normalize_category_name(category) or category
                row = conn.execute(
                    """SELECT COUNT(*) AS c FROM articles 
                       WHERE category = ? OR LOWER(category) = LOWER(?) OR category = ?""",
                    (cat_norm, cat_norm, category.strip())
                )
                c = row["c"] if row else 0
                if c == 0:
                    kw = cat_norm.lower()
                    row2 = conn.execute(
                        """SELECT COUNT(*) AS c FROM articles 
                           WHERE title LIKE ? OR summary LIKE ? OR category LIKE ?""",
                        (f"%{kw}%", f"%{kw}%", f"%{kw}%")
                    )
                    return row2["c"] if row2 else 0
                return c
            else:
                row = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()
                return row["c"] if row else 0
    except Exception:
        return 0


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


def log_visitor(visitor_hash: str, page: str = "/", referrer: str = "Doğrudan", device: str = "Mobil", country: str = "TR", city: str = "") -> bool:
    """Ziyaretçiyi kaydeder. Kullanıcı siteye ilk defa mı giriyor kontrol eder ve döner."""
    if not page or page.startswith("/api/") or page.startswith("/assets") or page.startswith("/images"):
        return False
    try:
        with get_connection() as conn:
            # Bu ziyaretçi daha önce hiç girdi mi?
            prev = conn.execute("SELECT 1 FROM visitor_logs WHERE visitor_hash = ? LIMIT 1", (visitor_hash,)).fetchone()
            is_first = 1 if not prev else 0

            conn.execute("""
                INSERT INTO visitor_logs (visitor_hash, is_first_visit, page, referrer, device, country, city)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (visitor_hash, is_first, page[:120], referrer[:50], device[:30], country[:10], city[:50]))
            return bool(is_first)
    except Exception as e:
        print(f"⚠️ Ziyaretçi loglanamadı: {e}")
        return False


def add_revenue_record(source: str, amount: float, date_str: str, notes: str = "") -> int:
    """Yeni gelir kaydı ekler (AdSense, Sponsorluk vb.)."""
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO revenue_records (source, amount, date, notes)
                VALUES (?, ?, ?, ?)
            """, (source, float(amount), date_str, notes))
            return 1
    except Exception as e:
        print(f"⚠️ Gelir eklenemedi: {e}")
        return 0


def delete_revenue_record(rec_id: int):
    """Gelir kaydını siler."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM revenue_records WHERE id = ?", (rec_id,))
    except Exception:
        pass


def get_dashboard_summary() -> Dict:
    """Yönetim paneli (/panel) için tüm ayrıntılı canlı analitik ve istatistikleri döner."""
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

        # CANLI TRAFİK & TEKİL KULLANICI ANALİTİĞİ
        active_now = 0
        today_uniques = 0
        first_time_today = 0
        live_visitors = []
        traffic_sources = []
        device_stats = []

        try:
            # Türkiye saatine göre zaman eşikleri (TSİ) -> UTC veritabanı eşdeğerleri
            now_tr = datetime.now(TR_TZ)
            today_start_tr = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_utc = today_start_tr.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            five_min_ago_utc = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            seven_days_ago_utc = (today_start_tr - timedelta(days=7)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            # Son 5 dakikada aktif olan tekil kişi sayısı
            act_row = conn.execute(
                "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ?", (five_min_ago_utc,)
            ).fetchone()
            active_now = act_row["c"] if act_row else 0

            # Bugünün tekil kullanıcı sayısı (TSİ gece 00:00'dan itibaren)
            uniq_row = conn.execute(
                "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ?", (today_start_utc,)
            ).fetchone()
            today_uniques = uniq_row["c"] if uniq_row else 0

            # Bugün ilk defa gelen yeni ziyaretçi sayısı
            first_row = conn.execute(
                "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ? AND is_first_visit = 1", (today_start_utc,)
            ).fetchone()
            first_time_today = first_row["c"] if first_row else 0

            # Son 7 günün trafik kaynakları
            traffic_rows = conn.execute(
                "SELECT referrer, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY referrer ORDER BY cnt DESC LIMIT 7", (seven_days_ago_utc,)
            ).fetchall()
            traffic_sources = [dict(r) for r in traffic_rows]

            # Son 7 günün cihaz dağılımı
            dev_rows = conn.execute(
                "SELECT device, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY device ORDER BY cnt DESC", (seven_days_ago_utc,)
            ).fetchall()
            device_stats = [dict(r) for r in dev_rows]

            # Canlı son 20 ziyaretçi (Türkiye Saatine çevrilmiş olarak - API çağrıları hariç)
            lv_rows = conn.execute(
                "SELECT * FROM visitor_logs WHERE page NOT LIKE ? ORDER BY id DESC LIMIT 20", ('/api/%',)
            ).fetchall()
            live_visitors = [_row_to_dict(r) for r in lv_rows]
        except Exception as e:
            print(f"⚠️ Analitik sorgulama hatası: {e}")

        # PARA KAZANMA & GELİR VERİLERİ
        total_revenue = 0.0
        month_revenue = 0.0
        revenue_records = []
        try:
            rev_all = conn.execute("SELECT COALESCE(SUM(amount), 0) AS s FROM revenue_records").fetchone()
            total_revenue = round(rev_all["s"] if rev_all else 0.0, 2)

            rev_rows = conn.execute("SELECT * FROM revenue_records ORDER BY id DESC LIMIT 20").fetchall()
            revenue_records = [_row_to_dict(r) for r in rev_rows]
            month_revenue = total_revenue  # Başlangıçta toplamı göster
        except Exception as e:
            print(f"⚠️ Gelir sorgulama hatası: {e}")

        images_count = 0
        db_size_mb = 0.0
        if USE_PG:
            images_count = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
            size = conn.execute("SELECT pg_database_size(current_database()) AS s").fetchone()["s"]
            db_size_mb = round(size / 1024 / 1024, 1)

    recent_list = [_row_to_dict(r) for r in recent_rows]
    top_list = [_row_to_dict(r) for r in top_rows]
    returning_today = max(0, today_uniques - first_time_today)

    return {
        "total_articles": total_articles,
        "total_views": total_views,
        "home_visits": home_visits,
        "total_all_hits": total_views + home_visits,
        "avg_views": round(total_views / total_articles, 1) if total_articles > 0 else 0,
        "active_now": max(1, active_now),
        "today_uniques": today_uniques,
        "first_time_today": first_time_today,
        "returning_today": returning_today,
        "traffic_sources": traffic_sources,
        "device_stats": device_stats,
        "live_visitors": live_visitors,
        "total_revenue": total_revenue,
        "month_revenue": month_revenue,
        "revenue_records": revenue_records,
        "images_count": images_count,
        "db_size_mb": db_size_mb,
        "use_pg": USE_PG,
        "last_article_time": recent_list[0]["created_at"] if recent_list else "-",
        "top_articles": top_list,
        "recent_articles": recent_list,
        "categories": [dict(r) for r in cat_rows],
        "sources": [dict(r) for r in src_rows],
    }
