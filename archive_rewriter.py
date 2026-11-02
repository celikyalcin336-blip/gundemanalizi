"""
Arşiv Yenileyici (Archive Rewriter)
===================================
Gemini zorunlu kuralından ÖNCE yayınlanmış, kısa / kaynağa çok benzeyen eski haberleri
arka planda tek tek, özgün ve doyurucu metinlerle yeniden yazar.

Kurallar:
- HİÇBİR HABER SİLİNMEZ. Link (slug), başlık, fotoğraf, tarih ve kategori aynen korunur.
- Eski metin `content_legacy` sütununda yedeklenir (istenirse geri alınabilir).
- Kaynak metin yetersizse (orijinal sayfa yok/kısa) haber YENİDEN YAZILMAZ; yapay zekanın
  bilgi uydurmasına izin verilmez. Haber sitede kalır, noindex olarak bekler.
- Haber yayın botunu ve Gemini kotasını yormamak için yavaş çalışır (varsayılan 5 dakikada 1 haber).

Durum değerleri (articles.rewrite_status):
  NULL       -> henüz bakılmadı
  'working'  -> şu an işleniyor
  'done'     -> yeniden yazıldı
  'ok'       -> zaten yeterince uzun, dokunulmadı
  'skip_src' -> kaynak metin yetersiz, dokunulmadı (uydurma riski)
  'fail'     -> yapay zeka metin üretemedi (sonra tekrar denenebilir)
"""
import os
import time
import traceback

import database

REWRITE_INTERVAL_SEC = int(os.getenv("ARCHIVE_REWRITE_INTERVAL", "300"))
MIN_SOURCE_WORDS = 150
_COLUMNS_READY = False


def ensure_columns():
    """articles tablosuna yedek ve durum sütunlarını ekler (varsa dokunmaz)."""
    global _COLUMNS_READY
    if _COLUMNS_READY:
        return
    for col in ("content_legacy TEXT", "rewrite_status TEXT"):
        try:
            with database.get_connection() as conn:
                if conn.is_pg:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col}")
                else:
                    conn.execute(f"ALTER TABLE articles ADD COLUMN {col}")
        except Exception:
            pass  # SQLite: sütun zaten varsa hata verir, sorun değil
    try:
        with database.get_connection() as conn:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_rewrite ON articles (rewrite_status)")
    except Exception:
        pass
    _COLUMNS_READY = True


def _set_status(article_id: int, status: str):
    with database.get_connection() as conn:
        conn.execute("UPDATE articles SET rewrite_status = ? WHERE id = ?", (status, article_id))


