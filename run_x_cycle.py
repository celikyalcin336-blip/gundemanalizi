"""
X (Twitter) 7/24 Bağımsız Bulut Döngüsü
- Render veya GitHub Actions üzerinde PC kapalıyken bile çalışır.
- Veritabanındaki en güncel haberleri kalite süzgecinden geçirir.
- 45 dakikada 1 adet flaş haberi fotoğraflı tweet olarak yayınlar.
"""
import os
import sys
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
import database
import x_poster


def run_cycle(force: bool = False):
    print("🚀 [X Auto-Poster] Kontrol başlatılıyor...")

    # 1. Zaman ve Sessiz Saat Kontrolü
    allowed, reason = x_poster.can_post_to_x(force=force)
    if not allowed:
        print(f"⏳ [X Auto-Poster] {reason}")
        return False

    # 2. Veritabanındaki Son Haberleri Tara
    articles = database.get_articles(limit=12)
    if not articles:
        print("ℹ️ Veritabanında henüz haber bulunamadı.")
        return False

    for art in articles:
        title = art.get("title", "")
        summary = art.get("summary", "")
        category = art.get("category", "Gündem")
        slug = art.get("slug", "")
        image_path = art.get("image_path", "")

        # Bu haber daha önce tweetlendi mi?
        tweet_flag = database.get_setting(f"tweeted_{slug}", "0")
        if tweet_flag == "1":
            continue

        # Kalite Filtresi
        worthy, w_reason = x_poster.is_worthy_for_x(title, summary, category)
        if not worthy:
            # Çöp haberi işaretle ki tekrar tekrar taranmasın
            database.set_setting(f"tweeted_{slug}", "skip")
            print(f"⏩ [Kalite Filtresi] Atlandı ({title[:35]}...): {w_reason}")
            continue

        # Onaylı Aday!
        site_url = f"{config.SITE_URL}/haber/{slug}"
        print(f"🎯 [X Paylaşım Adayı] Kategori: {category} | Başlık: {title}")

        res = x_poster.post_article_to_x(
            title=title,
            summary=summary,
            site_url=site_url,
            image_path=image_path,
            category=category,
            force=force
        )

        if res.get("status") == "success":
            database.set_setting(f"tweeted_{slug}", "1")
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
