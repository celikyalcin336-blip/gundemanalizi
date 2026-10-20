import sqlite3
import os
import re
import unicodedata
from typing import List, Dict, Optional

DB_DIR = os.path.join(os.path.dirname(__file__), "data")
DB_PATH = os.path.join(DB_DIR, "news_bot.db")

def get_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Paylaşılan haber kimlikleri
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posted_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        conn.commit()

def is_already_posted(news_hash: str) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM posted_news WHERE news_hash = ?", (news_hash,))
        return cursor.fetchone() is not None

def mark_as_posted(news_hash: str, title: str, source: str = "", link: str = "", fb_id: str = None, ig_id: str = None):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO posted_news 
            (news_hash, title, source, link, facebook_post_id, instagram_post_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (news_hash, title, source, link, fb_id, ig_id))
        conn.commit()

def save_article(title: str, summary: str, content: str, image_path: str, source: str, category: str = "Gündem") -> str:
    """Makaleyi web sitesi veritabanına kaydeder ve SEO URL slug'ını döner."""
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "haber"
    
    slug = base_slug
    with get_connection() as conn:
        cursor = conn.cursor()
        # Slug benzersizliği sağla
        counter = 1
        while True:
            cursor.execute("SELECT 1 FROM articles WHERE slug = ?", (slug,))
            if not cursor.fetchone():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        cursor.execute("""
            INSERT INTO articles (slug, title, summary, content, category, image_path, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (slug, title, summary, content, category, image_path, source))
        conn.commit()
    return slug

def get_articles(limit: int = 20, category: str = None) -> List[Dict]:
    """Son yayınlanan makaleleri listeler."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT * FROM articles WHERE category = ? ORDER BY id DESC LIMIT ?", (category, limit))
        else:
            cursor.execute("SELECT * FROM articles ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_article_by_slug(slug: str) -> Optional[Dict]:
    """Slug'a göre makale detayını çeker ve okunma sayısını 1 artırır."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE slug = ?", (slug,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE articles SET views = views + 1 WHERE id = ?", (row["id"],))
            conn.commit()
            return dict(row)
        return None
