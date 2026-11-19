# -*- coding: utf-8 -*-
"""
Çok Kaynaklı Haber & Analiz Motoru (Gündem Analizi)

Aynı olayı anlatan 1-4 farklı kaynağın haberlerini sentezleyerek:
- ⚡ 30 Saniyede Özet (3 sıkı madde)
- Konuya Özgü Gazetecilik Ara Başlıkları (<h3>) — sabit kalıp ("Ne Oldu?" vb.) kullanılmaz
- Konuya Uygun Etki / Yansıma Kutusu (zorlama bağlantı varsa basılmaz)
- Analiz modunda Konuya Özgü Senaryo Bölümü
- Şeffaf Kaynak Karşılaştırması / Kaynak Notu (Habere git → dış bağlantılı)
- Yalnızca >= 3 farklı somut veri olduğunda gösterilen Öne Çıkan Veriler tablosu (veri tekrarını önler)

Model: yalnızca Gemini 3.5 ailesi (gemini-3.5-flash, yedek: gemini-3.5-flash-lite)
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

    for pre_sib in (primary.get("siblings") or []):
        s_name = _clean_src_name(pre_sib.get("source", ""))
        if not s_name or s_name in seen_src:
            continue
        seen_src.add(s_name)
        out.append(pre_sib)
        if len(out) >= max_n:
            return out

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
    "Ekonomi": "Açıklanan verilerin vatandaşın bütçesine, kredi/mevduat koşullarına ve piyasa dengelerine somut etkisini anlat. Yatırım tavsiyesi verme.",
    "Sağlık": "Uzman uyarılarını, belirtileri ve dikkat edilmesi gerekenleri sade anlat. Teşhis veya tedavi önerme; okuru uzman hekime yönlendir.",
    "Eğitim": "Resmi takvimi, başvuru/sınav şartlarını ve öğrenci, veli ve öğretmenler açısından uygulama adımlarını net aktar.",
    "Spor": "Gelişmenin puan durumu, fikstür, kadro derinliği ve takımın hedeflerine etkisini spor gazeteciliği diliyle anlat.",
    "Teknoloji": "Teknolojinin öne çıkan özelliklerini, rakiplerden farkını ve kullanıcı/sektör açısından somut karşılığını anlat.",
    "Otomobil": "Aracın segmentteki konumunu, teknik yapısını, Türkiye pazarı ve vergi/maliyet açısından yansımalarını anlat.",
    "Dünya": "Gelişmenin bölgesel dengeler, diplomasi ve Türkiye açısından gerçekçi yansımalarını abartmadan anlat.",
}

_FORBIDDEN_TEMPLATE_HEADINGS = {
    "ne oldu",
    "neler oldu",
    "neden önemli",
    "neden onemli",
    "arka plan",
    "arka plan ve önceki gelişmeler",
    "olası senaryolar",
    "olasi senaryolar",
    "bundan sonra ne izlenmeli",
    "bundan sonra",
    "giriş",
    "gelişme",
    "sonuç",
    "değerlendirme",
}


def _build_prompt(sources: List[Dict], category: str, mode: str, extra_length_hint: bool = False, feedback: str = "") -> str:
    blocks = []
    for i, s in enumerate(sources, 1):
        blocks.append(f"[{i}] KAYNAK: {s['name']}\nBaşlık: {s['title']}\nMetin: {s['body']}")
    focus = _CAT_FOCUS.get(
        category,
        "Resmi açıklamaları, sahadaki somut durumu, hukuki/idari çerçeveyi ve kamuoyunu ilgilendiren yönlerini berrak bir gazetecilik diliyle aktar.",
    )
    if mode == "analysis":
        length_rule = (
            "Bu bir GÜNLÜK ÖZEL ANALİZ dosyasıdır: neden-sonuç ilişkisini, etkileri ve olası senaryoları tekrara düşmeden incele. "
            "Uzunluğu kaynaklardaki bilgi belirler (genellikle 450-700 kelime); kaynakta olmayan bilgiyle metni uzatma."
        )
        scen_section = """
[SENARYO_BASLIK]
Önümüzdeki sürece dair konuya özgü 4-8 kelimelik özgün ara başlık (kesinlikle "Olası Senaryolar" yazma)

