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
    Sosyal medya (Facebook, Instagram, Reels, TikTok) için optimize edilmiş metin ve hashtag üretir.
    Gemini API anahtarı varsa yapay zeka ile yazar, yoksa akıllı formatlama uygular.
    """
    import news_fetcher
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            
            prompt = f"""
Sen Türkiye gündemini yakından takip eden profesyonel bir sosyal medya içerik yöneticisisin.
Aşağıdaki haber için Instagram (Reels) ve Facebook'ta yüksek organik erişim ve etkileşim alacak Türkçe bir paylaşım metni hazırla.

Haber Başlığı: {title}
Haber Detayı: {summary}

UYULMASI ZORUNLU KURALLAR:
1. Haberin en can alıcı noktasını tek ve akıcı bir ana paragrafta anlat. Başlığı veya aynı cümleyi ASLA iki kez tekrar etme.
2. Metnin içine ASLA "Kaynak: ..." yazma (kaynak sistem tarafından otomatik ve tek seferlik eklenecektir).
3. Metnin içine ASLA dış web linki veya URL yazma.
4. Metnin sonuna takipçileri yorum yapmaya teşvik eden merak uyandırıcı tek bir soru cümlesi ekle (Örn: "Siz bu konuda ne düşünüyorsunuz? Yorumlarda buluşalım.").
5. En alta haber konusuna uygun 4-5 popüler Türkçe hashtag ekle (#sondakika #haber #gündem vb.).
6. Sadece doğrudan paylaşılacak nihai metni yaz, fazladan selamlama veya açıklama koyma.
"""
            # Model denemesi (önce 2.5-flash, sonra 2.0-flash, sonra 1.5-flash)
            for m_name in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    response = client.models.generate_content(
                        model=m_name,
                        contents=prompt
                    )
                    if response and response.text:
                        return {
                            "caption": response.text.strip(),
                            "source_used": f"Gemini AI ({m_name})"
                        }
                except Exception:
                    continue
        except Exception as e:
            print(f"Gemini API çağrısı başarısız, şablon fallback kullanılıyor: {e}")

    # Fallback (API anahtarı girilmediğinde veya kota aşıldığında çalışan akıllı şablon)
    clean_summary = summary.replace("\n", " ").strip() if summary else ""
    # Başlık ile özet aynıysa veya özet boşsa tekrarlama yapma
    if clean_summary and clean_summary.lower() != title.strip().lower():
        if len(clean_summary) > 220:
            clean_summary = clean_summary[:217] + "..."
        body = f"📢 {title}\n\n📰 {clean_summary}"
    else:
        body = f"📢 {title}"

    caption_text = f"""{body}

💬 Siz bu konuda ne düşünüyorsunuz? Görüşlerinizi yorumlarda paylaşın!

#sondakika #haber #gündem #türkiye #gündemanalizi"""

    return {
        "caption": caption_text,
        "source_used": "Template"
    }

def generate_full_article(title: str, summary: str, source: str) -> dict:
    """
    Web sitesi için 3-4 paragraflık zenginleştirilmiş, akıcı ve özgün haber makalesi üretir.
    """
    import news_fetcher
    title = news_fetcher.sanitize_news_text(html.unescape(html.unescape(title.strip())))
    summary = news_fetcher.sanitize_news_text(html.unescape(html.unescape(summary.strip()))) if summary else ""

    category = "Gündem"
    lower_title = title.lower()
    if any(k in lower_title for k in ["faiz", "enflasyon", "borsa", "dolar", "bakan şimşek", "ekonomi", "zam", "vergi"]):
        category = "Ekonomi"
    elif any(k in lower_title for k in ["savaş", "abd", "rusya", "israil", "avrupa", "gazze", "iran", "dünya"]):
        category = "Dünya"
    elif any(k in lower_title for k in ["maç", "futbol", "fenerbahçe", "galatasaray", "beşiktaş", "şampiyon"]):
        category = "Spor"

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
                            "summary": summary[:200] if summary else title,
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
        "summary": lead_para[:200],
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
