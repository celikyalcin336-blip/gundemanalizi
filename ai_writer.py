import os
import sys
import html
import re

# Windows konsolunda Türkçe ve emoji karakterlerin hatasız yazdırılması için
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config

def generate_telegram_post(title: str, summary: str, source: str) -> str:
    """
    Önde gelen haber Telegram kanallarının (ANA HABER, Asayiş Berkemal, BPT) tarzında:
    - İlk satır: Vurucu başlık / giriş
    - 2-3 adet madde işareti (— ...) ile kritik rakamlar, kararlar, cezalar ve gelişmeler
    - En altta kaynak parantezi: (Kaynak)
    - Kesinlikle hashtag veya yapay soru içermez.
    """
    import news_fetcher
    headline = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    clean_summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.replace("\r", "").strip()))) if summary else ""

    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            prompt = f"""
Sen Türkiye'nin en popüler haber Telegram kanallarının (BPT, Asayiş Berkemal, Ana Haber) uzman editörüsün.
Aşağıdaki haber için Telegram takipçilerinin tek bakışta okuyabileceği, net, vurucu ve maddeli bir haber metni hazırla.

Haber Başlığı: {title}
Haber Detayı: {summary}
Kaynak: {source}

Format:
İlk satır: Haberin ana konusu / vurucu özeti (1 kısa cümle).
Boş satır.
Maddeler: Haberdeki en kritik sayıları, gelişmeleri ve ayrıntıları içeren 2-3 adet madde işareti (— ile başlayan).
Son satır: Parantez içinde kaynak, örn: ({source})

Kurallar:
1. ASLA hashtag (#haber, #sondakika vb.) KULLANMA.
2. ASLA 'Siz ne düşünüyorsunuz' gibi yapay sorular SORMA.
3. ASLA link/URL ekleme.
4. Varsa kesin sayıları, TL tutarlarını, oranları, ceza/hapis sürelerini maddelere koy.
5. Yalnızca doğrudan paylaşılacak nihai metni yaz.
"""
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    res = client.models.generate_content(model=m_name, contents=prompt)
                    if res and res.text:
                        return res.text.strip()
                except Exception:
                    continue
        except Exception:
            pass

    # Kural Tabanlı Akıllı Editör (Fallback)
    import re
    # Finans / Borsa canlı ticker yüzdelerini ve kategori kırıntılarını ayıkla
    clean_summary = re.sub(r'^(?:\s*%\s*[-+]?\d+[\.,]\d+\s*)+(?:Haberler|FİNANS|Ekonomi|Gündem|Son Dakika|\s)*', '', clean_summary, flags=re.I)
    clean_summary = re.sub(r'\b(?:Haberler\s+FİNANS\s+Ekonomi)\b', '', clean_summary, flags=re.I)

    raw_sentences = [s.strip() for s in re.split(r'(?<=[!?:])\s+|(?<=[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]{3}\.)\s+(?=[A-ZÇĞİÖŞÜ0-9])', clean_summary) if len(s.strip()) > 20]

    # Başlık parçalarını topla (başlıktaki cümlelerin maddelerde tekrarlanmasını önle)
    headline_parts = [p.strip().lower() for p in re.split(r'[:!,—\-\.]+', headline) if len(p.strip()) > 10]

    filtered_sentences = []
    for s in raw_sentences:
        s_clean = s.strip()
        s_lower = s_clean.lower()

        if s_lower == headline.lower():
            continue
        if any(s_lower == part for part in headline_parts):
            continue

        # Eğer cümlenin başı başlığın bir parçasıyla başlıyorsa kırp
        for part in headline_parts:
            if s_lower.startswith(part):
                s_clean = s_clean[len(part):].lstrip(' ,:!-—.')
                s_lower = s_clean.lower()

        if len(s_clean) < 25:
            continue
        if any(b in s_lower for b in ["tıklayınız", "tıklayın", "abone olun", "ayrıntılar geliyor", "fotoğraf:", "iha", "aa", "dha", "son haberler", "kategoriler nasıl yapılır", "donanım yazılım", "ai ile özetle"]):
            continue

        # Başındaki yazar adı ve tarihi temizle (Erhan Şencan 24 Ekim 2026, Hakan Hasırcıoğlu 24 Ekim 2026 vb.)
        s_clean = re.sub(r'^[A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,35}\s+\d{1,2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\s*', '', s_clean, flags=re.I).strip()
        if len(s_clean) < 25:
            continue

        filtered_sentences.append(s_clean)

    data_keywords = ["tl", "lira", "dolar", "yüzde", "%", "bin", "milyon", "milyar", "hapis", "yıl", "ay", "ceza", "maliyet", "tutar", "tespit", "karar", "açıkladı", "belirlendi", "kesinleşti", "arttı", "düştü", "zam", "indirim", "metre", "icra", "iade"]

    priority_sentences = []
    normal_sentences = []

    for s in filtered_sentences:
        if any(char.isdigit() for char in s) or any(k in s.lower() for k in data_keywords):
            priority_sentences.append(s)
        else:
            normal_sentences.append(s)

    selected_bullets = (priority_sentences + normal_sentences)[:3]

    if selected_bullets:
        bullet_text = "\n".join([f"— {s}" for s in selected_bullets])
        return f"{headline}\n\n{bullet_text}\n({source})"
    else:
        return f"{headline}\n({source})"

