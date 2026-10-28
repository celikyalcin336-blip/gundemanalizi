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

    # 4.1. X (Twitter) Akıllı ve Seçici Paylaşım Kalkanı (@gndmanalizi)
    # Çöp ve magazin haberleri eler; sadece yüksek değerli flaş haberleri 45 dk aralıkla fotoğraflı tweet atar
    try:
        import x_poster
        x_res = x_poster.post_article_to_x(
            title=title,
            summary=summary,
            site_url=site_article_url,
            image_path=visual_path,
            category=category
        )
        if x_res.get("status") == "success":
            print(f"   [X/Twitter Paylaşıldı: {x_res.get('url')}]")
        elif x_res.get("status") == "skipped":
            print(f"   [X/Twitter Pas Geçildi: {x_res.get('reason')}]")
    except Exception as e:
        print(f"⚠️ X/Twitter paylaşımı atlandı: {e}")

    # 4.2. VIP WhatsApp Kanalı Paylaşım Asistanı (Yalçın Bey Özel Bildirim)
    # Her kaliteli haber yayınlandığında Yalçın Bey'in telefonuna tek tıkla "WhatsApp Kanalında Paylaş" butonu atar
    try:
        telegram_notifier.send_admin_whatsapp_prompt(
            image_path=visual_path,
            title=title,
            summary=summary,
            site_url=site_article_url,
            category=category
        )
    except Exception as e:
        print(f"⚠️ VIP WhatsApp bildirimi atlandı: {e}")

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

def get_seconds_since_last_article() -> float:
    """Botun en son yayınladığı haberin üzerinden kaç saniye geçtiğini kesin olarak hesaplar (Manuel videolar botu durdurmaz)."""
    try:
        # 1. Önce botun kendi paylaştığı son habere bak (Yalçın Bey'in panele attığı manuel videolar botun saatini bozmaz!)
        last_time_str = database.get_last_bot_posted_time()
        if not last_time_str:
            articles = database.get_articles(limit=1)
            if not articles:
                return 999999.0
            last_time_str = str(articles[0].get("created_at") or "")

        if not last_time_str:
            return 999999.0

        clean_val = str(last_time_str).split(".")[0].replace("T", " ")[:19]
        dt = datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S").replace(tzinfo=database.TR_TZ)
        now_tr = datetime.now(database.TR_TZ)
        diff_sec = (now_tr - dt).total_seconds()
        if diff_sec < -60:
            return 999999.0
        return max(0.0, diff_sec)
    except Exception as e:
        print(f"Son haber zamanı kontrolü hatası: {e}")
    return 999999.0

def get_minutes_since_last_article() -> float:
    return get_seconds_since_last_article() / 60.0

