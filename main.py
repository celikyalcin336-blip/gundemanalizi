import os
import sys
import time
import argparse
from datetime import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config
import database
import news_fetcher
import ai_writer
import image_generator
import meta_poster
import telegram_notifier

def process_single_news(item: dict) -> bool:
    """
    Tek bir haberi işler:
    1. AI veya şablon ile metin ve hashtag üretir.
    2. Instagram/Facebook için haber kartı görseli oluşturur.
    3. Facebook ve Instagram'a gönderir (veya Dry Run modunda simüle eder).
    4. Başarılı olursa veritabanına kaydeder.
    """
    title = item["title"]
    source = item["source"]
    link = item["link"]
    image_url = item.get("image_url")
    news_hash = item["hash"]

    # Mükerrer Paylaşım Kalkanı: Son saniye kontrolü (Aynı veya benzer haber varsa kesinlikle atla)
    if database.is_already_posted(news_hash, title=title, link=link):
        print(f"⚠️ [Mükerrer Paylaşım Engellendi] '{title[:50]}' daha önce yayınlanmış. Atlanıyor.")
        return False

    print("\n" + "="*60)
    print(f"🔥 İşlenen Haber: {title}")
    print(f"📌 Kaynak: {source}")
    print("="*60)

    # 1. Metin, Makale ve Yüksek Kaliteli Medya Toplama
    print("✍️  Sosyal medya metni, web makalesi ve yüksek çözünürlüklü görseller toplanıyor...")
    raw_summary = item.get("summary", "")
    
    # Haberin orijinal web sayfasına giderek gerçek paragrafları ve Full HD görselleri al
    article_details = news_fetcher.fetch_article_details(link)
    scraped_body = article_details.get("body", "")
    summary = scraped_body if (scraped_body and len(scraped_body) > len(raw_summary)) else raw_summary

    # Telegram ve Sosyal Medya Metinleri
    telegram_caption = ai_writer.generate_telegram_post(title, summary, source)
    ai_result = ai_writer.generate_social_caption(title, summary, source)
    social_caption = ai_result["caption"]
    item_category = item.get("category")
    article_data = ai_writer.generate_full_article(title, summary, source, force_category=item_category)
    category = article_data.get("category", "Gündem")
    print(f"   [Kategori: {category} | Telegram Metni Hazır]")

    # 2. Kristal Netliğinde Görsel & Yan Yana 2'li Kolaj Üretimi
    print("🎨 Yüksek çözünürlüklü haber görseli hazırlanıyor...")
    candidate_images = article_details.get("images", [])
    if image_url and image_url not in candidate_images:
        candidate_images.append(image_url)

    img_filename = f"post_{news_hash[:10]}.jpg"
    visual_path = image_generator.create_news_visual(
        candidate_urls=candidate_images,
        output_filename=img_filename,
        title=title,
        category=category
    )
    print(f"   [Görsel Hazırlandı: {visual_path} | Aday Görsel Sayısı: {len(candidate_images)}]")

    # 3. Web Sitesinde Yayınlama (Yazısız, saf ve kristal netliğinde görsel)
    print("🌐 Kendi sitemizde yayınlanıyor...")
    slug = database.save_article(
        title=article_data["title"],
        summary=article_data["summary"],
        content=article_data["content"],
        image_path=visual_path,
        source=source,
        category=category
    )
    site_article_url = f"{config.SITE_URL}/haber/{slug}"
    print(f"   [Haber Linki: {site_article_url}]")

    # 3.1. Google Indexing API - Anlık Google Bot İndeksleme Çağrısı
    try:
        import google_indexer
        google_indexer.notify_google_indexing(site_article_url)
    except Exception as e:
        print(f"⚠️ Google Indexing API atlandı: {e}")

    # 4. Telegram Bildirimi (Rakiplerin formatında: Net fotoğraf / 2'li kolaj + Maddeli özet)
    print("📲 Telegram kanalına profesyonel maddeli formatla gönderiliyor...")
    telegram_notifier.send_telegram_news(visual_path, telegram_caption, site_article_url)

    # 5. Otomatik Hikaye (Story) Kalkanı:
    # Gönderi akışını spama boğmadan, 4 saatte 1 (günde 5-6 adet) Facebook ve Instagram'a
    # BAŞLIKLI, LOGOLU VE 9:16 DİKEY FORMATTA profesyonel HİKAYE (STORY) atar!
    try:
        story_filename = f"story_{news_hash[:10]}.jpg"
        story_path = image_generator.create_story_card(
            candidate_urls=candidate_images,
            output_filename=story_filename,
            title=title,
            category=category
        )
        print(f"   [Dikey Hikaye Kartı Hazırlandı: {story_path}]")
        meta_poster.post_stories_with_cooldown(story_path)
    except Exception as e:
        print(f"⚠️ Otomatik hikaye istisnası: {e}")

    fb_id = None
    ig_id = None

    # 4. Veritabanına kaydet
    database.mark_as_posted(
        news_hash=news_hash,
        title=title,
        source=source,
        link=link,
        fb_id=fb_id,
        ig_id=ig_id
    )
    print("💾 Haber veritabanına kaydedildi (tekrar paylaşılmayacak).")
    return True

