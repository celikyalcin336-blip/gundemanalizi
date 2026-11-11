# -*- coding: utf-8 -*-
"""
Çok Kaynaklı Haber & Analiz Motoru (Gündem Analizi)

Aynı olayı anlatan 1-4 farklı kaynağın haberlerini sentezleyerek
"⚡ 30 Saniyede Özet / Ne Oldu? / Neden Önemli? / Arka Plan ve Önceki Gelişmeler /
🇹🇷 Türkiye'ye Etkisi / (Analizde: Olası Senaryolar) / Kaynaklar Ne Diyor? /
Rakamlarla / Bundan Sonra Ne İzlenmeli?" yapısında özgün haber-analiz metni üretir.

- Model: yalnızca Gemini 3.5 ailesi (gemini-3.5-flash, yedek: gemini-3.5-flash-lite)
- Etiketli düz metin (tagged plain-text) protokolü: JSON şema kısıtlamasının
  lite modelde yol açtığı kısa metin ve Türkçe karakter düşmesi sorunlarını tamamen sıfırlar.
"""
import html as _html
import json
import os
import re
import time
from typing import Dict, List, Optional

import config

MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_MULTI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite").split(",")
    if m.strip()
]

# Günlük kota (429 RESOURCE_EXHAUSTED / quota) dolduğunda modeli geçici soğutmaya alır;
# böylece her haberde boşuna 8 sn beklemek yerine anında aktif Gemini 3.5 modeline geçer.
_MODEL_COOLDOWN_UNTIL: Dict[str, float] = {}

_STOP = set(
    "ve ile için bir bu şu da de mi mu mü ne çok daha en son yeni olarak olan oldu olduğu gibi kadar sonra önce göre "
    "ise ama hem değil var yok ilk iki üç tüm her nasıl neden haber haberi açıklama açıkladı dedi büyük önemli flaş "
    "son dakika bugün yarın dün kasım ekim aralık ocak şubat mart nisan mayıs haziran temmuz ağustos eylül 2025 2026 2027".split()
)

_TR_SUFFIX_RE = re.compile(
    r"(?:sında|sinde|sından|sinden|larında|lerinde|larından|lerinden|nda|nde|dan|den|tan|ten|"
    r"nın|nin|nun|nün|ları|leri|daki|deki|taki|teki|yla|yle|da|de|ta|te|ya|ye|yı|yi|yu|yü)$"
)


def _stem_tr(word: str) -> str:
    if len(word) <= 4:
        return word
    s = _TR_SUFFIX_RE.sub("", word)
    if len(s) < 4:
        s = word
    return s[:6] if len(s) >= 7 else s


def _tokens(text: str) -> set:
    t = (text or "").replace("İ", "i").replace("I", "ı").lower()
    raw_words = [w for w in re.findall(r"[a-zçğıöşü0-9]{4,}", t) if w not in _STOP]
    return {_stem_tr(w) for w in raw_words if _stem_tr(w) not in _STOP}


def _clean_src_name(name: str) -> str:
    try:
        import content_quality
        return content_quality.clean_source_name(name)
    except Exception:
        return (name or "").strip()


def find_siblings(primary: Dict, pool: List[Dict], max_n: int = 3) -> List[Dict]:
    """
    Önce news_fetcher çapraz RSS eşleşmesinden gelen hazır kardeş haberleri alır,
    ardından havuzdaki farklı kaynaklardan aynı olayı anlatan haberleri ekler.
    """
    p_src = _clean_src_name(primary.get("source", ""))
    p_cat = primary.get("category")
    seen_src = {p_src}
    out: List[Dict] = []

    # 1) news_fetcher.fetch_latest_news sırasında yakalanan doğrudan kardeş haberler
    for pre_sib in (primary.get("siblings") or []):
        s_name = _clean_src_name(pre_sib.get("source", ""))
        if not s_name or s_name in seen_src:
            continue
        seen_src.add(s_name)
        out.append(pre_sib)
        if len(out) >= max_n:
            return out

    # 2) Havuzdaki diğer haberler (ve onların alt kardeşleri) üzerinden kök örtüşmesi taraması
    p_tok = _tokens(primary.get("title", ""))
    if len(p_tok) < 3:
        return out

    candidates: List[Dict] = []
    for it in (pool or []):
        if it is primary or it.get("link") == primary.get("link"):
            continue
        candidates.append(it)
        for sub in (it.get("siblings") or []):
            candidates.append(sub)

    scored = []
    for it in candidates:
        if it.get("link") == primary.get("link"):
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
        "name": _clean_src_name(primary.get("source", "")) or "Ajans Kaynağı",
        "link": primary.get("link", ""),
        "title": primary.get("title", ""),
        "body": (primary_body or primary.get("summary") or "")[:3800],
    }]
    try:
        import news_fetcher
    except Exception:
        news_fetcher = None
    for sib in find_siblings(primary, pool, max_n=max_siblings):
        body = ""
        if news_fetcher is not None and sib.get("link"):
            try:
                body = (news_fetcher.fetch_article_details(sib.get("link", ""), max_paragraphs=10) or {}).get("body", "") or ""
            except Exception:
                body = ""
        sib_sum = sib.get("summary") or ""
        body = body if len(body) > len(sib_sum) else sib_sum
        if len(f"{sib.get('title', '')} {body}".split()) < 14:
            continue
        sources.append({
            "name": _clean_src_name(sib.get("source", "")),
            "link": sib.get("link", ""),
            "title": sib.get("title", ""),
            "body": body[:3200],
            "_raw_item": sib,
        })
    return sources


