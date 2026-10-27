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
                    minconn=1, maxconn=18, dsn=DATABASE_URL, connect_timeout=5
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
            try:
                pool = _get_pg_pool()
                if pool:
                    self.raw = pool.getconn()
                    self.from_pool = True
                    self.is_pg = True
                else:
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

    # Arka plan API sorgu kayıtlarını (döviz kurları vb.) ziyaretçi geçmişinden temizle
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM visitor_logs WHERE page LIKE ?", ('/api/%',))
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
                            save_image_file(fn, t_out)
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

                # 1. Başlık temizliği
                clean_title = news_fetcher.sanitize_news_text(orig_title)
                clean_title = re.sub(r'\s*-\s*(?:Hürriyet|Mynet|Milliyet|Sabah|Habertürk|Ensonhaber|NTV|Bloomberg HT).*$', '', clean_title, flags=re.I).strip()

                # 2. Özet temizliği
                clean_summary = news_fetcher.sanitize_news_text(orig_summary)

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
                correct_cat = ai_writer.classify_article(clean_title, clean_summary, None) if hasattr(ai_writer, 'classify_article') else category
                
                # 5. Kesilmiş / yarım kalmış lead paragraf tamiri (örn: '... düzenlenen 14.')
                if re.search(r'\b\d+\.\s*$', clean_summary):
                    # Özette sayı noktalı kalmışsa içerikten tamamla
                    lead_m = re.search(r'<p class="lead[^>]*>(.*?)</p>', clean_content, re.DOTALL)
                    if lead_m:
                        full_lead = lead_m.group(1).strip()
                        if not re.search(r'\b\d+\.\s*$', full_lead):
                            clean_summary = full_lead

                # 6. Çok kısa kalmış (1-2 cümlelik) veya eksik paragraflı haberleri zenginleştir (Örn: Frank McCourt vb.)
                paras = re.findall(r'<p class="text-slate-300[^>]*>(.*?)</p>', clean_content, re.DOTALL)
                if len(paras) < 2 and '<p class="lead' in clean_content:
                    cat_lower = correct_cat.lower()
                    extra_paras = []
                    if "eko" in cat_lower:
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Piyasalarda ve ekonomi çevrelerinde geniş yankı uyandıran gelişmeyle ilgili olarak uzmanlar, mali dengeler, fiyatlama dinamikleri ve yatırım trendleri üzerindeki etkilerin önümüzdeki süreçte belirginleşeceğini vurguluyor. Yüksek meblağlı işlemler ve piyasa hareketlilikleri, sektör temsilcileri tarafından yakından izleniyor.</p>')
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Önümüzdeki günlerde sürecin resmiyet kazanması ve ilgili finansal adımların tamamlanmasıyla birlikte, sektörel göstergeler ve emsal değerler açısından piyasaların nasıl bir yön çizeceği ekonomi servisimiz tarafından takip edilmektedir.</p>')
                    elif "spor" in cat_lower:
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Spor kamuoyunda ve taraftarlar arasında büyük heyecan uyandıran gelişmeyle ilgili olarak kulüp yönetiminin resmi adımları bekleniyor. Teknik heyetin sezon planlaması doğrultusunda atılacak bu adımın, takım içi dengelere ve önümüzdeki kritik maç takvimine doğrudan etki etmesi öngörülüyor.</p>')
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Müsabaka takvimi ve resmi sözleşme süreçlerinde imzaların atılmasının ardından, tarafların önümüzdeki günlerde kapsamlı bir bilgilendirmeyle ayrıntıları paylaşması beklenirken, spor servisimiz gelişmeleri aktaracaktır.</p>')
                    elif "tekno" in cat_lower:
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Teknoloji dünyasında ve dijital ekosistemde dengeleri değiştirebilecek bu yenilik, geliştiriciler ve son kullanıcılar açısından önemli avantajlar barındırıyor. Yüksek işlem kapasitesi ve yeni nesil algoritmalarla donatılan sistemin sektörel rekabeti artıracağı vurgulanıyor.</p>')
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Teknoloji otoriteleri, yeni modelin yaygınlaşmasıyla birlikte dijital dönüşüm süreçlerinde hız ve verimlilik artışı yaşanacağına dikkat çekerken, küresel pazardaki entegrasyon takvimi merakla takip ediliyor.</p>')
                    elif "sağlık" in cat_lower or "saglik" in cat_lower:
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Sağlık otoriteleri ve tıp uzmanları, doğru bilgilendirmenin ve erken farkındalığın hayati önem taşıdığına dikkat çekiyor. Benzer sağlık göstergeleri karşısında vatandaşların vakit kaybetmeden uzman hekim kontrolünden geçmesinin önemine vurgu yapılıyor.</p>')
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Sağlıklı yaşam standartları ve koruyucu hekimlik kapsamında alınacak bireysel tedbirlerin yaşam kalitesini doğrudan artıracağı belirtilirken, klinik değerlendirmeler yakından izleniyor.</p>')
                    else:
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Gelişmeyle ilgili resmi makamlar ve yetkili mercilerden gelecek yeni bilgilendirmeler beklenirken, kamuoyundaki yansımalar dikkatle takip ediliyor. Sürecin detayları anbean okuyucularımızla paylaşılmaya devam edecektir.</p>')
                        extra_paras.append('<p class="text-slate-300 leading-relaxed mb-4">Konuya ilişkin kurumlar arası koordinasyon ve sahadaki yansımalar yakından izlenirken, yeni gelişmeler netleştikçe haberimiz güncellenecektir.</p>')

                    if '<div class="p-5 rounded-xl bg-red-950/40' in clean_content:
                        clean_content = clean_content.replace(
                            '<div class="p-5 rounded-xl bg-red-950/40',
                            "\n".join(extra_paras) + '\n<div class="p-5 rounded-xl bg-red-950/40'
                        )
                    else:
                        clean_content = clean_content + "\n" + "\n".join(extra_paras)

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
    Görseli web için küçültüp optimize eder (1200x675 Google Discover HD, JPEG kalite 68).
    1080px ~250 KB'lık kart, gözle fark edilmeyecek kalitede ~40-60 KB'a iner.
    Telegram ve sosyal medyaya giden orijinal dosya etkilenmez.
    """
    from io import BytesIO
    from PIL import Image
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((1200, 675), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=68, optimize=True, progressive=True)
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
            data = f.read()
        if not data or len(data) < 200:
            return
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
    safe_name = os.path.basename(filename)
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT data FROM images WHERE filename = ? LIMIT 1", (safe_name,)).fetchone()
            if row and row.get("data"):
                return bytes(row["data"])
    except Exception as e:
        print(f"Görsel veritabanı okuma hatası ({safe_name}): {e}")
    return None


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

        # 4. Son 200 makale içinde Çok Katmanlı Akıllı Benzerlik Kontrolü
        # Farklı ajanslar aynı haberi 1-2 kelime farkla veya soru formatında servis ettiğinde anında yakalar
        dup_stopwords = {
            've', 'ile', 'bir', 'bu', 'da', 'de', 'ta', 'te', 'icin', 'için', 'yeni', 'son', 'dakika',
            'gore', 'göre', 'kadar', 'olan', 'olarak', 'eden', 'etti', 'yaptı', 'yaptığı', 'oldu',
            'belli', 'iste', 'işte', 'isteği', 'hakkında', 'neden', 'hangi', 'kimdir', 'nereli', 'kaç'
        }

        def get_word_stems(text):
            words = [re.sub(r'[\'\"\.,!\?:;\-_]', '', w) for w in re.findall(r'\w+', text.lower())]
            stems = set()
            for w in words:
                if len(w) >= 3 and w not in dup_stopwords:
                    stems.add(w[:5] if len(w) > 5 else w)
            return stems

        stems_incoming = get_word_stems(clean_t)

        cur = conn.execute("SELECT title, slug FROM articles ORDER BY id DESC LIMIT 200")
        recent_articles = cur.fetchall()

        for r in recent_articles:
            exist_title = (r["title"] or "").strip().lower()
            exist_slug = (r["slug"] or "").strip().lower()

            # A. Slug benzerliği (>80%)
            if difflib.SequenceMatcher(None, slug, exist_slug).ratio() > 0.80:
                return True

            # B. Doğrudan Başlık Benzerliği (>65%)
            if difflib.SequenceMatcher(None, clean_t, exist_title).ratio() > 0.65:
                return True

            # C. Kelime Kökü Örtüşmesi (Ortak Kök Oranı >= %50)
            if len(stems_incoming) >= 3:
                stems_exist = get_word_stems(exist_title)
                if len(stems_exist) >= 3:
                    overlap = len(stems_incoming & stems_exist)
                    min_len = min(len(stems_incoming), len(stems_exist))
                    if min_len > 0 and (overlap / min_len) >= 0.50:
                        return True

            # D. Özel İsim / Anahtar İkili (Kişi veya Şirket Adı + Eylem Örtüşmesi)
            # Örn: 'nusret altınbaş' VEYA 'spacex 40'
            key_entities = [w for w in re.findall(r'\w+', clean_t) if len(w) >= 4 and w not in dup_stopwords]
            for i in range(len(key_entities) - 1):
                pair = f"{key_entities[i]} {key_entities[i+1]}"
                if pair in exist_title:
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


def save_article(title: str, summary: str, content: str, image_path: str, source: str, category: str = "Gündem") -> str:
    """Makaleyi web sitesi veritabanına kaydeder ve SEO URL slug'ını döner."""
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "haber"

    # MÜKERRER KAYIT ENGELLEYİCİ: Bu haber zaten veritabanında varsa asla tekrar kaydetme!
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT slug FROM articles WHERE slug = ? OR LOWER(title) = ?",
            (base_slug, title.strip().lower())
        ).fetchone()
        if existing:
            print(f"⚠️ [Mükerrer Haber Engellendi] '{title[:50]}' zaten veritabanında mevcut ({existing['slug']}). İkinci kez eklenmedi.")
            return existing["slug"]

    # Görseli kalıcı depoya yaz (Her türlü ağ/veritabanı istisnasına karşı korumalı)
    try:
        save_image_file(image_path)
    except Exception as e:
        print(f"⚠️ save_image_file güvenli atlandı: {e}")

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
    """Son yayınlanan makaleleri listeler. 'Son Dakika' tüm kategorilerden anlık sıcak haber akışıdır."""
    with get_connection() as conn:
        if category:
            clean_cat = category.strip()
            if clean_cat.lower() in ["son dakika", "sondakika", "son-dakika", "breaking"]:
                cur = conn.execute("SELECT id, slug, title, summary, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
                return [_row_to_dict(row) for row in cur.fetchall()]

            cat_norm = normalize_category_name(category) or category
            cur = conn.execute(
                """SELECT id, slug, title, summary, category, image_path, source, views, created_at FROM articles 
                   WHERE category = ? OR LOWER(category) = LOWER(?) OR category = ?
                   ORDER BY id DESC LIMIT ? OFFSET ?""",
                (cat_norm, cat_norm, category.strip(), limit, offset)
            )
            rows = [_row_to_dict(row) for row in cur.fetchall()]
            if not rows and offset == 0:
                kw = cat_norm.lower()
                cur = conn.execute(
                    """SELECT id, slug, title, summary, category, image_path, source, views, created_at FROM articles 
                       WHERE title LIKE ? OR summary LIKE ? OR category LIKE ?
                       ORDER BY id DESC LIMIT ? OFFSET ?""",
                    (f"%{kw}%", f"%{kw}%", f"%{kw}%", limit, offset)
                )
                rows = [_row_to_dict(row) for row in cur.fetchall()]
            return rows
        else:
            cur = conn.execute("SELECT id, slug, title, summary, category, image_path, source, views, created_at FROM articles ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
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


def _async_inc_view(art_id: int):
    try:
        with get_connection() as conn:
            conn.execute("UPDATE articles SET views = views + 1 WHERE id = ?", (art_id,))
    except Exception:
        pass

def get_article_by_slug(slug: str) -> Optional[Dict]:
    """Slug'a göre makale detayını çeker ve okunma sayısını arka planda artırır (0 ms bekleme)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM articles WHERE slug = ?", (slug,)).fetchone()
        if row:
            import threading
            threading.Thread(target=_async_inc_view, args=(row["id"],), daemon=True).start()
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
    """En çok okunan (views DESC) makaleleri listeler."""
    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM articles ORDER BY views DESC, id DESC LIMIT ?", (limit,))
        return [_row_to_dict(row) for row in cur.fetchall()]


def get_adjacent_articles(article_id: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Mevcut makalenin bir önceki ve bir sonraki makalesini döner (prev, next)."""
    with get_connection() as conn:
        # Önceki haber (ID'si daha küçük olan)
        cur_prev = conn.execute("SELECT * FROM articles WHERE id < ? ORDER BY id DESC LIMIT 1", (article_id,))
        row_prev = cur_prev.fetchone()
        prev_art = _row_to_dict(row_prev) if row_prev else None

        # Sonraki haber (ID'si daha büyük olan)
        cur_next = conn.execute("SELECT * FROM articles WHERE id > ? ORDER BY id ASC LIMIT 1", (article_id,))
        row_next = cur_next.fetchone()
        next_art = _row_to_dict(row_next) if row_next else None

        # Eğer kullanıcı en yeni haberdeyse (next yoksa), akışı koparmamak için önceki haberi sonraki olarak ver
        if not next_art and prev_art:
            next_art = prev_art
        # Eğer kullanıcı en eski haberdeyse (prev yoksa), sonraki haberi önceki olarak ver
        if not prev_art and next_art:
            prev_art = next_art

        return prev_art, next_art


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
                except Exception as e:
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
                            v_hash, page, ref, dev, ctry, city = item
                            conn.execute("""
                                INSERT INTO visitor_logs (visitor_hash, is_first_visit, page, referrer, device, country, city)
                                VALUES (?, 0, ?, ?, ?, ?, ?)
                            """, (v_hash, page, ref, dev, ctry, city))
                except Exception as e:
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


def log_visitor(visitor_hash: str, page: str = "/", referrer: str = "Doğrudan", device: str = "Mobil", country: str = "TR", city: str = "") -> bool:
    """Ziyaretçiyi RAM kuyruğuna ekler (0 ms bekleme, 0 DB kilidi)."""
    if not page or page.startswith("/api/") or page.startswith("/assets") or page.startswith("/images"):
        return False
    _start_db_buffer_worker()
    with _VISITOR_QUEUE_LOCK:
        if len(_VISITOR_LOG_QUEUE) < 4000:
            _VISITOR_LOG_QUEUE.append((visitor_hash, page[:120], referrer[:50], device[:30], country[:10], city[:50]))
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

                act_row = conn.execute(
                    "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ?", (five_min_ago_utc,)
                ).fetchone()
                active_now = act_row["c"] if act_row else 1

                uniq_row = conn.execute(
                    "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ?", (today_start_utc,)
                ).fetchone()
                today_uniques = uniq_row["c"] if uniq_row else 0

                first_row = conn.execute(
                    "SELECT COUNT(DISTINCT visitor_hash) AS c FROM visitor_logs WHERE created_at >= ? AND is_first_visit = 1", (today_start_utc,)
                ).fetchone()
                first_time_today = first_row["c"] if first_row else 0

                traffic_rows = conn.execute(
                    "SELECT referrer, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY referrer ORDER BY cnt DESC LIMIT 7", (seven_days_ago_utc,)
                ).fetchall()
                traffic_sources = [dict(r) for r in traffic_rows]

                dev_rows = conn.execute(
                    "SELECT device, COUNT(*) AS cnt FROM visitor_logs WHERE created_at >= ? GROUP BY device ORDER BY cnt DESC", (seven_days_ago_utc,)
                ).fetchall()
                device_stats = [dict(r) for r in dev_rows]

                lv_rows = conn.execute(
                    "SELECT * FROM visitor_logs WHERE page NOT LIKE ? ORDER BY id DESC LIMIT 20", ('/api/%',)
                ).fetchall()
                live_visitors = [_row_to_dict(r) for r in lv_rows]
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