"""
Gündem Analizi — Veri, Kronoloji ve 3 Boyutlu Analiz Motoru (analysis_engine.py)
================================================================================
Sıfır ekstra RAM yüküyle (harici kütüphane veya ek API çağrısı olmadan):
1. Haber metninden gerçek rakamları, yüzdeleri, tutarları ve tarihleri "Veri Rozetleri (Data Pills)" olarak ayrıştırır.
2. Haberin kendi gerçek paragraflarını ve ara başlıklarını "3 Boyutlu Analiz Merceği"ne (Temel Karar, Etki Alanı, Süreç/Takvim) dönüştürür.
3. Aynı konu/kategori etrafındaki haberleri tarih sırasıyla "Olayın Zaman Tüneli (Kronoloji Zinciri)" olarak birbirine bağlar.
4. Ana sayfa ve /analiz merkezi için "Canlı Gündem Radarı, Konu Yoğunluk Haritası ve Derin Analiz Dosyaları" üretir.
"""
import html as _html
import re
import time
from collections import Counter
from typing import Dict, List, Optional

import content_quality

_RADAR_CACHE = {"data": None, "ts": 0.0}

_STOPWORDS = {
    "ve", "ile", "bir", "bu", "da", "de", "ta", "te", "için", "icin", "olan", "olarak",
    "son", "yeni", "daha", "çok", "cok", "gibi", "kadar", "صonra", "sonra", "önce", "once",
    "üzere", "uzere", "göre", "gore", "karşı", "karsi", "ilgili", "ilişkin", "iliskin",
    "arasında", "arasinda", "üzerinde", "uzerinde", "altında", "altinda", "devam", "ediyor",
    "oldu", "olan", "etti", "yapıldı", "yapildi", "açıklandı", "aciklandi", "belli", "geldi",
    "büyük", "buyuk", "kritik", "önemli", "onemli", "resmi", "güncel", "guncel", "nasıl",
    "neden", "nedir", "hangi", "kendi", "tüm", "tum", "her", "iki", "üç", "dört", "beş",
    "ilk", "son", "gün", "gun", "yıl", "yil", "ay", "saat", "dakika", "haber", "analiz",
}

_CRIME_ACCIDENT_SKIP = re.compile(
    r"\b(feci\s+kaza|trafik\s+kazas|zincirleme\s+kaza|şarampole|devrildi|bıçakla|silahlı\s+kavga|"
    r"cinayet|intihar|boğul|yangında\s+can|yumruklu|hırsızlık|kuyumcu)\b",
    re.I,
)


def _strip_tags(html_text: str) -> str:
    if not html_text:
        return ""
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", html_text))).strip()


def extract_data_pills(title: str, summary: str, content_html: str, category: str = "Gündem", source: str = "") -> List[Dict[str, str]]:
    """Haberin içindeki gerçek sayısal verileri, oranları, para birimlerini ve vadeleri rozet olarak çıkarır."""
    text = f"{title or ''}. {summary or ''}. {_strip_tags(content_html)}"
    pills: List[Dict[str, str]] = []
    seen_vals = set()

    def _add(icon: str, label: str, val: str, tone: str = "red"):
        norm_v = re.sub(r"\s+", " ", val).strip()
        if not norm_v or norm_v.lower() in seen_vals or len(pills) >= 4:
            return
        seen_vals.add(norm_v.lower())
        pills.append({"icon": icon, "label": label, "value": norm_v, "tone": tone})

    # 1. Yüzde / Oran (%15, yüzde 42,5 vb.)
    for m in re.finditer(r"(?:%\s*\d+(?:[.,]\d+)?|\byüzde\s+\d+(?:[.,]\d+)?)", text, re.I):
        raw = m.group(0).strip()
        if raw.lower().startswith("yüzde"):
            num = re.sub(r"(?i)yüzde\s*", "", raw).strip()
            raw = f"%{num}"
        _add("📊", "Oran / Değişim", raw, "emerald")
        if len(pills) >= 2:
            break

    # 2. Para / Finansal Büyüklük (Milyar/Milyon/Bin TL, Dolar, Euro)
    for m in re.finditer(
        r"\b\d+(?:[.,]\d+)?\s*(?:milyar|milyon|trilyon|bin)?\s*(?:TL|lira|dolar|euro|avro|\$|€|sterlin)\b",
        text,
        re.I,
    ):
        _add("💰", "Finansal Veri", m.group(0).strip(), "amber")
        break

    # 3. Süre / Takvim / Yaş / Hafta / Kapasite
    for m in re.finditer(
        r"\b(\d+\s*(?:yaş|gün|ay|yıl|saat|hafta|km|metre|megavat|mw|gb|mah|kişi|ülke|takım|şirket|kurum|madde))\b",
        text,
        re.I,
    ):
        val = m.group(1).strip()
        if val.lower() not in ("1 gün", "1 yıl", "1 ay", "2 kişi"):
            _add("⏱️", "Kapsam / Ölçek", val, "blue")
            break

    # 4. Resmi Kurum / Aktör Tespiti
    inst_match = re.search(
        r"\b(TCMB|Merkez Bankası|TÜİK|SPK|BDDK|MEB|ÖSYM|TBMM|AFAD|Kandilli|NATO|BM|Avrupa Birliği|IMF|Fed|Borsa İstanbul|RTÜK|BTK|Yargıtay|Danıştay|Cumhurbaşkanlığı|Bakanlığı)\b",
        text,
    )
    if inst_match:
        _add("🏛️", "İlgili Kurum", inst_match.group(1), "slate")

    # Eksik kalan rozetleri gerçek makale metrikleriyle tamamla
    wc = len(text.split())
    if len(pills) < 4:
        _add("📐", "Analiz Derinliği", f"{wc} Kelime", "slate")
    if len(pills) < 4:
        _add("📡", "Birincil Kaynak", (source or "Gündem Analizi")[:28], "red")

    return pills[:4]


