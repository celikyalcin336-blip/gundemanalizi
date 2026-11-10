# -*- coding: utf-8 -*-
"""
Çok Kaynaklı Haber & Analiz Motoru (Gündem Analizi)

Aynı olayı anlatan 2-4 farklı kaynağın haberlerini birleştirerek
"Ne oldu / Neden önemli / Arka plan / Türkiye'ye etkisi / Kaynaklar ne diyor /
Rakamlarla / Bundan sonra" yapısında özgün bir haber-analiz metni üretir.

- Model: yalnızca Gemini 3.5 ailesi (gemini-3.5-flash, yedek: gemini-3.5-flash-lite)
- Başarısız olursa None döner; çağıran taraf mevcut (eski) yazım akışına geri düşer,
  böylece bot hiçbir koşulda durmaz.
"""
import html as _html
import json
import os
import re
import time
from typing import Dict, List, Optional

import config

MODELS = [m.strip() for m in os.getenv("GEMINI_MULTI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite").split(",") if m.strip()]

_STOP = set(
    "ve ile için bir bu şu da de mi mu mü ne çok daha en son yeni olarak olan oldu olduğu gibi kadar sonra önce göre "
    "ise ama hem değil var yok ilk iki üç tüm her nasıl neden haber haberi açıklama açıkladı dedi büyük önemli flaş "
    "son dakika bugün yarın dün kasım ekim aralık ocak 2025 2026 2027".split()
)


def _tokens(text: str) -> set:
    t = (text or "").replace("İ", "i").replace("I", "ı").lower()
    return {w for w in re.findall(r"[a-zçğıöşü0-9]{4,}", t) if w not in _STOP}


def _clean_src_name(name: str) -> str:
    try:
        import content_quality
        return content_quality.clean_source_name(name)
    except Exception:
        return (name or "").strip()


def find_siblings(primary: Dict, pool: List[Dict], max_n: int = 3) -> List[Dict]:
    """
    Havuzdan aynı olayı anlatan, FARKLI kaynaklardan en fazla max_n haber bulur.
    Kural sıkı tutulmuştur (farklı konuları birleştirmemek için):
      - en az 4 ortak anlamlı kelime ve kısa başlığa göre >= %50 örtüşme, veya
      - en az 3 ortak kelime ve >= %65 örtüşme
      - kategori biliniyorsa aynı kategori
    """
    p_tok = _tokens(primary.get("title", ""))
    if len(p_tok) < 3:
        return []
    p_src = _clean_src_name(primary.get("source", ""))
    p_cat = primary.get("category")
    scored = []
    seen_src = {p_src}
    for it in pool or []:
        if it is primary or it.get("link") == primary.get("link"):
            continue
        src = _clean_src_name(it.get("source", ""))
        if not src or src in seen_src:
            continue
        if p_cat and it.get("category") and it.get("category") != p_cat:
            continue
        b_tok = _tokens(it.get("title", ""))
        if len(b_tok) < 3:
            continue
        inter = len(p_tok & b_tok)
        ratio = inter / max(1, min(len(p_tok), len(b_tok)))
        if (inter >= 4 and ratio >= 0.5) or (inter >= 3 and ratio >= 0.65):
            scored.append((inter + ratio, src, it))
    scored.sort(key=lambda x: -x[0])
    out = []
    for _, src, it in scored:
        if src in seen_src:
            continue
        seen_src.add(src)
        out.append(it)
        if len(out) >= max_n:
            break
    return out