def get_minutes_since_last_article() -> float:
    """Veritabanındaki en son yayınlanan haberin üzerinden kaç dakika geçtiğini kesin olarak hesaplar."""
    try:
        articles = database.get_articles(limit=1)
        if not articles:
            return 999.0
        art = articles[0]
        val = art.get("created_at")
        if not val:
            return 999.0
        clean_str = str(val).split(".")[0].replace("T", " ")[:19]
        dt = datetime.strptime(clean_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=database.TR_TZ)
        now_tr = datetime.now(database.TR_TZ)
        diff_sec = (now_tr - dt).total_seconds()
        return max(0.0, diff_sec / 60.0)
    except Exception as e:
        print(f"Son haber zamanı kontrolü hatası: {e}")
    return 999.0

def run_bot(max_items: int = 1, force: bool = False):
    """Gündemi kontrol edip en güncel ve en yüksek puanlı taze haberleri kategori kısıtlaması olmaksızın paylaşır."""
    if not force:
        target_cooldown = max(14.0, float(config.CHECK_INTERVAL_MINUTES) - 1.0)
        minutes_passed = get_minutes_since_last_article()
        if minutes_passed < target_cooldown:
            remaining = round(target_cooldown - minutes_passed, 1)
            print(f"⏳ [Zaman Kilidi] Son haber {round(minutes_passed, 1)} dk önce paylaşıldı. Hedef: 15 dk. Yeni haber için {remaining} dk bekleniyor.")
            return 0

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Güncel haberler taranıyor...")
    news_items = news_fetcher.fetch_latest_news(limit_per_feed=12)

    if not news_items:
        print("ℹ️  Yeni paylaşılacak haber bulunamadı. Tüm haberler güncel.")
        return 0

    # Mükerrer Olmayan Yepyeni Haberleri Filtrele (Aynı veya benzer haber asla tekrar paylaşılmaz)
    fresh_news = [item for item in news_items if not database.is_already_posted(item["hash"], title=item["title"], link=item["link"])]
    if not fresh_news:
        print("ℹ️  Tüm haberler daha önce paylaşılmış. Yeni taze haber bekleniyor.")
        return 0

    print(f"📡 Paylaşılmaya hazır {len(fresh_news)} adet taze ve benzersiz haber tespit edildi.")

    # 🎯 TAM 8 KATEGORİLİ ADİL DÖNGÜ MOTORU (Sitedeki 8 Sekmenin Tamamını Sırayla Besler)
    # Gündem | Ekonomi | Eğitim | Otomobil | Teknoloji | Sağlık | Spor | Dünya (+ Son Dakika)
    OFFICIAL_CATEGORIES = [
        "Gündem", "Ekonomi", "Eğitim", "Otomobil",
        "Teknoloji", "Sağlık", "Spor", "Dünya"
    ]
    recent_arts = database.get_articles(limit=24)
    recent_cats = [a.get("category", "") for a in recent_arts if a.get("category")]
    last_cat = recent_cats[0] if recent_cats else ""

    # Her kategorinin en son kaç haber önce yayınlandığını hesapla (Hiç yoksa 999 ile en acil sıraya koy)
    cat_wait_distance = {}
    for idx_c, c in enumerate(OFFICIAL_CATEGORIES):
        if c in recent_cats:
            cat_wait_distance[c] = recent_cats.index(c)
        else:
            cat_wait_distance[c] = 999 - idx_c

    # En uzun süredir haber girilmeyen kategoriden en yeniye doğru sırala
    priority_categories = sorted(
        OFFICIAL_CATEGORIES,
        key=lambda c: cat_wait_distance[c],
        reverse=True
    )
    print(f"📋 Son Yayınlanan: [{last_cat or 'Yok'}] | Sıradaki Kategori Önceliği: {priority_categories}")

    # Sırası gelen en acil kategorinin en yüksek puanlı haberini en başa koy
    selected_pool = []
    for target_cat in priority_categories:
        cat_items = [item for item in fresh_news if item.get("category") == target_cat]
        cat_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        selected_pool.extend(cat_items)

    # Eğer herhangi bir nedenle liste dışı kategori varsa en sona ekle
    remaining_items = [item for item in fresh_news if item not in selected_pool]
    selected_pool.extend(remaining_items)

    processed_count = 0
    for item in selected_pool:
        if processed_count >= max_items:
            break
        title_snippet = item.get('title', '')[:45]
        cat = item.get('category', 'Gündem')
        score = item.get('score', 0)
        print(f"🎯 [Otonom Bot] Sıradaki Kategoriden Seçilen Haber: [{cat}] {title_snippet}... (Puan: {score})")
        try:
            success = process_single_news(item)
            if success:
                processed_count += 1
                database.set_setting("last_bot_category", cat)
                time.sleep(2)
                break
            else:
                print(f"⚠️ Haber atlandı ({title_snippet}...), sıradaki deneniyor...")
        except Exception as e:
            print(f"❌ Haber ({title_snippet}...) işlenirken hata oluştu: {e}, sıradaki taze haber deneniyor...")
            continue

    return processed_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gündem Analizi Otonom Haber Botu")
    parser.add_argument("--max-items", type=int, default=1, help="Paylaşılacak maksimum haber sayısı")
    args = parser.parse_args()
    count = run_bot(max_items=args.max_items)
    print(f"🏁 Bot çalışması tamamlandı. İşlenen haber: {count}")