_CAT_FOCUS = {
    "Ekonomi": "Rakamların vatandaşın bütçesine, maaşına, kredi/mevduat koşullarına ve alım gücüne somut etkisini açıkla. Yatırım tavsiyesi verme.",
    "Sağlık": "Uzman uyarılarını ve dikkat edilmesi gerekenleri sade anlat. Teşhis veya tedavi önerme; okuru uzman hekime yönlendir.",
    "Eğitim": "Resmi takvimi, başvuru/sınav şartlarını ve öğrenci-veli-öğretmen açısından atılacak adımları net aktar.",
    "Spor": "Gelişmenin puan durumu, fikstür, kadro derinliği ve takımın sezon hedeflerine etkisini spor gazeteciliği diliyle anlat.",
    "Teknoloji": "Teknolojinin öne çıkan özelliklerini, rakiplerden farkını ve son kullanıcıya/sektöre somut karşılığını anlat.",
    "Otomobil": "Aracın segmentteki konumunu, teknik mimarisini, Türkiye pazarı ve ÖTV/maliyet açısından yansımalarını anlat.",
    "Dünya": "Gelişmenin bölgesel dengeler, uluslararası diplomasi ve Türkiye açısından olası yansımalarını abartmadan anlat.",
}


def _build_prompt(sources: List[Dict], category: str, mode: str, extra_length_hint: bool = False) -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(f"[{i}] KAYNAK: {s['name']}\nBaşlık: {s['title']}\nMetin: {s['body']}")
    focus = _CAT_FOCUS.get(
        category,
        "Resmi açıklamaları, sahadaki durumu, hukuki/idari çerçeveyi ve kamuoyunu ilgilendiren yönlerini net bir gazetecilik diliyle aktar.",
    )
    if mode == "analysis":
        length_rule = "Toplam metin EN AZ 680, ideal 780-950 kelime olmalı. Bu bir GÜNLÜK ÖZEL ANALİZ dosyasıdır: neden-sonuç ilişkisini, etkileri ve olası senaryoları derinlemesine incele."
        scen_section = """
[SENARYOLAR]
- 1. olası gelişme senaryosu (2-3 tam cümleyle açıkla)
- 2. olası gelişme senaryosu (2-3 tam cümleyle açıkla)
- 3. olası gelişme senaryosu (2-3 tam cümleyle açıkla)
"""
    else:
        length_rule = "Toplam metin EN AZ 450, ideal 520-680 kelime olmalı."
        scen_section = ""

    if extra_length_hint:
        length_rule += " DİKKAT: Bir önceki deneme kısa kaldı; her paragrafı en az 4-5 tam ve doyurucu cümleyle ayrıntılı yaz."

    multi_rule = (
        f"Aşağıda AYNI olayı anlatan {len(sources)} farklı kaynağın haberleri var. Bunları BİRLEŞTİR ve SENTEZLE; hiçbir kaynağı tek başına yeniden yazma."
        if len(sources) > 1
        else "Aşağıda bu olayı anlatan kaynak haber var. Yalnızca kısa bülten tekrarı yapma; kesinlikle uydurma bilgi/rakam eklemeden olayın hukuki/idari/sektörel bağlamını, önemini ve Türkiye açısından somut karşılığını analitik gazetecilik diliyle açıkla."
    )

    src_instruction = (
        "Her kaynağın olayı hangi açıdan verdiğini veya öne çıkardığı detayı ayrı satırda `Kaynak Adı | 1-2 cümlelik açıklama` biçiminde yaz."
        if len(sources) > 1
        else f"`{sources[0]['name']} | Bu kaynağın haberde aktardığı temel bilgi ve öne çıkan detay (1-2 cümle)` biçiminde yaz."
    )

    return f"""Sen Türkçe haber ve analiz sitesi 'Gündem Analizi'nin kıdemli baş editörüsün.
{multi_rule}
Kategori: {category}. Kategori odağı: {focus}

KESİN KURALLAR:
1. DOĞRULUK: SADECE kaynaklarda geçen somut bilgi, isim, tarih ve rakamları kullan. Kaynakta olmayan rakam, kişi, alıntı veya iddia KESİNLİKLE UYDURMA. Kaynak metin kısa bir son dakika bülteni olsa bile hayali olay detayı uydurmadan konunun genel kabul görmüş kurumsal, hukuki, teknik veya toplumsal çerçevesini ve standart resmi prosedürleri anlatarak metni zenginleştir.
2. ÖZGÜNLÜK: Kaynak cümlelerini kopyalama; tamamen kendi cümlelerinle, akıcı gazetecilik diliyle yaz.
3. UZUNLUK: {length_rule} Paragrafları tek cümleyle geçiştirme; her paragraf en az 4-5 tam cümleden oluşsun.
4. DİL VE TÜRKÇE İMLA: Kusursuz, duru, tarafsız Türkçe. Başlık dahil TÜM alanlarda Türkçe karakterleri (ç, ğ, ı, İ, ö, ş, ü) eksiksiz ve doğru kullan; kesinlikle İngilizce/ASCII harflerle ("Cip ureticisi", "Yatirim", "Basciligi", "Olum" gibi) yazma. Tık tuzağı, ünlem (!), üç nokta (...), emoji, hashtag ve yapay zeka ibaresi YOK.
   "Sonuç olarak", "Özetle", "merakla bekleniyor", "yakından takip ediliyor", "büyük önem taşımaktadır" gibi klişeleri KULLANMA.
5. ÇIKTI FORMATI: JSON veya ``` kod bloğu KULLANMA. Yanıtı SADECE aşağıdaki köşeli parantezli bölüm etiketleriyle düz metin olarak ver:

[BASLIK]
7-13 kelimelik, kaynak başlıkların hiçbiriyle birebir aynı olmayan, Türkçe harfleri eksiksiz ve olayın anlamını koruyan özgün başlık

[OZET]
Haberin özünü somut bilgilerle anlatan 2-3 cümlelik özet (meta açıklama olarak kullanılacak).

[MADDELER]
- 30 saniyede özet 1. madde (tam ve somut cümle)
- 30 saniyede özet 2. madde (tam ve somut cümle)
- 30 saniyede özet 3. madde (tam ve somut cümle)

[NE_OLDU]
Olayın kim, nerede, ne zaman ve nasıl gerçekleştiğini tüm somut verilerle anlatan 4-5 cümlelik birinci paragraf.

Tarafların veya resmi makamların açıklamalarını, müdahale ya da uygulama ayrıntılarını aktaran 4-5 cümlelik ikinci paragraf.

[NEDEN_ONEMLI]
Bu gelişmenin neden önemli olduğunu, sektörel, hukuki, ekonomik veya toplumsal boyutunu inceleyen 4-5 cümlelik doyurucu paragraf.

[ARKA_PLAN]
Konunun doğrulanabilir genel arka planını, önceki benzer süreçleri veya mevzuat/sektör çerçevesini anlatan 4-5 cümlelik doyurucu paragraf.

[TURKIYE_ETKISI]
Olay Türkiye'de yaşandıysa doğrudan vatandaş, kamu düzeni, bütçe veya ilgili kurumlar açısından somut etkisini; yurt dışı haberi ise Türkiye'ye olası yansımasını anlatan 3-4 cümlelik paragraf.
{scen_section}
[KAYNAKLAR]
- {src_instruction}

[RAKAMLAR]
- Etiket | Kaynakta geçen somut sayısal veri (en fazla 6 satır; kaynakta hiç sayısal veri yoksa yalnızca YOK yaz)

[SONRA]
Bundan sonra izlenecek resmi süreci, soruşturma/uygulama adımlarını veya takvimdeki somut aşamaları anlatan 3-4 cümlelik paragraf.

KAYNAKLAR:
""" + "\n\n".join(blocks)


