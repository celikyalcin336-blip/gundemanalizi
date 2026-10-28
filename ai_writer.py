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
    Önde gelen haber kanallarının (BPT, Ana Haber) tarzında:
    - İlk satır: Vurucu, net başlık
    - Boşluk
    - En az 3, en fazla 4 adet doyurucu, akıcı ve bilgilendirici madde (— ...)
    - KESİNLİKLE kaynak adı yazılmaz (Kaynak biziz).
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
Sen Türkiye'nin en popüler haber kanallarının uzman baş editörüsün.
Aşağıdaki haber için Telegram takipçilerine olayın arka planını, nedenlerini, perde arkasını ve ayrıntılarını net şekilde aktaran, DOYURUCU VE EN AZ 3-4 MADDELİ bir haber metni hazırla.

Haber Başlığı: {title}
Haber Detayı: {summary}

Format:
İlk satır: Haberin ana konusunu ve önemini anlatan net, açıklayıcı ve vurucu bir giriş başlığı.
Boş satır.
Maddeler: KESİNLİKLE EN AZ 3, EN FAZLA 4 ADET DOYURUCU MADDE (— ile başlayan).
- Her madde tam ve akıcı bir Türkçe cümleden oluşmalı; olayın nedenini, arka planını, varsa kritik rakamları, cezaları, kurum açıklamalarını ve sektörel/toplumsal etkilerini net bir dille izah etmelidir.
- Haber detayı kısa veya tek cümle bile olsa, haber başlığından ve konunun genel bağlamından yararlanarak olayı doyurucu, bilgilendirici cümlelerle açıkla. Tek kelimelik veya yarım cümle KESİNLİKLE yazma.