def gather_sources(primary: Dict, primary_body: str, pool: List[Dict], max_siblings: int = 3) -> List[Dict]:
    """Birincil haber + kardeş haberlerin tam metinlerini toplar."""
    sources = [{
        "name": _clean_src_name(primary.get("source", "")),
        "link": primary.get("link", ""),
        "title": primary.get("title", ""),
        "body": (primary_body or primary.get("summary") or "")[:3500],
    }]
    try:
        import news_fetcher
    except Exception:
        news_fetcher = None
    for sib in find_siblings(primary, pool, max_n=max_siblings):
        body = ""
        if news_fetcher is not None:
            try:
                body = (news_fetcher.fetch_article_details(sib.get("link", "")) or {}).get("body", "") or ""
            except Exception:
                body = ""
        body = body if len(body) > len(sib.get("summary") or "") else (sib.get("summary") or "")
        if len(body.split()) < 25:
            continue
        sources.append({
            "name": _clean_src_name(sib.get("source", "")),
            "link": sib.get("link", ""),
            "title": sib.get("title", ""),
            "body": body[:3000],
            "_raw_item": sib,
        })
    return sources


_CAT_FOCUS = {
    "Ekonomi": "Rakamların vatandaşın bütçesine, maaşına, kredi/mevduat koşullarına ve alım gücüne somut etkisini açıkla. Yatırım tavsiyesi verme.",
    "Sağlık": "Uzman uyarılarını ve dikkat edilmesi gerekenleri sade anlat. Teşhis veya tedavi önerme; okuru hekime yönlendir.",
    "Eğitim": "Resmi takvimi, başvuru/sınav şartlarını ve öğrenci-veli açısından atılacak adımları net aktar.",
    "Spor": "Gelişmenin puan durumu, fikstür ve takımın sezon hedeflerine etkisini spor gazeteciliği diliyle anlat.",
    "Teknoloji": "Teknolojinin öne çıkan özelliklerini, rakiplerden farkını ve kullanıcıya somut karşılığını anlat.",
    "Otomobil": "Aracın segmentteki konumunu, Türkiye pazarı ve ÖTV/fiyat açısından yansımalarını anlat.",
    "Dünya": "Gelişmenin bölgesel dengeler ve Türkiye açısından olası yansımalarını abartmadan anlat.",
}