[SENARYOLAR]
- 1. olası gelişme veya süreç ihtimali (2 tam cümle)
- 2. olası gelişme veya süreç ihtimali (2 tam cümle)
- 3. olası gelişme veya süreç ihtimali (2 tam cümle)
"""
    else:
        length_rule = (
            "UZUNLUK KURALI (ÇOK KRİTİK): Metnin uzunluğunu kaynaklardaki GERÇEK BİLGİ miktarı belirler. "
            "Kaynak kısaysa kısa ve net yaz (yaklaşık 180-300 kelime); kaynaklar zenginse 300-550 kelimeye çıkabilirsin. "
            "Metni uzatmak için genel geçer, her habere uyacak cümleler YAZMA "
            "(örnek yasak cümleler: '... dikkatle izleniyor', '... bir kez daha gösterdi', '... önem taşıyor', "
            "'... dengeleri yeniden şekillendirebilir', '... küresel çapta takip edilecek'). "
            "Bir bölüm için kaynakta yeterli somut bilgi yoksa o bölüme yalnızca YOK yaz; bölümü boş laf ile doldurma."
        )
        scen_section = ""

    multi_rule = (
        f"Aşağıda AYNI olayı anlatan {len(sources)} farklı kaynağın haberleri var. Bunları BİRLEŞTİR ve SENTEZLE; hiçbir kaynağı tek başına kopyalama. Kaynakların birbirini tamamlayan farklı ayrıntılarını tek akışta topla."
        if len(sources) > 1
        else "Aşağıda bu olayı anlatan kaynak haber var. Kaynaktaki bilgiyi kendi cümlelerinle, okurun hızlıca anlayacağı net bir haber akışıyla anlat. Kaynakta olmayan bilgi EKLEME."
    )

    if len(sources) > 1:
        src_instruction = "Her satırda ters tırnak kullanmadan düz metinle: Kaynak Adı | Bu kaynağın haberi hangi açıdan ele aldığı ve öne çıkardığı farklı detay (1 cümle)"
    else:
        src_instruction = f"Ters tırnak kullanmadan düz metinle: {sources[0]['name']} | Kaynağın aktardığı ana gelişme ve öne çıkan somut bilgi (1 cümle)"

    feedback_block = f"\nÖNCEKİ DENEMEDEKİ HATA (MUTLAKA DÜZELT): {feedback}\n" if feedback else ""

    return f"""Sen Türkçe ulusal haber ve analiz sitesi Gündem Analizi'nin kıdemli baş editörüsün.
{multi_rule}
Kategori: {category}. Kategori odağı: {focus}
{feedback_block}
KESİN KURALLAR:
1. DOĞRULUK (EN ÖNEMLİ KURAL): SADECE kaynaklarda geçen somut bilgi, isim, tarih ve rakamları kullan. Kaynakta yazmayan HİÇBİR rakam, yüzde, tarih, süre, kişi, alıntı veya iddia yazma. Kendi hesapladığın rakamları (toplam, fark, kaç ay geçtiği vb.) da yazma. Yazdığın her sayı kaynak metinde birebir geçmelidir; otomatik kontrol edilir ve kaynakta olmayan sayı içeren metin reddedilir.
2. SIFIR TEKRAR: Özette (MADDELER), paragraflarda ve veri tablosunda (RAKAMLAR) aynı rakamları ve aynı cümleleri evirip çevirip tekrarlama.
   - Temel bilgileri ve olayın 5N1K akışını BOLUM_1 içinde ver.
   - BOLUM_2 içinde BOLUM_1'i tekrar etmeden, kaynakta geçen etkileri, tarafların gerekçelerini veya farklı ayrıntıları aktar.
   - BOLUM_3 içinde kaynakta geçen geçmiş/arka plan bilgisini aktar.
