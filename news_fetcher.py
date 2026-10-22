import feedparser
import hashlib
import re
import html
import requests
from typing import List, Dict, Optional
import config
import database

def get_news_hash(title: str, link: str) -> str:
    """Haber için benzersiz bir MD5 özeti üretir."""
    normalized = f"{title.strip().lower()}_{link.strip()}"
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()

def extract_image_url(entry) -> Optional[str]:
    """RSS girdisinden haber görseli URL'sini çıkarmaya çalışır."""
    # 1. media_content kontrolü
    if "media_content" in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get("url")

    # 2. enclosures kontrolü
    if "enclosures" in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/"):
                return enc.get("href")

    # 3. description veya summary içindeki <img> etiketini arama
    content = entry.get("summary", "") or entry.get("description", "")
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)

    return None

def clean_html(text: str) -> str:
    """HTML etiketlerini temizler."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return clean.strip()

def fetch_article_details(link: str, max_paragraphs: int = 5) -> dict:
    """
    Haberin orijinal web sayfasına gidip:
    1. Yüksek çözünürlüklü og:image, twitter:image ve içerik içi görselleri ayıklar.
    2. Gerçek makale paragraflarını (tıklama tuzakları yerine sayılar, oranlar ve kararları) çeker.
    """
    if not link or not link.startswith("http"):
        return {"body": "", "images": []}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        resp = requests.get(link, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {"body": "", "images": []}

        raw_text = resp.text

        # 1. Görselleri topla (OG Image, Twitter Image, ve Gövde İçi Haber Fotoğrafları)
        candidate_images = []

        # OG Image (Genelde 1200x630 veya 1920x1080 orijinal editoryal fotoğraftır)
        og_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', raw_text, re.I)
        if not og_match:
            og_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', raw_text, re.I)
        if og_match:
            og_url = html.unescape(og_match.group(1).strip())
            if og_url.startswith("//"):
                og_url = "https:" + og_url
            if og_url.startswith("http"):
                candidate_images.append(og_url)

        # Twitter Image
        tw_match = re.search(r'<meta[^>]*name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)["\']', raw_text, re.I)
        if tw_match:
            tw_url = html.unescape(tw_match.group(1).strip())
            if tw_url.startswith("//"):
                tw_url = "https:" + tw_url
            if tw_url.startswith("http") and tw_url not in candidate_images:
                candidate_images.append(tw_url)

        # Gövde İçi Fotoğraflar
        raw_imgs = re.findall(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)["\']', raw_text, re.I)
        bad_words = [
            'logo', 'icon', 'avatar', 'pixel', 'advert', 'banner', 'blank', 'gif',
            'svg', 'share', 'button', 'badge', 'spinner', 'tracker', 'stats',
            'footer', 'header', 'gravatar', 'kurdele', 'placeholder', 'transparent', 'emoji'
        ]
        for raw_src in raw_imgs:
            clean_src = html.unescape(raw_src.strip())
            if clean_src.startswith("//"):
                clean_src = "https:" + clean_src
            if not clean_src.startswith("http"):
                continue
            if any(b in clean_src.lower() for b in bad_words):
                continue
            if any(ext in clean_src.lower() for ext in ['.jpg', '.jpeg', '.webp', '.png', '/resim', '/image', '/img']):
                if clean_src not in candidate_images:
                    candidate_images.append(clean_src)

        # 2. Makale Metnini Ayıkla (Script ve stilleri temizle)
        clean_html_text = re.sub(r'<script[^>]*>.*?</script>', '', raw_text, flags=re.DOTALL | re.IGNORECASE)
        clean_html_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_html_text, flags=re.DOTALL | re.IGNORECASE)

        p_matches = re.findall(r'<p[^>]*>(.*?)</p>', clean_html_text, re.DOTALL | re.IGNORECASE)
        clean_paras = []
        bad_body_phrases = [
            "çerez", "cookie", "telif", "copyright", "kullanım koşulları",
            "gizlilik", "künye", "reklam", "abone", "yayın grubu",
            "tıklayın", "tıklayınız", "indir", "fotoğraf:", "menüyü aç", "tüm hakları saklıdır"
        ]
        for p in p_matches:
            c = clean_html(p)
            if len(c) > 55 and not any(b in c.lower() for b in bad_body_phrases):
                clean_paras.append(c)
                if len(clean_paras) >= max_paragraphs:
                    break

        return {
            "body": "\n\n".join(clean_paras),
            "images": candidate_images
        }
    except Exception as e:
        print(f"fetch_article_details hatası: {e}")
        return {"body": "", "images": []}

def fetch_article_body(link: str, max_paragraphs: int = 4) -> str:
    """Haberin orijinal web sayfasından zengin makale metnini çeker."""
    details = fetch_article_details(link, max_paragraphs)
    return details.get("body", "")

def calculate_virality_score(title: str, summary: str, source: str) -> int:
    """
    Haberin halkın ilgisini, cüzdanını ve günlük yaşamını ne kadar etkilediğini puanlar.
    Yüksek puan = Viral, tıklanma garantili, halkın cebine ve hayatına dokunan haber.
    Düşük puan = Kuru resmi protokol, bürokratik sıkıcı haberler.
    """
    text = f"{title} {summary}".lower()
    score = 50  # Taban puan

    # 1. HALKIN CÜZDANI, ALIŞVERİŞ, TAKSİT & PARA (+35 - +60 Puan)
    cuzdan_keywords = [
        "taksit", "kredi kartı", "kredi", "bddk", "alışveriş", "zam", "indirim",
        "asgari ücret", "emekli", "maaş", "ikramiye", "promosyon", "altın", "dolar",
        "euro", "faiz", "mevduat", "akaryakıt", "benzin", "motorin", "lpg",
        "vergi", "ceza", "yapılandırma", "fatura", "elektrik", "doğalgaz",
        "kira", "ev sahibi", "kiracı", "konut kredisi", "toki", "borsa", "hisse",
        "para", "fiyat", "enflasyon", "market", "kdv", "ötv", "kota", "limit"
    ]
    for kw in cuzdan_keywords:
        if kw in text:
            score += 35
            break

    # Ekstra yüksek tetikleyiciler (taksit, kota, zam, emekli, asgari ücret, altın)
    super_triggers = ["taksit", "kota", "limit", "asgari ücret", "emekli maaşı", "akaryakıt", "altın", "faiz kararı"]
    for st in super_triggers:
        if st in text:
            score += 25
            break

    # 2. GÜNLÜK YAŞAM, TÜKETİCİ & RESMİ HAKLAR (+25 Puan)
    yasam_keywords = [
        "ehliyet", "pasaport", "kimlik", "bayram", "tatil", "okul", "milli eğitim",
        "üniversite", "sınav", "ösym", "yks", "kpss", "e-devlet", "sgk",
        "sağlık", "hastane", "randevu", "mhrs", "ulaşım", "metro", "marmaray"
    ]
    for kw in yasam_keywords:
        if kw in text:
            score += 25
            break

    # 3. DİJİTAL & TEKNOLOJİ TÜKETİCİSİ (+20 Puan)
    tekno_keywords = [
        "whatsapp", "instagram", "apple", "iphone", "android", "telefon",
        "dolandırıcılık", "oltalama", "yapay zeka", "tiktok", "sosyal medya"
    ]
    for kw in tekno_keywords:
        if kw in text:
            score += 20
            break

    # 4. BÜYÜK AFETLER & HAVA DURUMU (+30 Puan)
    afet_keywords = ["deprem", "kandilli", "afad", "fırtına", "meteoroloji", "sarı kod", "turuncu kod"]
    for kw in afet_keywords:
        if kw in text:
            score += 30
            break

    # 5. PROTOKOL & KURU BÜROKRATİK SİYASET CEZASI (-45 Puan)
    # Halkı ilgilendirmeyen protokol temasları ve kuru demeçleri geri plana at
    protokol_keywords = [
        "kabul etti", "ziyaret etti", "bir araya geldi", "görüştü",
        "tebrik etti", "basın toplantısı düzenledi", "heyetini ağırladı",
        "açıklamalarda bulundu", "tbmm komisyon", "toplantısı sona erdi",
        "protokol imzalandı", "büyükelçisi", "diplomatik temas"
    ]
    for pk in protokol_keywords:
        if pk in text:
            score -= 45
            break

    return score

def fetch_latest_news(limit_per_feed: int = 4) -> List[Dict]:
    """
    Tanımlı seçkin RSS kaynaklarını tarar ve 'Halkın İlgisi ve Cüzdan Puanı'na göre
    en yüksekten en düşüğe sıralanmış paylaşılmaya hazır haberleri döner.
    """
    database.init_db()
    unposted_news = []

    for feed_info in config.RSS_FEEDS:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]

        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit_per_feed]:
                title = clean_html(entry.get("title", ""))
                link = entry.get("link", "")
                summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
                image_url = extract_image_url(entry)
                published = entry.get("published", "")

                if not title or not link:
                    continue

                news_hash = get_news_hash(title, link)

                # Daha önce paylaşılmış mı kontrol et
                if not database.is_already_posted(news_hash):
                    # Haberin viral/tüketici/cüzdan ilgi puanını hesapla
                    score = calculate_virality_score(title, summary, feed_name)
                    # Görseli olan haberlere +10 avantaj puanı
                    if image_url:
                        score += 10

                    unposted_news.append({
                        "hash": news_hash,
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "image_url": image_url,
                        "source": feed_name,
                        "published": published,
                        "score": score
                    })
        except Exception as e:
            print(f"[{feed_name}] RSS okunurken hata oluştu: {e}")

    # En yüksek puanlı (en çok merak edilen, halkın cebine dokunan) haberi en başa al
    unposted_news.sort(key=lambda x: x.get("score", 0), reverse=True)
    return unposted_news

if __name__ == "__main__":
    news = fetch_latest_news(limit_per_feed=2)
    print(f"Bulunan yeni haber sayısı: {len(news)}")
    for n in news[:3]:
        print(f"- [{n['source']}] {n['title']} (Görsel: {n['image_url']})")