def generate_social_caption(title: str, summary: str, source: str) -> dict:
    """
    Saygın ve kurumsal bir haber medya kuruluşu (Gündem Analizi) tarzında:
    - Net, tarafsız ve akıcı editoryal basın dili (1-2 paragraf)
    - KESİNLİKLE yapay sorular ("Siz ne düşünüyorsunuz?", "Yorumlarda buluşalım" vb.) İÇERMEZ.
    - KESİNLİKLE hashtag (#haber, #sondakika vb.) İÇERMEZ.
    - Haberin ne olduğunu, nerede ve nasıl gerçekleştiğini doğrudan aktarır.
    """
    import news_fetcher
    import re
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            
            prompt = f"""
Sen saygın ve profesyonel bir ulusal haber ajansının (Gündem Analizi) kıdemli baş editörüsün.
Aşağıdaki haber için kurumsal haber medya kuruluşlarının (BBC Türkçe, TRT Haber, NTV) standartlarına uygun, sade, tarafsız ve net bir Türkçe haber paylaşım metni hazırla.

Haber Başlığı: {title}
Haber Detayı: {summary}

UYULMASI ZORUNLU KURALLAR:
1. Basın ve ajans ciddiyetine uygun, tarafsız, bilgilendirici ve profesyonel bir dil kullan (1 veya en fazla 2 akıcı paragraf).
2. ASLA takipçilere yapay sorular sorma (Örn: 'Siz ne düşünüyorsunuz?', 'Yorumlarda buluşalım', 'Sizce ne yapılmalı?' gibi amatör etkileşim tuzaklarını KESİNLİKLE KULLANMA).
3. ASLA hashtag (#haber, #sondakika, #gündem vb.) KULLANMA. Metin tamamen temiz, kurumsal ve sade olmalıdır.
4. Başlığı veya aynı cümleyi metin içinde ASLA iki kez tekrar etme.
5. Metnin içine link/URL veya 'Kaynak: ...' yazma (kaynak ve link sistem tarafından otomatik ve tek seferlik eklenecektir).
6. Yalnızca doğrudan yayınlanacak nihai basın metnini yaz; selamlama, kapanış veya fazladan açıklama ekleme.
"""
            # Model denemesi (önce 2.5-flash, sonra 2.0-flash, sonra 1.5-flash)
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=m_name,
                        contents=prompt
                    )
                    if response and response.text:
                        raw_ai = response.text.strip()
                        # Güvenlik filtresi: Olası soru ve hashtag kalıntılarını temizle
                        clean_ai = re.sub(r'#\w+', '', raw_ai)
                        clean_ai = re.sub(r'(?:sizce|siz\s+bu\s+konuda|ne\s+düşünüyorsunuz|yorumlarda\s+buluşalım|görüşlerinizi\s+paylaşın)[^\.\n]*[\.\?!]?', '', clean_ai, flags=re.I)
                        clean_ai = re.sub(r'\n{3,}', '\n\n', clean_ai).strip()
                        return {
                            "caption": clean_ai,
                            "source_used": f"Gemini AI ({m_name})"
                        }
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini API çağrısı başarısız, şablon fallback kullanılıyor: {e}")

    # Kural Tabanlı Kurumsal Medya Formatı (Fallback)
    clean_summary = summary.replace("\n", " ").strip() if summary else ""
    # Metin içindeki yapay soru ve yorum çağrılarını temizle
    clean_summary = re.sub(r'(?:sizce|siz\s+bu\s+konuda|ne\s+düşünüyorsunuz|yorumlarda\s+buluşalım|görüşlerinizi\s+paylaşın)[^\.\n]*[\.\?!]?', '', clean_summary, flags=re.I).strip()
    
    # Başlık ile özet aynıysa veya özet boşsa tekrarlama yapma
    if clean_summary and clean_summary.lower() != title.strip().lower():
        if len(clean_summary) > 280:
            clean_summary = clean_summary[:275].rsplit(' ', 1)[0] + "..."
        caption_text = f"{title}\n\n{clean_summary}"
    else:
        caption_text = f"{title}"

    return {
        "caption": caption_text,
        "source_used": "Corporate Template"
    }