ÖNEMLİ KURALLAR:
1. KESİNLİKLE HİÇBİR KAYNAK ADI YAZMA (örn: Motor1, Habertürk, AA, İHA, TRT vb. ASLA YAZILMAYACAK). Kaynak biz kendimiziz.
2. Metnin sonuna KESİNLİKLE parantez içinde kaynak veya ajans adı EKLEME.
3. ASLA hashtag (#haber, #sondakika vb.) KULLANMA.
4. ASLA 'Siz ne düşünüyorsunuz?' gibi yapay sorular SORMA.
5. ASLA link/URL ekleme.
6. Cümleleri dil bilgisi hatası olmadan, duru ve kusursuz Türkçe ile yaz.
7. Yalnızca doğrudan paylaşılacak nihai metni yaz.
"""
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    res = client.models.generate_content(model=m_name, contents=prompt)
                    if res and res.text:
                        text = res.text.strip()
                        # Güvenlik Kalkanı: Metin sonundaki parantezli kaynak kalıntılarını temizle
                        text = re.sub(r'\s*\([A-Za-z0-9\sğüşıöçĞÜŞİÖÇ\.\'\-]{3,40}\)\s*$', '', text)
                        return text
                except Exception:
                    continue
        except Exception:
            pass

    # Kural Tabanlı Akıllı Editör (Fallback)
    import re
    clean_summary = re.sub(r'^(?:\s*%\s*[-+]?\d+[\.,]\d+\s*)+(?:Haberler|FİNANS|Ekonomi|Gündem|Son Dakika|\s)*', '', clean_summary, flags=re.I)
    clean_summary = re.sub(r'\b(?:Haberler\s+FİNANS\s+Ekonomi)\b', '', clean_summary, flags=re.I)

    raw_sentences = [s.strip() for s in re.split(r'(?<=[!?:])\s+|(?<=[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]{3}\.)\s+(?=[A-ZÇĞİÖŞÜ0-9])', clean_summary) if len(s.strip()) > 20]

    headline_parts = [p.strip().lower() for p in re.split(r'[:!,—\-\.]+', headline) if len(p.strip()) > 10]

    filtered_sentences = []
    for s in raw_sentences:
        s_clean = s.strip()
        s_lower = s_clean.lower()

        if s_lower == headline.lower():
            continue
        if any(w in s_lower for w in ["spk", "yatırım danışmanlığı", "resmi gazete", "tavsiyesi değildir", "mevduat kabul etmeyen", "aracı kurumlar", "portföy yönetim", "yasal uyarı", "burada yer alan", "kişisel görüşlerine"]):
            continue
        if any(s_lower == part for part in headline_parts):
            continue

        for part in headline_parts:
            if s_lower.startswith(part):
                s_clean = s_clean[len(part):].lstrip(' ,:!-—.')
                s_lower = s_clean.lower()

        if len(s_clean) < 25:
            continue
        if any(b in s_lower for b in ["tıklayınız", "tıklayın", "abone olun", "ayrıntılar geliyor", "fotoğraf:", "iha", "aa", "dha", "son haberler", "kategoriler nasıl yapılır", "donanım yazılım", "ai ile özetle"]):
            continue

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

    selected_bullets = (priority_sentences + normal_sentences)[:4]

    # Eğer kaynak metin çok kısaysa (1 cümle vb.), haberi tek satırda bırakma; doyurucu hale getir
    if len(selected_bullets) == 1 and clean_summary:
        first_s = selected_bullets[0]
        # Uzun bileşik cümleyi mantıklı iki parçaya ayır
        clauses = [c.strip() for c in re.split(r'[,;]\s+(?:ve|ancak|fakat|ayrıca|çünkü|bu kapsamda|bununla birlikte)\s+', first_s, flags=re.I) if len(c.strip()) > 20]
        if len(clauses) >= 2:
            selected_bullets = clauses[:3]
        else:
            selected_bullets.append("Gelişmenin sektörel maliyet dengeleri ve tüketici süreçleri üzerindeki olası etkileri yakından takip ediliyor.")

    if selected_bullets:
        bullet_text = "\n".join([f"— {s}" for s in selected_bullets])
        res = f"{headline}\n\n{bullet_text}"
    else:
        res = f"{headline}\n\n— Konuyla ilgili resmi açıklamalar ve son dakika detayları geldikçe aktarılmaya devam edecektir."

    # Kesinlikle kaynak parantezi yazma (Kaynak biz kendimiziz)
    res = re.sub(r'\s*\([A-Za-z0-9\sğüşıöçĞÜŞİÖÇ\.\'\-]{3,40}\)\s*$', '', res)
    return res

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
Aşağıdaki haber için kurumsal haber medya kuruluşlarının (BBC Türkçe, TRT Haber, NTV) standartlarına uygun, doyurucu, açıklayıcı, tarafsız ve profesyonel bir Türkçe haber metni hazırla.

Haber Başlığı: {title}
Haber Detayı: {summary}

UYULMASI ZORUNLU KURALLAR:
1. Basın ve ajans ciddiyetine uygun, tarafsız, bilgilendirici ve profesyonel bir dil kullan (2-3 akıcı, doyurucu ve açıklayıcı paragraf).
2. Olayın kim, nerede, nasıl ve neden gerçekleştiğini, yetkililerin veya tarafların açıklamalarını detaylıca aktar.
3. CÜMLE YAPISI: Cümleleri uzatacağım diye yapay, devrik, anlamsız veya bozuk cümleler kurma. Her cümlenin öznesi ve yüklemi tam, Türkçesi berrak ve akıcı olsun.
4. ASLA takipçilere yapay sorular sorma (Örn: 'Sizce ne olmalı?', 'Yorumlarda buluşalım' gibi amatör tuzakları KESİNLİKLE KULLANMA).
5. ASLA hashtag (#haber, #sondakika vb.) KULLANMA. Metin tamamen temiz ve kurumsal olmalıdır.
6. Başlığı veya aynı cümleyi metin içinde iki kez tekrar etme.
7. Metnin içine link/URL veya 'Kaynak: ...' yazma.
8. Yalnızca doğrudan yayınlanacak nihai basın metnini yaz.
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
    Haber metnini 'Başlık Ağırlıklı' (Title-Weighted) ve Türkçe çekim eklerine tam uyumlu
    kapsamlı sınıflandırma motoru ile analiz eder.
    Hatalı kategori eşleşmelerini (Örn: Ölümlü trafik kazalarının Otomobil'e gitmesi,
    KKTC bakan istifasının Sağlık'a gitmesi, Dünya/Spor haberlerinin Gündem'e sıkışması)
    kesin kurallarla engeller.
    """
    clean_title = (title or "").strip()
    clean_summary = (summary or "").strip()

    # RSS Menü ve Ekmek Kırıntısı (Breadcrumbs) Çöplerini Temizle
    nav_junk = r'(?:ARA English Version|Haberler Yapay Zeka Otomobil Mobil|Kategoriler Nasıl Yapılır\?|Paylaş tweetle paylaştır|Donanım Yazılım Android)'
    clean_summary = re.sub(nav_junk, '', clean_summary, flags=re.IGNORECASE)

    lower_title = clean_title.lower()
    lower_summary = clean_summary.lower()
    full_text = f"{lower_title} {lower_summary}"

    # 0. VEFAT, CENAZE, TAZİYE, YAS, ÖLÜM, KAZA & FACİA KORUMASI (En Yüksek Öncelik: KESİNLİKLE GÜNDEM)
    # Kurban veya vefat eden kişi üniversiteli, liseli, öğretmen, doktor, polis veya sporcu olsa bile:
    # Ölüm, kaza, çarpışma, cinayet, facia haberleri ASLA Eğitim, Sağlık veya Spor yapılamaz!
    death_accident_regex = r'\b(ölüm\w*|öldü\w*|ölen\w*|ölü\b|vefat\w*|cenaze\w*|son yolculuğuna\w*|toprağa verildi\w*|defnedildi\w*|hayatını kaybetti\w*|yaşamını yitirdi\w*|can verdi\w*|can pazarı\w*|facia\w*|katliam\w*|cinayet\w*|katledil\w*|kıyd\w*|vahşet\w*|bıçakla\w*|vurul\w*|öldürül\w*|boğazı\w*|kaza\w*|feci kaza\w*|zincirleme kaza\w*|çarpıştı\w*|şarampole\w*|devrildi\w*|feci şekilde|araç hurdaya\w*|otomobil hurdaya\w*|tır devrildi\w*|otobüs devrildi\w*|fren patladı\w*|alkollü sürücü\w*|ehliyetine el konuldu|ehliyetsiz sürücü\w*|cansız beden\w*|ceset\w*|cesed\w*|dehşet\w*|intihar\w*|boğul\w*|yangında can\w*)\b'
    if re.search(death_accident_regex, lower_title, re.IGNORECASE):
        return "Gündem"

    # 2. ASAYİŞ, POLİS, YARGI & SUÇ KORUMASI (En Yüksek Öncelik: KESİNLİKLE GÜNDEM)
    crime_regex = r'\b(suç örgütü\w*|çete\w*|tutukla\w*|gözaltı\w*|adliye\w*|başsavcılık\w*|savcılık\w*|emniyet\w*|kaçakçılık\w*|narkotik\w*|cinayet\w*|dolandırıcılık\w*|dolandırıcı\w*|cezaevi\w*|operasyon\w*|asayiş\w*|polis ekipleri\w*|polis\w*|jandarma\w*|hırsızlık\w*|hırsız\w*|yağma\w*|suç duyurusu\w*|hapis cezası\w*|mahkeme\w*|dava açıldı\w*|şüpheli\w*|zanlı\w*|silahlı saldırı\w*|örgüt lideri\w*|kuriş\w*|fetö\w*|pkk\w*|deaş\w*|yakalama kararı\w*)\b'
    if re.search(crime_regex, lower_title, re.IGNORECASE):
        return "Gündem"

    # 3. DOĞAL AFET / DEPREM / YANGIN (KESİNLİKLE GÜNDEM)
    disaster_regex = r'\b(kandilli\w*|afad\w*|deprem\w*|sarsıntı\w*|artçı sarsıntı\w*|fay hattı\w*|tsunami\w*|heyelan\w*|yangın söndürme\w*)\b'
    if re.search(disaster_regex, lower_title, re.IGNORECASE):
        return "Gündem"

    # 4. BAKAN İSTİFASI / DIŞ SİYASET / KKTC KORUMASI (KKTC Sağlık Bakanı istifa etti -> KESİNLİKLE DÜNYA)
    if "kktc" in lower_title or "kıbrıs" in lower_title:
        return "Dünya"
    if any(country in lower_title for country in ["fransa", "bulgaristan", "almanya", "abd", "çin", "rusya", "ukrayna", "israil", "gazze", "iran", "lübnan", "yunanistan", "ingiltere", "hürmüz"]):
        if any(w in lower_title for w in ["seçim", "sandık", "istifa", "fırtına", "elektrik", "boğazı", "işçi çıkar", "savaş", "füze", "hava saldırısı", "ateşkes", "cumhurbaşkanı", "başbakan"]):
            return "Dünya"

    # KATEGORİ TANIMLARI (Türkçe çekim eklerini \w* ile destekleyen zengin kök yapısı)
    regex_map = {
        "Spor": r'\b(fenerbahçe\w*|galatasaray\w*|beşiktaş\w*|trabzonspor\w*|başakşehir\w*|pendikspor\w*|kayserispor\w*|konyaspor\w*|antalyaspor\w*|sivasspor\w*|kasımpaşa\w*|alanyaspor\w*|rizespor\w*|göztepe\w*|bodrum fk|eyüpspor\w*|süper lig\w*|şampiyonlar ligi\w*|uefa\w*|avrupa ligi\w*|konferans ligi\w*|el clasico\w*|derbi\w*|futbol\w*|basketbol\w*|voleybol\w*|tenis\w*|formula 1|f1|motogp|nba|euroleague\w*|wimbledon\w*|olimpiyat\w*|milli takım\w*|a milli|arda güler\w*|kenan yıldız\w*|hakan çalhanoğlu\w*|osimhen\w*|icardi\w*|dzeko\w*|tadic\w*|muslera\w*|fred\w*|mourinho\w*|okan buruk\w*|courtois\w*|skriniar\w*|bonservis\w*|transfer\w*|karşılaşma\w*|maç\w*|galibiyet\w*|mağlubiyet\w*|beraberlik\w*|puan durumu\w*|nesibe aydın\w*)\b',
        "Otomobil": r'\b(otomobil\w*|araba\w*|araç lansmanı\w*|yeni model\w*|fiyat listesi\w*|başlangıç fiyatı\w*|ötv indirimi\w*|taşıt kredisi\w*|sıfır araç\w*|sıfır km|ikinci el oto\w*|elektrikli araç\w*|elektrikli otomobil\w*|hibrit\w*|şarj istasyonu\w*|menzil\w*|batarya kapasitesi\w*|beygir gücü\w*|şanzıman\w*|suv\w*|sedan\w*|hatchback\w*|togg\w*|t10x|t10f|fiat\w*|egea\w*|doblo\w*|renault\w*|clio\w*|megane\w*|chery\w*|tiggo\w*|omoda\w*|jaecoo\w*|byd\w*|tesla\w*|model y|model 3|volkswagen\w*|golf\w*|passat\w*|toyota\w*|corolla\w*|hyundai\w*|i20\w*|tucson\w*|honda\w*|civic\w*|skoda\w*|octavia\w*|ford\w*|focus\w*|bmw\w*|mercedes\w*|audi\w*|porsche\w*|volvo\w*|nissan\w*|qashqai\w*|peugeot\w*|citroen\w*|dacia\w*|sandero\w*|kia\w*|sportage\w*|cupra\w*|mg\w*|suzuki\w*)\b',
        "Eğitim": r'\b(meb\w*|milli eğitim\w*|yusuf tekin\w*|ösym\w*|yks\w*|tyt\w*|ayt\w*|lgs\w*|kpss\w*|dgs\w*|ales\w*|tus\w*|sınav\w*|soru kitapçığı\w*|cevap anahtarı\w*|taban puan\w*|tercih sonuç\w*|üniversite\w*|öğretmen\w*|öğrenci\w*|okul\w*|ara tatil\w*|yarıyıl tatili\w*|kar tatili\w*|karne\w*|müfredat\w*|öğretmen atama\w*)\b',
        "Teknoloji": r'\b(yapay zeka\w*|yapay zekâ\w*|ai|chatgpt\w*|openai\w*|gemini\w*|claude\w*|deepseek\w*|midjourney\w*|sora\w*|kimi k3|robot\w*|robotik\w*|akıllı telefon\w*|cep telefonu\w*|iphone\w*|apple\w*|samsung\w*|galaxy\w*|xiaomi\w*|redmi\w*|huawei\w*|honor\w*|android\w*|ios\w*|işlemci\w*|snapdragon\w*|intel\w*|amd\w*|ryzen\w*|nvidia\w*|rtx\w*|ekran kartı\w*|çip\w*|mikroçip\w*|yarı iletken\w*|bilgisayar\w*|laptop\w*|dizüstü\w*|tablet\w*|ipad\w*|akıllı saat\w*|kulaklık\w*|airpods\w*|playstation\w*|play station\w*|ps5\w*|ps4\w*|xbox\w*|nintendo\w*|steam\w*|konsol\w*|video oyunu\w*|pc oyunu\w*|oyun dünyası\w*|jailbreak\w*|yazılım\w*|siber güvenlik\w*|hacker\w*|whatsapp\w*|instagram\w*|meta\w*|tiktok\w*|youtube\w*|twitter\w*|telegram\w*|discord\w*|uzay aracı\w*|nasa\w*|spacex\w*|uydu\w*|astronot\w*|teleskop\w*|4k|blu-ray\w*|akıllı televizyon\w*|akıllı tv\w*|güneş paneli\w*|perovskit\w*)\b',
        "Sağlık": r'\b(estetik\w*|plastik cerrahi\w*|bıçak altına\w*|genç görün\w*|botoks\w*|dolgu\w*|saç ekim\w*|burun ameliyat\w*|liposuction|dermatolog\w*|klinik\w*|hastalık\w*|virüs\w*|bakteri\w*|enfeksiyon\w*|salgın\w*|grip\w*|nezle\w*|koronavirüs\w*|covid\w*|kanser\w*|tümör\w*|kalp krizi\w*|tansiyon\w*|kolesterol\w*|diyabet\w*|şeker hastalığı\w*|obezite\w*|karaciğer\w*|böbrek\w*|organ nakli\w*|ameliyat\w*|cerrahi\w*|tedavi\w*|ilaç\w*|reçete\w*|aşı\w*|aşılama\w*|doktor\w*|hekim\w*|uzman hekim\w*|hastane\w*|acil servis\w*|poliklinik\w*|mhrs\w*|randevu\w*|beslenme\w*|diyet\w*|diyetisyen\w*|kalori\w*|vitamin\w*|bağışıklık\w*|uyku apnesi\w*|kronik yorgunluk\w*|göz sağlığı\w*|diş sağlığı\w*|cilt sağlığı\w*|sağlık\w*)\b',
        "Ekonomi": r'\b(ekonomi\w*|finans\w*|borsa\w*|bist\w*|hisse\w*|faiz\w*|tcmb\w*|merkez bankası\w*|enflasyon\w*|tüfe\w*|üfe\w*|dolar\w*|euro\w*|döviz\w*|altın\w*|ons altın\w*|gümüş\w*|emtia\w*|petrol\w*|brent\w*|doğalgaz\w*|mevduat\w*|kredi\w*|kredi kartı\w*|asgari ücret\w*|emekli maaşı\w*|emekli zammı\w*|memur zammı\w*|zam\w*|indirim\w*|vergi\w*|kdv\w*|ötv\w*|hazine\w*|bakan şimşek\w*|mehmet şimşek\w*|fed\w*|ecb\w*|ihracat\w*|ithalat\w*|cari açık\w*|resesyon\w*|gss\w*|genel sağlık sigortası\w*|borç\w*|borcu silinecek\w*|warren buffett\w*|yatırım\w*|fon\w*|işçi çıkar\w*)\b',
        "Dünya": r'\b(dünya\w*|bm|birleşmiş milletler\w*|iklim planı\w*|küresel ısınma\w*|körfez ülkeleri\w*|abd\w*|amerika\w*|rusya\w*|ukrayna\w*|çin\w*|almanya\w*|fransa\w*|ingiltere\w*|israil\w*|gazze\w*|filistin\w*|iran\w*|ırak\w*|suriye\w*|lübnan\w*|kktc\w*|kıbrıs\w*|yunanistan\w*|bulgaristan\w*|nato\w*|pentagon\w*|beyaz saray\w*|kremlin\w*|tahran\w*|tel aviv\w*|kudüs\w*|hürmüz\w*|zelenskiy\w*|putin\w*|trump\w*|biden\w*|netanyahu\w*|diplomasi\w*|uluslararası\w*|ateşkes\w*|füze saldırısı\w*|hava saldırısı\w*)\b',
    }

    # Puanlama (Başlık 4 Kat Daha Ağırlıklıdır + Kaynak Kategorisi Koruması)
    scores = {}
    if force_category in regex_map:
        # Kaynağın kendi kategorisine +3 taban puan ver (Özetten gelen tek bir 'dolar/tl' kelimesi Teknoloji/Sağlık/Eğitim haberini bozmasın)
        scores[force_category] = 3

    for cat, reg in regex_map.items():
        title_hits = len(re.findall(reg, lower_title, re.IGNORECASE))
        summary_hits = min(2, len(re.findall(reg, lower_summary, re.IGNORECASE)))
        total = (title_hits * 5) + summary_hits
        if total > 0:
            scores[cat] = scores.get(cat, 0) + total

    if scores:
        best_cat = max(scores.items(), key=lambda x: x[1])[0]
        return best_cat

    # ADIM 3: Besleme kategorisi varsa içerikle çapraz doğrula
    if force_category and force_category in regex_map:
        if force_category == "Ekonomi":
            econ_check = r'(lira|tl|faiz|enflasyon|dolar|euro|altın|borsa|hisse|maaş|zam|vergi|kdv|ötv|banka|kredi|mevduat|ihracat|ithalat|bütçe)'
            if not re.search(econ_check, full_text, re.IGNORECASE):
                if re.search(r'(estetik|ameliyat|bıçak altına|hasta|doktor|tedavi|sağlık)', full_text, re.IGNORECASE):
                    return "Sağlık"
                return "Gündem"
        return force_category

    return "Gündem"

    # ADIM 3: Besleme kategorisi varsa içerikle çapraz doğrula
    if force_category and force_category in regex_map:
        if force_category == "Ekonomi":
            econ_check = r'(lira|tl|faiz|enflasyon|dolar|euro|altın|borsa|hisse|maaş|zam|vergi|kdv|ötv|banka|kredi|mevduat|ihracat|ithalat|bütçe)'
            if not re.search(econ_check, full_text, re.IGNORECASE):
                if re.search(r'(estetik|ameliyat|bıçak altına|hasta|doktor|tedavi|sağlık)', full_text, re.IGNORECASE):
                    return "Sağlık"
                return "Gündem"
        return force_category

    return "Gündem"

def generate_full_article(title: str, summary: str, source: str, force_category: str = None) -> dict:
    """
    Web sitesi için 3-4 paragraflık zenginleştirilmiş, akıcı ve özgün haber makalesi üretir.
    """
    import news_fetcher
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    valid_official_cats = {"Gündem", "Ekonomi", "Eğitim", "Otomobil", "Teknoloji", "Sağlık", "Spor", "Dünya"}
    if force_category in valid_official_cats:
        category = force_category
    else:
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
Sen 'Gündem Analizi' bağımsız haber portalının baş editörüsün.
Aşağıdaki haber için Anadolu Ajansı, Reuters ve BBC Türkçe standartlarında; kapsamlı, doyurucu, derinlemesine açıklayıcı ve akıcı bir Türkçe haber makalesi yaz.

Haber Başlığı: {title}
Haber Detayı ve Gelişmeler: {summary}
Kaynak: {source}
Kategori: {category}
Özel Kategori Odak Noktası: {category_guide}

EDİTORYAL KURALLAR VE YAZIM İLKELERİ:
1. UZUNLUK VE AÇIKLAYICILIK: Haber yüzeysel veya tekdüze kalmamalıdır. Olayın 'Kim, Ne, Nerede, Ne Zaman, Nasıl ve Neden' (5N1K) unsurlarını, sürecin arka planını, tarafların açıklamalarını, somut rakamları ve geleceğe dönük yansımalarını detaylandır.
2. CÜMLE YAPISI VE DİL BİLGİSİ (ÇOK ÖNEMLİ):
   - Metni uzatacağım diye cümleleri yapay şekilde uzatma, devrik veya karmaşık hale getirme!
   - Her cümlenin öznesi, yüklemi ve mantıksal akışı tam, duru ve anlaşılır Türkçe dil bilgisi kurallarına uygun olmalıdır.
   - Uzunluk gereksiz laf kalabalığıyla değil; konunun teknik, hukuki, ekonomik ve insani ayrıntılarını adım adım açıklayarak sağlanmalıdır.
   - Tekrarlardan ve içi boş klişelerden kesinlikle kaçın.
3. KESİNLİKLE YAPILMAYACAKLAR:
   - ASLA 'Siz ne düşünüyorsunuz?', 'Yorumlarda buluşalım' gibi yapay sorular sorma.
   - ASLA hashtag (#haber, #sondakika vb.) kullanma.
   - ASLA SPK / borsa yasal uyarı kalıplarını metne dahil etme.

İSTENEN ÇIKTI FORMATI:
Lütfen yanıtını AYNEN şu iki bölüm halinde ver:

[ÖZET]
Haberin en can alıcı ayrıntılarını, sayılar ve somut bilgilerle özetleyen, 2-3 akıcı ve doyurucu cümleden oluşan editoryal özet.

[İÇERİK]
HTML formatında yazılmış, en az 4-5 doyurucu paragraftan ve ara başlıklardan oluşan tam makale:
<p class="lead font-medium text-lg text-slate-200 mb-6">
[Giriş: Olayın başlangıcını ve ana gelişmeyi tüm boyutlarıyla anlatan güçlü paragraf]
</p>

<h3 class="text-xl font-bold text-white mt-6 mb-3">Gelişmenin Ayrıntıları ve Sürecin İşleyişi</h3>
<p class="text-slate-300 leading-relaxed mb-4">
[Detaylar, yetkililerin/kurumların açıklamaları ve olay anına ilişkin bilgiler]
</p>
<p class="text-slate-300 leading-relaxed mb-4">
[Rakamlar, teknik detaylar, yasal/mali boyut veya olayın geçmişe uzanan arka planı]
</p>

<h3 class="text-xl font-bold text-white mt-6 mb-3">Sektörel ve Toplumsal Yansımaları</h3>
<p class="text-slate-300 leading-relaxed mb-4">
[Gelişmenin vatandaşa, piyasalara veya sektöre etkileri, uzman değerlendirmeleri]
</p>

<div class="p-5 rounded-xl bg-red-950/40 border border-red-800/40 my-6">
    <h4 class="font-bold text-red-400 flex items-center gap-2 mb-2">
        <span>🔴</span> GÜNDEM ANALİZİ DEĞERLENDİRMESİ
    </h4>
    <p class="text-slate-300 text-sm leading-relaxed">
        [Sürecin geleceğine ve olası sonuçlarına dair editoryal tarafsız değerlendirme]
    </p>
</div>
"""
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt
                    )
                    if res and res.text:
                        raw_text = res.text.strip()
                        gen_summary = summary if summary else title
                        gen_content = raw_text
                        if "[İÇERİK]" in raw_text:
                            parts = raw_text.split("[İÇERİK]")
                            extracted_sum = parts[0].replace("[ÖZET]", "").strip()
                            if len(extracted_sum) > 30:
                                gen_summary = extracted_sum
                            gen_content = parts[1].strip()
                        elif "[ÖZET]" in raw_text:
                            gen_content = raw_text.replace("[ÖZET]", "").strip()
                        
                        # Markdown ```html temizliği
                        gen_content = re.sub(r'^```html\s*', '', gen_content, flags=re.I)
                        gen_content = re.sub(r'^```\s*', '', gen_content)
                        gen_content = re.sub(r'\s*```$', '', gen_content)

                        return {
                            "title": title,
                            "summary": gen_summary,
                            "content": gen_content.strip(),
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
