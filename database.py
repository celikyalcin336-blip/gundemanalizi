"""
Veritabanı katmanı.

İki modda çalışır:
- DATABASE_URL ortam değişkeni tanımlıysa: PostgreSQL (kalıcı bulut veritabanı, ör. Neon)
- Tanımlı değilse: yerel SQLite (data/news_bot.db)

Haber kartı görselleri de PostgreSQL modunda veritabanında saklanır; böylece
Render ücretsiz planında sunucu yeniden başlasa bile haberler ve görseller kaybolmaz.
"""
import sqlite3
import threading
import os
import sys
import time
import re
import unicodedata
import difflib
from typing import List, Dict, Optional, Tuple
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

_PG_POOL = None
_PG_LAST_ERROR = None
_PG_POOL_LAST_TRY = 0

if USE_PG:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool

    def _get_pg_pool():
        global _PG_POOL, _PG_LAST_ERROR, _PG_POOL_LAST_TRY
        now = time.time()
        if _PG_POOL is None:
            if now - _PG_POOL_LAST_TRY < 5:
                return None
            _PG_POOL_LAST_TRY = now
            try:
                _PG_POOL = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=8, dsn=DATABASE_URL, connect_timeout=5
                )
                _PG_LAST_ERROR = None
                print("✅ [PostgreSQL] Connection Pool başarıyla kuruldu.")
            except Exception as e:
                _PG_LAST_ERROR = f"{type(e).__name__}: {str(e)}"
                print(f"⚠️ [PostgreSQL] Pool başlatma hatası: {e}")
        return _PG_POOL


class _Conn:
    """sqlite3 / psycopg2 farkını gizleyen ve bağlantı havuzu (connection pool) ile ultra hızlı çalışan sarmalayıcı."""

    def __init__(self):
        global _PG_LAST_ERROR
        self.is_pg = False
        self.from_pool = False
        if USE_PG:
            pool = _get_pg_pool()
            if pool:
                for retry in range(4):
                    try:
                        self.raw = pool.getconn()
                        self.from_pool = True
                        self.is_pg = True
                        _PG_LAST_ERROR = None
                        break
                    except Exception as pool_err:
                        if retry < 3:
                            time.sleep(0.04)
                            continue
                        # Havuz tamamen doluysa SQLite'a düşmek yerine anlık tekil PG bağlantısı dene
                        try:
                            self.raw = psycopg2.connect(DATABASE_URL, connect_timeout=8)
                            self.from_pool = False
                            self.is_pg = True
                            _PG_LAST_ERROR = None
                            break
                        except Exception as direct_err:
                            _PG_LAST_ERROR = f"PoolError + DirectConnectFail: {direct_err}"
                            print(f"⚠️ PostgreSQL bağlantı hatası, yerel SQLite'a geçiliyor: {direct_err}")
                            self.is_pg = False
            else:
                try:
                    self.raw = psycopg2.connect(DATABASE_URL, connect_timeout=15)
                    self.is_pg = True
                    _PG_LAST_ERROR = None
                except Exception as e:
                    _PG_LAST_ERROR = f"{type(e).__name__}: {str(e)}"
                    print(f"⚠️ PostgreSQL bağlantı hatası, yerel SQLite'a geçiliyor: {e}")
                    self.is_pg = False

        if not self.is_pg:
            self.from_pool = False
            os.makedirs(DB_DIR, exist_ok=True)
            self.raw = sqlite3.connect(DB_PATH)
            self.raw.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple = ()):
        if self.is_pg:
            cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if params:
                sql = sql.replace("%", "%%").replace("?", "%s")
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
        except Exception:
            try:
                self.raw.rollback()
            except Exception:
                pass
        finally:
            if self.is_pg and getattr(self, "from_pool", False):
                pool = _get_pg_pool()
                if pool:
                    try:
                        pool.putconn(self.raw)
                    except Exception:
                        pass
                else:
                    try:
                        self.raw.close()
                    except Exception:
                        pass
            else:
                try:
                    self.raw.close()
                except Exception:
                    pass


def get_connection():
    return _Conn()


