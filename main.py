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

    print("\n" + "="*60)
    print(f"🔥 İşlenen Haber: {title}")
    print(f"📌 Kaynak: {source}")
    print("="*60)

    # 1. Metin ve Makale Üretimi
    print("✍️  Sosyal medya metni ve web makalesi hazırlanıyor...")
    raw_summary = item.get("summary", "")
    # Eğer özet çok kısaysa veya 'işte detaylar' gibi yarım kalmışsa, orijinal linkten gerçek paragrafları çek
    summary = raw_summary
    if len(raw_summary) < 220 or any(k in raw_summary.lower() for k in ["işte", "ayrıntı", "belli oldu", "..."]):
        scraped_body = news_fetcher.fetch_article_body(link)
        if scraped_body and len(scraped_body) > len(raw_summary):
            summary = scraped_body

    ai_result = ai_writer.generate_social_caption(title, summary, source)
    caption = ai_result["caption"]
    article_data = ai_writer.generate_full_article(title, summary, source)
    print(f"   [Kullanılan Yöntem: {ai_result['source_used']}]")

    # 2. Görsel Üretimi
    print("🎨 Haber kartı görseli tasarlanıyor...")
    category = article_data.get("category", "Gündem")
    tag_map = {
        "Ekonomi": "EKONOMİ & PİYASA",
        "Teknoloji": "TEKNOLOJİ & DİJİTAL",
        "Yaşam": "YAŞAM & TÜKETİCİ",
        "Spor": "SPOR GÜNDEMİ",
        "Dünya": "DÜNYA GÜNDEMİ",
        "Gündem": "TÜRKİYE GÜNDEMİ"
    }
    card_tag = tag_map.get(category, "TÜRKİYE GÜNDEMİ")

    img_filename = f"post_{news_hash[:10]}.jpg"
    card_path = image_generator.generate_news_card(
        title=title,
        source=source,
        image_url=image_url,
        tag=card_tag,
        output_filename=img_filename
    )
    print(f"   [Görsel Kaydedildi: {card_path} | Kategori: {card_tag}]")

    # 3. Web Sitesinde Yayınlama
    print("🌐 Kendi sitemizde yayınlanıyor...")
    slug = database.save_article(
        title=article_data["title"],
        summary=article_data["summary"],
        content=article_data["content"],
        image_path=card_path,
        source=source,
        category=article_data.get("category", "Gündem")
    )
    site_article_url = f"{config.SITE_URL}/haber/{slug}"
    print(f"   [Haber Linki: {site_article_url}]")

    # 4. Telegram Bildirimi (Kendi sitemizin linkiyle gönderim)
    print("📲 Telegram kanalına sitemizin linkiyle gönderiliyor...")
    telegram_notifier.send_telegram_news(card_path, caption, site_article_url)

    # 5. Otomatik Hikaye (Story) Kalkanı:
    # Gönderi akışını spama boğmadan, 4 saatte 1 (günde 5-6 adet) Facebook ve Instagram'a doğrudan HİKAYE (STORY) atar!
    try:
        meta_poster.post_stories_with_cooldown(card_path)
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

def run_bot(max_items: int = 1):
    """Gündemi kontrol edip en güncel haberleri paylaşır."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Güncel haberler taranıyor...")
    news_items = news_fetcher.fetch_latest_news(limit_per_feed=3)

    if not news_items:
        print("ℹ️  Yeni paylaşılacak haber bulunamadı. Tüm haberler güncel.")
        return 0

    print(f"🎯 Paylaşılmaya hazır {len(news_items)} yeni haber tespit edildi.")
    processed_count = 0

    for item in news_items[:max_items]:
        try:
            success = process_single_news(item)
            if success:
                processed_count += 1
                time.sleep(2)
        except Exception as e:
            print(f"❌ Haber işlenirken hata oluştu: {e}")

    return processed_count

def main():
    parser = argparse.ArgumentParser(description="Otonom Sosyal Medya Haber Botu (Facebook & Instagram)")
    parser.add_argument("--loop", action="store_true", help="Sürekli arka planda döngü olarak çalıştır")
    parser.add_argument("--count", type=int, default=1, help="Tek seferde paylaşılacak maksimum haber sayısı (Varsayılan: 1)")
    args = parser.parse_args()

    database.init_db()

    print("\n" + "#"*60)
    print("🤖 Otonom Sosyal Medya Haber Botu Başlatıldı")
    print(f"⚙️  Dry Run Modu: {'AÇIK (Test Modu - Gerçek Paylaşım Yapılmaz)' if config.DRY_RUN else 'KAPALI (CANLI PAYLAŞIM MODU)'}")
    print("#"*60)

    if args.loop:
        print(f"⏱️  Döngü Modu Aktif: Her {config.CHECK_INTERVAL_MINUTES} dakikada bir kontrol edilecek.\n")
        while True:
            try:
                run_bot(max_items=args.count)
            except Exception as e:
                print(f"⚠️  Döngü sırasında beklenmeyen bir hata oluştu: {e}")
            print(f"\n💤 {config.CHECK_INTERVAL_MINUTES} dakika bekleniyor... (Durdurmak için Ctrl+C)")
            time.sleep(config.CHECK_INTERVAL_MINUTES * 60)
    else:
        run_bot(max_items=args.count)
        print("\n✨ Görev tamamlandı.")

if __name__ == "__main__":
    main()
