import os
import sys
import html

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
    raw_sentences = [s.strip() for s in re.split(r'(?<=[!?:])\s+|(?<=[0-9a-zA-ZçğıöşüÇĞİÖŞÜ]{3}\.)\s+(?=[A-ZÇĞİÖŞÜ0-9])', clean_summary) if len(s.strip()) > 25]

    filtered_sentences = []
    for s in raw_sentences:
        if s.lower() == headline.lower():
            continue
        if any(b in s.lower() for b in ["tıklayınız", "tıklayın", "abone olun", "ayrıntılar geliyor", "fotoğraf:", "iha", "aa", "dha"]):
            continue
        filtered_sentences.append(s)

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

def generate_full_article(title: str, summary: str, source: str, force_category: str = None) -> dict:
    """
    Web sitesi için 3-4 paragraflık zenginleştirilmiş, akıcı ve özgün haber makalesi üretir.
    """
    import news_fetcher
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    lower_all = f"{title} {summary}".lower()
    if force_category and force_category in ["Otomobil", "Teknoloji", "Ekonomi", "Eğitim", "Sağlık", "Dünya", "Spor", "Gündem"]:
        category = force_category
    elif any(k in lower_all for k in ["öğrenci", "okul", "meb", "öğretmen", "üniversite", "ösym", "yks", "lgs", "kpss", "burs", "tatil", "sınav", "eğitim", "müfredat"]):
        category = "Eğitim"
    elif any(k in lower_all for k in ["otomobil", "araba", "sıfır araç", "fiyat listesi", "kampanya", "togg", "t10x", "egea", "doblo", "clio", "ötv", "faizsiz", "taşıt kredisi", "elektrikli araç", "hyundai", "toyota", "volkswagen", "chery", "byd", "renault", "fiat", "peugeot", "skoda"]):
        category = "Otomobil"
    elif any(k in lower_all for k in ["yapay zeka", "chatgpt", "openai", "gemini", "claude", "anthropic", "midjourney", "sora", "deepseek", "nemotron", "llm", "ai model", "yapay zekâ", "iphone", "apple", "samsung", "galaxy", "android", "telefon", "nvidia", "işlemci", "akıllı telefon", "ios", "yazılım", "donanım"]):
        category = "Teknoloji"
    elif any(k in lower_all for k in ["sağlık", "hastane", "grip", "aşı", "beslenme", "diyet", "kolesterol", "tansiyon", "kanser", "tedavi", "ilaç", "check-up", "kalp sağlığı", "doktor", "mhrs", "sağlık bakanlığı"]):
        category = "Sağlık"
    elif any(k in lower_all for k in ["faiz", "enflasyon", "borsa", "dolar", "euro", "bakan şimşek", "ekonomi", "zam", "vergi", "mevduat", "asgari ücret", "emekli", "promosyon", "altın", "akaryakıt", "benzin"]):
        category = "Ekonomi"
    elif any(k in lower_all for k in ["maç", "futbol", "fenerbahçe", "galatasaray", "beşiktaş", "şampiyon", "süper lig", "uefa", "transfer"]):
        category = "Spor"
    elif any(k in lower_all for k in ["savaş", "abd", "rusya", "israil", "avrupa", "gazze", "iran", "dünya", "nato", "ukrayna", "çin"]):
        category = "Dünya"
    else:
        category = "Gündem"

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
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw_clean) if len(s.strip()) > 20]
    
    # Başlıkla aynı olan veya çöp soru olan cümleleri filtrele
    filtered = []
    for s in sentences:
        if s.lower() == title.lower() or title.lower() in s.lower():
            continue
        if s.endswith('?') and len(s) < 55:
            continue
        filtered.append(s)

    if filtered:
        lead_para = filtered[0]
        remaining = filtered[1:]
    else:
        lead_para = raw_clean if raw_clean else title
        remaining = []

    body_paras_list = []
    if remaining:
        # Kalan cümleleri 2'şerli paragraflara grupla
        chunk1 = " ".join(remaining[:2])
        body_paras_list.append(f'<p class="text-slate-300 leading-relaxed mb-4">{chunk1}</p>')
        if len(remaining) > 2:
            chunk2 = " ".join(remaining[2:5])
            body_paras_list.append(f'<p class="text-slate-300 leading-relaxed mb-4">{chunk2}</p>')
    else:
        # Tek cümlelik haberlerde ASLA girişi tekrar etme; kategoriye özel editoryal arka plan ekle
        if category == "Ekonomi":
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Piyasalarda ve ekonomi çevrelerinde yankı uyandıran gelişmeyle ilgili olarak uzmanlar, mali dengeler ve tüketici üzerindeki yansımaların önümüzdeki günlerde netleşeceğini belirtiyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Sektör temsilcileri ve ilgili finans kurumlarının alacağı yeni kararlar yakından takip edilirken, sürecin piyasa dinamiklerine etkisi ekonomi masamız tarafından izlenmektedir.</p>')
        elif category == "Eğitim":
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Öğrencileri, öğretmenleri ve velileri yakından ilgilendiren bu gelişmeyle ilgili Milli Eğitim Bakanlığı (MEB) ve ilgili resmi kurumların açıklamaları takip ediliyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Sınav takvimleri, başvuru şartları ve eğitim süreçlerine dair resmi duyurular anlık olarak eğitim servisimiz tarafından aktarılacaktır.</p>')
        elif category == "Spor":
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Spor camiasında geniş yankı uyandıran gelişmeyle ilgili taraflardan gelecek yeni açıklamalar merakla beklenirken, teknik heyet ve yönetimin atacağı adımlar takip ediliyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Gelişmenin ligdeki dengelere ve takımın önümüzdeki fikstürüne olası etkileri spor masamız tarafından aktarılmaya devam edecektir.</p>')
        elif category == "Dünya":
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Bölgesel ve uluslararası dengeleri yakından ilgilendiren olay sonrasında ilgili ülkelerin diplomatik temasları hız kazandı.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Uluslararası gözlemciler ve diplomasi çevreleri sürecin seyrine ilişkin değerlendirmelerini sürdürürken, gelişmeler anlık olarak takip edilmektedir.</p>')
        else:
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Gelişmeyle ilgili resmi makamlar ve yetkili mercilerden gelecek yeni bilgilendirmeler beklenirken, kamuoyundaki yansımalar dikkatle takip ediliyor.</p>')
            body_paras_list.append('<p class="text-slate-300 leading-relaxed mb-4">Sürecin detayları ve yaşanacak yeni gelişmeler anbean okuyucularımızla paylaşılmaya devam edecektir.</p>')

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