def _build_prompt(sources: List[Dict], category: str, mode: str) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(f"[{i}] KAYNAK: {s['name']}\nBaşlık: {s['title']}\nMetin: {s['body']}")
    focus = _CAT_FOCUS.get(category, "Resmi açıklamaları, sahadaki durumu ve kamuoyunu ilgilendiren yönlerini net bir gazetecilik diliyle aktar.")
    if mode == "analysis":
        length_rule = "Toplam metin EN AZ 650, ideal 750-900 kelime olsun. Bu bir GÜNLÜK ANALİZ yazısıdır: neden-sonuç ilişkisini ve olası senaryoları derinlemesine incele."
        extra_field = '"senaryolar": ["olası gelişme 1 (1-2 cümle)", "olası gelişme 2", "olası gelişme 3"],'
    else:
        length_rule = "Toplam metin EN AZ 420, ideal 500-650 kelime olsun."
        extra_field = ""
    multi_rule = (
        f"Aşağıda AYNI olayı anlatan {len(sources)} farklı kaynağın haberleri var. Bunları BİRLEŞTİR; hiçbir kaynağı tek başına yeniden yazma."
        if len(sources) > 1 else
        "Aşağıda bu olayı anlatan kaynak haber var. Haberi tekrar etmekle yetinme; bağlam, önem ve etki boyutunu ekle."
    )
    return f"""Sen Türkçe haber ve analiz sitesi 'Gündem Analizi'nin kıdemli editörüsün.
{multi_rule}
Kategori: {category}. Kategori odağı: {focus}

KESİN KURALLAR:
1. DOĞRULUK: SADECE kaynaklarda geçen bilgi, isim, tarih ve rakamları kullan. Kaynakta olmayan rakam, alıntı veya iddia UYDURMA.
   "Arka plan" bölümünde yalnızca kaynaklarda geçen ya da genel kabul görmüş, doğrulanabilir bilgileri yaz; emin değilsen yazma.
2. ÖZGÜNLÜK: Kaynak cümlelerini kopyalama; tamamen kendi cümlelerinle yaz.
3. {length_rule}
4. DİL VE TÜRKÇE İMLA: Sade, akıcı, tarafsız Türkçe. Başlık dahil TÜM alanlarda Türkçe karakterleri (ç, ğ, ı, İ, ö, ş, ü) eksiksiz ve doğru kullan; kesinlikle İngilizce/ASCII harflerle ("Basciligi", "Olum", "Kasif" gibi) yazma. Kelime kök ve eklerini Türk Dil Kurumu yazım kurallarına uygun, hatasız kur. Tık tuzağı, ünlem (!), üç nokta (...), emoji, hashtag YOK.
   "Sonuç olarak", "Özetle", "merakla bekleniyor", "yakından takip ediliyor", "büyük önem taşımaktadır" gibi klişeleri KULLANMA.
5. BAŞLIK: 7-13 kelime, kaynak başlıkların hiçbiriyle birebir aynı olmayan, Türkçe harfleri eksiksiz ve olayın anlamını koruyan özgün başlık.
6. "kaynaklar": her kaynağın olayı HANGİ AÇIDAN verdiğini ya da diğerlerinden farkını 1 cümleyle yaz. Kaynak adını aynen kullan.
7. "rakamlar": yalnızca kaynaklarda geçen somut sayısal veriler (en fazla 6 satır). Sayısal veri yoksa boş liste ver.
8. "turkiye_etkisi": olay Türkiye'yi doğrudan ilgilendiriyorsa vatandaşa etkisini, değilse Türkiye açısından olası yansımasını yaz.
   Bağlantı zayıfsa bunu açıkça belirt, abartma.

Yanıtı SADECE geçerli JSON olarak ver:
{{
 "baslik": "...",
 "ozet": "2 cümlelik özet (meta açıklama olarak kullanılacak)",
 "maddeler": ["30 saniyede özet maddesi 1", "madde 2", "madde 3"],
 "ne_oldu": ["paragraf 1", "paragraf 2"],
 "neden_onemli": ["paragraf"],
 "arka_plan": ["paragraf"],
 "turkiye_etkisi": "paragraf",
 {extra_field}
 "kaynaklar": [{{"kaynak": "Kaynak adı", "aci": "1 cümle"}}],
 "rakamlar": [{{"etiket": "...", "deger": "..."}}],
 "sonra": "Bundan sonra ne izlenmeli: 1 paragraf (somut tarih/süreç varsa onu yaz)"
}}

KAYNAKLAR:
""" + "\n\n".join(blocks)


def _json_schema(mode: str) -> Dict:
    props = {
        "baslik": {"type": "STRING"},
        "ozet": {"type": "STRING"},
        "maddeler": {"type": "ARRAY", "items": {"type": "STRING"}},
        "ne_oldu": {"type": "ARRAY", "items": {"type": "STRING"}},
        "neden_onemli": {"type": "ARRAY", "items": {"type": "STRING"}},
        "arka_plan": {"type": "ARRAY", "items": {"type": "STRING"}},
        "turkiye_etkisi": {"type": "STRING"},
        "kaynaklar": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"kaynak": {"type": "STRING"}, "aci": {"type": "STRING"}},
                "required": ["kaynak", "aci"],
            },
        },
        "rakamlar": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"etiket": {"type": "STRING"}, "deger": {"type": "STRING"}},
                "required": ["etiket", "deger"],
            },
        },
        "sonra": {"type": "STRING"},
    }
    req = ["baslik", "ozet", "maddeler", "ne_oldu", "neden_onemli", "arka_plan", "turkiye_etkisi", "kaynaklar", "rakamlar", "sonra"]
    if mode == "analysis":
        props["senaryolar"] = {"type": "ARRAY", "items": {"type": "STRING"}}
        req.append("senaryolar")
    return {"type": "OBJECT", "properties": props, "required": req}


