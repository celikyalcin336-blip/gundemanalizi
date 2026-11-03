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
            from google.genai import types as genai_types
            client = genai.Client(
                api_key=config.GEMINI_API_KEY,
                http_options=genai_types.HttpOptions(timeout=25000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
            )
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
            for m_name in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
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
            from google.genai import types as genai_types
            client = genai.Client(
                api_key=config.GEMINI_API_KEY,
                http_options=genai_types.HttpOptions(timeout=25000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
            )
            
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
            for m_name in ["gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]:
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
        # X Premium (Mavi Tik) desteği: Cümleyi asla yarıda kesme, tam cümlelerle aktar
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

    # 3. DOĞAL AFET / DEPREM / YANGIN / ŞANS OYUNLARI (KESİNLİKLE GÜNDEM)
    disaster_regex = r'\b(kandilli\w*|afad\w*|deprem\w*|sarsıntı\w*|artçı sarsıntı\w*|fay hattı\w*|tsunami\w*|heyelan\w*|yangın söndürme\w*|sayısal loto\w*|süper loto\w*|şans topu\w*|on numara\w*|milli piyango\w*|çekiliş sonuç\w*)\b'
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

    if not config.GEMINI_API_KEY:
        print("❌ [Makale] GEMINI_API_KEY tanımlı değil. Kopya/şablon metin yayınlanmaz; haber atlandı.")
        return None

    source_text = (summary or "").strip()
    if len(source_text.split()) < 28:
        print(f"⏩ [Makale] Kaynak metin çok kısa ({len(source_text.split())} kelime); özgün ve doyurucu haber yazılamaz, atlandı.")
        return None

    prompt = f"""
Sen 'Gündem Analizi' adlı Türkçe haber sitesinin kıdemli editörüsün. Aşağıdaki kaynak haberden yola çıkarak
okura gerçekten değer katan, ÖZGÜN cümlelerle yazılmış, kapsamlı bir haber-analiz metni hazırla.

Haber Başlığı: {title}
Kategori: {category}
Kategori Odağı: {category_guide}
Kaynak Kuruluş: {source}
Kaynak Metin:
\"\"\"{source_text[:6000]}\"\"\"

KESİN KURALLAR:
1. ÖZGÜNLÜK: Kaynak metinden cümle KOPYALAMA. Tüm bilgiyi kendi cümlelerinle, farklı bir kurgu ve akışla yeniden anlat.
2. DOĞRULUK: Kaynakta OLMAYAN rakam, isim, tarih, alıntı veya iddia UYDURMA. Arka plan ve bağlam bölümünde yalnızca
   genel kabul görmüş, doğrulanabilir bilgiler ver; emin olmadığın hiçbir bilgiyi yazma.
3. UZUNLUK: Metin en az 450, ideal olarak 500-700 kelime olmalı. Uzunluğu laf kalabalığıyla değil; bağlam, arka plan,
   etkiler ve okurun bilmesi gerekenlerle sağla.
4. DİL: Sade, akıcı, dil bilgisi kurallarına uygun Türkçe. Klişe, abartı, tık tuzağı, hashtag, emoji ve okura soru sorma YOK.
5. Her habere uyan genel geçer dolgu cümleleri ("gelişmeler yakından takip ediliyor", "kamuoyunun gündeminde" vb.) YAZMA.
6. Yatırım tavsiyesi verme; sağlık konularında teşhis/tedavi önerme, uzman görüşüne yönlendir.

ÇIKTI BİÇİMİ (aynen bu üç bölüm):
[BAŞLIK]
Kaynak başlıkla kelimesi kelimesine aynı OLMAYAN, olayın gerçekliğini ve anlamını %100 koruyan, tık tuzağı içermeyen, 6-12 kelimelik tamamen özgün ve güçlü Türkçe haber başlığı.

[ÖZET]
Haberin özünü somut bilgilerle anlatan 2-3 cümlelik özgün özet.

[İÇERİK]
Sadece aşağıdaki HTML etiketlerini kullan ve HER ARA BAŞLIĞIN ALTINA EN AZ 2 DOLU PARAGRAF (her paragraf 4-5 cümle) yazarak toplamda EN AZ 450-600 KELİME üret:
<p class="lead font-medium text-lg text-slate-200 mb-6">Haberin ana gelişmesini tüm temel unsurlarıyla (ne, nerede, ne zaman, kim, neden) anlatan kapsamlı giriş paragrafı (4-5 cümle)</p>
<h3 class="text-xl font-bold text-white mt-6 mb-3">Neler Oldu?</h3>
<p class="text-slate-300 leading-relaxed mb-4">Olayın gelişimini ve kaynaktaki tüm somut ayrıntıları aktaran birinci paragraf (4-5 cümle).</p>
<p class="text-slate-300 leading-relaxed mb-4">Tarafların açıklamalarını, teknik veya hukuki detayları ve sahadaki durumu aktaran ikinci paragraf (4-5 cümle).</p>
<h3 class="text-xl font-bold text-white mt-6 mb-3">Arka Plan ve Sürecin Geçmişi</h3>
<p class="text-slate-300 leading-relaxed mb-4">Bu gelişmeye zemin hazırlayan önceki olayları ve konunun tarihsel/sektörel bağlamını anlatan birinci paragraf (4-5 cümle).</p>
<p class="text-slate-300 leading-relaxed mb-4">Konuyla ilgili mevcut kuralları, standartları veya daha önce atılan adımları açıklayan ikinci paragraf (4-5 cümle).</p>
<h3 class="text-xl font-bold text-white mt-6 mb-3">Neden Önemli ve Etkileri Neler?</h3>
<p class="text-slate-300 leading-relaxed mb-4">Gelişmenin vatandaşlar, ekonomi, ilgili sektör veya uluslararası dengeler açısından neden kritik olduğunu açıklayan birinci paragraf (4-5 cümle).</p>
<p class="text-slate-300 leading-relaxed mb-4">Kısa ve orta vadede günlük hayata, piyasaya veya kurumlara yansımalarını somut çerçevede değerlendiren ikinci paragraf (4-5 cümle).</p>
<h3 class="text-xl font-bold text-white mt-6 mb-3">Bundan Sonra Ne Bekleniyor?</h3>
<p class="text-slate-300 leading-relaxed mb-4">Takvimde öne çıkan kritik tarihleri, resmi süreçleri ve beklenen somut adımları anlatan kapanış paragrafı (4-5 cümle).</p>
<h3 class="text-xl font-bold text-white mt-6 mb-3">Haberin Konusuna Özgü Değerlendirme Başlığı</h3>
<p class="text-slate-300 leading-relaxed mb-4">Editoryal değerlendirme (3-4 cümle): Bu gelişmenin sektöre, topluma, piyasaya veya günlük hayata somut yansıması nedir? Kaynakta olmayan rakam veya iddia UYDURMA. Genel geçer cümle kurma ve son cümlede ASLA "en doğru yaklaşım olacaktır", "en doğru korunma yöntemidir" gibi kalıp ifadeler kullanma; doğrudan bu habere özgü, doğal bir gazetecilik cümlesiyle bitir.</p>
Tüm ara başlıkları (son bölüm dahil) haberin konusuna göre tamamen özgün ve doğal gazetecilik diliyle yaz; hiçbir haberde sabit/şablon başlık kullanma. Başka etiket, markdown veya kod bloğu kullanma.
"""

    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=genai_types.HttpOptions(timeout=40000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
        )
    except Exception as e:
        print(f"❌ [Makale] Gemini istemcisi başlatılamadı: {e}")
        return None

    import content_quality
    # Bir model yoğun/kotası dolu olursa sıradakine geçilir (ücretsiz kotalar model bazında ayrıdır)
    model_chain = [m.strip() for m in os.getenv(
        "GEMINI_ARTICLE_MODELS",
        "gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-flash-latest,gemini-3.8-flash"
    ).split(",") if m.strip()]
    for m_name in model_chain:
        try:
            res = client.models.generate_content(model=m_name, contents=prompt)
            raw_text = (res.text or "").strip() if res else ""
            if not raw_text or "[İÇERİK]" not in raw_text:
                print(f"⚠️ [Makale] {m_name} beklenen biçimde yanıt vermedi.")
                continue
            head_and_sum, content_part = raw_text.split("[İÇERİK]", 1)
            gen_title = title
            if "[ÖZET]" in head_and_sum:
                t_part, s_part = head_and_sum.split("[ÖZET]", 1)
                cand_title = t_part.replace("[BAŞLIK]", "").strip().strip('"#* \'')
                cand_title = content_quality.fix_brand_splits(re.sub(r'\s+', ' ', cand_title))
                cand_title = cand_title.splitlines()[0].strip()
                if 15 <= len(cand_title) <= 130:
                    gen_title = cand_title
                gen_summary = s_part.strip()
            else:
                gen_summary = head_and_sum.replace("[BAŞLIK]", "").strip()
            gen_content = content_part.strip()
            gen_content = re.sub(r'^```(?:html)?\s*', '', gen_content, flags=re.I)
            gen_content = re.sub(r'\s*```$', '', gen_content).strip()
            gen_content = content_quality.fix_brand_splits(gen_content)

            words = content_quality.visible_word_count(gen_content)
            if words < 350:
                print(f"⚠️ [Makale] {m_name} metni kısa kaldı ({words} kelime), tekrar deneniyor.")
                continue
            if len(gen_summary) < 40:
                gen_summary = content_quality._norm(gen_content).split(". ")[0][:300]
            print(f"✅ [Makale] {m_name} ile {words} kelimelik özgün haber yazıldı. Başlık: {gen_title}")
            return {
                "title": gen_title,
                "summary": gen_summary,
                "content": gen_content,
                "category": category,
            }
        except Exception as e:
            print(f"⚠️ [Makale] {m_name} hatası: {str(e)[:200]}")
            continue

    print("❌ [Makale] Yapay zeka kaliteli metin üretemedi. Kopya/şablon metin yayınlanmaz; haber atlandı.")
    return None

if __name__ == "__main__":
    sample = generate_social_caption(
        "Yeni Karar Resmi Gazete'de Yayımlandı",
        "Merkez Bankası ve Hazine koordinasyonunda yeni finansal düzenlemeler yürürlüğe girdi.",
        "NTV Haber"
    )
    print("Üretilen Metin:")
    print(sample["caption"])