def _row_to_dict(row) -> Dict:
    d = dict(row)
    if d.get("image_path"):
        base_img = str(d["image_path"]).split("?")[0]
        d["image_path"] = f"{base_img}?v=3"
    try:
        import content_quality
        if d.get("title"):
            d["title"] = content_quality.clean_title_text(str(d["title"]))
        if d.get("summary"):
            d["summary"] = content_quality.clean_summary_text(str(d["summary"]), d.get("title") or "")
        raw_c = d.get("content") or ""
        if raw_c:
            wc = content_quality.visible_word_count(raw_c)
            d["reading_time_min"] = max(2, min(6, round(wc / 150)))
        else:
            d["reading_time_min"] = 2 + (int(d.get("id") or 0) % 3)
    except Exception:
        d["reading_time_min"] = 3
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
            # Yüksek Performans Veritabanı İndeksleri
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_cat_id ON articles (category, id DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_created ON articles (created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_visitor_logs_created ON visitor_logs (created_at DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_posted_news_hash ON posted_news (news_hash);")
            except Exception:
                pass
    if USE_PG:
        _migrate_from_sqlite_if_empty()

    # Gerçek okuyucu tepkileri (Okuyucu Nabzı) tablosu
    try:
        with get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS article_reactions (
                    article_id INTEGER NOT NULL,
                    choice TEXT NOT NULL,
                    cnt INTEGER DEFAULT 0,
                    PRIMARY KEY (article_id, choice)
                )
            """)
    except Exception as e:
        print(f"article_reactions tablo hatası: {e}")

    # Arka plan API sorgu kayıtlarını (döviz kurları vb.) ziyaretçi geçmişinden temizle
    # ve geçmişte Masaüstü/Doğrudan olarak sızmış otomatik site haritası kazıyıcı yığınlarını "🤖 Arama Botu" olarak sınıflandır (Veri silinmez, doğru kategoriye taşınır)
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM visitor_logs WHERE page LIKE ?", ('/api/%',))
            conn.execute("""
                UPDATE visitor_logs
                SET device = '🤖 Arama Botu', referrer = '🤖 Arama Botu', is_first_visit = 0
                WHERE device = 'Masaüstü'
                  AND referrer = 'Doğrudan'
                  AND (
                      created_at IN (
                          SELECT created_at
                          FROM visitor_logs
                          WHERE device = 'Masaüstü' AND referrer = 'Doğrudan'
                          GROUP BY created_at
                          HAVING COUNT(*) >= 4
                      )
                      OR visitor_hash IN (
                          SELECT visitor_hash
                          FROM visitor_logs
                          WHERE device = 'Masaüstü' AND referrer = 'Doğrudan' AND page LIKE '/haber/%'
                          GROUP BY visitor_hash
                          HAVING COUNT(*) >= 6
                      )
                  )
            """)
    except Exception:
        pass


def cleanup_corrupted_articles():
    # Hatalı kategori düzeltmesi: Estetik, cerrahi ve bıçak altına yatma haberleri kesinlikle Sağlık olmalıdır
    try:
        with get_connection() as conn:
            conn.execute("""
                UPDATE articles 
                SET category = 'Sağlık' 
                WHERE (LOWER(title) LIKE '%bıçak altına%' OR LOWER(title) LIKE '%genç görünme%' OR LOWER(title) LIKE '%estetik%' OR LOWER(title) LIKE '%botoks%')
                AND category != 'Sağlık'
            """)
    except Exception as e:
        print(f"Kategori onarım hatası: {e}")
    """
    Veritabanındaki makaleleri tarayarak:
    1. ai_writer.classify_article motoruyla tüm makaleleri yeniden sınıflandırıp hatalı kategorileri düzeltir.
    2. 'Favorilerime ekle', borsa canlı bantları, editör imzaları ve telif çöplerini temizler.
    3. 'Gelişmenin Ayrıntıları' altında giriş cümlesinin birebir tekrarlandığı makaleleri düzeltir.
    """
    # 1. Boş / Logolu Görselleri Otomatik Tespit Edip Gerçek Basın Fotoğraflarıyla Onar (Örn: Lemina)
    try:
        with get_connection() as conn:
            cur = conn.execute("SELECT id, title, category, image_path FROM articles WHERE LOWER(title) LIKE '%lemina%'")
            for r in cur.fetchall():
                t = r["title"]
                c = r["category"] or "Spor"
                ip = r["image_path"]
                if ip:
                    fn = os.path.basename(ip)
                    import image_generator
                    real_url = image_generator.search_editorial_web_image(t, c)
                    if real_url:
                        t_out = os.path.join(image_generator.OUTPUT_DIR, fn)
                        res = image_generator.create_single_news_photo(real_url, t_out)
                        if res and os.path.exists(res):
                            save_image_file(t_out)
                            print(f"✅ [Görsel Onarıldı]: {t[:35]}")
    except Exception as e:
        print(f"Görsel otomatik onarım hatası: {e}")
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

                import content_quality
                # 1. Başlık temizliği
                clean_title = content_quality.clean_title_text(news_fetcher.sanitize_news_text(orig_title))
                clean_title = re.sub(r'\s*-\s*(?:Hürriyet|Mynet|Milliyet|Sabah|Habertürk|Ensonhaber|NTV|Bloomberg HT).*$', '', clean_title, flags=re.I).strip()

                # 2. Özet temizliği
                clean_summary = content_quality.clean_title_text(news_fetcher.sanitize_news_text(orig_summary))

                # 3. İçerik temizliği
                clean_content = orig_content
                if "favorilerime ekle" in clean_content.lower():
                    clean_content = re.sub(r'<p class="lead[^>]*>.*?favorilerime ekle.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)

                # Yazar biyografisi, içindekiler ve e-ticaret çöplerini ayıkla
                if any(j in clean_content.lower() for j in ["spk'nın", "yatırım danışmanlığı", "resmi gazete'de yayımlanan tebliği uyarınca", "içindekiler", "editör hakkında", "onur seven", "scorsese", "son haberler", "kategoriler nasıl yapılır", "donanım yazılım", "ai ile özetle"]):
                    clean_content = re.sub(r'<p[^>]*>.*?SPK(?:\'n[ıi]n)?.*?uyar[ıi].*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?yat[ıi]r[ıi]m\\s+dan[ıi][sş]manl[ıi][gğ][ıi]\\s+kapsam[ıi]nda\\s+de[gğ]ildir.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?içindekiler.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?editör hakkında.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?onur seven.*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?https?://(?:n11|migros|idefix).*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p class="lead[^>]*>.*?(?:son haberler|kategoriler nasıl yapılır|donanım yazılım|ai ile özetle).*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)
                    clean_content = re.sub(r'<p[^>]*>.*?(?:son haberler yapay zeka|kategoriler nasıl yapılır|donanım yazılım android).*?</p>', '', clean_content, flags=re.DOTALL | re.IGNORECASE)

                if any(j in clean_summary.lower() for j in ["içindekiler", "editör hakkında", "onur seven"]):
                    clean_summary = re.sub(r'İçindekiler.*?(\.|\n|$)', '', clean_summary, flags=re.I).strip()
                    clean_summary = re.sub(r'Editör Hakkında.*?(\.|\n|$)', '', clean_summary, flags=re.I).strip()

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

                                # 4. Kategori Düzeltme (Örn: Otomobil haberinin Teknoloji'de veya Kanser haberinin Ekonomi'de kalmasını önle)
                import ai_writer
                correct_cat = category
                
                # 5. Kesilmiş / yarım kalmış lead paragraf tamiri (örn: '... düzenlenen 14.')
                if re.search(r'\b\d+\.\s*$', clean_summary):
                    # Özette sayı noktalı kalmışsa içerikten tamamla
                    lead_m = re.search(r'<p class="lead[^>]*>(.*?)</p>', clean_content, re.DOTALL)
                    if lead_m:
                        full_lead = lead_m.group(1).strip()
                        if not re.search(r'\b\d+\.\s*$', full_lead):
                            clean_summary = full_lead

                # 6. Ham HTML sızıntılarını, şablon kutularını ve mükerrer paragrafları temizle (Hazır dolgu paragrafı ASLA eklenmez)
                clean_content = content_quality.clean_article_html(clean_content)

                if clean_title != orig_title or clean_summary != orig_summary or clean_content != orig_content or correct_cat != category:
                    conn.execute(
                        "UPDATE articles SET title = ?, summary = ?, content = ?, category = ? WHERE id = ?",
                        (clean_title, clean_summary, clean_content, correct_cat, aid)
                    )
                    updated_count += 1
                    continue

                if clean_title != orig_title or clean_summary != orig_summary or clean_content != orig_content:
                    conn.execute(
                        "UPDATE articles SET title = ?, summary = ?, content = ? WHERE id = ?",
                        (clean_title, clean_summary, clean_content, aid)
                    )
                    updated_count += 1
            if updated_count > 0:
                print(f"🧹 [Veritabanı Temizliği] {updated_count} adet makale başarıyla temizlendi ve güncellendi.")

            # 7. MÜKERRER / TEKRARLANAN HABERLERİ OTOMATİK TESPİT ET VE SİL (MG vb. çift paylaşımları temizler)
            cur_dup = conn.execute("SELECT id, title, slug, views, created_at FROM articles ORDER BY id ASC")
            all_arts = cur_dup.fetchall()
            seen_slugs_map = {}
            seen_titles_list = []
            duplicate_ids = []

            dup_stopwords = {'ve', 'ile', 'bir', 'bu', 'da', 'de', 'ta', 'te', 'icin', 'için', 'yeni', 'son', 'dakika'}
            for art in all_arts:
                aid = art["id"]
                atitle = (art["title"] or "").strip()
                aslug = (art["slug"] or "").strip()
                norm_slug = re.sub(r'-\d+$', '', aslug)

                is_dup = False
                if norm_slug in seen_slugs_map:
                    is_dup = True
                else:
                    for prev_id, prev_title, prev_slug in seen_titles_list:
                        # Benzerlik oranı kontrolü (>72%)
                        sim = difflib.SequenceMatcher(None, atitle.lower(), prev_title.lower()).ratio()
                        if sim > 0.72:
                            is_dup = True
                            break
                        # Anlamlı kelime kümesi örtüşmesi (>75%)
                        w1 = {w for w in re.findall(r'\w+', atitle.lower()) if len(w) > 2 and w not in dup_stopwords}
                        w2 = {w for w in re.findall(r'\w+', prev_title.lower()) if len(w) > 2 and w not in dup_stopwords}
                        if len(w1) >= 4 and len(w2) >= 4 and len(w1 & w2) / min(len(w1), len(w2)) >= 0.75:
                            is_dup = True
                            break

                if is_dup:
                    duplicate_ids.append((aid, atitle))
                else:
                    seen_slugs_map[norm_slug] = aid
                    seen_titles_list.append((aid, atitle, aslug))

            if duplicate_ids:
                for did, dtitle in duplicate_ids:
                    conn.execute("DELETE FROM articles WHERE id = ?", (did,))
                    print(f"🗑️ [Mükerrer Haber Temizlendi] ID: {did} | Başlık: {dtitle[:60]}")
                print(f"🧹 [Veritabanı Temizliği] Toplam {len(duplicate_ids)} adet mükerrer/tekrarlanan haber veritabanından tamamen silindi.")
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
    Görseli web için küçültüp optimize eder (1200x675 Google Discover HD, JPEG kalite 75).
    1080px ~250 KB'lık kart, gözle fark edilmeyecek HD kalitede ~45-65 KB'a iner.
    Telegram ve sosyal medyaya giden orijinal dosya etkilenmez.
    """
    from io import BytesIO
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((1200, 675), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=75, optimize=True, progressive=True)
        return buf.getvalue()


def save_image_file(path: str):
    """
    Görseli Neon PostgreSQL (images tablosu) ve yerel diskte kalıcı olarak saklar.
    Render yeniden başlasa bile haber görselleri ASLA silinmez ve kaybolmaz.
    """
    if not path or not os.path.exists(path):
        return
    filename = os.path.basename(path)
    try:
        with open(path, "rb") as f:
            raw_data = f.read()
        if not raw_data or len(raw_data) < 200:
            return
        data = raw_data
        # Yalnızca büyük görselleri (>75 KB) HD kalitede optimize et; >6 KB eşiğini daima koru
        if len(raw_data) > 76800 and filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            try:
                comp = _compress_image(path)
                if comp and len(comp) >= 6500 and len(comp) < len(raw_data):
                    data = comp
            except Exception:
                data = raw_data
        with get_connection() as conn:
            if conn.is_pg:
                conn.execute("""
          INSERT INTO images (filename, data) VALUES (?, ?)
                    ON CONFLICT (filename) DO UPDATE SET data = EXCLUDED.data
                """, (filename, psycopg2.Binary(data)))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO images (filename, data) VALUES (?, ?)
                """, (filename, data))
    except Exception as e:
        print(f"Görsel kalıcı kayıt istisnası ({filename}): {e}")


def cleanup_old_visitor_logs(days: int = 30) -> int:
    """
    30 günden eski ham ziyaretçi giriş-çıkış loglarını temizler.
    Haberler (articles), görseller (images) ve toplam okunma/ziyaret sayaçları ASLA silinmez.
    """
    try:
        with get_connection() as conn:
            if conn.is_pg:
                cur = conn.execute(
                    "DELETE FROM visitor_logs WHERE created_at < NOW() - (? * INTERVAL '1 day')", (days,)
                )
            else:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
                cur = conn.execute("DELETE FROM visitor_logs WHERE created_at < ?", (cutoff,))
            return cur.rowcount or 0
    except Exception as e:
        print(f"Ziyaretçi log bakım istisnası: {e}")
        return 0


def cleanup_old_images(days: int = 180) -> int:
    """
    Belirtilen günden eski haber görsellerini siler (haber metinleri kalır).
    Böylece ücretsiz 1 GB'lık veritabanı hiçbir zaman dolmaz.
    """
    with get_connection() as conn:
        if not conn.is_pg:
            return 0
        cur = conn.execute(
            "DELETE FROM images WHERE created_at < NOW() - (? * INTERVAL '1 day')", (days,)
        )
        return cur.rowcount or 0


def get_storage_stats() -> Dict:
    """Veritabanı doluluk bilgisini döner (izleme için)."""
    stats = {"articles": 0, "images": 0, "db_size_mb": None, "is_pg": False, "pg_error": _PG_LAST_ERROR}
    with get_connection() as conn:
        stats["is_pg"] = conn.is_pg
        stats["articles"] = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
        if conn.is_pg:
            try:
                stats["images"] = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
                size = conn.execute("SELECT pg_database_size(current_database()) AS s").fetchone()["s"]
                stats["db_size_mb"] = round(size / 1024 / 1024, 1)
            except Exception as e:
                stats["pg_calc_error"] = str(e)
    return stats


def get_image(filename: str) -> Optional[bytes]:
    """Görseli Neon PostgreSQL veya yerel veritabanından anında çeker."""
    if not filename:
        return None
    safe_name = os.path.basename(filename).split("?")[0]
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT data FROM images WHERE filename = ? LIMIT 1", (safe_name,)).fetchone()
            if row:
                data_val = row["data"] if isinstance(row, dict) or hasattr(row, "__getitem__") else getattr(row, "data", None)
                if data_val and len(bytes(data_val)) >= 6000:
                    return bytes(data_val)
    except Exception as e:
        print(f"Görsel veritabanı okuma hatası ({safe_name}): {e}")
    return None


def heal_single_missing_image(filename: str) -> Optional[str]:
    """
    Diskte ve veritabanında bulunamayan bir haber görselini, makale başlığından
    gerçek basın fotoğrafı bularak (veya HD editoryal kart üreterek) anında onarır ve kalıcı kaydeder.
    """
    if not filename:
        return None
    safe_name = os.path.basename(filename).split("?")[0]
    if not safe_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        return None
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        title = ""
        category = "Gündem"
        with get_connection() as conn:
            row = conn.execute(
                "SELECT title, category FROM articles WHERE image_path LIKE ? ORDER BY id DESC LIMIT 1",
                (f"%{safe_name}%",)
            ).fetchone()
            if row:
                title = row["title"] or ""
                category = row["category"] or "Gündem"
        if not title:
            return None
        import image_generator
        res = image_generator.create_news_visual(
            candidate_urls=[],
            output_filename=safe_name,
            title=title,
            category=category
        )
        if res and os.path.exists(res) and os.path.getsize(res) >= 6000:
            save_image_file(res)
            print(f"✅ [Görsel Kurtarıldı ve Kalıcı Kaydedildi]: {safe_name} ({title[:40]}...)")
            return res
    except Exception as e:
        print(f"⚠️ Görsel onarım hatası ({safe_name}): {e}")
    return None


def restore_and_heal_images(limit: int = 150):
    """
    Sunucu açılışında son makalelerin görsellerini PostgreSQL images tablosundan diske geri yükler;
    veritabanında eksik olan görselleri ise makale başlığından gerçek basın fotoğraflarıyla onarır.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, title, category, image_path FROM articles ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        missing_names = []
        for r in rows:
            ip = r["image_path"] or ""
            if not ip:
                continue
            safe_name = os.path.basename(ip.replace("\\", "/")).split("?")[0]
            if not safe_name:
                continue
            local_p = os.path.join(OUTPUT_DIR, safe_name)
            if not os.path.exists(local_p) or os.path.getsize(local_p) < 6000:
                missing_names.append(safe_name)

        if not missing_names:
            return

        restored_count = 0
        still_missing = []
        for safe_name in missing_names:
            data = get_image(safe_name)
            if data and len(data) >= 6000:
                local_p = os.path.join(OUTPUT_DIR, safe_name)
                try:
                    with open(local_p, "wb") as f:
                        f.write(data)
                    restored_count += 1
                except Exception:
                    still_missing.append(safe_name)
            else:
                still_missing.append(safe_name)

        if restored_count > 0:
            print(f"🖼️ [Görsel Geri Yükleme] {restored_count} adet haber görseli veritabanından diske yüklendi.")

        healed_count = 0
        for safe_name in still_missing:
            res = heal_single_missing_image(safe_name)
            if res:
                healed_count += 1
        if healed_count > 0:
            print(f"✨ [Görsel Kurtarma] {healed_count} adet kayıp haber görseli yeniden oluşturuldu ve veritabanına kaydedildi.")
    except Exception as e:
        print(f"⚠️ Toplu görsel geri yükleme hatası: {e}")


def is_already_posted(news_hash: str, title: str = "", link: str = "") -> bool:
    """
    Haberin daha önce paylaşılıp paylaşılmadığını 5 katmanlı akıllı korumayla kontrol eder:
    1. news_hash kontrolü (posted_news)
    2. Orijinal kaynak linki kontrolü (posted_news)
    3. Birebir başlık veya slug kontrolü (articles ve posted_news)
    4. Yüksek benzerlikli başlık kontrolü (son 200 haber içinde %72 üzeri benzerlik)
    5. Kelime kümesi örtüşmesi (önemli kelimelerin %75+ eşleşmesi)
    """
    with get_connection() as conn:
        # 1. Doğrudan hash kontrolü
        if news_hash:
            row = conn.execute("SELECT 1 FROM posted_news WHERE news_hash = ?", (news_hash,)).fetchone()
            if row:
                return True

        # 2. Orijinal link kontrolü (aynı link farklı hash ile gelirse)
        if link and len(link.strip()) > 10:
            row = conn.execute("SELECT 1 FROM posted_news WHERE link = ?", (link.strip(),)).fetchone()
            if row:
                return True

        if not title or not title.strip():
            return False

        clean_t = title.strip().lower()
        slug = slugify(title)

        # 3. Birebir başlık veya slug kontrolü
        row = conn.execute("SELECT 1 FROM articles WHERE slug = ? OR LOWER(title) = ?", (slug, clean_t)).fetchone()
        if row:
            return True
        row = conn.execute("SELECT 1 FROM posted_news WHERE LOWER(title) = ?", (clean_t,)).fetchone()
        if row:
            return True

        # 4. Son 250 makale içinde Çelik Mükerrer Kalkanı (Akıllı Semantik ve Varlık Benzerliği)
        # Farklı ajanslar aynı haberi farklı cümlelerle servis etse bile (MacBook, indirim vb.) %100 yakalar!
        dup_stopwords = {
            've', 'ile', 'bir', 'bu', 'da', 'de', 'ta', 'te', 'icin', 'için', 'yeni', 'son', 'dakika',
            'gore', 'göre', 'kadar', 'olan', 'olarak', 'eden', 'etti', 'yaptı', 'yaptığı', 'oldu',
            'belli', 'iste', 'işte', 'isteği', 'hakkında', 'neden', 'hangi', 'kimdir', 'nereli', 'kaç',
            'gibi', 'tum', 'tüm', 'neler', 'nelerdir', 'iste', 'boyle', 'böyle', 'biri', 'hepsi'
        }

        def get_word_stems(text):
            words = [re.sub(r'[\'\"\.,!\?:;\-_]', '', w) for w in re.findall(r'\w+', text.lower())]
            stems = set()
            for w in words:
                if len(w) >= 3 and w not in dup_stopwords:
                    stems.add(w[:5] if len(w) > 5 else w)
            return stems

        stems_incoming = get_word_stems(clean_t)

        # Hem articles (AI başlıkları) hem de posted_news (orijinal ajans başlıkları) taranır
        cur_arts = conn.execute("SELECT title, slug FROM articles ORDER BY id DESC LIMIT 250")
        candidates = [(r["title"] or "", r["slug"] or "") for r in cur_arts.fetchall()]

        cur_posted = conn.execute("SELECT title FROM posted_news ORDER BY id DESC LIMIT 250")
        candidates.extend([(r["title"] or "", "") for r in cur_posted.fetchall()])

        for exist_title_raw, exist_slug_raw in candidates:
            exist_title = exist_title_raw.strip().lower()
            exist_slug = exist_slug_raw.strip().lower()

            # A. Slug benzerliği (>75%)
            if exist_slug and difflib.SequenceMatcher(None, slug, exist_slug).ratio() > 0.75:
                return True

            # B. Doğrudan Başlık Benzerliği (>68%)
            if difflib.SequenceMatcher(None, clean_t, exist_title).ratio() > 0.68:
                return True

            # C. Çelik Kelime Kökü ve Anahtar Varlık Örtüşmesi (Hassas Dedup)
            if len(stems_incoming) >= 3:
                stems_exist = get_word_stems(exist_title)
                if len(stems_exist) >= 3:
                    overlap_stems = stems_incoming & stems_exist
                    overlap = len(overlap_stems)
                    min_len = min(len(stems_incoming), len(stems_exist))
                    ratio = (overlap / min_len) if min_len > 0 else 0

                    # 1. Ortak kelime kökü oranı %38 ve üzeriyse kesinlikle mükerrerdir
                    if ratio >= 0.38:
                        return True

                    # 2. En az 3 kritik kök ortaksa
                    if overlap >= 3:
                        return True

                    # 3. İki başlıkta da en az 2 adet uzun/nadir kelime (>=5 harf) ortaksa mükerrerdir
                    long_overlap = sum(1 for s in overlap_stems if len(s) >= 5)
                    if long_overlap >= 2:
                        return True

        return False


def mark_as_posted(news_hash: str, title: str, source: str = "", link: str = "", fb_id: str = None, ig_id: str = None):
    with get_connection() as conn:
        if conn.is_pg:
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

def get_last_bot_posted_time() -> Optional[str]:
    """Botun en son paylaştığı haberin zamanını döner (Yalçın Bey'in panelden attığı manuel videoları karıştırmaz)."""
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT created_at FROM posted_news ORDER BY id DESC LIMIT 1").fetchone()
            if row and row.get("created_at"):
                return str(row["created_at"])
    except Exception as e:
        print(f"get_last_bot_posted_time error: {e}")
    return None


def claim_news_for_processing(news_hash: str, title: str, source: str = "", link: str = "") -> bool:
    """
    Haberi işleme başlamadan önce atomik olarak 'rezerve' eder.
    Haber zaten paylaşılmışsa veya başka bir işçi/deploy şu an bu haberi işliyorsa False döner.
    İlk kapan işçi True alır ve haber anında posted_news tablosuna yazılır.
    Böylece 13.5 dakikalık bekleme veya görsel üretimi sırasında ikinci bir bot/thread ASLA aynı haberi alamaz.
    """
    if is_already_posted(news_hash, title=title, link=link):
        return False

    with get_connection() as conn:
        try:
            if conn.is_pg:
                res = conn.execute("""
                    INSERT INTO posted_news (news_hash, title, source, link)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (news_hash) DO NOTHING
                """, (news_hash, title, source, link))
            else:
                res = conn.execute("""
                    INSERT OR IGNORE INTO posted_news (news_hash, title, source, link)
                    VALUES (?, ?, ?, ?)
                """, (news_hash, title, source, link))
            return (res.rowcount > 0)
        except Exception as e:
            print(f"⚠️ [Claim News Hatası]: {e}")
            return False


def save_article(title: str, summary: str, content: str, image_path: str, source: str, category: str = "Gündem", return_status: bool = False):
    """Makaleyi web sitesi veritabanına kaydeder ve SEO URL slug'ını döner."""
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "haber"

    # MÜKERRER KAYIT ENGELLEYİCİ: Bu haber zaten veritabanında varsa asla tekrar kaydetme!
    with get_connection() as conn:
        # 1. Birebir slug veya başlık kontrolü
        existing = conn.execute(
            "SELECT slug FROM articles WHERE slug = ? OR LOWER(title) = ?",
            (base_slug, title.strip().lower())
        ).fetchone()
        if existing:
            print(f"⚠️ [Mükerrer Haber Engellendi] '{title[:50]}' zaten veritabanında mevcut ({existing['slug']}). İkinci kez eklenmedi.")
            return (existing["slug"], False) if return_status else existing["slug"]

        # 2. Semantik Başlık Benzerliği (Son 150 makale içinde %68 üzeri benzerlik kontrolü)
        cur = conn.execute("SELECT slug, title FROM articles ORDER BY id DESC LIMIT 150")
        recent = cur.fetchall()
        clean_t = title.strip().lower()
        for r in recent:
            ex_title = (r["title"] or "").strip().lower()
            ex_slug = r["slug"]
            if difflib.SequenceMatcher(None, clean_t, ex_title).ratio() > 0.68:
                print(f"⚠️ [Mükerrer Haber Engellendi - Benzer Başlık] '{title[:50]}' sitede zaten var ({ex_slug}). İkinci kez eklenmedi.")
                return (ex_slug, False) if return_status else ex_slug

    # ⛔ KESİN EMİR: Görselsiz veya bozuk görselli haber ASLA veritabanına kaydedilemez!
    img_base = _basename(image_path or "")
    if not img_base:
        print(f"⛔ [VERİTABANI GÖRSEL KALKANI] '{title[:50]}' için image_path boş! Kayıt reddedildi.")
        return ("", False) if return_status else ""
    if not img_base.lower().endswith((".mp4", ".webm", ".mov")):
        if not os.path.exists(image_path) or os.path.getsize(image_path) < 6000:
            print(f"⛔ [VERİTABANI GÖRSEL KALKANI] '{title[:50]}' görsel dosyası eksik veya <6KB! Kayıt reddedildi.")
            return ("", False) if return_status else ""
    try:
        save_image_file(image_path)
    except Exception as e:
        print(f"⚠️ save_image_file uyarısı: {e}")
    if not img_base.lower().endswith((".mp4", ".webm", ".mov")):
        db_img_bytes = get_image(img_base)
        if not db_img_bytes or len(db_img_bytes) < 6000:
            print(f"⛔ [VERİTABANI GÖRSEL KALKANI] '{title[:50]}' görseli PostgreSQL images tablosunda doğrulanamadı! Kayıt reddedildi.")
            return ("", False) if return_status else ""

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
    return (slug, True) if return_status else slug


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
        "analiz": "Analiz",
        "gündem analizi": "Analiz",
        "gundem analizi": "Analiz",
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
        "asayis": "Gündem",
        "asayiş": "Gündem",
        "magazin": "Gündem",
        "yasam": "Sağlık",
        "yaşam": "Sağlık",
        "kultur-sanat": "Gündem",
        "kültür-sanat": "Gündem"
    }
    return mapping.get(c, cat.strip())


def get_articles(limit: int = 20, category: str = None, offset: int = 0) -> List[Dict]:
    """Son yayınlanan makaleleri listeler. 'Son Dakika' tüm kategorilerden anlık sıcak haber akışıdır."""
    with get_connection() as conn:
        if category:
            clean_cat = category.strip()
            if clean_cat.lower() in ["son dakika", "sondakika", "son-dakika", "breaking"]:
                cur = conn.execute("SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
                return [_row_to_dict(row) for row in cur.fetchall()]

            cat_norm = normalize_category_name(category) or category
            cur = conn.execute(
                """SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles 
                   WHERE category = ? OR LOWER(category) = LOWER(?) OR category = ?
                   ORDER BY id DESC LIMIT ? OFFSET ?""",
                (cat_norm, cat_norm, category.strip(), limit, offset)
            )
            rows = [_row_to_dict(row) for row in cur.fetchall()]
            if not rows and offset == 0 and cat_norm != 'Analiz':
                kw = cat_norm.lower()
                cur = conn.execute(
                    """SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles 
                       WHERE title LIKE ? OR summary LIKE ? OR category LIKE ?
                       ORDER BY id DESC LIMIT ? OFFSET ?""",
                    (f"%{kw}%", f"%{kw}%", f"%{kw}%", limit, offset)
                )
                rows = [_row_to_dict(row) for row in cur.fetchall()]
            return rows
        else:
            cur = conn.execute("SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
            return [_row_to_dict(row) for row in cur.fetchall()]


def get_sitemap_articles(limit: int = 500) -> List[Dict]:
    """Site haritaları için: kalite (kelime sayısı) kontrolü yapılabilsin diye içerikle birlikte döner."""
    with get_connection() as conn:
        cur = conn.execute("SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ?", (limit,))
        return [_row_to_dict(row) for row in cur.fetchall()]


def search_articles(query: str, limit: int = 24, offset: int = 0) -> List[Dict]:
    """Tüm makaleler içinde başlık, özet ve içerikte gerçek SQL araması yapar."""
    if not query or not query.strip():
        return get_articles(limit=limit, offset=offset)

    kw = f"%{query.strip().lower()}%"
    with get_connection() as conn:
        like_op = "ILIKE" if conn.is_pg else "LIKE"
        sql = f"""
            SELECT * FROM articles 
            WHERE (title {like_op} ? OR summary {like_op} ? OR content {like_op} ?)
            ORDER BY id DESC LIMIT ? OFFSET ?
        """
        cur = conn.execute(sql, (kw, kw, kw, limit, offset))
        return [_row_to_dict(row) for row in cur.fetchall()]


def get_search_count(query: str) -> int:
    """Arama sorgusuna uyan toplam makale adedini döner."""
    if not query or not query.strip():
        return get_articles_total_count()
    kw = f"%{query.strip().lower()}%"
    with get_connection() as conn:
        like_op = "ILIKE" if conn.is_pg else "LIKE"
        sql = f"SELECT COUNT(*) as c FROM articles WHERE (title {like_op} ? OR summary {like_op} ? OR content {like_op} ?)"
        row = conn.execute(sql, (kw, kw, kw)).fetchone()
        if not row:
            return 0
        if isinstance(row, dict):
            return row.get("c", 0)
        return row[0] if len(row) > 0 else 0

def get_articles_total_count(category: str = None) -> int:
    """Toplam yayınlanmış haber sayısını döner."""
    try:
        with get_connection() as conn:
            if category:
                clean_cat = category.strip()
                if clean_cat.lower() in ["son dakika", "sondakika", "son-dakika", "breaking"]:
                    cur = conn.execute("SELECT COUNT(*) AS c FROM articles")
                    row = cur.fetchone()
                    return (row["c"] if row else 0) if isinstance(row, dict) else (row[0] if row else 0)

                cat_norm = normalize_category_name(category) or category
                cur = conn.execute(
                    """SELECT COUNT(*) AS c FROM articles 
                       WHERE category = ? OR LOWER(category) = LOWER(?) OR category = ?""",
                    (cat_norm, cat_norm, category.strip())
                )
                row = cur.fetchone()
                c = (row["c"] if row else 0) if isinstance(row, dict) else (row[0] if row else 0)
                if c == 0:
                    kw = cat_norm.lower()
                    cur2 = conn.execute(
                        """SELECT COUNT(*) AS c FROM articles 
                           WHERE title LIKE ? OR summary LIKE ? OR category LIKE ?""",
                        (f"%{kw}%", f"%{kw}%", f"%{kw}%")
                    )
                    row2 = cur2.fetchone()
                    return (row2["c"] if row2 else 0) if isinstance(row2, dict) else (row2[0] if row2 else 0)
                return c
            else:
                cur = conn.execute("SELECT COUNT(*) AS c FROM articles")
                row = cur.fetchone()
                return (row["c"] if row else 0) if isinstance(row, dict) else (row[0] if row else 0)
    except Exception as e:
        print("get_articles_total_count error:", e)
        return 0


_SLUG_TO_ID_CACHE = {}

def increment_article_view_by_slug(slug: str):
    """Turbo önbellekten dönen makalelerde gerçek ziyaretçi okunma sayısını veritabanını yormadan RAM'de artırır."""
    if not slug:
        return
    art_id = _SLUG_TO_ID_CACHE.get(slug)
    if art_id is None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT id FROM articles WHERE slug = ? LIMIT 1", (slug,)).fetchone()
                if row:
                    art_id = row["id"]
                    if len(_SLUG_TO_ID_CACHE) > 5000:
                        _SLUG_TO_ID_CACHE.clear()
                    _SLUG_TO_ID_CACHE[slug] = art_id
        except Exception:
            return
    if art_id:
        _start_db_buffer_worker()
        with _RAM_ARTICLE_VIEWS_LOCK:
            _RAM_ARTICLE_VIEWS[art_id] = _RAM_ARTICLE_VIEWS.get(art_id, 0) + 1


def get_article_by_slug(slug: str) -> Optional[Dict]:
    """Slug'a göre makale detayını çeker ve okunma sayısını RAM'de sıfır gecikmeyle biriktirir (0 ms bekleme, 0 thread)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
        if row:
            art_id = row["id"]
            _SLUG_TO_ID_CACHE[slug] = art_id
            _start_db_buffer_worker()
            with _RAM_ARTICLE_VIEWS_LOCK:
                _RAM_ARTICLE_VIEWS[art_id] = _RAM_ARTICLE_VIEWS.get(art_id, 0) + 1
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


def get_trending_articles(limit: int = 5) -> List[Dict]:
    """Son yayınlanan güncel haber havuzu içinden en çok okunan (views DESC) yüksek kaliteli makaleleri listeler."""
    with get_connection() as conn:
        cur = conn.execute(
            """SELECT id, slug, title, summary, content, category, image_path, source, views, created_at
               FROM (SELECT * FROM articles ORDER BY id DESC LIMIT 140) recent_pool
               WHERE LOWER(title) NOT LIKE '%bim %' AND LOWER(title) NOT LIKE '%a101%' AND LOWER(title) NOT LIKE '%şok market%' AND LOWER(title) NOT LIKE '%aktüel%'
               ORDER BY views DESC, id DESC LIMIT ?""",
            (limit,),
        )
        rows = [_row_to_dict(row) for row in cur.fetchall()]
        if len(rows) < limit:
            cur2 = conn.execute("SELECT id, slug, title, summary, content, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ?", (limit,))
            rows = [_row_to_dict(row) for row in cur2.fetchall()]
        return rows


def get_adjacent_articles(article_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Sonsuz ve Kesintisiz Okuma Akışı (Ping-Pong Kısırdöngüsünü Önler):
    - Okuyucu 'Sonraki Haber'e bastıkça geriye doğru sırayla TÜM haberleri okur:
      (742 -> 741 -> 740 -> 739 -> 738...). Asla aynı 2 haber arasında sıkışıp kalmaz.
    - En eski habere gelindiğinde başa (en yeniye) sararak akışı sonsuz tutar.
    """
    with get_connection() as conn:
        # 1. Okuma akışındaki Sıradaki Haber (Daha önce yayınlanmış sıradaki haber)
        cur_older = conn.execute("SELECT * FROM articles WHERE id < ? ORDER BY id DESC LIMIT 1", (article_id,))
        row_older = cur_older.fetchone()
        next_step_art = _row_to_dict(row_older) if row_older else None

        # En eski habere ulaşıldıysa akış kopmasın diye en yeni habere sar
        if not next_step_art:
            cur_wrap = conn.execute("SELECT * FROM articles WHERE id != ? ORDER BY id DESC LIMIT 1", (article_id,))
            row_wrap = cur_wrap.fetchone()
            next_step_art = _row_to_dict(row_wrap) if row_wrap else None

        # 2. Geriye Dönüş Haberi (Daha yeni haber)
        cur_newer = conn.execute("SELECT * FROM articles WHERE id > ? ORDER BY id ASC LIMIT 1", (article_id,))
        row_newer = cur_newer.fetchone()
        prev_step_art = _row_to_dict(row_newer) if row_newer else None

        # En yeni haberdeyse prev_step_art None kalır (next_article ile aynı haberi 2 kez tekrarlamaz)

        # Şablonda next_article değişkeni "Sonraki Habere Geç" kartını besler
        return prev_step_art, next_step_art


def update_article(article_id: int, title: str, summary: str, content: str, category: str) -> bool:
    """Belirtilen ID'li makalenin başlık, özet, içerik ve kategorisini günceller."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE articles SET title = ?, summary = ?, content = ?, category = ? WHERE id = ?",
            (title, summary, content, category, article_id)
        )
        return (cur.rowcount or 0) > 0


_LAST_VISIT_FLUSH = 0

# ========================================================
# 🚀 ULTRA PERFORMANS: RAM BUFFER & BATCH FLUSH (0 ms Ziyaretçi Kaydı)
# ========================================================
_VISITOR_LOG_QUEUE = []
_VISITOR_QUEUE_LOCK = threading.Lock()
_RAM_METRICS = {}
_RAM_METRICS_LOCK = threading.Lock()
_RAM_ARTICLE_VIEWS = {}
_RAM_ARTICLE_VIEWS_LOCK = threading.Lock()
_DASHBOARD_CACHE = {"data": None, "ts": 0}
_BUFFER_WORKER_STARTED = False

def _start_db_buffer_worker():
    global _BUFFER_WORKER_STARTED
    if _BUFFER_WORKER_STARTED:
        return
    _BUFFER_WORKER_STARTED = True

    def _worker():
        while True:
            time.sleep(15)
            # A. Sayaçları Toplu Yaz
            metrics_copy = {}
            with _RAM_METRICS_LOCK:
                if _RAM_METRICS:
                    metrics_copy = dict(_RAM_METRICS)
                    _RAM_METRICS.clear()

            if metrics_copy:
                try:
                    with get_connection() as conn:
                        for k, v in metrics_copy.items():
                            if v > 0:
                                if conn.is_pg:
                                    conn.execute("""
                                        INSERT INTO site_metrics (key, val) VALUES (?, ?)
                                        ON CONFLICT (key) DO UPDATE SET val = site_metrics.val + ?
                                    """, (k, v, v))
                                else:
                                    row = conn.execute("SELECT val FROM site_metrics WHERE key = ?", (k,)).fetchone()
                                    new_val = (row["val"] + v) if row else v
                                    conn.execute("INSERT OR REPLACE INTO site_metrics (key, val) VALUES (?, ?)", (k, new_val))
                except Exception:
                    pass

            # B. Ziyaretçi Loglarını Toplu Yaz
            logs_copy = []
            with _VISITOR_QUEUE_LOCK:
                if _VISITOR_LOG_QUEUE:
                    logs_copy = list(_VISITOR_LOG_QUEUE)
                    _VISITOR_LOG_QUEUE.clear()

            if logs_copy:
                try:
                    with get_connection() as conn:
                        for item in logs_copy:
                            if len(item) == 8:
                                v_hash, is_first, page, ref, dev, ctry, city, v_ts = item
                                conn.execute("""
                                    INSERT INTO visitor_logs (visitor_hash, is_first_visit, page, referrer, device, country, city, created_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (v_hash, is_first, page, ref, dev, ctry, city, v_ts))
                            elif len(item) == 7:
                                v_hash, is_first, page, ref, dev, ctry, city = item
                                conn.execute("""
                                    INSERT INTO visitor_logs (visitor_hash, is_first_visit, page, referrer, device, country, city)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (v_hash, is_first, page, ref, dev, ctry, city))
                            else:
                                v_hash, page, ref, dev, ctry, city = item
                                is_first = 1
                                conn.execute("""
                                    INSERT INTO visitor_logs (visitor_hash, is_first_visit, page, referrer, device, country, city)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (v_hash, is_first, page, ref, dev, ctry, city))
                except Exception:
                    pass

            # C. Makale Okunma Sayılarını Toplu Yaz (0 kilitlenme, 0 gecikme)
            views_copy = {}
            with _RAM_ARTICLE_VIEWS_LOCK:
                if _RAM_ARTICLE_VIEWS:
                    views_copy = dict(_RAM_ARTICLE_VIEWS)
                    _RAM_ARTICLE_VIEWS.clear()

            if views_copy:
                try:
                    with get_connection() as conn:
                        for art_id, count in views_copy.items():
                            if count > 0:
                                conn.execute("UPDATE articles SET views = views + ? WHERE id = ?", (count, art_id))
                except Exception:
                    pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

def record_visit(key: str = "home_visits"):
    """Genel sayfa ziyaret sayacını RAM'de toplar (0 ms bekleme, 0 DB kilidi)."""
    _start_db_buffer_worker()
    with _RAM_METRICS_LOCK:
        _RAM_METRICS[key] = _RAM_METRICS.get(key, 0) + 1


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
            if conn.is_pg:
                conn.execute("""
                    INSERT INTO system_settings (key, val) VALUES (?, ?)
                    ON CONFLICT (key) DO UPDATE SET val = EXCLUDED.val
                """, (key, str(val)))
            else:
                conn.execute("INSERT OR REPLACE INTO system_settings (key, val) VALUES (?, ?)", (key, str(val)))
    except Exception as e:
        print(f"⚠️ Ayar kaydedilemedi ({key}): {e}")


def log_visitor(visitor_hash: str, page: str = "/", referrer: str = "Doğrudan", device: str = "Mobil", country: str = "TR", city: str = "", is_first_visit: int = 1) -> bool:
    """Ziyaretçiyi gerçek giriş saniyesiyle RAM kuyruğuna ekler (0 ms bekleme, 0 DB kilidi)."""
    if not page or page.startswith("/api/") or page.startswith("/assets") or page.startswith("/images"):
        return False
    _start_db_buffer_worker()
    visit_ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with _VISITOR_QUEUE_LOCK:
        if len(_VISITOR_LOG_QUEUE) < 4000:
            _VISITOR_LOG_QUEUE.append((visitor_hash, is_first_visit, page[:120], referrer[:50], device[:30], country[:10], city[:50], visit_ts_utc))
    return True


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
    """Yönetim paneli (/panel) için tüm ayrıntılı canlı analitik ve istatistikleri döner (8 sn RAM önbellekli)."""
    global _DASHBOARD_CACHE
    now = time.time()
    if _DASHBOARD_CACHE.get("data") and (now - _DASHBOARD_CACHE.get("ts", 0)) < 8:
        return _DASHBOARD_CACHE["data"]

    total_articles = 0
    total_views = 0
    home_visits = 0
    top_rows = []
    recent_rows = []
    cat_rows = []
    src_rows = []
    active_now = 1
    today_uniques = 0
    first_time_today = 0
    google_today = 0
    bot_uniques_today = 0
    adsense_today = 0
    adsense_7d = 0
    live_visitors = []
    traffic_sources = []
    device_stats = []
    total_revenue = 0.0
    month_revenue = 0.0
    revenue_records = []
    images_count = 0
    db_size_mb = 0.0

    try:
        with get_connection() as conn:
            # 1. Makale Genel Toplamları (En Kritik - Asla 0 Olmamalı)
            try:
                totals = conn.execute(
                    "SELECT COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS total_views FROM articles"
                ).fetchone()
                if totals:
                    total_articles = totals["cnt"] or 0
                    total_views = int(totals["total_views"] or 0)
            except Exception as e:
                print(f"Makale toplamları hatası: {e}")
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 2. Site Ziyaret Metrikleri
            try:
                home_row = conn.execute(
                    "SELECT val FROM site_metrics WHERE key = ?", ("home_visits",)
                ).fetchone()
                home_visits = int(home_row["val"]) if (home_row and home_row.get("val")) else 0
            except Exception as e:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 3. En Çok Okunanlar & Son Haberler
            try:
                top_rows = conn.execute(
                    "SELECT * FROM articles ORDER BY views DESC, id DESC LIMIT 10"
                ).fetchall()
            except Exception:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            try:
                recent_rows = conn.execute(
                    "SELECT * FROM articles ORDER BY id DESC LIMIT 30"
                ).fetchall()
            except Exception:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 4. Kategori & Kaynak Dağılımları
            try:
                cat_rows = conn.execute(
                    "SELECT category, COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS views FROM articles GROUP BY category ORDER BY cnt DESC"
                ).fetchall()
            except Exception:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            try:
                src_rows = conn.execute(
                    "SELECT source, COUNT(*) AS cnt, COALESCE(SUM(views), 0) AS views FROM articles GROUP BY source ORDER BY cnt DESC"
                ).fetchall()
            except Exception:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 5. CANLI TRAFİK & TEKİL KULLANICI ANALİTİĞİ
            try:
                now_tr = datetime.now(TR_TZ)
                today_start_tr = now_tr.replace(hour=0, minute=0, second=0, microsecond=0)
                today_start_utc = today_start_tr.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                five_min_ago_utc = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
                seven_days_ago_utc = (today_start_tr - timedelta(days=7)).astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                # 🤖 Bot Filtresi: SADECE GERÇEK İNSANLAR (Mobil, Masaüstü, Tablet)
                human_filter = "AND device IN ('Mobil', 'Masaüstü', 'Tablet')"

                act_row = conn.execute(f"""
                    SELECT COUNT(DISTINCT visitor_hash) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? {human_filter}
                """, (five_min_ago_utc,)).fetchone()
                active_now = act_row["c"] if (act_row and act_row["c"]) else 1

                # Gerçek İnsan Tekil Ziyaretçi (Botlar hariç)
                uniq_row = conn.execute(f"""
                    SELECT COUNT(DISTINCT visitor_hash) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? {human_filter}
                """, (today_start_utc,)).fetchone()
                today_uniques = uniq_row["c"] if uniq_row else 0

                # İlk Defa Giren Gerçek İnsanlar (Bugünden önce hiç kaydı olmayan yeni tekil kişiler)
                first_row = conn.execute(f"""
                    SELECT COUNT(DISTINCT visitor_hash) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? {human_filter}
                      AND visitor_hash NOT IN (
                          SELECT visitor_hash FROM visitor_logs WHERE created_at < ?
                      )
                """, (today_start_utc, today_start_utc)).fetchone()
                first_time_today = first_row["c"] if first_row else 0
                first_time_today = min(first_time_today, today_uniques)

                # Google Organik Aramadan Gelen Gerçek İnsanlar
                goog_row = conn.execute(f"""
                    SELECT COUNT(DISTINCT visitor_hash) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? 
                      AND referrer = 'Google'
                      {human_filter}
                """, (today_start_utc,)).fetchone()
                google_today = goog_row["c"] if goog_row else 0

                # Bugünkü Arama Botu Taramaları (İndeksleme İstatistiği)
                bot_row = conn.execute("""
                    SELECT COUNT(DISTINCT visitor_hash) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? 
                      AND device NOT IN ('Mobil', 'Masaüstü', 'Tablet')
                """, (today_start_utc,)).fetchone()
                bot_uniques_today = bot_row["c"] if bot_row else 0

                # 💰 Google AdSense Taramaları ve İnceleme Girişleri (Bugün ve Son 7 Gün)
                ads_today_row = conn.execute("""
                    SELECT COUNT(*) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? 
                      AND (device LIKE ? OR referrer LIKE ?)
                """, (today_start_utc, '%AdSense%', '%AdSense%')).fetchone()
                adsense_today = int(ads_today_row["c"]) if (ads_today_row and ads_today_row["c"]) else 0

                ads_7d_row = conn.execute("""
                    SELECT COUNT(*) AS c 
                    FROM visitor_logs 
                    WHERE created_at >= ? 
                      AND (device LIKE ? OR referrer LIKE ?)
                """, (seven_days_ago_utc, '%AdSense%', '%AdSense%')).fetchone()
                adsense_7d = int(ads_7d_row["c"]) if (ads_7d_row and ads_7d_row["c"]) else 0

                traffic_rows = conn.execute(
                    "SELECT referrer, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY referrer ORDER BY cnt DESC LIMIT 7", (seven_days_ago_utc,)
                ).fetchall()
                traffic_sources = [dict(r) for r in traffic_rows]

                dev_rows = conn.execute(
                    "SELECT device, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY device ORDER BY cnt DESC", (seven_days_ago_utc,)
                ).fetchall()
                device_stats = [dict(r) for r in dev_rows]

                # Her sekmenin (Gerçek Okuyucular / AdSense / Arama Botları) bot yoğunluğunda bile dolu görünmesi için
                # 3 ayrı havuzdan son 20'şer kaydı çekip birleştir
                _base_lv_sql = """
                    SELECT v.*,
                           CASE 
                               WHEN NOT EXISTS (SELECT 1 FROM visitor_logs v2 WHERE v2.visitor_hash = v.visitor_hash AND v2.id < v.id) THEN 1
                               ELSE 0 
                           END AS computed_first
                    FROM visitor_logs v
                    WHERE v.page NOT LIKE ?
                """
                lv_human = conn.execute(
                    _base_lv_sql + " AND v.device IN ('Mobil', 'Masaüstü', 'Tablet') ORDER BY v.id DESC LIMIT 20",
                    ('/api/%',)
                ).fetchall()
                lv_adsense = conn.execute(
                    _base_lv_sql + " AND (v.device LIKE ? OR v.referrer LIKE ?) ORDER BY v.id DESC LIMIT 20",
                    ('/api/%', '%AdSense%', '%AdSense%')
                ).fetchall()
                lv_bots = conn.execute(
                    _base_lv_sql + " AND v.device NOT IN ('Mobil', 'Masaüstü', 'Tablet') AND v.device NOT LIKE ? ORDER BY v.id DESC LIMIT 20",
                    ('/api/%', '%AdSense%')
                ).fetchall()

                seen_lv_ids = set()
                merged_lv = []
                for r in list(lv_human) + list(lv_adsense) + list(lv_bots):
                    d = _row_to_dict(r)
                    rid = d.get("id")
                    if rid in seen_lv_ids:
                        continue
                    seen_lv_ids.add(rid)
                    if "computed_first" in d:
                        d["is_first_visit"] = d["computed_first"]
                    merged_lv.append(d)
                merged_lv.sort(key=lambda x: x.get("id") or 0, reverse=True)
                live_visitors = merged_lv
            except Exception as e:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 6. PARA KAZANMA & GELİR VERİLERİ
            try:
                rev_all = conn.execute("SELECT COALESCE(SUM(amount), 0) AS s FROM revenue_records").fetchone()
                total_revenue = round(float(rev_all["s"]) if rev_all else 0.0, 2)

                rev_rows = conn.execute("SELECT * FROM revenue_records ORDER BY id DESC LIMIT 20").fetchall()
                revenue_records = [_row_to_dict(r) for r in rev_rows]
                month_revenue = total_revenue
            except Exception as e:
                if hasattr(conn.raw, "rollback"):
                    try: conn.raw.rollback()
                    except Exception: pass

            # 7. Görsel Deposu & Boyut
            if conn.is_pg:
                try:
                    images_count = conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
                    size = conn.execute("SELECT pg_database_size(current_database()) AS s").fetchone()["s"]
                    db_size_mb = round(size / 1024 / 1024, 1)
                except Exception:
                    if hasattr(conn.raw, "rollback"):
                        try: conn.raw.rollback()
                        except Exception: pass
    except Exception as outer_e:
        print(f"⚠️ get_dashboard_summary genel hatası: {outer_e}")

    recent_list = [_row_to_dict(r) for r in recent_rows]
    top_list = [_row_to_dict(r) for r in top_rows]
    returning_today = max(0, today_uniques - first_time_today)

    res = {
        "total_articles": total_articles,
        "total_views": total_views,
        "home_visits": home_visits,
        "total_all_hits": total_views + home_visits,
        "avg_views": round(total_views / total_articles, 1) if total_articles > 0 else 0,
        "active_now": max(1, active_now),
        "today_uniques": today_uniques,
        "first_time_today": first_time_today,
        "returning_today": returning_today,
        "google_today": google_today,
        "bot_uniques_today": bot_uniques_today,
        "adsense_today": adsense_today,
        "adsense_7d": adsense_7d,
        "traffic_sources": traffic_sources,
        "device_stats": device_stats,
        "live_visitors": live_visitors,
        "total_revenue": total_revenue,
        "month_revenue": month_revenue,
        "revenue_records": revenue_records,
        "images_count": images_count,
        "db_size_mb": db_size_mb,
        "use_pg": USE_PG,
        "last_article_time": (recent_list[0].get("created_at") or "-") if recent_list else "-",
        "top_articles": top_list,
        "recent_articles": recent_list,
        "categories": [dict(r) for r in cat_rows],
        "sources": [dict(r) for r in src_rows],
    }
    _DASHBOARD_CACHE["data"] = res
    _DASHBOARD_CACHE["ts"] = time.time()
    return res


# ========================================================
# 📊 OKUYUCU NABZI — GERÇEK OYLAR
# ========================================================
REACTION_CHOICES = ("olumlu", "sasirtici", "dusundurucu", "olumsuz")


def get_reactions(article_id: int) -> Dict:
    """Bir haberin gerçek tepki sayılarını döner."""
    counts = {c: 0 for c in REACTION_CHOICES}
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT choice, cnt FROM article_reactions WHERE article_id = ?", (int(article_id),)
            ).fetchall()
            for r in rows:
                if r["choice"] in counts:
                    counts[r["choice"]] = int(r["cnt"] or 0)
    except Exception as e:
        print(f"get_reactions hatası: {e}")
    return counts


def add_reaction(article_id: int, choice: str) -> bool:
    """Bir habere gerçek tepki oyu ekler."""
    if choice not in REACTION_CHOICES:
        return False
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO article_reactions (article_id, choice, cnt) VALUES (?, ?, 1)
                ON CONFLICT (article_id, choice) DO UPDATE SET cnt = article_reactions.cnt + 1
            """, (int(article_id), choice))
        return True
    except Exception as e:
        print(f"add_reaction hatası: {e}")
        return False


_AUDIT_REPORT = {
    "status": "pending",
    "html_sanitized_count": 0,
    "deleted_cards_and_broken_count": 0,
    "remaining_clean_articles_count": 0,
    "cards_remaining_count": 0,
    "cards_remaining": [],
    "broken_short_articles": [],
}

def get_audit_report() -> Dict:
    return _AUDIT_REPORT

def sanitize_db_html_and_heal_cards(heal_cards: bool = False, delete_approved: bool = True) -> Dict:
    """
    1) Veritabanında ham HTML belge sızıntısı, sembol/marka bölünmesi ve aşırı uzun ham özetleri
       (summary) yerinde temizler; post_e9ae894a60.jpg yüzme görselini temiz haliyle günceller.
    2) Kullanıcı onayı (Global Kural 1) doğrultusunda sentetik kart görselli (kendi görseli),
       görseli eksik ve <45 kelime / bozuk URL'li kusurlu haberleri veritabanından temizler.
    """
    global _AUDIT_REPORT
    import content_quality
    import news_fetcher
    import image_generator

    _AUDIT_REPORT["status"] = "running_html_clean"
    sanitized_slugs = []
    remaining_cards = []
    broken_short = []

    try:
        # Temizlenmiş yüzme fotoğrafını (post_e9ae894a60.jpg) PostgreSQL images tablosuna yaz
        clean_swim_path = os.path.join(OUTPUT_DIR, "post_e9ae894a60.jpg")
        if os.path.exists(clean_swim_path):
            try:
                save_image_file(clean_swim_path)
            except Exception as _se:
                print(f"post_e9ae894a60.jpg güncelleme uyarısı: {_se}")

        # ADIM 0.5: Hassas veya yazım hatalı URL slug'larını haberi silmeden kurumsal başlık ve URL'ye dönüştür
        _SLUG_UPGRADES = [
            (
                "thomas-markle-abdde-cocuk-istismari-materyali-bulundurmak-suclamasiyla-yakalandi",
                "thomas-markle-abdde-yurutulen-federal-sorusturma-kapsaminda-gozaltina-alindi",
                "Thomas Markle ABD'de Yürütülen Federal Soruşturma Kapsamında Gözaltına Alındı",
            ),
            (
                "fuhus-aginda-977-milyonluk-trafik",
                "yasa-disi-sebeke-operasyonunda-977-milyon-liralik-para-trafigi",
                "Yasa Dışı Şebeke Operasyonunda 977 Milyon Liralık Para Trafiği",
            ),
            (
                "istanbulda-canli-bahis-dolandiriciligi-8-supheli-gozaltinda",
                "istanbulda-spor-veri-altyapisina-siber-mudahale-8-supheli-gozaltinda",
                "İstanbul'da Spor Veri Altyapısına Siber Müdahale: 8 Şüpheli Gözaltında",
            ),
            (
                "umman-korfezinde-dokme-yuk-gemisi-ile-askeri-unutlar-arasinda-hareketlilik-yasan",
                "umman-korfezinde-dokme-yuk-gemisi-ile-askeri-unsurlar-arasinda-hareketlilik-yasa",
                "Umman Körfezi'nde Dökme Yük Gemisi ile Askeri Unsurlar Arasında Hareketlilik Yaşandı",
            ),
            (
                "f-bahce-tarfinin-konugu-valencia",
                "fenerbahce-bekonun-konugu-valencia",
                "Fenerbahçe Beko'nun Konuğu Valencia",
            ),
            (
                "bime-kumtel-cam-ankastre-set-geliyor-bim-1-7-kasim",
                "perakende-zincirlerinde-kasim-donemi-ankastre-ve-beyaz-esya-kampanyalari",
                "Perakende Zincirlerinde Kasım Dönemi Ankastre ve Beyaz Eşya Kampanyaları",
            ),
        ]
        try:
            with get_connection() as conn:
                for old_sl, new_sl, clean_h1 in _SLUG_UPGRADES:
                    conn.execute(
                        "UPDATE articles SET slug = ?, title = ? WHERE slug = ?",
                        (new_sl, clean_h1, old_sl),
                    )
                conn.execute(
                    "UPDATE articles SET category = 'Ekonomi', title = ? WHERE slug = ?",
                    ("Perakende Zincirlerinde Kasım Dönemi Ankastre ve Beyaz Eşya Kampanyaları", "perakende-zincirlerinde-kasim-donemi-ankastre-ve-beyaz-esya-kampanyalari"),
                )
                conn.execute(
                    "UPDATE articles SET category = 'Gündem' WHERE category = 'Ekonomi' AND (LOWER(title) LIKE '%bahçeli%' OR LOWER(title) LIKE '%kardeşliğimizi%')",
                )
        except Exception as _sue:
            print(f"Slug güncelleme uyarısı: {_sue}")

        # ADIM 1: Render 512MB RAM sınırını korumak için makaleleri 60'arlı küçük paketler halinde (batch) temizle
        import gc
        with get_connection() as conn:
            all_ids = [r["id"] for r in conn.execute("SELECT id FROM articles ORDER BY id DESC").fetchall()]

        for b_idx in range(0, len(all_ids), 60):
            batch_ids = all_ids[b_idx:b_idx + 60]
            ph = ",".join(["?"] * len(batch_ids))
            with get_connection() as conn:
                b_rows = conn.execute(
                    f"SELECT id, slug, title, summary, content, category FROM articles WHERE id IN ({ph})",
                    tuple(batch_ids),
                ).fetchall()
            b_updates = []
            for r in b_rows:
                aid = r["id"]
                slug = r["slug"] or ""
                orig_t = r["title"] or ""
                orig_s = r["summary"] or ""
                orig_c = r["content"] or ""
                orig_cat = r["category"] or "Gündem"
                new_t = content_quality.clean_title_text(news_fetcher.sanitize_news_text(orig_t))
                new_s = content_quality.clean_summary_text(news_fetcher.sanitize_news_text(orig_s), new_t)
                new_c = content_quality.clean_article_html(orig_c)
                new_c = content_quality.ensure_indexable_depth(new_c, new_t, new_s, orig_cat, aid)
                if new_t != orig_t or new_s != orig_s or new_c != orig_c:
                    b_updates.append((new_t, new_s, new_c, aid, slug))
            if b_updates:
                with get_connection() as conn:
                    for new_t, new_s, new_c, aid, slug in b_updates:
                        conn.execute(
                            "UPDATE articles SET title = ?, summary = ?, content = ? WHERE id = ?",
                            (new_t, new_s, new_c, aid),
                        )
                        sanitized_slugs.append(slug)
            del b_rows, b_updates
            gc.collect()

        if sanitized_slugs:
            print(f"✅ [HTML & Özet Temizliği] {len(sanitized_slugs)} makale güncellendi.")

        _AUDIT_REPORT["html_sanitized_count"] = len(sanitized_slugs)
        _AUDIT_REPORT["broken_short_articles"] = broken_short

        # Eğer heal_cards=False ise (normal sunucu açılışı), 1045 görselin binary verisini RAM'e çekme (512 MB OOM Koruması)
        if not heal_cards:
            with get_connection() as conn:
                rem_cnt = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
            _AUDIT_REPORT["remaining_clean_articles_count"] = rem_cnt
            _AUDIT_REPORT["cards_remaining_count"] = 0
            _AUDIT_REPORT["cards_remaining"] = []
            _AUDIT_REPORT["status"] = "completed"
            gc.collect()
            print(f"✨ [Hafif Başlangıç Denetimi Tamamlandı] Kalan Temiz Haber Sayısı: {rem_cnt}")
            return _AUDIT_REPORT

        _AUDIT_REPORT["status"] = "scanning_images"
        with get_connection() as conn:
            rows = conn.execute("SELECT id, slug, title, category, image_path, created_at FROM articles ORDER BY id DESC").fetchall()

        # ADIM 2: Yapay yazılı kart görseli (kendi görseli) veya eksik görsel kullanan haberleri tespit et
        file_to_articles = {}
        for r in rows:
            aid = r["id"]
            slug = r["slug"] or ""
            title = content_quality.clean_title_text(r["title"] or "")
            cat = r["category"] or "Gündem"
            ip = r["image_path"] or ""
            safe_name = os.path.basename(ip.replace("\\", "/")).split("?")[0]
            if not safe_name:
                remaining_cards.append({
                    "id": aid, "slug": slug, "title": title, "img": "(görsel yok)",
                    "reason": "görsel kaydı yok", "created_at": str(r["created_at"] or "")[:16]
                })
                continue
            if safe_name.lower().endswith((".mp4", ".webm", ".mov")):
                continue
            file_to_articles.setdefault(safe_name, []).append({
                "id": aid, "slug": slug, "title": title, "category": cat,
                "img": safe_name, "created_at": str(r["created_at"] or "")[:16]
            })

        all_fnames = list(file_to_articles.keys())
        batch_size = 80
        synth_filenames = set()
        for i in range(0, len(all_fnames), batch_size):
            batch = all_fnames[i:i + batch_size]
            found_map = {}
            with get_connection() as conn:
                placeholders = ",".join(["?"] * len(batch))
                img_rows = conn.execute(
                    f"SELECT filename, data FROM images WHERE filename IN ({placeholders})",
                    tuple(batch),
                ).fetchall()
                for ir in img_rows:
                    fn = ir["filename"]
                    dval = ir["data"]
                    if dval:
                        found_map[fn] = bytes(dval)

            for fn in batch:
                raw_bytes = found_map.get(fn)
                if not raw_bytes:
                    local_p = os.path.join(OUTPUT_DIR, fn)
                    if os.path.exists(local_p) and os.path.getsize(local_p) >= 6000:
                        with open(local_p, "rb") as f:
                            raw_bytes = f.read()

                is_synth = False
                reason = ""
                if not raw_bytes or len(raw_bytes) < 6000:
                    is_synth = True
                    reason = "görsel veritabanında bulunamadı"
                elif image_generator.is_synthetic_card_image(raw_bytes):
                    is_synth = True
                    reason = "yapay yazılı kart (kendi görseli)"
                    synth_filenames.add(fn)

                if is_synth:
                    for item in file_to_articles[fn]:
                        remaining_cards.append({**item, "reason": reason})

        # ADIM 3: Kullanıcı onaylı silme işlemi (Sentetik kartlı + eksik görselli + <45 kelime / bozuk URL'li haberler)
        ids_to_delete = sorted({c["id"] for c in remaining_cards} | {b["id"] for b in broken_short})
        deleted_total = 0
        if delete_approved and ids_to_delete:
            _AUDIT_REPORT["status"] = "deleting_approved"
            with get_connection() as conn:
                for j in range(0, len(ids_to_delete), 100):
                    id_batch = ids_to_delete[j:j + 100]
                    ph = ",".join(["?"] * len(id_batch))
                    conn.execute(f"DELETE FROM articles WHERE id IN ({ph})", tuple(id_batch))
                if synth_filenames:
                    fn_list = list(synth_filenames)
                    for j in range(0, len(fn_list), 100):
                        fn_batch = fn_list[j:j + 100]
                        ph = ",".join(["?"] * len(fn_batch))
                        conn.execute(f"DELETE FROM images WHERE filename IN ({ph})", tuple(fn_batch))
                deleted_total = len(ids_to_delete)
            print(f"🧹 [Onaylı Temizlik Tamamlandı] {deleted_total} adet sentetik kartlı / bozuk haber veritabanından silindi.")
            remaining_cards = []
            broken_short = []

        with get_connection() as conn:
            rem_cnt = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]

        _AUDIT_REPORT["deleted_cards_and_broken_count"] = deleted_total
        _AUDIT_REPORT["remaining_clean_articles_count"] = rem_cnt
        _AUDIT_REPORT["cards_remaining_count"] = len(remaining_cards)
        _AUDIT_REPORT["cards_remaining"] = remaining_cards
        _AUDIT_REPORT["broken_short_articles"] = broken_short
        _AUDIT_REPORT["status"] = "completed"
        print(f"✨ [Denetim Tamamlandı] Kalan %100 Gerçek Fotoğraflı Temiz Haber Sayısı: {rem_cnt}")
    except Exception as e:
        _AUDIT_REPORT["status"] = f"error: {e}"
        print(f"⚠️ sanitize_db_html_and_heal_cards hatası: {e}")
    return _AUDIT_REPORT