def _parse_json_safe(raw: str) -> Optional[Dict]:
    if not raw:
        return None
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        s = s[start:end + 1]
    try:
        return json.loads(s)
    except Exception:
        s_fixed = re.sub(r",\s*([}\]])", r"\1", s)
        return json.loads(s_fixed)


def generate(sources: List[Dict], category: str = "Gündem", mode: str = "news") -> Optional[Dict]:
    if not sources or not getattr(config, "GEMINI_API_KEY", ""):
        return None
    try:
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=genai_types.HttpOptions(timeout=90000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
        )
    except Exception as e:
        print(f"⚠️ [Çok Kaynaklı] Gemini istemcisi başlatılamadı: {e}")
        return None
    prompt = _build_prompt(sources, category, mode)
    schema = _json_schema(mode)
    src_has_tr = bool(re.search(r"[çğıöşüÇĞİÖŞÜ]", " ".join(s.get("title", "") for s in sources)))
    # Anlık yoğunluk dalgalarına (503/429) karşı her modeli kademeli bekleme ile 2 kez dene
    attempt_chain = []
    for m_name in MODELS:
        attempt_chain.append(m_name)
        attempt_chain.append(m_name)

    for step_i, m_name in enumerate(attempt_chain):
        try:
            res = client.models.generate_content(
                model=m_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            raw = (res.text or "").strip() if res else ""
            data = _parse_json_safe(raw)
            if not isinstance(data, dict) or not data.get("baslik") or not data.get("ne_oldu"):
                print(f"⚠️ [Çok Kaynaklı] {m_name} eksik yanıt verdi.")
                continue
            cand_title = str(data.get("baslik") or "").strip()
            if src_has_tr and len(cand_title) > 20 and not re.search(r"[çğıöşüÇĞİÖŞÜ]", cand_title):
                print(f"⚠️ [Çok Kaynaklı] {m_name} başlıkta Türkçe karakter kullanmadı, yeniden deneniyor: {cand_title[:60]}")
                continue
            data["_model"] = m_name
            return data
        except Exception as e:
            err_s = str(e)
            print(f"⚠️ [Çok Kaynaklı] {m_name} hatası: {err_s[:160]}")
            if step_i < len(attempt_chain) - 1 and ("503" in err_s or "429" in err_s or "UNAVAILABLE" in err_s):
                time.sleep(3.5 + step_i * 1.5)
            continue
    return None


def _as_list(v) -> List[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [p.strip() for p in re.split(r"\n\s*\n", v) if p.strip()]
    return []


def _e(s) -> str:
    return _html.escape(str(s or "").strip(), quote=True)


def render_html(data: Dict, sources: List[Dict], mode: str = "news") -> str:
    """JSON çıktısını sitenin şablonuna uygun, temiz HTML gövdesine çevirir."""
    parts = ['<div class="ga-multi">']

    bullets = _as_list(data.get("maddeler"))[:4]
    if bullets:
        parts.append('<div class="ga-box ga-tldr"><h4 class="ga-box-title">⚡ 30 Saniyede Özet</h4><ul>'
                     + "".join(f"<li>{_e(b)}</li>" for b in bullets) + "</ul></div>")

    def section(title: str, paras: List[str]):
        if paras:
            parts.append(f'<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">{_e(title)}</h3>')
            for p in paras:
                parts.append(f'<p class="text-slate-800 leading-relaxed mb-4">{_e(p)}</p>')

    section("Ne Oldu?", _as_list(data.get("ne_oldu")))
    section("Neden Önemli?", _as_list(data.get("neden_onemli")))
    section("Arka Plan ve Önceki Gelişmeler", _as_list(data.get("arka_plan")))

    tr = " ".join(_as_list(data.get("turkiye_etkisi")))
    if tr:
        parts.append(f'<div class="ga-box ga-tr"><h4 class="ga-box-title">🇹🇷 Türkiye\'ye Etkisi</h4><p>{_e(tr)}</p></div>')

    if mode == "analysis":
        scen = _as_list(data.get("senaryolar"))[:4]
        if scen:
            parts.append('<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Olası Senaryolar</h3><ol class="ga-list">'
                         + "".join(f"<li>{_e(s)}</li>" for s in scen) + "</ol>")

    # Kaynaklar ne diyor? (her kaynağa bağlantı)
    link_by_name = {}
    for s in sources:
        link_by_name.setdefault((s.get("name") or "").strip().lower(), s.get("link") or "")
    rows = []
    for k in (data.get("kaynaklar") or []):
        if not isinstance(k, dict):
            continue
        name = (k.get("kaynak") or "").strip()
        aci = (k.get("aci") or "").strip()
        if not name or not aci:
            continue
        link = link_by_name.get(name.lower(), "")
        if not link:
            for kname, kl in link_by_name.items():
                if kname and (kname in name.lower() or name.lower() in kname):
                    link = kl
                    break
        a = (f' <a href="{_e(link)}" target="_blank" rel="nofollow noopener" class="ga-src-link">Habere git →</a>'
             if link.startswith("http") else "")
        rows.append(f"<li><strong>{_e(name)}:</strong> {_e(aci)}{a}</li>")
    if len(rows) >= 2:
        parts.append('<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Kaynaklar Ne Diyor?</h3><ul class="ga-sources">'
                     + "".join(rows) + "</ul>")

    nums = [r for r in (data.get("rakamlar") or []) if isinstance(r, dict) and r.get("etiket") and r.get("deger")][:6]
    if nums:
        parts.append('<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Rakamlarla</h3><div class="ga-table-wrap"><table class="ga-table"><tbody>'
                     + "".join(f"<tr><td>{_e(r['etiket'])}</td><td><strong>{_e(r['deger'])}</strong></td></tr>" for r in nums)
                     + "</tbody></table></div>")

    section("Bundan Sonra Ne İzlenmeli?", _as_list(data.get("sonra")))
    parts.append("</div>")
    return "\n".join(parts)


def build_article(primary: Dict, primary_body: str, pool: List[Dict], category: str, mode: str = "news") -> Optional[Dict]:
    """
    Uçtan uca: kaynakları topla -> Gemini 3.5 ile yaz -> HTML'e çevir.
    Dönüş: {"title","summary","content","category","source_count","sources"} veya None
    """
    import content_quality
    sources = gather_sources(primary, primary_body, pool)
    if len(" ".join(s["body"] for s in sources).split()) < 60:
        print("⏩ [Çok Kaynaklı] Kaynak metin yetersiz, eski akışa dönülüyor.")
        return None
    data = generate(sources, category=category, mode=mode)
    if not data:
        return None
    title = content_quality.clean_title_text(re.sub(r"\s+", " ", str(data.get("baslik") or "")).strip())
    if not (15 <= len(title) <= 140):
        title = content_quality.clean_title_text(primary.get("title", ""))
    summary = content_quality.clean_title_text(str(data.get("ozet") or "").strip())
    body = render_html(data, sources, mode=mode)
    content = content_quality.clean_article_html(body)
    words = content_quality.visible_word_count(content)
    min_words = 450 if mode == "analysis" else 280
    if words < min_words:
        print(f"⚠️ [Çok Kaynaklı] Metin kısa kaldı ({words} kelime), eski akışa dönülüyor.")
        return None
    print(f"✅ [Çok Kaynaklı] {data.get('_model')} ile {len(sources)} kaynaktan {words} kelimelik metin yazıldı: {title}")
    return {
        "title": title,
        "summary": summary,
        "content": content,
        "category": category,
        "source_count": len(sources),
        "sources": [s["name"] for s in sources],
        "sibling_items": [s["_raw_item"] for s in sources[1:] if s.get("_raw_item")],
    }