def _claim(article_id: int) -> bool:
    """Aynı haberi iki işlemin birden almasını engeller."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "UPDATE articles SET rewrite_status = 'working' WHERE id = ? AND rewrite_status IS NULL",
            (article_id,),
        )
        return (cur.rowcount or 0) > 0


def _find_source_link(title: str, image_path: str = "") -> str:
    """Haberin orijinal kaynak linkini posted_news kayıtlarından bulur.
    Görsel adı `post_<news_hash[:10]>.jpg` biçiminde olduğundan önce hash ile birebir eşleştirilir."""
    import re as _re
    m = _re.search(r"post_([0-9a-f]{10})", image_path or "")
    if m:
        with database.get_connection() as conn:
            row = conn.execute(
                "SELECT link FROM posted_news WHERE news_hash LIKE ? AND link IS NOT NULL ORDER BY id DESC LIMIT 1",
                (m.group(1) + "%",),
            ).fetchone()
            if row and row["link"]:
                return row["link"]
    t = (title or "").strip()
    if not t:
        return ""
    with database.get_connection() as conn:
        row = conn.execute(
            "SELECT link FROM posted_news WHERE title = ? AND link IS NOT NULL ORDER BY id DESC LIMIT 1", (t,)
        ).fetchone()
        if row and row["link"]:
            return row["link"]
        like_op = "ILIKE" if conn.is_pg else "LIKE"
        prefix = t[:45].replace("%", "_")
        row = conn.execute(
            f"SELECT link FROM posted_news WHERE title {like_op} ? AND link IS NOT NULL ORDER BY id DESC LIMIT 1",
            (prefix + "%",),
        ).fetchone()
        return (row["link"] if row else "") or ""


def _next_candidate():
    """Yeniden yazılmayı bekleyen en yeni haberi döner (okurun ve denetçinin ilk gördüğü sayfalar önce)."""
    import content_quality
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT id, slug, title, summary, content, category, source, image_path FROM articles "
            "WHERE rewrite_status IS NULL ORDER BY id DESC LIMIT 25"
        ).fetchall()
    for r in rows:
        d = dict(r)
        try:
            import main as _bot_main
            if _bot_main.is_commodity_news(d.get("title") or ""):
                _set_status(d["id"], "commodity")  # loto/burç vb.: Gemini harcanmaz, noindex kalır
                continue
        except Exception:
            pass
        if content_quality.is_thin(d.get("content") or ""):
            return d
        _set_status(d["id"], "ok")
    return None


def rewrite_one(dry_run: bool = False) -> str:
    """Tek bir eski haberi işler. Dönüş: işlem sonucu ('done', 'skip_src', 'fail', 'ok', 'empty')."""
    import ai_writer
    import content_quality
    import news_fetcher

    ensure_columns()
    art = _next_candidate()
    if not art:
        return "empty"
    if not dry_run and not _claim(art["id"]):
        return "busy"

    aid, title = art["id"], art["title"]
    try:
        link = _find_source_link(title, art.get("image_path") or "")
        scraped = ""
        if link:
            try:
                scraped = (news_fetcher.fetch_article_details(link, max_paragraphs=15) or {}).get("body", "") or ""
            except Exception:
                scraped = ""
        existing = content_quality._norm(content_quality.clean_article_html(art.get("content") or ""))
        source_text = scraped if len(scraped.split()) > len(existing.split()) else existing

        if len(source_text.split()) < MIN_SOURCE_WORDS:
            print(f"⏩ [Arşiv] #{aid} kaynak metin yetersiz ({len(source_text.split())} kelime), uydurma riski nedeniyle dokunulmadı: {title[:60]}")
            if not dry_run:
                _set_status(aid, "skip_src")
            return "skip_src"

        data = ai_writer.generate_full_article(title, source_text, art.get("source") or "", force_category=art.get("category"))
        if not data or content_quality.is_thin(data.get("content") or ""):
            print(f"⚠️ [Arşiv] #{aid} yapay zeka yeterli metin üretemedi: {title[:60]}")
            if not dry_run:
                _set_status(aid, "fail")
            return "fail"

        if dry_run:
            print(f"🧪 [Arşiv DRY] #{aid} {content_quality.visible_word_count(data['content'])} kelime üretildi: {title[:60]}")
            return "done"

        with database.get_connection() as conn:
            conn.execute(
                "UPDATE articles SET content_legacy = COALESCE(content_legacy, content), "
                "content = ?, summary = ?, rewrite_status = 'done' WHERE id = ?",
                (data["content"], data.get("summary") or art.get("summary") or "", aid),
            )
        print(f"✅ [Arşiv] #{aid} yeniden yazıldı ({content_quality.visible_word_count(data['content'])} kelime): {title[:60]}")
        return "done"
    except Exception as e:
        print(f"⚠️ [Arşiv] #{aid} hata: {e}")
        traceback.print_exc()
        if not dry_run:
            try:
                _set_status(aid, "fail")
            except Exception:
                pass
        return "fail"


def get_progress() -> dict:
    ensure_columns()
    with database.get_connection() as conn:
        rows = conn.execute(
            "SELECT COALESCE(rewrite_status, 'bekliyor') AS s, COUNT(*) AS c FROM articles GROUP BY COALESCE(rewrite_status, 'bekliyor')"
        ).fetchall()
    return {r["s"]: r["c"] for r in rows}


def background_worker():
    """web_server başlangıcında thread olarak çalışır."""
    if os.getenv("ARCHIVE_REWRITE_ENABLED", "1") != "1":
        print("⏸️ [Arşiv] Arşiv yenileyici kapalı (ARCHIVE_REWRITE_ENABLED != 1).")
        return
    time.sleep(120)  # açılışta site ve haber botu önce ısınsın
    try:
        ensure_columns()
        # Yarım kalmış (sunucu yeniden başlarken kesilmiş) işleri tekrar kuyruğa al
        with database.get_connection() as conn:
            conn.execute("UPDATE articles SET rewrite_status = NULL WHERE rewrite_status = 'working'")
    except Exception as e:
        print(f"⚠️ [Arşiv] Başlangıç hatası: {e}")
    print(f"🗂️ [Arşiv] Eski haber yenileyici aktif ({REWRITE_INTERVAL_SEC} sn'de 1 haber).")
    fail_streak = 0
    last_fail_reset = 0
    while True:
        wait = REWRITE_INTERVAL_SEC
        try:
            if database.get_setting("archive_rewrite_paused", "0") == "1":
                time.sleep(600)
                continue
            res = rewrite_one()
            if res == "empty":
                wait = 3600  # bekleyen haber kalmadı, saatte bir kontrol et
                # Kota vb. nedeniyle başarısız olanları günde bir kez yeniden kuyruğa al
                if time.time() - last_fail_reset > 86400:
                    last_fail_reset = time.time()
                    with database.get_connection() as conn:
                        cur = conn.execute("UPDATE articles SET rewrite_status = NULL WHERE rewrite_status = 'fail'")
                        if (cur.rowcount or 0) > 0:
                            wait = 60
            elif res == "fail":
                fail_streak += 1
                wait = min(REWRITE_INTERVAL_SEC * (2 ** fail_streak), 3600)  # kota dolduysa geri çekil
            else:
                fail_streak = 0
                if res in ("ok", "skip_src"):
                    wait = 20  # Gemini çağrısı yapılmadı, hızlıca sıradakine geç
        except Exception as e:
            print(f"⚠️ [Arşiv] Döngü hatası: {e}")
            wait = 900
        time.sleep(wait)


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print(get_progress())
    print(rewrite_one(dry_run="--dry" in sys.argv))
