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
import threading

_BOT_PROCESS_LOCK = threading.Lock()

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

    # 🛡️ ÇELİK MÜKERRER KALKANI: Haberi atomik olarak anında rezerve et (Pre-claim Lock)
    # (Başka bir thread veya yeni deploy konteyneri 13.5 dk bekleme süresince ASLA aynı haberi alamaz!)
    if not database.claim_news_for_processing(news_hash, title=title, source=source, link=link):
        print(f"⚠️ [Mükerrer Paylaşım Engellendi] '{title[:50]}' daha önce yayınlanmış veya başka bir işlem tarafından rezerve edilmiş. Atlanıyor.")
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

    # Web Makalesi ve Özgün Başlık Üretimi
    item_category = item.get("category")
    article_data = ai_writer.generate_full_article(title, summary, source, force_category=item_category)
    if not article_data:
        # AdSense kalite kuralı: yapay zeka özgün metin üretemediyse kopya/şablon haber yayınlanmaz
        print(f"⏩ [Kalite Kalkanı] '{title[:50]}' için özgün metin üretilemedi; yayınlanmadı.")
        return False
    final_title = article_data.get("title") or title
    category = article_data.get("category", "Gündem")
    telegram_caption = ai_writer.generate_telegram_post(final_title, summary, source)
    print(f"   [Kategori: {category} | Özgün Başlık & Telegram Metni Hazır]")

    # 2. Kristal Netliğinde Görsel Üretimi
    print("🎨 Yüksek çözünürlüklü haber görseli hazırlanıyor...")
    candidate_images = article_details.get("images", [])
    if image_url and image_url not in candidate_images:
        candidate_images.append(image_url)

    img_filename = f"post_{news_hash[:10]}.jpg"
    visual_path = image_generator.create_news_visual(
        candidate_urls=candidate_images,
        output_filename=img_filename,
        title=final_title,
        category=category
    )
    if not visual_path or not os.path.exists(visual_path) or image_generator.is_synthetic_card_image(visual_path):
        print(f"⏩ [Görsel Kalite Kalkanı] '{final_title[:50]}' için gerçek haber fotoğrafı bulunamadı; yapay görselli haber yayınlanmadı.")
        return False
    print(f"   [Görsel Hazırlandı: {visual_path} | Aday Görsel Sayısı: {len(candidate_images)}]")

    # 2.5. HASSAS 13.5 DAKİKA NİŞANGAHI (En Fazla 15 Dk Garantisi):
    # Haber 10. dakikada önceden hazırlanır; 13.5. dakikada yayına basılır, en geç 14. dakikada kanallara düşer!
    TARGET_MINUTES = 28.5
    while True:
        mins_now = get_minutes_since_last_article()
        if mins_now >= TARGET_MINUTES:
            break
        wait_sec = min(10.0, max(1.0, (TARGET_MINUTES - mins_now) * 60.0))
        print(f"⏱️ [30 Dk Kuralı] Haber hazır! 28.5. dk hedefi için {round(wait_sec, 1)} sn bekleniyor (Geçen: {round(mins_now, 1)} dk)...")
        time.sleep(wait_sec)

    # 3. Web Sitesinde Yayınlama (Yazısız, saf ve kristal netliğinde görsel)
    print("🌐 Kendi sitemizde yayınlanıyor...")
    slug, is_created = database.save_article(
        title=article_data["title"],
        summary=article_data["summary"],
        content=article_data["content"],
        image_path=visual_path,
        source=source,
        category=category,
        return_status=True
    )
    if not is_created:
        print(f"⚠️ [Mükerrer Haber Engellendi] '{title[:50]}' sitemizde zaten mevcut ({slug}). İkinci kez eklenmedi ve Telegram'a bildirim GÖNDERİLMEDİ.")
        return False

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
    # Kullanıcı talebi gereğince Facebook & Instagram sayfalarını spamdan korumak için devre dışı bırakıldı.
    pass

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

_COMMODITY_PATTERNS = [
    # Şans oyunu sonuçları
    r"say[ıi]sal loto", r"s[üu]per loto", r"[şs]ans topu", r"on numara.*(sonu[çc]|[çc]ekili[şs])", r"milli piyango.*(sonu[çc]|[çc]ekili[şs])",
    r"loto.*sonu[çc]", r"[çc]ekili[şs] sonu[çc]lar[ıi]",
    # Yayın / izleme rehberleri
    r"hangi kanalda", r"saat ka[çc]ta.*(ma[çc]|kanal)", r"(ma[çc]|kanal).*saat ka[çc]ta", r"canl[ıi] izle", r"[şs]ifresiz",
    r"nereden izlenir", r"yay[ıi]n ak[ıi][şs][ıi]",
    # Burç / fal
    r"bur[çc] yorum", r"g[üu]nl[üu]k bur[çc]", r"haftal[ıi]k bur[çc]",
    # Rutin vakit ve fiyat listeleri (sitede kendi canlı sayfalarımız var)
    r"namaz vakit", r"imsakiye", r"iftar saati", r"sahur saati",
    r"alt[ıi]n fiyatlar[ıi].*(bug[üu]n|g[üu]ncel|canl[ıi])", r"(gram|[çc]eyrek) alt[ıi]n ka[çc] (tl|lira)",
    r"(dolar|euro) ka[çc] (tl|lira)", r"d[öo]viz kurlar[ıi] bug[üu]n",
    r"n[öo]bet[çc]i eczane", r"son depremler listesi", r"deprem mi oldu",
]
_COMMODITY_RE = __import__("re").compile("|".join(_COMMODITY_PATTERNS), __import__("re").I)