_TAG_NORM_MAP = {
    "BASLIK": "BASLIK",
    "BAŞLIK": "BASLIK",
    "OZET": "OZET",
    "ÖZET": "OZET",
    "MADDELER": "MADDELER",
    "30_SANIYEDE_OZET": "MADDELER",
    "NE_OLDU": "NE_OLDU",
    "NEDEN_ONEMLI": "NEDEN_ONEMLI",
    "NEDEN_ÖNEMLİ": "NEDEN_ONEMLI",
    "NEDEN_ÖNEMLI": "NEDEN_ONEMLI",
    "ARKA_PLAN": "ARKA_PLAN",
    "TURKIYE_ETKISI": "TURKIYE_ETKISI",
    "TÜRKİYE_ETKİSİ": "TURKIYE_ETKISI",
    "TÜRKIYE_ETKISI": "TURKIYE_ETKISI",
    "SENARYOLAR": "SENARYOLAR",
    "OLASI_SENARYOLAR": "SENARYOLAR",
    "KAYNAKLAR": "KAYNAKLAR",
    "RAKAMLAR": "RAKAMLAR",
    "SONRA": "SONRA",
    "BUNDAN_SONRA": "SONRA",
}

_TAG_LINE_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:\*{1,2}\s*)?\[\s*([A-ZÇĞİÖŞÜ0-9_ ]{4,26})\s*\](?:\s*\*{1,2})?\s*:?\s*$",
    re.M,
)