3. SABİT ŞABLON BAŞLIK YASAĞI: ARA_BASLIK_1, ARA_BASLIK_2, ARA_BASLIK_3, SENARYO_BASLIK ve SONRA_BASLIK alanlarında "Ne Oldu?", "Neden Önemli?", "Arka Plan", "Olası Senaryolar", "Bundan Sonra Ne İzlenmeli?" gibi sabit kalıp başlıklar KULLANMA. Her ara başlık o haberdeki kurum, şehir, kişi, yasa veya projeye özel 4-8 kelimelik gerçek gazetecilik başlığı olsun.
4. {length_rule}
5. BAŞLIK ÜSLUBU: Türk basını usulü CÜMLE DÜZENİNDE yaz: yalnızca ilk kelime ve özel isimler (kişi, kurum, şehir, marka) büyük harfle başlar. İngilizce gibi Her Kelimenin Baş Harfini Büyük YAZMA. Kaynakta geçmiyorsa "tarihi, dev, şok, rekor, kritik, sarstı, bomba, flaş, efsane" gibi abartı kelimeleri KULLANMA. Başlık olayı olduğu gibi, abartmadan anlatsın.
6. DİL VE TÜRKÇE İMLA: Kusursuz, duru Türkçe. Tüm alanlarda Türkçe karakterleri (ç, ğ, ı, İ, ö, ş, ü) eksiksiz kullan. Tık tuzağı, ünlem, üç nokta, ters tırnak işareti, kod bloğu, hashtag ve yapay zeka ibaresi YOK. "Sonuç olarak", "Özetle", "merakla bekleniyor", "yakından takip ediliyor", "büyük önem taşımaktadır" klişelerini KULLANMA.
7. ÇIKTI FORMATI: JSON veya kod bloğu KULLANMA. Yanıtı SADECE aşağıdaki köşeli parantezli etiketlerle düz metin olarak ver:

[BASLIK]
7-13 kelimelik, kaynak başlıklarla birebir aynı olmayan, cümle düzeninde, Türkçe harfleri eksiksiz özgün haber başlığı

[OZET]
Haberin özünü anlatan 2 cümlelik net özet.

[MADDELER]
- 1. özet maddesi (kısa, net, somut tek cümle)
- 2. özet maddesi (farklı bir somut boyutu anlatan tek cümle)
- 3. özet maddesi (kaynakta varsa sürecin takvimi veya etkisi; yoksa farklı bir somut ayrıntı)

[ARA_BASLIK_1]
Olayın somut gelişmesini anlatan konuya özel 4-8 kelimelik özgün ara başlık

[BOLUM_1]
Olayın kim, nerede, ne zaman ve nasıl gerçekleştiğini kaynaktaki somut verilerle anlatan 2-4 cümlelik birinci paragraf.

Kaynakta varsa yetkililerin/tarafların açıklamalarını veya uygulama detaylarını aktaran 2-4 cümlelik ikinci paragraf (yoksa bu paragrafı yazma).

[ARA_BASLIK_2]
Gelişmenin etkisini veya farklı boyutunu yansıtan konuya özel 4-8 kelimelik özgün ara başlık

[BOLUM_2]
BOLUM_1'i tekrar etmeden, kaynakta geçen etkileri, gerekçeleri veya ek ayrıntıları anlatan 2-4 cümlelik paragraf. Kaynakta böyle bir bilgi yoksa yalnızca YOK yaz.

[ARA_BASLIK_3]
Konunun geçmişini veya kurumsal çerçevesini yansıtan konuya özel 4-8 kelimelik özgün ara başlık

[BOLUM_3]
Kaynakta geçen arka plan veya önceki benzer adımları anlatan 2-3 cümlelik paragraf. Kaynakta arka plan bilgisi yoksa yalnızca YOK yaz.

[ETKI_BASLIK]
Konuya doğal uyan kısa kutu başlığı (ör: Vatandaş ve Sektör Açısından Önemi, Öğrenci ve Veliler İçin Kritik Detay)

[ETKI_METNI]
Kaynakta geçen bilgilere dayanarak olayın vatandaş veya ilgili sektör açısından somut karşılığını anlatan 1-2 cümle. Kaynakta buna dayanak yoksa veya bağlantı zorlama olacaksa yalnızca YOK yaz.
{scen_section}
[KAYNAKLAR]
- {src_instruction}

[RAKAMLAR]
- Etiket | Kaynakta birebir geçen sayısal veri (YALNIZCA kaynakta en az 3 FARKLI ve önemli sayısal veri varsa 3-5 satır yaz; yoksa yalnızca YOK yaz)

[SONRA_BASLIK]
Takvimdeki sıradaki aşamayı anlatan konuya özel 4-8 kelimelik özgün ara başlık

[SONRA]
Kaynakta açıkça geçen sıradaki resmi adımı veya takvimi anlatan 1-3 cümle. Kaynakta sıradaki adım/takvim bilgisi yoksa yalnızca YOK yaz.