def is_commodity_news(title: str) -> bool:
    """Loto sonucu, maç yayın saati, burç, günlük altın listesi gibi her sitede aynı olan haberleri tespit eder."""
    t = (title or "").replace("İ", "i").replace("I", "ı").lower()
    # Hava durumu: rutin tahminler atlanır, resmi uyarılar (turuncu/kırmızı kod, fırtına, sel) haberdir
    if "hava durumu" in t and not __import__("re").search(r"uyar|turuncu|k[ıi]rm[ıi]z[ıi]|f[ıi]rt[ıi]na|sel|kar ya[ğg][ıi][şs][ıi]|[çc]ığ", t):
        return True
    return bool(_COMMODITY_RE.search(t))

def get_minutes_since_last_article() -> float:
    """
    Veritabanındaki en son yayınlanan OTONOM BOT haberinin üzerinden kaç dakika geçtiğini hesaplar.
    (Panelden manuel yüklenen videolar veya son dakika girişleri otonom 15 dk sayacını sıfırlamaz!)
    """
    try:
        articles = database.get_articles(limit=6)
        if not articles:
            return 999.0
        target_art = None
        for a in articles:
            src = (a.get("source") or "").strip().lower()
            img_p = (a.get("image_path") or "").strip().lower()
            # Panelden yüklenen videoların kapak resmi viral_ ile başlar veya kaynağı Gündem Analizi'dir
            if "viral_" in img_p or src in ("gündem analizi", "özel", "sosyal medya"):
                continue
            target_art = a
            break
        if not target_art:
            target_art = articles[0]
        val = target_art.get("created_at")
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
    """
    11.5. dakikada uyanıp haberi önceden hazırlar ve tam 15:00. dakikada sıfır gecikmeyle yayınlar.
    Sabit Kategori Sırası: Gündem -> Ekonomi -> Dünya -> Spor -> Teknoloji -> Otomobil -> Sağlık -> Eğitim
    """
    global _BOT_PROCESS_LOCK
    if not _BOT_PROCESS_LOCK.acquire(blocking=False):
        print("⏳ [Bot Kilitli] Başka bir haber işleme süreci şu an aktif. Çakışmayı önlemek için bu çağrı atlandı.")
        return 0
    try:
        return _run_bot_internal(max_items=max_items, force=force)
    finally:
        _BOT_PROCESS_LOCK.release()

def _run_bot_internal(max_items: int = 1, force: bool = False):
    if not force:
        # En fazla 15 dk kuralı: Hazırlığa 10.0. dakikada başlar, 13.5. dakikada yayına basar!
        prep_start_minute = 25.0
        minutes_passed = get_minutes_since_last_article()
        if minutes_passed < prep_start_minute:
            remaining = round(prep_start_minute - minutes_passed, 1)
            print(f"⏳ [Zaman Kilidi] Son haber {round(minutes_passed, 1)} dk önce paylaşıldı. Hazırlık başlangıcı için {remaining} dk bekleniyor.")
            return 0

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Güncel haberler önceden hazırlanmak üzere taranıyor...")
    news_items = news_fetcher.fetch_latest_news(limit_per_feed=10)

    if not news_items:
        print("ℹ️  Yeni paylaşılacak haber bulunamadı. Tüm haberler güncel.")
        return 0

    fresh_news = [item for item in news_items if not database.is_already_posted(item["hash"], title=item["title"], link=item["link"])]

    # Her sitede birebir aynı olan, özgün değer katılamayan "sıradan" haberleri atla
    # (yayın aralığı değişmez: bot sıradaki gerçek habere geçer)
    _before = len(fresh_news)
    fresh_news = [item for item in fresh_news if not is_commodity_news(item.get("title", ""))]
    if _before != len(fresh_news):
        print(f"🧹 [İçerik Filtresi] {_before - len(fresh_news)} sıradan haber (loto sonucu, maç yayın saati, burç vb.) atlandı.")
    if not fresh_news:
        print("ℹ️  Tüm haberler daha önce paylaşılmış. Yeni taze haber bekleniyor.")
        return 0

    print(f"📡 Paylaşılmaya hazır {len(fresh_news)} adet taze ve benzersiz haber tespit edildi.")

    # 🎯 8 KATEGORİ TAM EŞİTLİK VE ADİL ROTASYON (Otomobil, Sağlık, Eğitim Asla Atlanamaz!)
    ALL_CATEGORIES = [
        "Gündem", "Ekonomi", "Dünya", "Spor",
        "Teknoloji", "Otomobil", "Sağlık", "Eğitim"
    ]
    recent_arts = database.get_articles(limit=24)
    recent_cats = [a.get("category", "") for a in recent_arts if a.get("category")]
    last_cat = recent_cats[0] if recent_cats else ""

    # En uzun süredir haber paylaşılmamış kategoriyi EN BAŞA koy:
    # Eğer bir kategori son 24 haberde hiç yoksa (Örn: Otomobil, Sağlık, Eğitim) puanı 9999 olur ve İLK SIRADA paylaşılır!
    def get_cat_starvation_score(cat):
        if cat not in recent_cats:
            return 9999
        return recent_cats.index(cat)

    priority_categories = sorted(ALL_CATEGORIES, key=get_cat_starvation_score, reverse=True)
    print(f"📋 Son Yayınlanan: [{last_cat or 'Yok'}] | Kesin Adil Sıra: {priority_categories}")

    selected_pool = []
    for target_cat in priority_categories:
        cat_items = [item for item in fresh_news if item.get("category") == target_cat]
        cat_items.sort(key=lambda x: x.get("score", 0), reverse=True)
        selected_pool.extend(cat_items)

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
                time.sleep(1)
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