def run_bot(max_items: int = 1, force: bool = False):
    """Gündemi kontrol edip en güncel ve en yüksek gelirli haberleri döngüsel paylaşır."""
    if not force:
        # Tam 15.0 dakika (900 saniye) kuralı:
        # 30 saniye erken uyanış (hazırlık payı) ile 870. saniyede (14.5 dk) başlar
        # ve tam 900. saniyede (15.0 dk) site ve Telegram'da yayına girer!
        target_cooldown_sec = 870.0
        sec_passed = get_seconds_since_last_article()
        if sec_passed < target_cooldown_sec:
            return 0
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Güncel haberler taranıyor...")
    news_items = news_fetcher.fetch_latest_news(limit_per_feed=25)

    if not news_items:
        print("ℹ️  Yeni paylaşılacak haber bulunamadı. Tüm haberler güncel.")
        return 0

    # Mükerrer Olmayan Yepyeni Haberleri Filtrele (Aynı haber asla tekrar paylaşılmaz)
    fresh_news = [item for item in news_items if not database.is_already_posted(item["hash"], title=item["title"], link=item["link"])]
    if not fresh_news:
        # Eğer katı filtreden geçmediyse, link ve hash bazlı taze olanları al (Bot asla 15 dakikayı kaçırmaz)
        fresh_news = [item for item in news_items if not database.is_already_posted(item["hash"])]
        if not fresh_news:
            print("ℹ️  Tüm haberler daha önce paylaşılmış. Yeni taze haber bekleniyor.")
            return 0

    print(f"📡 Paylaşılmaya hazır {len(fresh_news)} adet taze ve benzersiz haber tespit edildi.")

    # ⏰ SAATLİK AKILLI KATEGORİ MOTORU (TÜRKİYE ALIŞKANLIKLARI & 3 KADEMELİ ÇELİK KALKAN)
    now_tr = datetime.now(database.TR_TZ)
    h = now_tr.hour + (now_tr.minute / 60.0)

    if 7.0 <= h < 10.5:
        slot_name = "🌅 Sabah Kuşağı"
        preferred_cats = ["Ekonomi", "Gündem", "Otomobil"]
    elif 10.5 <= h < 16.5:
        slot_name = "☀️ Gün Ortası Kuşağı"
        preferred_cats = ["Teknoloji", "Otomobil", "Gündem", "Sağlık", "Eğitim"]
    elif 16.5 <= h < 23.0:
        slot_name = "🌆 Akşam Prime Time"
        preferred_cats = ["Spor", "Gündem", "Ekonomi"]
    else:
        slot_name = "🌙 Gece Kuşağı"
        preferred_cats = ["Dünya", "Teknoloji", "Otomobil", "Gündem"]

    last_cat = database.get_setting("last_bot_category", "")
    try:
        if last_cat in preferred_cats:
            next_idx = (preferred_cats.index(last_cat) + 1) % len(preferred_cats)
            target_cat = preferred_cats[next_idx]
        else:
            target_cat = preferred_cats[0]
    except Exception:
        target_cat = preferred_cats[0]

    print(f"🎯 [{slot_name}] Hedef Kategori: [{target_cat}] (Önceki: {last_cat or 'Yok'})")

    # 🛡️ ÇELİK KALKAN 1: Kuşağın öncelikli hedef kategorisindeki taze haberi ara
    selected_pool = [item for item in fresh_news if item.get("category") == target_cat]

    # 🛡️ ÇELİK KALKAN 2: Eğer o kategoride taze haber yoksa, aynı kuşağın diğer kategorilerine bak
    if not selected_pool:
        for alt_cat in preferred_cats:
            if alt_cat != target_cat:
                alt_items = [item for item in fresh_news if item.get("category") == alt_cat]
                if alt_items:
                    selected_pool = alt_items
                    print(f"ℹ️ [{target_cat}] kategorisinde bekleyen yayınlanmamış haber kalmadı; kuşağın [{alt_cat}] kategorisine geçildi.")
                    target_cat = alt_cat
                    break

    # 🛡️ ÇELİK KALKAN 3: Kuşaktaki hiçbir kategoride taze haber yoksa, havuzdaki herhangi bir taze haberi seç
    if not selected_pool:
        selected_pool = fresh_news
        print("⚠️ Kuşaktaki kategorilerde taze haber kalmadı, genel taze haber havuzundan seçiliyor (Bot asla durmaz).")

    processed_count = 0
    # 1. Aşama: Seçilen havuzdaki haberleri dene
    for item in selected_pool:
        if processed_count >= max_items:
            break
        try:
            success = process_single_news(item)
            if success:
                processed_count += 1
                cat_saved = item.get("category") or target_cat
                database.set_setting("last_bot_category", cat_saved)
                break
        except Exception as e:
            print(f"❌ Haber ({item.get('title', '')[:30]}...) işlenirken hata oluştu: {e}, sıradaki deneniyor...")
            continue

    # 2. Aşama: Eğer seçilen havuzdaki haberler mükerrer veya hatalı çıktıysa,
    # BOT ASLA BOŞ DÖNMEZ! 15 Dakika (900 sn) kuralı şaşmasın diye havuzdaki diğer taze haberleri hemen dene!
    if processed_count < max_items:
        fallback_pool = [item for item in fresh_news if item not in selected_pool]
        for item in fallback_pool:
            if processed_count >= max_items:
                break
            try:
                success = process_single_news(item)
                if success:
                    processed_count += 1
                    cat_saved = item.get("category") or "Gündem"
                    database.set_setting("last_bot_category", cat_saved)
                    print(f"✅ [15 Dakika Garantisi] Alternatif taze haber ({cat_saved}) başarıyla yayınlandı!")
                    break
            except Exception as e:
                print(f"❌ Alternatif haber hatası: {e}")
                continue

    return processed_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gündem Analizi Otonom Haber Botu")
    parser.add_argument("--max-items", type=int, default=1, help="Paylaşılacak maksimum haber sayısı")
    args = parser.parse_args()
    count = run_bot(max_items=args.max_items)
    print(f"🏁 Bot çalışması tamamlandı. İşlenen haber: {count}")