KAYNAKLAR:
""" + "\n\n".join(blocks)


_TAG_NORM_MAP = {
    "BASLIK": "BASLIK",
    "BAŞLIK": "BASLIK",
    "OZET": "OZET",
    "ÖZET": "OZET",
    "MADDELER": "MADDELER",
    "30_SANIYEDE_OZET": "MADDELER",
    "ARA_BASLIK_1": "ARA_BASLIK_1",
    "ARA_BAŞLIK_1": "ARA_BASLIK_1",
    "BOLUM_1": "BOLUM_1",
    "BÖLÜM_1": "BOLUM_1",
    "NE_OLDU": "BOLUM_1",
    "ARA_BASLIK_2": "ARA_BASLIK_2",
    "ARA_BAŞLIK_2": "ARA_BASLIK_2",
    "BOLUM_2": "BOLUM_2",
    "BÖLÜM_2": "BOLUM_2",
    "NEDEN_ONEMLI": "BOLUM_2",
    "NEDEN_ÖNEMLİ": "BOLUM_2",
    "ARA_BASLIK_3": "ARA_BASLIK_3",
    "ARA_BAŞLIK_3": "ARA_BASLIK_3",
    "BOLUM_3": "BOLUM_3",
    "BÖLÜM_3": "BOLUM_3",
    "ARKA_PLAN": "BOLUM_3",
    "ETKI_BASLIK": "ETKI_BASLIK",
    "ETKİ_BAŞLIK": "ETKI_BASLIK",
    "ETKI_METNI": "ETKI_METNI",
    "ETKİ_METNİ": "ETKI_METNI",
    "TURKIYE_ETKISI": "ETKI_METNI",
    "TÜRKİYE_ETKİSİ": "ETKI_METNI",
    "SENARYO_BASLIK": "SENARYO_BASLIK",
    "SENARYO_BAŞLIK": "SENARYO_BASLIK",
    "SENARYOLAR": "SENARYOLAR",
    "OLASI_SENARYOLAR": "SENARYOLAR",
    "KAYNAKLAR": "KAYNAKLAR",
    "RAKAMLAR": "RAKAMLAR",
    "SONRA_BASLIK": "SONRA_BASLIK",
    "SONRA_BAŞLIK": "SONRA_BASLIK",
    "SONRA": "SONRA",
    "BUNDAN_SONRA": "SONRA",
}

_TAG_LINE_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:\*{1,2}\s*)?\[\s*([A-ZÇĞİÖŞÜ0-9_ ]{4,28})\s*\](?:\s*\*{1,2})?\s*:?\s*$",
    re.M,
)


def _strip_ticks(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("`", "")).strip()


def _clean_heading_candidate(raw_h: str, fallback: str) -> str:
    lines = [_strip_ticks(l).strip('"#*:- ') for l in (raw_h or "").splitlines() if _strip_ticks(l).strip('"#*:- ')]
    h = lines[0] if lines else ""
    low = h.lower().strip(" ?.!-:")
    if not h or len(h) < 8 or len(h) > 115 or low in _FORBIDDEN_TEMPLATE_HEADINGS:
        return fallback
    return h


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
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", "", raw.strip()).replace("`", "")
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
            line = re.sub(r"^\s*(?:[-•*—–]|\d+[\.\)])\s*", "", _strip_ticks(line)).strip()
            if len(line) > 5 and line.upper() not in {"YOK", "YOK.", "-"}:
                out.append(line)
        return out

    def _paras(txt: str) -> List[str]:
        out = []
        for p in re.split(r"\n\s*\n", txt or ""):
            p = _strip_ticks(p)
            if len(p) > 15 and p.upper() not in {"YOK", "YOK."}:
                out.append(p)
        if not out and (txt or "").strip():
            single = _strip_ticks(txt)
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
        k_clean = _strip_ticks(k).strip("*[]\"' ")
        aci_clean = _strip_ticks(aci).strip("*\"' ")
        if k_clean and aci_clean:
            kaynaklar.append({"kaynak": k_clean, "aci": aci_clean})

    rakamlar = []
    seen_vals = set()
    for b in _bullets(sec.get("RAKAMLAR", "")):
        if "|" in b:
            et, dg = b.split("|", 1)
        elif ":" in b:
            et, dg = b.split(":", 1)
        else:
            continue
        et_clean = _strip_ticks(et).strip("*\"' ")
        dg_clean = _strip_ticks(dg).strip("*\"' ")
        val_key = dg_clean.lower()
        if (
            et_clean
            and dg_clean
            and dg_clean.upper() not in {"YOK", "YOK.", "BELİRTİLMEDİ", "BELIRTILMEDI"}
            and val_key not in seen_vals
        ):
            seen_vals.add(val_key)
            rakamlar.append({"etiket": et_clean, "deger": dg_clean})

    baslik_lines = [_strip_ticks(l).strip('"#* ') for l in (sec.get("BASLIK") or "").splitlines() if _strip_ticks(l).strip('"#* ')]
    return {
        "baslik": baslik_lines[0] if baslik_lines else "",
        "ozet": " ".join(_paras(sec.get("OZET", ""))),
        "maddeler": _bullets(sec.get("MADDELER", "")),
        "h1": _clean_heading_candidate(sec.get("ARA_BASLIK_1", ""), "Gelişmenin Ayrıntıları ve Resmi Açıklamalar"),
        "ne_oldu": _paras(sec.get("BOLUM_1", "")),
        "h2": _clean_heading_candidate(sec.get("ARA_BASLIK_2", ""), "Kararın Sektörel ve Toplumsal Yansımaları"),
        "neden_onemli": _paras(sec.get("BOLUM_2", "")),
        "h3": _clean_heading_candidate(sec.get("ARA_BASLIK_3", ""), "Sürecin Geçmişi ve Kurumsal Çerçeve"),
        "arka_plan": _paras(sec.get("BOLUM_3", "")),
        "etki_baslik": _clean_heading_candidate(sec.get("ETKI_BASLIK", ""), "Sahaya ve Vatandaşa Yansıması"),
        "turkiye_etkisi": " ".join(_paras(sec.get("ETKI_METNI", ""))),
        "senaryo_baslik": _clean_heading_candidate(sec.get("SENARYO_BASLIK", ""), "Önümüzdeki Süreçte Öne Çıkan İhtimaller"),
        "senaryolar": _bullets(sec.get("SENARYOLAR", "")),
        "kaynaklar": kaynaklar,
        "rakamlar": rakamlar,
        "sonra_baslik": _clean_heading_candidate(sec.get("SONRA_BASLIK", ""), "Takvimdeki Sıradaki Adımlar"),
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


def _guard_check(data: Dict, sources: List[Dict]) -> Dict:
    """Doğruluk kalkanı: kaynakta olmayan sayılar ve kaynakta olmayan abartı kelimeleri."""
    import fact_guard
    src_text = " ".join(f"{s.get('title', '')} {s.get('body', '')}" for s in sources)
    allowed = fact_guard.source_number_set([src_text])
    texts = [str(data.get("baslik") or ""), str(data.get("ozet") or "")]
    for key in ("maddeler", "ne_oldu", "neden_onemli", "arka_plan", "senaryolar"):
        texts.extend(str(x) for x in (data.get(key) or []))
    for key in ("turkiye_etkisi", "sonra"):
        texts.append(str(data.get(key) or ""))
    for r in (data.get("rakamlar") or []):
        if isinstance(r, dict):
            texts.append(f"{r.get('etiket', '')} {r.get('deger', '')}")
    bad_nums = []
    for t in texts:
        for n in fact_guard.unverified_numbers(t, allowed):
            if n not in bad_nums:
                bad_nums.append(n)
    hype = fact_guard.hype_violations(str(data.get("baslik") or ""), src_text)
    return {"bad_nums": bad_nums, "hype": hype, "allowed": allowed, "src_text": src_text}


def _salvage(data: Dict, chk: Dict, primary_title: str) -> Dict:
    """Son çare: kaynakta olmayan sayı içeren cümleleri/satırları çıkarır; sorunlu başlığı kaynak başlıkla değiştirir."""
    import fact_guard
    allowed = chk["allowed"]
    for key in ("ne_oldu", "neden_onemli", "arka_plan"):
        cleaned = []
        for p in (data.get(key) or []):
            p2 = fact_guard.drop_unverified_sentences(str(p), allowed)
            if len(p2.split()) >= 8:
                cleaned.append(p2)
        data[key] = cleaned
    for key in ("maddeler", "senaryolar"):
        data[key] = [b for b in (data.get(key) or []) if not fact_guard.unverified_numbers(str(b), allowed)]
    for key in ("turkiye_etkisi", "sonra", "ozet"):
        data[key] = fact_guard.drop_unverified_sentences(str(data.get(key) or ""), allowed)
    data["rakamlar"] = [
        r for r in (data.get("rakamlar") or [])
        if isinstance(r, dict) and not fact_guard.unverified_numbers(f"{r.get('etiket', '')} {r.get('deger', '')}", allowed)
    ]
    title = str(data.get("baslik") or "")
    if fact_guard.unverified_numbers(title, allowed) or fact_guard.hype_violations(title, chk["src_text"]):
        data["baslik"] = primary_title
    return data


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
    # Uzunluğu kaynak belirler: haber modunda yalnızca boş/yarım yanıtları eleyen düşük bir taban
    min_raw_words = 360 if mode == "analysis" else 110
    primary_title = sources[0].get("title", "")

    now_ts = time.time()
    active_models = [m for m in MODELS if _MODEL_COOLDOWN_UNTIL.get(m, 0.0) <= now_ts]
    if not active_models:
        active_models = list(MODELS)

    feedback = ""
    guard_failures = 0
    last_data = None
    last_chk = None
    attempt_chain = [m for m in active_models for _ in (0, 1)]

    for step_i, m_name in enumerate(attempt_chain):
        if _MODEL_COOLDOWN_UNTIL.get(m_name, 0.0) > time.time():
            continue
        prompt = _build_prompt(sources, category, mode, feedback=feedback)
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

            chk = _guard_check(data, sources)
            if chk["bad_nums"] or chk["hype"]:
                guard_failures += 1
                last_data, last_chk = data, chk
                msg = []
                if chk["bad_nums"]:
                    msg.append("Kaynakta geçmeyen sayılar yazdın: " + ", ".join(chk["bad_nums"][:8]) + ". Bu sayıları ve onlara dayanan cümleleri tamamen çıkar.")
                if chk["hype"]:
                    msg.append("Başlıkta kaynakta geçmeyen abartı kelimesi kullandın: " + ", ".join(chk["hype"]) + ". Başlığı abartısız yaz.")
                feedback = " ".join(msg)
                print(f"🛡️ [Doğruluk Kalkanı] {m_name}: {feedback[:200]}")
                if guard_failures < 2:
                    continue
                # İkinci ihlalde: sorunlu cümleleri çıkararak kurtar
                data = _salvage(data, chk, primary_title)
                print("🛡️ [Doğruluk Kalkanı] Kaynakta olmayan sayı içeren cümleler çıkarıldı.")

            est_w = _estimate_data_words(data)
            if est_w < min_raw_words:
                print(f"⚠️ [Çok Kaynaklı] {m_name} yanıtı yetersiz ({est_w} kelime < {min_raw_words}); yeniden deneniyor.")
                continue
            data["_model"] = m_name
            return data
        except Exception as e:
            err_s = str(e)
            print(f"⚠️ [Çok Kaynaklı] {m_name} hatası: {err_s[:160]}")
            if "429" in err_s and ("quota" in err_s.lower() or "RESOURCE_EXHAUSTED" in err_s):
                _MODEL_COOLDOWN_UNTIL[m_name] = time.time() + 1200
                continue
            if step_i < len(attempt_chain) - 1 and ("503" in err_s or "UNAVAILABLE" in err_s):
                time.sleep(3.0)
            continue

    # Tüm denemeler doğruluk kalkanına takıldıysa son yanıtı temizleyerek kurtarmayı dene
    if last_data is not None and last_chk is not None:
        data = _salvage(last_data, last_chk, primary_title)
        if _estimate_data_words(data) >= min_raw_words and data.get("ne_oldu"):
            data["_model"] = "salvaged"
            return data
    return None


def _as_list(v) -> List[str]:
    if isinstance(v, list):
        return [_strip_ticks(str(x)) for x in v if _strip_ticks(str(x))]
    if isinstance(v, str) and v.strip():
        return [_strip_ticks(p) for p in re.split(r"\n\s*\n", v) if _strip_ticks(p)]
    return []


def _e(s) -> str:
    return _html.escape(_strip_ticks(str(s or "")), quote=True)


def _dedup_sections(data: Dict, src_words: int = 250, mode: str = "news") -> Dict:
    """
    Aynı cümlenin/bilginin BOLUM_1, BOLUM_2, BOLUM_3, ETKI_METNI ve SONRA alanlarında
    farklı kelimelerle tekrarlanmasını engeller; kısa tekil kaynaklı haberlerde zorlama kutuları kapatır.
    """
    seen_sets: List[set] = []

    def _sent_toks(s: str) -> set:
        return _tokens(s)

    def _is_redundant_para(p: str, thresh: float = 0.48) -> bool:
        t = _sent_toks(p)
        if len(t) < 4:
            return len((p or "").split()) < 8
        for prev in seen_sets:
            if not prev:
                continue
            ov = len(t & prev) / max(1, min(len(t), len(prev)))
            if ov >= thresh:
                return True
        seen_sets.append(t)
        return False

    # BOLUM_1 referans havuzunu oluşturur
    b1 = []
    for p in _as_list(data.get("ne_oldu")):
        if not _is_redundant_para(p, thresh=0.65):
            b1.append(p)
    data["ne_oldu"] = b1

    # BOLUM_2 ve BOLUM_3: BOLUM_1 ile yüksek örtüşen veya tek cümlelik dolgu paragrafları elenir
    for key in ("neden_onemli", "arka_plan"):
        kept = []
        for p in _as_list(data.get(key)):
            if len(p.split()) < 14:
                continue
            if not _is_redundant_para(p, thresh=0.45):
                kept.append(p)
        data[key] = kept

    # Kısa kaynaklı (<180 kelime) haberlerde arka_plan ve etki kutusu zorlama tekrar üretir -> kapat
    if mode != "analysis" and src_words < 180:
        data["arka_plan"] = []
        data["turkiye_etkisi"] = ""

    # ETKI_METNI ve SONRA: önceki bölümlerle örtüşüyorsa veya yeni somut bilgi taşımıyorsa basma
    for key in ("turkiye_etkisi", "sonra"):
        val = " ".join(_as_list(data.get(key))).strip()
        if not val or val.upper() in {"YOK", "YOK."} or len(val.split()) < 14:
            data[key] = ""
            continue
        if _is_redundant_para(val, thresh=0.42):
            data[key] = ""
        else:
            data[key] = val

    return data


def render_html(data: Dict, sources: List[Dict], mode: str = "news") -> str:
    """Yapılandırılmış veriyi konuya özgü ara başlıklarla temiz .ga-multi HTML gövdesine çevirir."""
    src_words = len(" ".join(s.get("body") or "" for s in (sources or [])).split())
    data = _dedup_sections(dict(data), src_words=src_words, mode=mode)
    parts = ['<div class="ga-multi">']

    bullets = _as_list(data.get("maddeler"))[:3]
    _body_words = len(" ".join(
        _as_list(data.get("ne_oldu")) + _as_list(data.get("neden_onemli")) + _as_list(data.get("arka_plan")) + _as_list(data.get("sonra"))
    ).split())
    # Özet kutusu yalnızca okunacak kadar uzun haberlerde anlamlı; kısa haberde metni tekrar eder
    if bullets and len(bullets) >= 2 and _body_words >= 220:
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

    section(data.get("h1") or "Gelişmenin Ayrıntıları ve İlk Açıklamalar", _as_list(data.get("ne_oldu")))
    section(data.get("h2") or "Kararın Sektörel ve Toplumsal Yansımaları", _as_list(data.get("neden_onemli")))
    section(data.get("h3") or "Sürecin Geçmişi ve Kurumsal Çerçeve", _as_list(data.get("arka_plan")))

    tr = " ".join(_as_list(data.get("turkiye_etkisi")))
    if tr and tr.upper() not in {"YOK", "YOK."}:
        etki_h = _strip_ticks(data.get("etki_baslik") or "Sahaya ve Vatandaşa Yansıması")
        icon = "🇹🇷 " if ("türkiye" in etki_h.lower() and not etki_h.startswith("🇹🇷")) else ("📌 " if not re.match(r"^[\W_]", etki_h) else "")
        parts.append(
            f'<div class="ga-box ga-tr"><h4 class="ga-box-title">{icon}{_e(etki_h)}</h4><p>{_e(tr)}</p></div>'
        )

    if mode == "analysis":
        scen = _as_list(data.get("senaryolar"))[:4]
        if scen:
            scen_h = data.get("senaryo_baslik") or "Önümüzdeki Süreçte Öne Çıkan İhtimaller"
            parts.append(
                f'<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">{_e(scen_h)}</h3><ol class="ga-list">'
                + "".join(f"<li>{_e(s)}</li>" for s in scen)
                + "</ol>"
            )

    # Yalnızca >= 3 farklı somut sayısal veri olduğunda veri tablosu göster (1-2 verilik haberlerde tekrarı önler)
    nums = [
        r
        for r in (data.get("rakamlar") or [])
        if isinstance(r, dict) and r.get("etiket") and r.get("deger")
    ][:6]
    if len(nums) >= 3:
        parts.append(
            '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Öne Çıkan Veriler</h3><div class="ga-table-wrap"><table class="ga-table"><tbody>'
            + "".join(f"<tr><td>{_e(r['etiket'])}</td><td><strong>{_e(r['deger'])}</strong></td></tr>" for r in nums)
            + "</tbody></table></div>"
        )

    section(data.get("sonra_baslik") or "Takvimdeki Sıradaki Adımlar", _as_list(data.get("sonra")))

    # Kaynak karşılaştırması / şeffaf kaynak bağlantısı (yazının sonunda, ters tırnaksız tertemiz kutu)
    link_by_name = {}
    for s in sources:
        link_by_name.setdefault((s.get("name") or "").strip().lower(), s.get("link") or "")

    rows = []
    for k in (data.get("kaynaklar") or []):
        if not isinstance(k, dict):
            continue
        name = _strip_ticks(k.get("kaynak") or "").strip("*[] ")
        aci = _strip_ticks(k.get("aci") or "").strip()
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

    if not rows and sources:
        for s in sources:
            s_name = _strip_ticks(s.get("name") or "")
            s_title = _strip_ticks(s.get("title") or "")
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
            '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Kaynakların Öne Çıkardığı Detaylar</h3><ul class="ga-sources">'
            + "".join(rows)
            + "</ul>"
        )
    elif len(rows) == 1:
        parts.append('<ul class="ga-sources mt-6">' + rows[0] + "</ul>")

    parts.append("</div>")
    return "\n".join(parts)


LAST_REJECT_REASON = ""


def build_article(primary: Dict, primary_body: str, pool: List[Dict], category: str, mode: str = "news") -> Optional[Dict]:
    """
    Uçtan uca: kaynakları topla -> Gemini 3.5 ile yaz -> HTML'e çevir.
    Dönüş: {"title","summary","content","category","source_count","sources","sibling_items"} veya None
    None dönerse LAST_REJECT_REASON: "thin_source" (kaynak yetersiz, haber atlanmalı) | "ai_failed" | "too_short"
    """
    global LAST_REJECT_REASON
    LAST_REJECT_REASON = ""
    import content_quality
    import fact_guard
    sources = gather_sources(primary, primary_body, pool)
    for s in sources:
        s["body"] = fact_guard.strip_source_junk(s.get("body") or "")
    total_input_words = len((" ".join(f"{s['title']} {s['body']}" for s in sources)).split())
    body_words = len((" ".join(s.get("body") or "" for s in sources)).split())
    # Kaynak yeterliliği: tek cümlelik kaynaktan haber şişirilmez. Ya ikinci bir kaynak olmalı ya da metin yeterli olmalı.
    min_body = 70 if mode == "analysis" else 90
    if total_input_words < 18 or (body_words < min_body and len(sources) < 2):
        LAST_REJECT_REASON = "thin_source"
        print(f"⏩ [Çok Kaynaklı] Kaynak metin yetersiz ({body_words} kelime, {len(sources)} kaynak); şişirme yapılmaz, haber atlandı.")
        return None
    data = generate(sources, category=category, mode=mode)
    if not data:
        LAST_REJECT_REASON = "ai_failed"
        return None
    title = content_quality.clean_title_text(_strip_ticks(str(data.get("baslik") or "")))
    if not (15 <= len(title) <= 140):
        title = content_quality.clean_title_text(primary.get("title", ""))
    try:
        title = fact_guard.to_turkish_sentence_case(title, " ".join(f"{s['title']}. {s['body']}" for s in sources))
    except Exception:
        pass
    summary = content_quality.clean_title_text(_strip_ticks(str(data.get("ozet") or "")))
    body = render_html(data, sources, mode=mode)
    content = content_quality.clean_article_html(body)
    words = content_quality.visible_word_count(content)
    min_words = 380 if mode == "analysis" else 170
    if words < min_words:
        LAST_REJECT_REASON = "too_short"
        print(f"⚠️ [Çok Kaynaklı] Metin kısa kaldı ({words} kelime < {min_words}); haber atlandı.")
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
        "bullets": _as_list(data.get("maddeler"))[:4],
        "sibling_items": [s["_raw_item"] for s in sources[1:] if s.get("_raw_item")],
    }