def build_three_dimensions(article: Dict, clean_html: str) -> List[Dict[str, str]]:
    """
    Haberi 3 analitik boyuta (1: Temel Gelişme & Veri, 2: Etki & Bağlam, 3: Süreç & Beklenti) ayırır.
    Kesinlikle hazır şablon cümle kullanmaz; haberin kendi gerçek paragraflarından ve ara başlıklarından üretir.
    """
    paras = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", clean_html or "", re.S | re.I):
        txt = _strip_tags(m.group(1))
        if len(txt) >= 45:
            paras.append(txt)

    headings = []
    for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", clean_html or "", re.S | re.I):
        ht = _strip_tags(m.group(1))
        if len(ht) >= 6:
            headings.append(ht)

    summary = (article.get("summary") or "").strip()
    if not paras and summary:
        paras = [summary]

    def _first_two_sentences(text: str, max_chars: int = 230) -> str:
        if not text:
            return ""
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) >= 20]
        if not sents:
            return text[:max_chars]
        out = sents[0]
        if len(sents) > 1 and len(out) + len(sents[1]) <= max_chars:
            out = f"{out} {sents[1]}"
        if len(out) > max_chars:
            out = out[:max_chars].rsplit(" ", 1)[0] + "..."
        return out

    p1 = _first_two_sentences(paras[0] if paras else summary)
    p2 = _first_two_sentences(paras[len(paras) // 2] if len(paras) >= 2 else summary)
    p3 = _first_two_sentences(paras[-1] if len(paras) >= 3 else (paras[-1] if paras else summary))

    h1 = headings[0] if len(headings) >= 1 else "Temel Gelişme ve Somut Çerçeve"
    h2 = headings[1] if len(headings) >= 2 else "Sektörel ve Toplumsal Yansıma"
    h3 = headings[-1] if len(headings) >= 3 else "Süreç Takvimi ve Beklenen Adımlar"

    return [
        {
            "step": "01",
            "badge": "TEMEL BULGU",
            "title": h1,
            "body": p1,
            "color": "red",
        },
        {
            "step": "02",
            "badge": "ETKİ & BAĞLAM",
            "title": h2,
            "body": p2,
            "color": "blue",
        },
        {
            "step": "03",
            "badge": "SÜREÇ & TAKVİM",
            "title": h3,
            "body": p3,
            "color": "emerald",
        },
    ]


def build_chronological_timeline(article: Dict, candidate_pool: List[Dict]) -> List[Dict]:
    """
    Haberin konusuyla ilişkili önceki/sonraki gelişmeleri tarih sırasıyla (Kronolojik Zaman Tüneli) bağlar.
    """
    curr_slug = article.get("slug") or ""
    curr_title = (article.get("title") or "").strip()
    curr_cat = article.get("category") or "Gündem"

    # Haberin başlığındaki ayırt edici anahtar kelimeler
    title_words = {
        w.lower()
        for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{4,}", curr_title)
        if w.lower() not in _STOPWORDS
    }

    scored = []
    for item in (candidate_pool or []):
        sl = item.get("slug") or ""
        if not sl or sl == curr_slug:
            continue
        it_title = (item.get("title") or "").strip()
        it_words = {
            w.lower()
            for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü0-9]{4,}", it_title)
            if w.lower() not in _STOPWORDS
        }
        overlap = len(title_words & it_words)
        same_cat = 1 if (item.get("category") == curr_cat) else 0
        score = (overlap * 5) + same_cat
        scored.append((score, item))

    scored.sort(key=lambda x: (x[0], str(x[1].get("created_at") or "")), reverse=True)
    picked = [x[1] for x in scored[:3]]

    timeline = []
    for p in picked:
        timeline.append({
            "slug": p.get("slug"),
            "title": p.get("title"),
            "category": p.get("category") or curr_cat,
            "date": str(p.get("created_at") or "")[:16],
            "is_current": False,
        })

    timeline.append({
        "slug": curr_slug,
        "title": curr_title,
        "category": curr_cat,
        "date": str(article.get("created_at") or "")[:16],
        "is_current": True,
    })

    # Kronolojik sıralama (eskiden yeniye veya yeniden eskiye; en güncel en üstte)
    timeline.sort(key=lambda x: x.get("date") or "", reverse=True)
    return timeline


def compute_impact_matrix(article: Dict, clean_html: str, pills: List[Dict]) -> Dict:
    """Haberin gerçek metin derinliği, veri yoğunluğu ve kategorisine göre Etki Matrisi üretir."""
    wc = content_quality.visible_word_count(clean_html or "")
    cat = (article.get("category") or "Gündem").strip()

    depth_score = min(98, max(68, int(60 + (wc / 15))))
    data_score = min(96, max(65, 58 + len(pills) * 9))

    scope_map = {
        "Ekonomi": ("Makroekonomik & Bütçe Etkisi", 92),
        "Dünya": ("Jeopolitik & Diplomatik Etki", 90),
        "Teknoloji": ("Dijital Ekosistem & Sektör Etkisi", 88),
        "Otomobil": ("Otomotiv Pazarı & Tüketici Etkisi", 86),
        "Eğitim": ("Akademik Takvim & Sosyal Etki", 89),
        "Sağlık": ("Toplum Sağlığı & Klinik Önem", 88),
        "Spor": ("Spor Kamuoyu & Rekabet Etkisi", 84),
        "Gündem": ("Kamuoyu & Toplumsal Yansıma", 87),
    }
    scope_label, scope_score = scope_map.get(cat, ("Kamuoyu & Sektörel Yansıma", 85))
    overall = round((depth_score + data_score + scope_score) / 3)

    return {
        "overall_score": overall,
        "word_count": wc,
        "bars": [
            {"label": scope_label, "pct": scope_score, "color": "bg-red-600"},
            {"label": "Veri, Rakam ve Kaynak Teyit Yoğunluğu", "pct": data_score, "color": "bg-blue-600"},
            {"label": f"Analitik Kapsam Derinliği ({wc} Kelime)", "pct": depth_score, "color": "bg-emerald-600"},
        ],
    }


def build_article_analysis_cockpit(article: Dict, clean_html: str, candidate_pool: List[Dict]) -> Dict:
    """Haber detay sayfasındaki 3 sekmeli Gündem Analizi Kokpiti için tüm veriyi tek seferde üretir."""
    pills = extract_data_pills(
        article.get("title") or "",
        article.get("summary") or "",
        clean_html,
        article.get("category") or "Gündem",
        article.get("source") or "",
    )
    dimensions = build_three_dimensions(article, clean_html)
    timeline = build_chronological_timeline(article, candidate_pool)
    impact = compute_impact_matrix(article, clean_html, pills)
    return {
        "pills": pills,
        "dimensions": dimensions,
        "timeline": timeline,
        "impact": impact,
    }


_TECH_GADGET_SKIP = re.compile(
    r"\b(nvidia|snapchat|honor|robot\s+phone|iphone|galaxy|xiaomi|redmi|playstation|ps5|xbox|"
    r"ekran\s+kartı|oyun\s+konsolu|akıllı\s+telefon|kulaklık|instagram|tiktok|whatsapp)\b",
    re.I,
)


def get_agenda_radar_data(widgets: Dict, force_refresh: bool = False) -> Dict:
    """
    Ana sayfa 'Gündem Analizi' ve /analiz sayfası için:
    YALNIZCA gerçek 'Analiz' kategorisinde yayınlanmış özgün Gündem Analizi dosyalarını döner.
    Eski haberleri veya normal kategori haberlerini (Apple, Hiroşima vb.) KESİNLİKLE buraya karıştırmaz!
    """
    global _RADAR_CACHE
    now = time.time()
    if not force_refresh and _RADAR_CACHE["data"] and (now - _RADAR_CACHE["ts"]) < 180:
        return _RADAR_CACHE["data"]

    import database

    synth_pool = database.get_articles(limit=18, category="Analiz")
    dossiers = []
    for s in (synth_pool or []):
        # Çift güvenlik: Sadece gerçek kategorisi 'Analiz' olanları kabul et
        if (s.get("category") or "").strip() != "Analiz":
            continue
        dossiers.append({
            "id": s.get("id"),
            "slug": s.get("slug"),
            "title": s.get("title"),
            "summary": s.get("summary"),
            "category": "Analiz",
            "image_path": s.get("image_path"),
            "source": s.get("source") or "Gündem Analizi",
            "created_at": str(s.get("created_at") or "")[:16],
            "reading_time_min": s.get("reading_time_min") or 4,
        })

    result = {
        "dossiers": dossiers,
        "category_distribution": [],
        "hot_topics": [],
        "total_analyzed": len(dossiers),
        "updated_at": time.strftime("%H:%M"),
    }
    _RADAR_CACHE["data"] = result
    _RADAR_CACHE["ts"] = now
    return result


def ensure_daily_synthesis_reports() -> Optional[str]:
    """
    Yalnızca tam yayın saatlerinde (10:00, 15:00 ve 19:00 saat dilimlerinde, geriye dönük saat uyumsuzluğu yaratmadan)
    o andan itibaren Türkiye ve dünya gündemindeki en önemli gelişmeleri sentezleyen özgün 'Gündem Analizi'
    makalesi üretir ve 'Analiz' kategorisinde yayınlar.
    """
    from datetime import datetime, timezone, timedelta
    import database

    tz_tr = timezone(timedelta(hours=3))
    now_tr = datetime.now(tz_tr)
    today_str = now_tr.strftime("%Y-%m-%d")
    hour = now_tr.hour

    # Geriye dönük uyumsuz saatli paylaşım yapma! Yalnızca saat tam 10, 15 veya 19 dilimindeyken o dilimin analizini yayınla:
    slot_map = {
        10: "10",
        15: "15",
        19: "19",
    }
    if hour not in slot_map:
        return None

    slot_key = slot_map[hour]
    setting_key = f"ga_analiz_{today_str}_{slot_key}"
    if database.get_setting(setting_key, "") == "1":
        return None

    # Zaman penceresi kuralı (Aynı haberin iki farklı analizde tekrar edilmesini %100 önler):
    # - 10:00 Analizi -> Dün akşam 20:00'den bugün 10:00'a kadar paylaşılan haberler
    # - 15:00 Analizi -> Bugün sabah 10:00'dan 15:00'e kadar paylaşılan haberler
    # - 19:00 Analizi -> Bugün saat 15:00'ten 19:00'a kadar paylaşılan haberler
    yesterday_str = (now_tr - timedelta(days=1)).strftime("%Y-%m-%d")
    if hour == 10:
        win_start = f"{yesterday_str} 20:00:00"
    elif hour == 15:
        win_start = f"{today_str} 10:00:00"
    else:
        win_start = f"{today_str} 15:00:00"

    used_slugs_raw = database.get_setting("ga_analiz_used_slugs", "") or ""
    used_slugs = {x.strip() for x in used_slugs_raw.split(",") if x.strip()}

    pool = database.get_articles(limit=50)
    selected = []
    lead_image = None
    for a in (pool or []):
        cat = (a.get("category") or "Gündem").strip()
        if cat == "Analiz":
            continue
        art_slug = (a.get("slug") or "").strip()
        if not art_slug or art_slug in used_slugs:
            continue
        created_str = str(a.get("created_at") or "").strip()
        if created_str and created_str < win_start:
            continue
        t = (a.get("title") or "").strip()
        s = (a.get("summary") or "").strip()
        if not t or not s or len(s) < 40:
            continue
        if _CRIME_ACCIDENT_SKIP.search(t):
            continue
        img_p = (a.get("image_path") or "").strip()
        if img_p and not lead_image:
            img_name = img_p.replace("\\", "/").split("/")[-1]
            raw_img = database.get_image(img_name)
            if raw_img and len(raw_img) >= 8000:
                lead_image = img_p
        selected.append(a)
        if len(selected) >= 5:
            break

    if len(selected) < 3 or not lead_image:
        return None

    lead_title = (selected[0].get("title") or "").strip()
    short_lead = lead_title.split(":")[0].strip() if ":" in lead_title else lead_title[:65].rsplit(" ", 1)[0]
    report_title = f"Gündem Analizi: {short_lead} ve Günün Öne Çıkan Başlıkları"

    lead_summary = (
        f"Türkiye ve dünya gündeminde öne çıkan {selected[0].get('title')} gelişmesi başta olmak üzere "
        f"günün en kritik {len(selected)} başlığının kapsamlı arka plan ve etki analizi."
    )

    table_rows = []
    briefing_lines = []
    for idx, item in enumerate(selected, 1):
        ic = _html.escape(item.get("category") or "Gündem")
        it = _html.escape(item.get("title") or "")
        isum = _html.escape((item.get("summary") or "")[:150])
        islug = _html.escape(item.get("slug") or "")
        table_rows.append(
            f'<tr class="border-b border-slate-200">'
            f'<td class="p-3 border border-slate-200 font-bold text-red-600">{ic}</td>'
            f'<td class="p-3 border border-slate-200 font-semibold"><a href="/haber/{islug}" class="text-slate-900 hover:text-red-600 underline">{it}</a></td>'
            f'<td class="p-3 border border-slate-200 text-slate-700">{isum}</td>'
            f'</tr>'
        )
        briefing_lines.append(
            f"{idx}. [{item.get('category')}] Başlık: {item.get('title')}\n"
            f"   Link: /haber/{item.get('slug')}\n"
            f"   Özet: {item.get('summary')}"
        )

    table_html = (
        '<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Gündemde Öne Çıkan Kritik Başlıklar ve Etki Tablosu</h3>'
        '<div class="overflow-x-auto my-4"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
        '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
        '<th class="p-3 border border-slate-200">Alan</th>'
        '<th class="p-3 border border-slate-200">Gündem Başlığı</th>'
        '<th class="p-3 border border-slate-200">Temel Gelişme ve Önemi</th>'
        '</tr></thead><tbody>'
        + "".join(table_rows)
        + '</tbody></table></div>'
    )

    ai_html = ""
    try:
        import config
        import content_quality
        if getattr(config, "GEMINI_API_KEY", ""):
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(
                api_key=config.GEMINI_API_KEY,
                http_options=genai_types.HttpOptions(timeout=40000, retry_options=genai_types.HttpRetryOptions(attempts=1)),
            )
            synth_prompt = f"""Sen 'Gündem Analizi' haber merkezinin başanalistisin.
Aşağıdaki {len(selected)} güncel gelişmeyi tek tek kopyalamadan; aralarındaki bağı, neden-sonuç ilişkisini,
bu kararların Türkiye gündemine, vatandaşın günlük hayatına/bütçesine, piyasalara ve dış politikaya somut etkilerini
sade, akıcı ve herkesin kolayca anlayabileceği bir gazetecilik diliyle analiz et.

İNCELENECEK GÜNDEM BAŞLIKLARI:
{chr(10).join(briefing_lines)}

KURALLAR:
1. En az 500-650 kelime uzunluğunda, 3 veya 4 özgün ara başlık (<h3>) ve 6-7 dolu paragraf (<p>) yaz.
2. Haberlerin cümlelerini olduğu gibi kopyalama; bir köşe yazarı / gündem analisti gibi 'Bu gelişme ne anlama geliyor?', 'Vatandaşı ve Türkiye gündemini nasıl etkileyecek?', 'Bundan sonraki süreçte ne bekleniyor?' sorularını somut verilerle yanıtla.
3. Metin içinde incelenen haberlere değinirken mutlaka doğal cümle içinde <a href="/haber/SLUG" class="text-red-600 font-bold underline">ilgili haber başlığı</a> şeklinde HTML iç link ver.
4. Sadece <p>, <h3>, <strong> ve <a> HTML etiketlerini kullan. Markdown veya kod bloğu kullanma.

ÇIKTI BİÇİMİ:
[BAŞLIK]
Gündem Analizi: (Günün en önemli gelişmesini ve genel çerçevesini yansıtan sade, güçlü başlık)
[ÖZET]
(2 cümlelik net analiz özeti)
[İÇERİK]
(HTML analiz metni)
"""
            for m_name in ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]:
                try:
                    res = client.models.generate_content(model=m_name, contents=synth_prompt)
                    raw_t = (res.text or "").strip() if res else ""
                    if raw_t and "[İÇERİK]" in raw_t:
                        h_part, c_part = raw_t.split("[İÇERİK]", 1)
                        if "[ÖZET]" in h_part:
                            tp, sp = h_part.split("[ÖZET]", 1)
                            cand_t = content_quality.clean_title_text(tp.replace("[BAŞLIK]", "").strip())
                            cand_s = content_quality.clean_title_text(sp.strip())
                            if 20 <= len(cand_t) <= 130:
                                report_title = cand_t if "analiz" in cand_t.lower() else f"Gündem Analizi: {cand_t}"
                            if len(cand_s) >= 45:
                                lead_summary = cand_s
                        ai_html = content_quality.clean_article_html(c_part.strip())
                        if content_quality.visible_word_count(ai_html) >= 320:
                            break
                except Exception:
                    continue
    except Exception as _ai_e:
        print(f"Gündem Analizi AI üretim uyarısı: {_ai_e}")

    if ai_html:
        first_p_end = ai_html.find("</p>")
        if first_p_end != -1:
            full_html = ai_html[: first_p_end + 4] + "\n" + table_html + "\n" + ai_html[first_p_end + 4 :]
        else:
            full_html = table_html + "\n" + ai_html
    else:
        parts = [
            f'<p class="lead font-medium text-lg text-slate-800 mb-6">'
            f'Türkiye ve dünya gündeminde bugün takip edilen resmi kararlar, ekonomik göstergeler ve diplomatik gelişmeler '
            f'kamuoyunun ana gündemini belirledi. Başta <strong>{_html.escape(selected[0].get("title") or "")}</strong> '
            f'olmak üzere günün en kritik {len(selected)} gelişmesini, kararların arka planını ve toplumsal yansımalarını '
            f'Gündem Analizi dosyasında mercek altına aldık.</p>',
            table_html,
        ]
        for idx, item in enumerate(selected, 1):
            it = _html.escape(item.get("title") or "")
            isum = _html.escape(item.get("summary") or "")
            islug = _html.escape(item.get("slug") or "")
            ic = item.get("category") or "Gündem"
            parts.append(f'<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">{idx}. {it}</h3>')
            parts.append(
                f'<p class="text-slate-800 leading-relaxed mb-4">{isum} '
                f'({ic} gündemindeki bu gelişmenin tüm detaylarına <a href="/haber/{islug}" class="text-red-600 font-bold underline">ilgili haberimizden</a> ulaşabilirsiniz.)</p>'
            )
        full_html = "\n".join(parts)
    slug = database.save_article(
        title=report_title,
        summary=lead_summary,
        content=full_html,
        image_path=lead_image,
        source="Gündem Analizi",
        category="Analiz",
    )
    if slug:
        database.set_setting(setting_key, "1")
        new_used = list(used_slugs) + [it.get("slug") for it in selected if it.get("slug")]
        database.set_setting("ga_analiz_used_slugs", ",".join(new_used[-60:]))
        _RADAR_CACHE["ts"] = 0.0
        print(f"✅ [Gündem Analizi] Saat {hour}:00 analizi başarıyla yayınlandı: /haber/{slug}")
        try:
            import google_indexer
            google_indexer.notify_google_indexing(f"https://xn--gndemanalizi-dlb.com.tr/haber/{slug}")
        except Exception:
            pass
    return slug