def smart_sentence_split(text: str) -> list:
    """Türkçe sıra sayıları (14., 1., 2026.) ve unvan/kısaltmaları (Dr., Prof., vb.) bozmadan tam cümlelere böler."""
    import re
    if not text:
        return []
    t = text
    abbrevs = ["dr", "prof", "doç", "doc", "av", "uzm", "vb", "vs", "yy", "mad", "no", "m", "km"]
    for ab in abbrevs:
        t = re.sub(rf'\b({ab})\.', r'\1___DOT___', t, flags=re.I)
    t = re.sub(r'(\b\d+)\.', r'\1___DOT___', t)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ"“])', t)
    clean_sents = []
    for p in parts:
        restored = p.replace('___DOT___', '.').strip()
        if len(restored) > 25:
            clean_sents.append(restored)
    return clean_sents


import re

def classify_article(title: str, summary: str = "", force_category: str = None) -> str:
    """
    Haber metnini 'Başlık Ağırlıklı' (Title-Weighted) ve çok katmanlı puanlama
    motoru ile analiz eder. RSS beslemelerinden gelen menü/navigasyon çöplerinin
    (ör. 'Teknoloji Otomobil Mobil 5G Kategoriler') başlığı yanıltmasını kesin olarak engeller.
    """
    clean_title = (title or "").strip()
    clean_summary = (summary or "").strip()

    # RSS Menü ve Ekmek Kırıntısı (Breadcrumbs) Çöplerini Temizle
    nav_junk = r'(?:ARA English Version|Haberler Yapay Zeka Otomobil Mobil|Kategoriler Nasıl Yapılır\?|Paylaş tweetle paylaştır)'
    clean_summary = re.sub(nav_junk, '', clean_summary, flags=re.IGNORECASE)

    lower_title = clean_title.lower()
    lower_summary = clean_summary.lower()

    # 1. ASAYİŞ, POLİS, YARGI & SUÇ KORUMASI (En Yüksek Öncelik: KESİNLİKLE GÜNDEM)
    crime_regex = r'\b(suç örgütü|çete|çetesi|tutuklama|tutuklandı|tutuklanan|gözaltı|gözaltına|adliye|adliyeye|başsavcılık|savcılık|emniyet|kaçakçılık|narkotik|cinayet|cinayeti|dolandırıcılık|dolandırıcı|cezaevi|cezaevine|operasyon|operasyonu|operasyonunda|operasyonları|asayiş|polis ekipleri|polis|jandarma|hırsızlık|hırsız|yağma|suç duyurusu|hapis cezası|mahkeme|mahkemesi|dava açıldı|şüpheli|şüpheliler|zanlı|zanlılar|silahlı saldırı|örgüt lideri|kuriş|fetö|pkk|deaş)\b'
    if re.search(crime_regex, lower_title, re.IGNORECASE) or re.search(crime_regex, lower_summary, re.IGNORECASE):
        return "Gündem"

    # 2. DEPREM & DOĞAL AFET KORUMASI (Öncelik: KESİNLİKLE GÜNDEM)
    disaster_regex = r'\b(kandilli|afad|deprem|depremi|sarsıntı|artçı sarsıntı|fay hattı|tsunami|heyelan|sel felaketi|yangın söndürme)\b'
    if re.search(disaster_regex, lower_title, re.IGNORECASE):
        return "Gündem"

    # KATEGORİ TANIMLARI
    regex_map = {
        "Teknoloji": r'\b(yapay zeka|yapay zekâ|chatgpt|openai|gemini|claude|deepseek|midjourney|sora|kimi|akıllı telefon|iphone|apple|samsung|galaxy|android|nvidia|işlemci|yazılım|güneş paneli|güneş hücresi|perovskit|uzay aracı|nasa|spacex|uydu|robotik|siber güvenlik|çip krizi|mikroçip|ekran kartı|bilgisayar|tablet|moonshot ai)\b',
        "Sağlık": r'\b(karaciğer|karaciğer yağlanması|böbrek|böbrekler|kalp|kalp krizi|kalp sağlığı|damar|beyin kanaması|felç|inme|tansiyon|yüksek tansiyon|kolesterol|diyabet|şeker hastalığı|obezite|kanser|kanser tedavisi|tümör|organ nakli|göz sağlığı|diş sağlığı|cilt sağlığı|omurga|eklem|romatizma|bağırsak|mide|akciğer|solunum|astım|alerji|alzheimer|demans|epilepsi|bağışıklık|bağışıklık sistemi|enfeksiyon|salgın|virüs|bakteri|grip|grip aşısı|nezle|koronavirüs|covid|yorgun uyan|yorgun uyanıyorsanız|kronik yorgunluk|uyku apnesi|uyku düzeni|beslenme|diyet|diyetisyen|vitamin|vitaminler|mineral|metabolizma|kalori|protein|detoks|sağlıklı yaşam|zayıflama|kilo verme|kilo alma|yağ yakımı|doktor|doktorlar|hekim|uzman hekim|başhekim|tabip|tabipler odası|hastane|hastaneler|klinik|poliklinik|sağlık bakanlığı|sağlık bakanı|mhrs|ameliyat|cerrahi|tedavi|ilaç|ilaçlar|reçete|aşı|aşılar|aşılama)\b',
        "Otomobil": r'\b(otomobil|araba|araç|araçlar|araçta|araçtan|araca|taşıt|suv|sedan|hatchback|şanzıman|motor hacmi|ötv|ötv indirimi|taşıt kredisi|sıfır km|ikinci el|elektrikli araç|hibrit araç|otomotiv|otopark|yakıt tüketimi|beygir gücü|togg|t10x|egea|clio|fiat|renault|peugeot|volkswagen|toyota|hyundai|honda|skoda|opel|ford|bmw|mercedes|audi|porsche|bentley|torcal|ferrari|lamborghini|aston martin|maserati|chery|byd|tesla|mg|gunther werks|citroen|dacia|nissan|kia|seat|cupra|volvo|suzuki|jeep|alfa romeo|land rover|range rover)\b',
        "Spor": r'\b(maç|maçı|maçlar|karşılaşma|müsabaka|futbol|basketbol|voleybol|fenerbahçe|galatasaray|beşiktaş|trabzonspor|başakşehir|süper lig|şampiyonlar ligi|uefa|avrupa ligi|konferans ligi|a milli takım|milli takım|bonservis|futbolcu|teknik direktör|derbi|formula 1|motogp|nba|euroleague|wimbledon|grand slam|olimpiyat|sarı kart|kırmızı kart|penaltı|ofsayt|gol krallığı|transfer teklifi)\b',
        "Eğitim": r'\b(meb|milli eğitim bakanlığı|ösym|yks|lgs|kpss|öğretmen ataması|müfredat|karneler|bursluluk sınavı|ara tatil|yarıyıl tatili|okul tatili|üniversite taban puanları|öğretmenlik|okul|okullar|öğrenci|öğrenciler|öğretmen|öğretmenler|ders yılı|sınav sonuçları)\b',
        "Ekonomi": r'\b(borsa|bist|bist 100|faiz|faiz kararı|faiz oranı|enflasyon|tüfe|üfe|dolar|euro|döviz|bakan şimşek|mehmet şimşek|merkez bankası|tcmb|asgari ücret|emekli maaşı|emekli zammı|memur zammı|mevduat|mevduat faizi|zam|zammı|zamlar|zam oranı|vergi|vergi dilimi|kdv|altın|gram altın|çeyrek altın|ons altın|kredi kartı aidatı|konut kredisi faizi|ihracat|ithalat|cari açık|para politikası)\b',
        "Dünya": r'\b(trump|savaş|israil|gazze|iran|nato|ukrayna|lübnan|pentagon|beyaz saray|zelenskiy|putin|kremlin|dışişleri|diplomasi|uluslararası|avrupa birliği|ateşkes|füze|hava saldırısı|biden|pekin|tahran|tel aviv)\b',
    }

    # ADIM 1: ÖNCELİK BAŞLIKTADIR!
    # Eğer haberin BAŞLIĞI doğrudan bir kategoriyle eşleşiyorsa (ör. 'Yapay Zeka Modeli'),
    # özetteki menü/çöp kelimeler (ör. menüdeki 'Otomobil') BAŞLIĞI ASLA EZEMEZ!
    title_matches = {}
    for cat, reg in regex_map.items():
        found = re.findall(reg, lower_title, re.IGNORECASE)
        if found:
            title_matches[cat] = len(found)

    if title_matches:
        best_cat = max(title_matches.items(), key=lambda x: x[1])[0]
        return best_cat

    # ADIM 2: Başlıkta özel kategori kelimesi yoksa, Özet (Summary) puanlaması yap
    summary_matches = {}
    for cat, reg in regex_map.items():
        found = re.findall(reg, lower_summary, re.IGNORECASE)
        if found:
            summary_matches[cat] = len(found)

    if summary_matches:
        best_cat = max(summary_matches.items(), key=lambda x: x[1])[0]
        return best_cat

    # ADIM 3: Besleme kategorisi varsa doğrula
    if force_category and force_category in regex_map:
        return force_category

    return "Gündem"

