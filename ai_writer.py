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
    Sosyal medya (Facebook ve Instagram) için optimize edilmiş metin ve hashtag üretir.
    Gemini API anahtarı varsa yapay zeka ile yazar, yoksa şablon tabanlı akıllı formatlama uygular.
    """
    if config.GEMINI_API_KEY:
        try:
            from google import genai
            client = genai.Client(api_key=config.GEMINI_API_KEY)
            
            prompt = f"""
Sen Türkiye gündemini takip eden profesyonel bir sosyal medya içerik yöneticisisin.
Aşağıdaki haber için Instagram ve Facebook'ta yüksek etkileşim alacak Türkçe bir paylaşım metni hazırla.

Haber Başlığı: {title}
Haber Özeti: {summary}
Kaynak: {source}

İstenen Format:
1. Dikkat çekici, merak uyandıran 1-2 cümlelik açılış cümlesi (emoji ile).
2. Haberin en önemli detayını anlatan 1-2 cümlelik özet.
3. Takipçilere yönelik kısa bir soru/etkileşim cümlesi (Örn: "Siz bu konuda ne düşünüyorsunuz? Yorumlarda buluşalım.").
4. Türkiye gündemine ve haber konusuna uygun 4-6 popüler hashtag (#türkiyegündemi, #sondakika vb.).

Lütfen sadece doğrudan paylaşılacak nihai metni yaz, fazladan açıklama veya başlık koyma.
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if response and response.text:
                return {
                    "caption": response.text.strip(),
                    "source_used": "Gemini AI"
                }
        except Exception as e:
            print(f"Gemini API çağrısı başarısız, şablon fallback kullanılıyor: {e}")

    # Fallback (API anahtarı girilmediğinde veya hata olduğunda çalışan şablon)
    clean_summary = summary.replace("\n", " ").strip()
    if len(clean_summary) > 220:
        clean_summary = clean_summary[:217] + "..."

    caption_text = f"""📢 {title}

📰 {clean_summary if clean_summary else title}

📌 Gelişmeleri ve son dakika haberlerini kaçırmamak için takipte kalın!
💬 Sizce bu durum nasıl sonuçlanır? Görüşlerinizi yorumlarda paylaşın!

Kaynak: {source}
---
#türkiyegündemi #sondakika #haber #gündem #türkiye #haberler"""

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
            res = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if res and res.text:
                return {
                    "title": title,
                    "summary": summary[:200] if summary else title,
                    "content": res.text.strip(),
                    "category": category
                }
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
