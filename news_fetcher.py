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
    """RSS girdisinden haber görseli URL'sini çıkarmaya çalışır (Enclosures, Links, MediaContent, Og:Image)."""
    # 1. media_content kontrolü
    if "media_content" in entry and len(entry.media_content) > 0:
        url = entry.media_content[0].get("url")
        if url:
            return url

    # 2. enclosures kontrolü
    if "enclosures" in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image/") or any(ext in enc.get("href", "").lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return enc.get("href")

    # 3. links kontrolü (Fotomaç, A Spor, Sabah, Milliyet)
    if "links" in entry and len(entry.links) > 0:
        for l in entry.links:
            href = l.get("href", "")
            ltype = l.get("type", "")
            if ltype.startswith("image/") or any(ext in href.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return href

    # 4. media_thumbnail
    if "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
        url = entry.media_thumbnail[0].get("url")
        if url:
            return url

    # 5. description veya summary içindeki <img> etiketini arama
    content = entry.get("summary", "") or entry.get("description", "")
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        return img_match.group(1)

    # Harici site kazıma kaldırıldı (Performans koruması)
    pass

    return None


def clean_html(text: str) -> str:
    """
    HTML etiketlerini temizler ve HTML entity kodlarını (&#350;, &uuml;, &ccedil;, &amp; vb.)
    gerçek Türkçe harflere dönüştürür.
    """
    if not text:
        return ""
    # 1. HTML etiketlerini kaldır (kelimelerin birbirine yapışmaması için boşluk bırak)
    clean = re.sub(r'<[^>]+>', ' ', text)
    # 2. HTML karakter kodlarını çöz (bazı siteler çift encode ettiği için iki kez uygulanır)
    clean = html.unescape(clean)
    clean = html.unescape(clean)
    # 3. Google News ve benzeri RSS'lerin sonuna eklediği diğer kaynak zincirlerini temizle
    clean = re.sub(r'\s+(?:Hürriyet|Milliyet|NTV Haber|Haberler|Sözcü|Sabah|Habertürk|Ensonhaber|Mynet)[A-ZÇĞİÖŞÜ].*$', '', clean)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()

def sanitize_news_text(text: str) -> str:
    """
    Haber metnindeki ajans/site butonlarını, paylaşım çöplerini, borsa bantlarını,
    editör imzalarını, telif uyarılarını ve arama motoru tuzaklarını temizler.
    """
    if not text:
        return ""
    t = text
    # 0. Finans / Borsa canlı ticker yüzdeleri ve kategori kırıntıları (örn: %-0,14 %-2,48 Haberler FİNANS Ekonomi)
    t = re.sub(r'^(?:\s*%\s*[-+]?\d+[\.,]\d+\s*)+(?:Haberler|FİNANS|Ekonomi|Gündem|Son Dakika|\s)*', '', t, flags=re.I)
    t = re.sub(r'\b(?:Haberler\s+FİNANS\s+Ekonomi)\b', '', t, flags=re.I)

    # 1. Menü, Kategori, Breadcrumb ve AI kutusu kalıntıları (ShiftDelete, Webtekno, DonanımHaber vb.)
    t = re.sub(r'(?:i\s+)?Son\s+Haberler\s+Yapay\s+Zeka.*?(?:Nasıl\s+Yapılır\?|Kategoriler|Haberler)\s*', ' ', t, flags=re.I)
    t = re.sub(r'Donanım\s+Yazılım\s+Android.*?AI\s+ile\s+Özetle\s*', ' ', t, flags=re.I)
    t = re.sub(r'AI\s+ile\s+Özetle\s*', ' ', t, flags=re.I)
    t = re.sub(r'ARA\s+English\s+Version.*?(?:Nasıl\s+Yapılır\?|Kategoriler|Haberler)\s*', ' ', t, flags=re.I)
    t = re.sub(r'English\s+Version\s+Teknoloji\s+Haberleri[^\.\n]*', ' ', t, flags=re.I)

    # 2. Yazar adı ve tarih kırıntısı (Erhan Şencan 24 Ekim 2026, Hakan Hasırcıoğlu 24 Ekim 2026 vb.)
    t = re.sub(r'^[A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,35}\s+\d{1,2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\s*', '', t, flags=re.I)

    # 1. Yapışık kelimeleri ve noktalama bitişikliklerini ayır
    t = re.sub(r'([a-zçğıöşü\)])([A-ZÇĞİÖŞÜ])', r'\1 \2', t)
    t = re.sub(r'(\d{2}:\d{2})([A-ZÇĞİÖŞÜ])', r'\1 \2', t)
    t = re.sub(r'([\.!?])([A-ZÇĞİÖŞÜ])', r'\1 \2', t)

    # 2. Site buton, menü, SEO, borsa bandı ve telif çöplerini kaldır
    junk_patterns = [
        # ShiftDelete / Webtekno menü, arama çubuğu ve kategori kırıntıları
        r'ARA\s+English\s+Version.*?(?:Nasıl\s+Yapılır\?|Kategoriler|Haberler)\s*',
        r'English\s+Version\s+Teknoloji\s+Haberleri[^\.\n]*',
        # Mynet / Haber siteleri favori butonları
        r'Favorilerime\s+ekle.*?(?:ekleyebilirsin[i\.]?|ekleyin[i\.]?|kaydet|ikonuna\s+tıklayarak[^\.\n]*)',
        r'Favorilerime\s+ekle\s*\([^\)]*\)[^\.\n]*',
        # Finans / Borsa / Kripto canlı döviz bantları (DOLAR 49,7373 GRAM ALTIN 6.425,77...)
        r'(?:DOLAR|EURO|BİST\s*100|GRAM\s+ALTIN|ALTIN|BİTCOİN|PETROL)\s+[\d\.,]+.*?(?:PETROL|BİTCOİN|EURO|DOLAR|ALTIN|BİST|ÇEYREK)\s+[\d\.,]+',
        # Editör / Yazar / Ajans imzaları (Cansu Çamcı / Mynet Haber / İçerik Editörü...)
        r'[A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,35}/\s*(?:Mynet|Hürriyet|Milliyet|Sabah|DHA|İHA|AA|Ensonhaber)?\s*Haber\s*/\s*İçerik Editörü[^\.\n]*',
        r'(?:Editör|Muhabir|Fotoğraf):\s*[A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,30}',
        # Telif ve Hürriyet / Mynet kopyalama yasak uyarıları
        r'(?:Hurriyet\.com\.tr|Mynet|Milliyet|Sabah|TRT Haber).*?haber içerikleri kaynak gösterilmeden alıntı yapılamaz[^\.\n]*',
        r'Kanuna aykırı ve izinsiz olarak kopyalanamaz[^\.\n]*',
        r'başka yerde yayınlanamaz\.?',
        r'Hürriyet\'in internet haber sitesi hurriyet\.com\.tr;[^\.\n]*',
        r'Tüm hakları saklıdır\.?',
        # SPK, Borsa ve Yatırım Danışmanlığı Yasal Uyarıları (Mynet Finans, Bigpara, Borsa Gündem vb.)
        r"SPK(?:'n[ıi]n)?.*?Resmi\s+Gazete.*?uyar[ıi].*?(?:dayanmaktad[ıi]r|sunulmaktad[ıi]r|de[gğ]ildir|al[ıi]nmal[ıi]d[ıi]r|\.|\n|$)",
        r"Burada\s+yer\s+alan\s+yat[ıi]r[ıi]m\s+bilgi.*?(?:de[gğ]ildir|dayanmaktad[ıi]r|sunulmaktad[ıi]r|al[ıi]nmal[ıi]d[ıi]r|\.|\n|$)",
        r"Yat[ıi]r[ıi]m\s+dan[ıi][sş]manl[ıi][gğ][ıi]\s+hizmeti,?\s*arac[ıi]\s+kurumlar.*?(?:sunulmaktad[ıi]r|dayanmaktad[ıi]r|de[gğ]ildir|\.|\n|$)",
        r"Burada\s+yer\s+alan\s+yorum\s+ve\s+tavsiyeler.*?(?:dayanmaktad[ıi]r|al[ıi]nmal[ıi]d[ıi]r|de[gğ]ildir|\.|\n|$)",
        r"Yasal\s+Uyar[ıi]:\s*Burada\s+yer\s+alan.*?(?:dayanmaktad[ıi]r|de[gğ]ildir|\.|\n|$)",
        r"\bSPK(?:'n[ıi]n)?\s*uyar[ıi]s[ıi]\b[^\.\n]*",
        r"\((?:Mynet Finans|Mynet|AA|İHA|DHA|Haber Global|Ensonhaber|Hürriyet|Milliyet|Sabah)\)",
        r'Ayrıntılar Geliyor\.+',
        r'Detaylar birazdan\.+',
        r'Haberin devamı aşağıdadır\.?',
        # DonanımHaber ve diğer sitelerin yazar biyografisi, içindekiler ve e-ticaret bağlantıları
        r'\bİçindekiler(?:\s+İçindekiler)*\b[^\.\n]*',
        r'Editör Hakkında Diğer Haberleri.*?(?:ilgi duyuyor|imza atmaya çalışıyor|\.|\n|$)',
        r'[A-Za-z0-9_\'\"]+\s*\)\s*\.\s*click\s*\(\s*\)\s*;\s*event\s*\.\s*prevent\s*Default\s*\(\s*\)\s*;\s*[\"\'>]*',
        r'Tam\s+Boyutta\s+Gör',
        r'Oy\s+Ver\s+[A-ZÇĞİÖŞÜa-zçğıöşü\s\?]+',
        r'https?://(?:www\.)?(?:n11|migros|idefix|trendyol|hepsiburada|amazon)\.com[^\s<]*',
        r'\b\d+\s*sa\.\s*önce\s*eklendi\b',
        # Standart buton ve Google promosyon çöpleri
        r'\bHABERLER\b.*?(?:Haberleri|Gündem)',
        r'Font\s*Boyutu.*?Linki\s*Kopyala',
        r'Haberlerimizi\s+Google.*?Haberin\s+Devam[ıi]',
        r'Google(?:\'da|\s+da)\s+tercih\s+edilen.*?ekleyin',
        r'Gelişmelerden\s+anında\s+haberdar\s+olun\.?',
        r'Haberin\s+Devam[ıi]',
        r'\b(?:Güncelleme|Oluşturulma)\s*Tarihi:[^\.\n\r]*?(?:\d{2}:\d{2}|\d{4})',
        r'[A-ZÇĞİÖŞÜ\s]{2,25}/\s+[A-ZÇĞİÖŞÜ\s]{2,25}\s*\([^)]+\)\s*,\s*\([A-ZÇĞİÖŞÜ]+\)',
        r'Fotoğraf:\s*[A-Za-zÇĞİÖŞÜçğıöşü0-9\s/]+',
        r'Paylaş\s*N?Sosyal.*?(?:Flipboard|Kopyala)',
    ]
    for p in junk_patterns:
        t = re.sub(p, ' ', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def is_valueless_clickbait(title: str, text: str) -> bool:
    """
    Fiyat, zam, indirim veya kur sorgulayan ama içinde hiçbir sayı,
    fiyat (TL, lira, kuruş, $) veya somut bilgi barındırmayan
    kullanıcıyı kandıran arama motoru (SEO) tuzaklarını tespit eder.
    (Örn: 'Benzin ne kadar oldu? Motorin kaç TL?' sorup hiç fiyat vermeyen çöp haberler)
    """
    t_low = (title or "").lower()
    # 1. Biyografi & Magazin Arama Motoru Çöpleri (Örn: 'X kimdir, nereli, kaç yaşında, serveti ne kadar')
    bio_spam_words = ["kimdir", "kaç yaşında", "nereli", "nerelidir", "ne iş yapar", "serveti ne kadar", "serveti kaç", "evli mi", "eşi kim", "sevgilisi kim", "biyografisi", "hangi şirketlerin sahibi"]
    if sum(1 for w in bio_spam_words if w in t_low) >= 2 or ("kimdir" in t_low and any(w in t_low for w in ["nereli", "yaşında", "tutuklandı", "servet", "sahibi"])):
        return True

    combined = f"{title} {text}".lower()
    price_keywords = [
        "akaryakıt", "benzin", "motorin", "lpg", "altın fiyat", "çeyrek altın",
        "gram altın", "kaç tl", "kaç lira", "fiyatı ne kadar", "ne kadar oldu",
        "zam geldi mi", "indirim var mı", "dolar ne kadar", "euro ne kadar"
    ]
    is_price_topic = any(k in combined for k in price_keywords)
    if not is_price_topic:
        return False

    # İçinde gerçek para/fiyat birimi veya rakam var mı?
    has_prices = bool(re.search(r'\b\d{1,3}(?:[\.,]\d{1,4})?\s*(?:tl|lira|kuruş|dolar|\$|€|euro)\b', text, re.I))
    if not has_prices:
        # 43,50 veya 44.10 gibi ondalıklı fiyat rakamları var mı?
        has_floating_nums = bool(re.search(r'\b\d{2}[\.,]\d{2}\b', text))
        if not has_floating_nums:
            return True

    # Soru döngüsü kontrolü: Cümlelerin yüzde 40'ından fazlası soru işareti içeriyorsa ve bilgi vermiyorsa
    sentences = [s.strip() for s in re.split(r'[\.!\?]\s+', text) if s.strip()]
    if sentences:
        question_count = sum(1 for char in text if char == '?')
        if question_count >= 3 and (question_count / len(sentences)) > 0.4:
            return True

    return False


def fetch_article_details(link: str, max_paragraphs: int = 5) -> dict:
    """
    Haberin orijinal web sayfasına gidip:
    1. Yüksek çözünürlüklü resmi og:image / twitter:image basın görselini ayıklar.
    2. BeautifulSoup ile menü/navigasyon/reklam çöplerini ayıklayarak saf haber paragraflarını çeker.
    """
    if not link or not link.startswith("http"):
        return {"body": "", "images": []}
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        }
        resp = requests.get(link, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {"body": "", "images": []}

        soup = BeautifulSoup(resp.content, "html.parser")

        # 1. Haberin Resmi Editoryal Görseli (OG Image / Twitter Image)
        candidate_images = []
        og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if og and og.get("content"):
            og_url = og.get("content").strip()
            if og_url.startswith("//"):
                og_url = "https:" + og_url
            if og_url.startswith("http"):
                candidate_images.append(og_url)

        # 2. Sayfa içi çöpleri (menü, script, stil, arama kutusu, yazar kutusu, sidebar) DOM'dan tamamen temizle
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "button"]):
            tag.decompose()

        # Makale gövdesini içeren ana kapsayıcıyı bul
        article_elem = (
            soup.find("article") or
            soup.find("div", class_=re.compile(r"entry-content|post-content|article-content|content-body|news-detail", re.I)) or
            soup.find("main") or
            soup
        )

        clean_paras = []
        bad_body_phrases = [
            "çerez", "cookie", "telif", "copyright", "kullanım koşulları",
            "gizlilik", "künye", "reklam", "abone", "yayın grubu",
            "tıklayın", "tıklayınız", "indir", "fotoğraf:", "menüyü aç", "tüm hakları saklıdır",
            "font boyutu", "yazıyı büyüt", "yazıyı küçült", "linki kopyala",
            "google'da takip edin", "google'da tercih edilen", "haberin devamı",
            "gelişmelerden anında", "oluşturulma tarihi", "güncelleme tarihi",
            "flipboard", "nsosyal", "yazı boyutu", "paylaş",
            "favorilerime ekle", "ikonuna tıklayarak", "içerik editörü", "haber / içerik",
            "kanuna aykırı ve izinsiz", "kaynak gösterilmeden alıntı yapılamaz", "ayrıntılar geliyor",
            "detaylar birazdan", "hurriyet.com.tr", "mynet haber", "bist 100", "gram altın",
            "whatsapp kanalımıza", "bizi takip edin", "e-bülten", "ayrıntılar için tıklayın",
            "içindekiler", "editör hakkında", "teknoloji editörü", "içerik editörü", "oy ver", "takipçi",
            "scorsese", "donanım haber", "donanimhaber", "tam boyutta gör", "click()", "preventdefault",
            "n11.com", "migros.com", "idefix.com", "trendyol.com", "hepsiburada.com",
            "son haberler", "yapay zeka otomobil", "kategoriler nasıl yapılır", "donanım yazılım android",
            "ai ile özetle", "yorum yap", "yorumlar", "giriş yap", "üye ol"
        ]

        for p in article_elem.find_all("p"):
            txt = p.get_text()
            c = clean_html(txt)
            c = sanitize_news_text(c)
            # 40 karakterden uzun, çöp içermeyen ve daha önce listeye eklenmemiş özgün paragraflar
            if len(c) > 40 and not any(b in c.lower() for b in bad_body_phrases):
                if not any(c.lower() in existing.lower() or existing.lower() in c.lower() for existing in clean_paras):
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

        # 3. OTOMOBİL & TAŞIT KAMPANYALARI (+35 Puan)
    oto_keywords = [
        "otomobil", "araba", "sıfır araç", "fiyat listesi", "kampanya", "togg",
        "t10x", "egea", "doblo", "clio", "ötv", "faizsiz", "taşıt kredisi",
        "elektrikli araç", "hyundai", "toyota", "volkswagen", "chery", "byd",
        "renault", "fiat", "peugeot", "skoda", "indirimli fiyat"
    ]
    for kw in oto_keywords:
        if kw in text:
            score += 35
            break

    # 4. DİJİTAL, TEKNOLOJİ & YAPAY ZEKA (+30 Puan)
    tekno_keywords = [
        "whatsapp", "instagram", "apple", "iphone", "android", "telefon",
        "dolandırıcılık", "oltalama", "yapay zeka", "chatgpt", "openai", "gemini",
        "samsung", "galaxy", "nvidia", "işlemci", "akıllı telefon", "ios", "güncelleme"
    ]
    for kw in tekno_keywords:
        if kw in text:
            score += 30
            break

    # 5. SAĞLIK & BESLENME (+30 Puan)
    saglik_keywords = [
        "sağlık bakanlığı", "grip", "aşı", "beslenme", "diyet", "kolesterol",
        "tansiyon", "kanser", "tedavi", "ilaç", "check-up", "kalp sağlığı",
        "bağışıklık", "vitamin", "doktor"
    ]
    for kw in saglik_keywords:
        if kw in text:
            score += 30
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