def generate_full_article(title: str, summary: str, source: str, force_category: str = None) -> dict:
    """
    Web sitesi için 3-4 paragraflık zenginleştirilmiş, akıcı ve özgün haber makalesi üretir.
    """
    import news_fetcher
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    category = classify_article(title, summary, force_category)

    category_guide = ""
    if category == "Otomobil":
        category_guide = "Bu bir OTOMOBİL & KAMPANYA haberidir. Kampanya şartları, fiyatlar, faizsiz kredi/taksit seçenekleri, model özellikleri ve tüketicinin nasıl yararlanacağını açıkça vurgula."
    elif category == "Teknoloji":
        category_guide = "Bu bir TEKNOLOJİ & YAPAY ZEKA haberidir. Cihazın veya teknolojinin öne çıkan özellikleri, tahmini/kesin Türkiye fiyatı, çıkış tarihi ve günlük hayattaki faydalarını tüketici odaklı anlat."
    elif category == "Eğitim":
        category_guide = "Bu bir EĞİTİM, MEB & SINAV haberidir. Tarihleri, sınav/başvuru detaylarını, öğrencileri ve velileri ilgilendiren önemli bilgileri açık, net ve güvenilir bir dille anlat."
    elif category == "Sağlık":
        category_guide = "Bu bir SAĞLIK & YAŞAM haberidir. Belirtileri, uzman tavsiyelerini ve dikkat edilmesi gereken noktaları güvenilir ve bilgilendirici bir dille anlat."
    elif category == "Ekonomi":
        category_guide = "Bu bir EKONOMİ & FİNANS haberidir. Rakamları, piyasa oranlarını ve vatandaşın bütçesine/cüzdanına yansımalarını somut verilerle açıkla."

    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            prompt = f"""
Sen 'Gündem Analizi' haber sitesinin baş editörüsün.
Aşağıdaki haber için tarafsız, profesyonel, okuyucu dostu bir Türkçe haber makalesi yaz.

Başlık: {title}
Özet Bilgi: {summary}
Kaynak: {source}
Kategori: {category}
Özel Talimat: {category_guide}

İstenen Format:
- Giriş: Haberin ana gelişmesini anlatan çarpıcı bir paragraf.
- Gelişme: Konunun arka planı, detayları ve önemli noktaları (2 paragraf).
- Gündem Analizi Yorumu: Olayın olası etkileri veya dikkat çeken yönleri üzerine kısa bir değerlendirme.

Lütfen çıktıyı düzgün HTML paragrafları (<p>...</p>) ve gerekiyorsa ara başlıklar (<h3>...</h3>) olarak ver.
"""
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt
                    )
                    if res and res.text:
                        return {
                            "title": title,
                            "summary": summary if summary else title,
                            "content": res.text.strip(),
                            "category": category
                        }
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini makale üretimi hatası: {e}")

    # Fallback (Şablon Makale - Asla Metni İki Kez Tekrarlamaz, Zengin ve Profesyonel Paragraflar Üretir)
    import re
    raw_clean = summary.strip()
    # Metni cümlelere ayır (Türkçe kısaltmaları ve noktalama işaretlerini gözeterek)
    sentences = smart_sentence_split(raw_clean)
    
    # Başlıkla aynı olan, çöp soru olan veya yazar/menü içeren cümleleri filtrele
    filtered = []
    for s in sentences:
        s_clean = re.sub(r'^[A-ZÇĞİÖŞÜa-zçğıöşü\s]{3,35}\s+\d{1,2}\s+(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+\d{4}\s*', '', s, flags=re.I).strip()
        if not s_clean:
            continue
        if s_clean.lower() == title.lower() or title.lower() in s_clean.lower():
            continue
        if any(b in s_clean.lower() for b in ["son haberler", "kategoriler nasıl yapılır", "donanım yazılım", "ai ile özetle"]):
            continue
        if s_clean.endswith('?') and len(s_clean) < 55:
            continue
        filtered.append(s_clean)

    if filtered:
        lead_para = filtered[0]
        remaining = filtered[1:]
    else:
        lead_para = raw_clean if raw_clean else title
        remaining = []

    body_paras_list = []
    if remaining:
        # Kalan gerçek haber cümlelerini ilk paragraflara koy
        chunk1 = " ".join(remaining[:2])
        body_paras_list.append(f'<p class="text-slate-300 leading-relaxed mb-4">{chunk1}</p>')
        if len(remaining) > 2:
            chunk2 = " ".join(remaining[2:5])
            body_paras_list.append(f'<p class="text-slate-300 leading-relaxed mb-4">{chunk2}</p>')

    # Her haberin doyurucu, zengin ve en az 3-4 paragraflık gerçek bir haber makalesi olması için
    # eğer gövdede az cümle varsa kategoriye özel derinlikli editoryal arka plan ekle (Asla 1 cümleyle bırakma!)
    if len(body_paras_list) < 2:
        cat_lower = category.lower()
        if "eko" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Piyasalarda ve ekonomi çevrelerinde geniş yankı uyandıran gelişmeyle ilgili olarak uzmanlar, mali dengeler, fiyatlama dinamikleri ve yatırım trendleri üzerindeki etkilerin önümüzdeki süreçte belirginleşeceğini vurguluyor. Yüksek meblağlı işlemler ve piyasa hareketlilikleri, sektör temsilcileri tarafından yakından izleniyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Önümüzdeki günlerde sürecin resmiyet kazanması ve ilgili finansal adımların tamamlanmasıyla birlikte, sektörel göstergeler ve emsal değerler açısından piyasaların nasıl bir yön çizeceği ekonomi servisimiz tarafından takip edilmektedir.</p>')
        elif "spor" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Spor kamuoyunda ve taraftarlar arasında büyük heyecan uyandıran gelişmeyle ilgili olarak kulüp yönetiminin resmi adımları bekleniyor. Teknik heyetin sezon planlaması ve kadro mühendisliği doğrultusunda atılacak bu adımın, takım içi dengelere ve önümüzdeki kritik maç takvimine doğrudan etki etmesi öngörülüyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Müsabaka takvimi ve resmi sözleşme süreçlerinde imzaların atılmasının ardından, tarafların önümüzdeki günlerde kapsamlı bir bilgilendirmeyle ayrıntıları paylaşması beklenirken, spor servisimiz gelişmeleri anbean aktaracaktır.</p>')
        elif "tekno" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Teknoloji dünyasında ve dijital ekosistemde dengeleri değiştirebilecek bu yenilik, geliştiriciler ve son kullanıcılar açısından önemli avantajlar barındırıyor. Yüksek işlem kapasitesi ve yeni nesil algoritmalarla donatılan sistemin, sektördeki küresel rekabeti farklı bir boyuta taşıyacağı vurgulanıyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Teknoloji otoriteleri, yeni modelin yaygınlaşmasıyla birlikte dijital dönüşüm süreçlerinde hız ve verimlilik artışı yaşanacağına dikkat çekerken, küresel pazardaki entegrasyon takvimi merakla takip ediliyor.</p>')
        elif "sağlık" in cat_lower or "saglik" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Sağlık otoriteleri ve tıp uzmanları, doğru bilgilendirmenin ve erken farkındalığın hayati önem taşıdığına dikkat çekiyor. Benzer semptomlar veya sağlık göstergeleri karşısında vatandaşların vakit kaybetmeden uzman hekim kontrolünden geçmesinin önemine vurgu yapılıyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Sağlıklı yaşam standartları ve koruyucu hekimlik kapsamında alınacak bireysel tedbirlerin, yaşam kalitesini doğrudan artıracağı belirtilirken, konuya ilişkin klinik değerlendirmeler yakından izleniyor.</p>')
        elif "oto" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Otomotiv sektöründe dikkat çeken model ve fiyat dinamikleri, tüketici tercihlerini ve pazar dengelerini doğrudan şekillendiriyor. Segmentindeki güçlü rakipleri karşısında öne çıkan donanım ve mühendislik detayları, kullanıcı deneyimi açısından önemli yenilikler sunuyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Türkiye pazarındaki bulunabilirlik, satış koşulları ve bayi kampanyalarına dair resmi duyurular yakından takip edilirken, otomotiv masamız süreci okuyucularımıza aktarmaya devam edecektir.</p>')
        elif "eğitim" in cat_lower or "egitim" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Öğrencileri, öğretmenleri ve velileri yakından ilgilendiren bu gelişmeyle ilgili Milli Eğitim Bakanlığı (MEB) ve ilgili resmi kurumların açıklamaları takip ediliyor. Takvimler, başvuru şartları ve sınav süreçlerine dair resmi duyurular anlık olarak eğitim servisimiz tarafından aktarılacaktır.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Eğitim camiasındaki güncel beklentiler ve başvuru takvimine dair resmi kılavuzlar yayınlandıkça detaylar anbean paylaşılacaktır.</p>')
        elif "dünya" in cat_lower or "dunya" in cat_lower:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Bölgesel ve uluslararası dengeleri yakından ilgilendiren olay sonrasında ilgili ülkelerin diplomatik temasları hız kazandı. Uluslararası gözlemciler ve diplomasi çevreleri sürecin seyrine ilişkin değerlendirmelerini sürdürürken, gelişmeler anlık olarak takip edilmektedir.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Bölgedeki aktörlerin atacağı yeni adımlar ve resmi zirvelerden çıkacak kararlar dünya masamız tarafından dikkatle izlenmektedir.</p>')
        else:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Gelişmeyle ilgili resmi makamlar ve yetkili mercilerden gelecek yeni bilgilendirmeler beklenirken, kamuoyundaki yansımalar dikkatle takip ediliyor. Sürecin yasal boyutu ve detayları anbean okuyucularımızla paylaşılmaya devam edecektir.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Konuya ilişkin kurumlar arası koordinasyon ve sahadaki yansımalar yakından izlenirken, yeni gelişmeler netleştikçe haberimiz güncellenecektir.</p>')

    body_paras = "\n".join(body_paras_list)

    eval_text = "Gelişmenin piyasalar ve kamuoyu üzerindeki yansımaları masamız tarafından yakından takip edilmektedir. Sürece dair resmi makamlardan gelecek yeni veriler anlık olarak aktarılacaktır."
    if category == "Ekonomi":
        eval_text = "Piyasalardaki fiyatlamalar, tüketici hakları ve makroekonomik dengeler açısından sürecin seyri ekonomi servisimiz tarafından yakından izlenmektedir."
    elif category == "Eğitim":
        eval_text = "Öğrenci, veli ve eğitim camiasını ilgilendiren resmi kılavuzlar ve takvim duyuruları eğitim masamız tarafından anlık olarak izlenmektedir."
    elif category == "Spor":
        eval_text = "Müsabaka takvimi ve spor kamuoyunun nabzı doğrultusunda kulüplerden gelecek resmi açıklamalar anlık olarak sayfalarımızda yer alacaktır."

    content_html = f"""
    <p class="lead font-medium text-lg text-slate-200 mb-6">
        {lead_para}
    </p>
    
    <h3 class="text-xl font-bold text-white mt-6 mb-3">Gelişmenin Ayrıntıları</h3>
    {body_paras}

    <div class="p-5 rounded-xl bg-red-950/40 border border-red-800/40 my-6">
        <h4 class="font-bold text-red-400 flex items-center gap-2 mb-2">
            <span>🔴</span> GÜNDEM ANALİZİ DEĞERLENDİRMESİ
        </h4>
        <p class="text-slate-300 text-sm leading-relaxed">
            {eval_text}
        </p>
    </div>
    """

    return {
        "title": title,
        "summary": lead_para,
        "content": content_html,
        "category": category
    }

if __name__ == "__main__":
    sample = generate_social_caption(
        "Yeni Karar Resmi Gazete'de Yayımlandı",
        "Merkez Bankası ve Hazine koordinasyonunda yeni finansal düzenlemeler yürürlüğe girdi.",
        "NTV Haber"
    )
    print("Üretilen Metin:")
    print(sample["caption"])