def _parse_json_safe(raw: str) -> Optional[Dict]:
    if not raw:
        return None
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end <= start:
        return None
    s = s[start:end + 1]
    try:
        return json.loads(s)
    except Exception:
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", s))
        except Exception:
            return None


def _parse_tagged_or_json(raw: str) -> Optional[Dict]:
    if not raw:
        return None
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", "", raw.strip())
    matches = []
    for m in _TAG_LINE_RE.finditer(cleaned):
        raw_key = re.sub(r"\s+", "_", m.group(1).strip().upper())
        norm_key = _TAG_NORM_MAP.get(raw_key)
        if norm_key:
            matches.append((norm_key, m.start(), m.end()))

    if not matches:
        return _parse_json_safe(cleaned)

    sec: Dict[str, str] = {}
    for idx, (norm_key, _, end_pos) in enumerate(matches):
        next_start = matches[idx + 1][1] if idx + 1 < len(matches) else len(cleaned)
        sec[norm_key] = cleaned[end_pos:next_start].strip()

    def _bullets(txt: str) -> List[str]:
        out = []
        for line in (txt or "").splitlines():
            line = re.sub(r"^\s*(?:[-•*—–]|\d+[\.\)])\s*", "", line).strip()
            if len(line) > 5 and line.upper() not in {"YOK", "YOK.", "-"}:
                out.append(line)
        return out

    def _paras(txt: str) -> List[str]:
        out = []
        for p in re.split(r"\n\s*\n", txt or ""):
            p = re.sub(r"\s+", " ", p).strip()
            if len(p) > 15 and p.upper() not in {"YOK", "YOK."}:
                out.append(p)
        if not out and (txt or "").strip():
            single = re.sub(r"\s+", " ", txt).strip()
            if len(single) > 15 and single.upper() not in {"YOK", "YOK."}:
                out.append(single)
        return out

    kaynaklar = []
    for b in _bullets(sec.get("KAYNAKLAR", "")):
        if "|" in b:
            k, aci = b.split("|", 1)
        elif ":" in b:
            k, aci = b.split(":", 1)
        elif " - " in b:
            k, aci = b.split(" - ", 1)
        else:
            continue
        k_clean = k.strip().strip("*[] ")
        aci_clean = aci.strip()
        if k_clean and aci_clean:
            kaynaklar.append({"kaynak": k_clean, "aci": aci_clean})

    rakamlar = []
    for b in _bullets(sec.get("RAKAMLAR", "")):
        if "|" in b:
            et, dg = b.split("|", 1)
        elif ":" in b:
            et, dg = b.split(":", 1)
        else:
            continue
        et_clean = et.strip().strip("* ")
        dg_clean = dg.strip().strip("* ")
        if et_clean and dg_clean and dg_clean.upper() not in {"YOK", "YOK.", "BELİRTİLMEDİ", "BELIRTILMEDI"}:
            rakamlar.append({"etiket": et_clean, "deger": dg_clean})

    baslik_lines = [l.strip().strip('"#* ') for l in (sec.get("BASLIK") or "").splitlines() if l.strip()]
    return {
        "baslik": baslik_lines[0] if baslik_lines else "",
        "ozet": " ".join(_paras(sec.get("OZET", ""))),
        "maddeler": _bullets(sec.get("MADDELER", "")),
        "ne_oldu": _paras(sec.get("NE_OLDU", "")),
        "neden_onemli": _paras(sec.get("NEDEN_ONEMLI", "")),
        "arka_plan": _paras(sec.get("ARKA_PLAN", "")),
        "turkiye_etkisi": " ".join(_paras(sec.get("TURKIYE_ETKISI", ""))),
        "senaryolar": _bullets(sec.get("SENARYOLAR", "")),
        "kaynaklar": kaynaklar,
        "rakamlar": rakamlar,
        "sonra": " ".join(_paras(sec.get("SONRA", ""))),
    }


