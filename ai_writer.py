import os
import sys

# Windows konsolunda Türkçe ve emoji karakterlerin hatasız yazdırılması için
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config

def generate_social_caption(title: str, summary: str, source: str) -> dict:
    """
    Sosyal medya (Facebook, Instagram, Reels, TikTok) için optimize edilmiş metin ve hashtag üretir.
    Gemini API anahtarı varsa yapay zeka ile yazar, yoksa akıllı formatlama uygular.
    """
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

    # Fallback (Şablon Makale)
    clean_summary = summary.replace("\n", " ").strip() if summary else title
    content_html = f"""
    <p class="lead font-medium text-lg text-slate-300 mb-6">
        {clean_summary}
    </p>
    
    <h3 class="text-xl font-bold text-white mt-6 mb-3">Gelişmenin Ayrıntıları</h3>
    <p class="text-slate-300 leading-relaxed mb-4">
        Türkiye ve dünya gündeminde dikkat çeken <strong>{title}</strong> başlığı altında yeni gelişmeler kaydedildi. 
        Gelen son bilgilere göre, sürecin etkileri kamuoyunda yakından takip ediliyor.
    </p>
    
    <p class="text-slate-300 leading-relaxed mb-6">
        Uzmanlar ve ilgili kurumlar konuya ilişkin değerlendirmelerini sürdürürken, önümüzdeki günlerde sürecin seyrine dair yeni açıklamaların yapılması bekleniyor. 
        Olayla ilgili resmi kanallardan yapılacak bilgilendirmeler kamuoyu ile paylaşılmaya devam edecek.
    </p>

    <div class="p-5 rounded-xl bg-red-950/40 border border-red-800/40 my-6">
        <h4 class="font-bold text-red-400 flex items-center gap-2 mb-2">
            <span>🔴</span> GÜNDEM ANALİZİ DEĞERLENDİRMESİ
        </h4>
        <p class="text-slate-300 text-sm leading-relaxed">
            Bu gelişme, ilgili sektör ve kamuoyu nezdinde önemli yankılar uyandırabilir. Gündem Analizi ekibi olarak sürecin perde arkasını ve olası yansımalarını tarafsız bir bakış açısıyla takip etmeyi sürdüreceğiz.
        </p>
    </div>
    """

    return {
        "title": title,
        "summary": clean_summary[:200],
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