def fetch_latest_news(limit_per_feed: int = 12) -> List[Dict]:
    """
    Tanımlı seçkin RSS kaynaklarını tarar ve 'Halkın İlgisi ve Cüzdan Puanı'na göre
    en yüksekten en düşüğe sıralanmış paylaşılmaya hazır haberleri döner.
    Çapraz RSS mükerrerlik koruması ve 5 katmanlı dedup içerir.
    """
    database.init_db()
    unposted_news = []
    seen_batch_slugs = set()
    seen_batch_titles = []
    import difflib

    for feed_info in config.RSS_FEEDS:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]

        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit_per_feed]:
                title = sanitize_news_text(clean_html(entry.get("title", "")))
                link = entry.get("link", "")
                summary = sanitize_news_text(clean_html(entry.get("summary", "") or entry.get("description", "")))
                image_url = extract_image_url(entry)
                published = entry.get("published", "")

                if not title or not link:
                    continue

                # 36 Saat Tazelik Kalkanı (Sabah 09:00 haberi öğlen/gece yayınlanabilir; günler öncesinin bayat haberi elenir)
                if entry.get('published_parsed'):
                    try:
                        import time
                        pub_ts = time.mktime(entry.published_parsed)
                        if time.time() - pub_ts > (36 * 3600):
                            continue
                    except Exception:
                        pass

                # Somut veri/fiyat içermeyen, yalnızca soru sorup duran arama motoru tuzaklarını baştan ele
                if is_valueless_clickbait(title, summary):
                    continue

                news_hash = get_news_hash(title, link)

                # 1. Veritabanı ve Geçmiş Kontrolü (5 Katmanlı Akıllı Dedup: Hash, Link, Başlık, Benzerlik)
                if database.is_already_posted(news_hash, title=title, link=link):
                    continue

                # 2. Aynı Tarama Döngüsünde Başka Bir Kaynak Aynı Haberi Verdi mi? (Çapraz RSS Koruması)
                from database import slugify
                item_slug = slugify(title)
                norm_slug = re.sub(r'-\d+$', '', item_slug)
                if norm_slug in seen_batch_slugs:
                    continue

                is_batch_dup = False
                for prev_title in seen_batch_titles:
                    if difflib.SequenceMatcher(None, title.lower(), prev_title.lower()).ratio() > 0.72:
                        is_batch_dup = True
                        break
                    stopwords = {'ve', 'ile', 'bir', 'bu', 'da', 'de', 'icin', 'için', 'yeni', 'son', 'dakika'}
                    w1 = {w for w in re.findall(r'\w+', title.lower()) if len(w) > 2 and w not in stopwords}
                    w2 = {w for w in re.findall(r'\w+', prev_title.lower()) if len(w) > 2 and w not in stopwords}
                    if len(w1) >= 4 and len(w2) >= 4 and len(w1 & w2) / min(len(w1), len(w2)) >= 0.75:
                        is_batch_dup = True
                        break

                if is_batch_dup:
                    continue

                seen_batch_slugs.add(norm_slug)
                seen_batch_titles.append(title)

                # Haberin viral/tüketici/cüzdan ilgi puanını hesapla
                score = calculate_virality_score(title, summary, feed_name)
                # Görseli olan haberlere +10 avantaj puanı
                if image_url:
                    score += 10

                feed_cat = feed_info.get("category", "Gündem")
                # Haberin gerçek kategorisini içerik analiz motoru ile doğrula
                import ai_writer
                real_cat = ai_writer.classify_article(title, summary, feed_cat)

                unposted_news.append({
                    "hash": news_hash,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "image_url": image_url,
                    "source": feed_name,
                    "category": real_cat,
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