def _estimate_data_words(data: Dict) -> int:
    chunks = []
    for key in ("maddeler", "ne_oldu", "neden_onemli", "arka_plan", "senaryolar"):
        v = data.get(key)
        if isinstance(v, list):
            chunks.extend(str(x) for x in v)
        elif isinstance(v, str):
            chunks.append(v)
    for key in ("turkiye_etkisi", "sonra"):
        if data.get(key):
            chunks.append(str(data[key]))
    for k in (data.get("kaynaklar") or []):
        if isinstance(k, dict):
            chunks.append(f"{k.get('kaynak', '')} {k.get('aci', '')}")
    return len(" ".join(chunks).split())


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

    src_has_tr = bool(re.search(r"[çğıöşüÇĞİÖŞÜ]", " ".join(s.get("title", "") for s in sources)))
    min_raw_words = 410 if mode == "analysis" else 245

    now_ts = time.time()
    active_models = [m for m in MODELS if _MODEL_COOLDOWN_UNTIL.get(m, 0.0) <= now_ts]
    if not active_models:
        active_models = list(MODELS)

    attempt_chain = []
    for m_name in active_models:
        attempt_chain.append((m_name, False))
        attempt_chain.append((m_name, True))

    for step_i, (m_name, extra_len) in enumerate(attempt_chain):
        if _MODEL_COOLDOWN_UNTIL.get(m_name, 0.0) > time.time():
            continue
        prompt = _build_prompt(sources, category, mode, extra_length_hint=extra_len)
        try:
            res = client.models.generate_content(model=m_name, contents=prompt)
            raw = (res.text or "").strip() if res else ""
            data = _parse_tagged_or_json(raw)
            if not isinstance(data, dict) or not data.get("baslik") or not data.get("ne_oldu"):
                print(f"⚠️ [Çok Kaynaklı] {m_name} eksik bölüm döndürdü, yeniden deneniyor.")
                continue
            cand_title = str(data.get("baslik") or "").strip()
            if src_has_tr and len(cand_title) > 20 and not re.search(r"[çğıöşüÇĞİÖŞÜ]", cand_title):
                print(f"⚠️ [Çok Kaynaklı] {m_name} başlıkta Türkçe karakter kullanmadı, yeniden deneniyor: {cand_title[:60]}")
                continue
            est_w = _estimate_data_words(data)
            if est_w < min_raw_words:
                print(f"⚠️ [Çok Kaynaklı] {m_name} kısa yanıt verdi ({est_w} kelime < {min_raw_words}), daha uzun istenerek tekrar deneniyor.")
                continue
            data["_model"] = m_name
            return data
        except Exception as e:
            err_s = str(e)
            print(f"⚠️ [Çok Kaynaklı] {m_name} hatası: {err_s[:160]}")
            if "429" in err_s and ("quota" in err_s.lower() or "RESOURCE_EXHAUSTED" in err_s):
                # Günlük/dakikalık kota doldu: bu modeli 20 dk soğutmaya alıp anında diğer Gemini 3.5 modeline geç
                _MODEL_COOLDOWN_UNTIL[m_name] = time.time() + 1200
                continue
            if step_i < len(attempt_chain) - 1 and ("503" in err_s or "UNAVAILABLE" in err_s):
                time.sleep(3.0)
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
    """Yapılandırılmış veriyi sitenin şablonuna uygun, temiz .ga-multi HTML gövdesine çevirir."""
    parts = ['<div class="ga-multi">']

    bullets = _as_list(data.get("maddeler"))[:4]
    if bullets:
        parts.append(
            '<div class="ga-box ga-tldr"><h4 class="ga-box-title">⚡ 30 Saniyede Özet</h4><ul>'
            + "".join(f"<li>{_e(b)}</li>" for b in bullets)
            + "</ul></div>"
        )

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
        parts.append(
            f'<div class="ga-box ga-tr"><h4 class="ga-box-title">🇹🇷 Türkiye\'ye Etkisi</h4><p>{_e(tr)}</p></div>'
        )

    if mode == "analysis":
        scen = _as_list(data.get("senaryolar"))[:4]
        if scen:
            parts.append(
                '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Olası Senaryolar</h3><ol class="ga-list">'
                + "".join(f"<li>{_e(s)}</li>" for s in scen)
                + "</ol>"
            )

    # Kaynaklar ne diyor? / Kaynak ve Öne Çıkan Detay (şeffaf dış bağlantı ile)
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
        if not link and len(sources) == 1:
            link = sources[0].get("link") or ""
        a = (
            f' <a href="{_e(link)}" target="_blank" rel="nofollow noopener" class="ga-src-link">Habere git →</a>'
            if link.startswith("http")
            else ""
        )
        rows.append(f"<li><strong>{_e(name)}:</strong> {_e(aci)}{a}</li>")

    # Model kaynak satırını boş bıraktıysa eldeki kaynaklardan şeffaf bağlantı üret
    if not rows and sources:
        for s in sources:
            s_name = (s.get("name") or "").strip()
            s_title = (s.get("title") or "").strip()
            s_link = (s.get("link") or "").strip()
            if not s_name or not s_title:
                continue
            a = (
                f' <a href="{_e(s_link)}" target="_blank" rel="nofollow noopener" class="ga-src-link">Habere git →</a>'
                if s_link.startswith("http")
                else ""
            )
            rows.append(f"<li><strong>{_e(s_name)}:</strong> {_e(s_title)}{a}</li>")

    if len(rows) >= 2:
        parts.append(
            '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Kaynaklar Ne Diyor?</h3><ul class="ga-sources">'
            + "".join(rows)
            + "</ul>"
        )
    elif len(rows) == 1:
        parts.append(
            '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Kaynak ve Öne Çıkan Detay</h3><ul class="ga-sources">'
            + rows[0]
            + "</ul>"
        )

    nums = [
        r
        for r in (data.get("rakamlar") or [])
        if isinstance(r, dict) and r.get("etiket") and r.get("deger")
    ][:6]
    if nums:
        parts.append(
            '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Rakamlarla</h3><div class="ga-table-wrap"><table class="ga-table"><tbody>'
            + "".join(f"<tr><td>{_e(r['etiket'])}</td><td><strong>{_e(r['deger'])}</strong></td></tr>" for r in nums)
            + "</tbody></table></div>"
        )

    section("Bundan Sonra Ne İzlenmeli?", _as_list(data.get("sonra")))
    parts.append("</div>")
    return "\n".join(parts)


def build_article(primary: Dict, primary_body: str, pool: List[Dict], category: str, mode: str = "news") -> Optional[Dict]:
    """
    Uçtan uca: kaynakları topla -> Gemini 3.5 ile yaz -> HTML'e çevir.
    Dönüş: {"title","summary","content","category","source_count","sources","sibling_items"} veya None
    """
    import content_quality
    sources = gather_sources(primary, primary_body, pool)
    total_input_words = len((" ".join(f"{s['title']} {s['body']}" for s in sources)).split())
    if total_input_words < 18:
        print(f"⏩ [Çok Kaynaklı] Kaynak metin çok kısa ({total_input_words} kelime), atlanıyor.")
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
    min_words = 420 if mode == "analysis" else 260
    if words < min_words:
        print(f"⚠️ [Çok Kaynaklı] Metin kısa kaldı ({words} kelime < {min_words}), eski akışa dönülüyor.")
        return None
    if len(summary) < 40:
        summary = content_quality._norm(content).split(". ")[0][:300]
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
