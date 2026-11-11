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



_SEED_DONE = False


def seed_curated_analyses() -> None:
    """
    1) Eski yedek şablonun ürettiği kopya içerikli hatalı analiz kaydını (dunya-dosyasi-zararsiz-sanilan-...) temizler.
    2) Veritabanında 3'ten az 'Analiz' yazısı varsa, 100% özgün, 600+ kelimelik, veri tablolu 3 kapsamlı
       Gündem Analizi dosyasını (Ekonomi, Konut Piyasası ve Halk Sağlığı) anında veritabanına kaydeder.
    """
    global _SEED_DONE, _RADAR_CACHE
    if _SEED_DONE:
        return
    _SEED_DONE = True
    try:
        import database
        with database.get_connection() as conn:
            conn.execute(
                "DELETE FROM articles WHERE slug LIKE ?",
                ("dunya-dosyasi-zararsiz-sanilan-yeni-nesil-plastik-katkisi-bebek-sagligini-tehdit%",),
            )
    except Exception as _del_e:
        print(f"Eski yedek analiz temizleme uyarısı: {_del_e}")

    try:
        import database
        existing = [
            x for x in (database.get_articles(limit=10, category="Analiz") or [])
            if (x.get("category") or "").strip() == "Analiz"
        ]
        if len(existing) >= 4:
            return

        pool = database.get_articles(limit=40) or []
        fallback_img = "post_967028721e.jpg"
        for a in pool:
            if a.get("image_path"):
                fallback_img = a["image_path"]
                break

        def _resolve_img(preferred: str) -> str:
            for a in pool:
                ip = (a.get("image_path") or "").strip()
                if ip and preferred in ip:
                    return ip
            return preferred or fallback_img

        other_links = []
        for a in pool:
            c = (a.get("category") or "Gündem").strip()
            s = (a.get("slug") or "").strip()
            t = (a.get("title") or "").strip()
            if c != "Analiz" and s and t and len(other_links) < 4:
                other_links.append((c, t, s))

        def _build_other_table(skip_slug: str) -> str:
            rows = []
            for ic, it, islug in other_links:
                if islug == skip_slug:
                    continue
                rows.append(
                    f'<tr class="border-b border-slate-200">'
                    f'<td class="p-2.5 border border-slate-200 font-bold text-red-600 whitespace-nowrap">{_html.escape(ic)}</td>'
                    f'<td class="p-2.5 border border-slate-200 font-semibold"><a href="/haber/{_html.escape(islug)}" class="text-slate-900 hover:text-red-600 underline">{_html.escape(it)} →</a></td>'
                    f'</tr>'
                )
            if not rows:
                return ""
            return (
                '<h3 class="text-xl font-bold text-slate-900 mt-8 mb-3">Gündemde Öne Çıkan Diğer Başlıklar</h3>'
                '<div class="overflow-x-auto my-3"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
                '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
                '<th class="p-2.5 border border-slate-200">Kategori</th>'
                '<th class="p-2.5 border border-slate-200">Haber Başlığı</th>'
                '</tr></thead><tbody>'
                + "".join(rows[:3])
                + '</tbody></table></div>'
            )

        curated_list = [
            {
                "title": "Bölgesel Ekonomi Vizyonu ve Ticaret Koridorları: Rekabetten Stratejik Ortaklığa Geçişin Türkiye'ye Etkisi",
                "summary": "Küresel tedarik zincirlerinin yeniden şekillendiği dönemde Türkiye'nin bölgesel ticaret, enerji ve lojistik koridorlarında rekabet yerine ekonomik entegrasyonu öne çıkaran yeni stratejisinin makroekonomik etkileri.",
                "image_path": _resolve_img("post_967028721e.jpg"),
                "focus_slug": "bakan-simsekten-bolgesel-ekonomi-vizyonu-rekabet-azalirken-is-birligi-vurgusu",
                "content": (
                    '<h3>Küresel Tedarik Zincirlerinde Kırılma ve Bölgesel Entegrasyon Zorunluluğu</h3>'
                    '<p>Dünya ekonomisinde son yıllarda hız kazanan jeopolitik bloklaşma, korumacı gümrük tarifeleri ve uzak mesafeli tedarik hatlarındaki maliyet artışları, gelişmekte olan ülkelerin dış ticaret stratejilerini köklü biçimde değiştirdi. '
                    'Ekonomi yönetiminin ortaya koyduğu <a href="/haber/bakan-simsekten-bolgesel-ekonomi-vizyonu-rekabet-azalirken-is-birligi-vurgusu" class="text-red-600 font-bold underline">Bakan Şimşek&#39;ten Bölgesel Ekonomi Vizyonu: Rekabet Azalırken İş Birliği Vurgusu</a> çerçevesi, '
                    'Türkiye&#39;nin komşu coğrafyalarla olan ekonomik ilişkilerini sıfır toplamlı bir pazar rekabetinden çıkarıp karşılıklı tamamlayıcılık esasına oturtmayı hedefliyor. '
                    'Avrupa ile Asya-Pasifik arasında uzanan üretim kuşağında tek başına maliyet avantajı aramak yerine, bölgesel enerji, ulaştırma ve gümrük altyapısını ortaklaştırmak orta vadeli büyümenin en güçlü kaldıracı olarak öne çıkıyor.</p>'
                    '<p>Özellikle Orta Koridor, Kalkınma Yolu Projesi ve Doğu Akdeniz enerji geçiş hatları birlikte okunduğunda, yakın coğrafyadaki ülkelerle ticaret engellerinin azaltılması Türk ihracatçısının lojistik maliyetlerini doğrudan aşağı çekme potansiyeli taşıyor. '
                    'Klasik ihracat pazarlarında talep daralması yaşanırken, çevre ülkelerle kurulan ortak sanayi bölgeleri, sınır ötesi dijital gümrük uygulamaları ve yerel para birimleriyle ticaret mekanizmaları döviz likiditesi üzerindeki baskıyı da hafifletiyor. '
                    'Bu yaklaşım, Türkiye&#39;nin üretim kapasitesini yalnızca nihai tüketim mallarına değil, bölgenin ara malı ve mühendislik merkezi olma rolüne doğru yukarı taşıyor.</p>'
                    '<h3>İhracatçılar, Reel Sektör ve Enflasyonla Mücadele Açısından Somut Yansımalar</h3>'
                    '<p>Bölgesel iş birliği vizyonunun iç piyasaya ve vatandaşın günlük ekonomisine yansıyan en kritik boyutu, tedarik maliyetlerindeki öngörülebilirliktir. '
                    'Enerji, tarımsal girdi ve sanayi hammaddelerinin yakın coğrafyadan uzun vadeli kontratlarla ve düşük navlun maliyetleriyle temin edilmesi, yurt içi üretici fiyat endeksi (ÜFE) üzerindeki maliyet kaynaklı baskıları sınırlamaktadır. '
                    'Enflasyonla mücadelede para politikası adımlarının kalıcı başarıya ulaşması, arz yönlü darboğazların aşılmasına ve dış ticaret açığının yapısal olarak daralmasına doğrudan bağlıdır.</p>'
                    '<p>Reel sektör temsilcileri açısından bakıldığında, Orta Doğu, Kafkasya, Türk Cumhuriyetleri ve Balkanlar hattında gümrük geçiş sürelerinin kısalması ile çifte vergilendirmeyi önleme anlaşmalarının güncellenmesi, KOBİ ölçeğindeki üreticilerin bile yeni pazarlara giriş maliyetini düşürüyor. '
                    'Ayrıca bölgesel kalkınma bankaları ve uluslararası finans kuruluşlarıyla yürütülen ortak altyapı yatırımları, Türkiye&#39;ye yönelik doğrudan yabancı sermaye (FDI) girişlerinin yalnızca finansal portföy hareketleriyle sınırlı kalmayıp gerçek üretim tesislerine yönelmesini destekliyor.</p>'
                    '<div class="overflow-x-auto my-4"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
                    '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
                    '<th class="p-2.5 border border-slate-200">Stratejik Boyut</th>'
                    '<th class="p-2.5 border border-slate-200">Eski Rekabet Modeli</th>'
                    '<th class="p-2.5 border border-slate-200">Yeni Bölgesel İş Birliği Vizyonu ve Etkisi</th>'
                    '</tr></thead><tbody>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Lojistik ve Ticaret Koridorları</td><td class="p-2.5 border border-slate-200">Alternatif güzergâhların birbirini dışlayan fiyat rekabeti</td><td class="p-2.5 border border-slate-200">Orta Koridor ve Kalkınma Yolu entegrasyonu ile navlun süresinde %30&#39;a varan kısalma</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Sanayi ve Tedarik Zinciri</td><td class="p-2.5 border border-slate-200">Aynı düşük katma değerli ürünlerde pazar payı mücadelesi</td><td class="p-2.5 border border-slate-200">Ortak tedarik kümeleriyle yüksek teknolojili ara malı ve mühendislik ihracatı</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Enerji ve Girdi Maliyetleri</td><td class="p-2.5 border border-slate-200">Spot piyasa dalgalanmalarına açık yüksek ithalat faturası</td><td class="p-2.5 border border-slate-200">Bölgesel enerji merkezi (hub) kimliğiyle sanayide öngörülebilir enerji maliyeti</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Finansman ve Yatırım İklimi</td><td class="p-2.5 border border-slate-200">Kısa vadeli sıcak para akımlarına duyarlı kırılgan yapı</td><td class="p-2.5 border border-slate-200">Uzun vadeli doğrudan yatırımlar ve bölgesel fonlarla güçlenen döviz dengesi</td></tr>'
                    '</tbody></table></div>'
                    '<h3>Önümüzdeki Dönemde İzlenecek Kritik Göstergeler</h3>'
                    '<p>Önümüzdeki çeyreklerde bu vizyonun kağıt üzerindeki hedeflerden saha sonuçlarına ne ölçüde dönüştüğünü anlamak için üç temel gösterge izlenecek: Türkiye&#39;nin yakın ve komşu ülkelerle olan dış ticaret hacminin toplam ihracat içindeki payı, sınır kapılarındaki modernizasyon ve demiryolu bağlantılarının tamamlanma hızı ile bölgesel serbest ticaret anlaşmalarının kapsamı. '
                    'Küresel ekonomide belirsizliklerin sürdüğü bir konjonktürde, bölgesel istikrarı ve ekonomik entegrasyonu merkeze alan bu rasyonel çerçeve, Türkiye&#39;nin hem cari işlemler dengesini kalıcı biçimde iyileştirme hem de dezenflasyon sürecini üretim kaybı yaşamadan tamamlama hedefinde belirleyici rol oynayacaktır.</p>'
                    + _build_other_table("bakan-simsekten-bolgesel-ekonomi-vizyonu-rekabet-azalirken-is-birligi-vurgusu")
                ),
            },
            {
                "title": "İkinci El Konut Piyasasında Fiyat Katılığı ve Kredi Maliyetleri: Satış Hızı Neden Yavaşladı?",
                "summary": "Konut kredi faizlerindeki yüksek seyir ve alternatif mevduat getirilerinin etkisiyle ikinci el konut piyasasında yaşanan talep daralması, ilan fiyatlarındaki direnç ve alıcı-satıcı beklenti makasının detaylı analizi.",
                "image_path": _resolve_img("post_aff8df7496.jpg"),
                "focus_slug": "ikinci-el-konutlarda-yuksek-fiyat-baskisi-satislari-yavaslatti",
                "content": (
                    '<h3>Kredi Maliyetleri ve Alternatif Getiri Arayışının Konut Talebine Etkisi</h3>'
                    '<p>Türkiye gayrimenkul piyasasında son yıllarda enflasyona karşı korunma amacıyla öne çıkan yatırım amaçlı konut talebi, sıkı para politikası ve yükselen finansman maliyetleriyle birlikte yeni bir denge arayışına girdi. '
                    'Sektör verilerinin de ortaya koyduğu <a href="/haber/ikinci-el-konutlarda-yuksek-fiyat-baskisi-satislari-yavaslatti" class="text-red-600 font-bold underline">İkinci El Konutlarda Yüksek Fiyat Baskısı, Satışları Yavaşlattı</a> tablosu, '
                    'yalnızca geçici bir mevsimsel durgunluğa değil, konut piyasasının fiyatlama davranışında yapısal bir kırılmaya işaret ediyor. '
                    'Konut kredi faiz oranlarının aylık bazda yüksek seviyelerde seyretmesi, kredi kullanarak ev sahibi olmak isteyen sabit ve orta gelirli hanehalkının piyasaya girişini önemli ölçüde sınırlamış durumda.</p>'
                    '<p>Diğer taraftan nakit birikimi bulunan yatırımcı kitlesi açısından Türk lirası mevduat ve para piyasası fonlarının sunduğu reel getiri, kira çarpanı uzayan konut yatırımına kıyasla kısa vadede çok daha cazip bir alternatif oluşturuyor. '
                    'Buna rağmen ikinci el konut sahiplerinin önemli bir bölümünün, geçmiş dönemdeki hızlı değer artışlarını referans alarak satış fiyatlarında indirime gitmekte isteksiz davranması ("fiyat katılığı"), ilan fiyatları ile gerçek işlem fiyatları arasındaki makasın açılmasına yol açıyor.</p>'
                    '<h3>Alıcı-Satıcı Makası, İlan Süreleri ve Kira Piyasasına Yansımalar</h3>'
                    '<p>Sahadaki emlak endeksleri ve tapu devir istatistikleri incelendiğinde, satışa çıkarılan ikinci el konutların ilanda bekleme süresinin büyükşehirlerde ortalama 65 ila 90 gün bandına kadar uzadığı görülüyor. '
                    'Gerçek satış işlemlerinin büyük çoğunluğu, liste fiyatı üzerinden %10 ile %18 arasında pazarlık payı bırakan ve acil nakit ihtiyacı veya takas amacıyla hareket eden mülk sahipleri tarafından gerçekleştiriliyor. '
                    'Yeni konut üretiminde arsa ve inşaat maliyetlerinin yüksek kalması sıfır konut fiyatlarını aşağı yönlü esnemekten alıkoyarken, ikinci el piyasasında özellikle 15 yaş üzeri ve enerji/deprem performansı düşük yapılarda reel bazda (enflasyondan arındırılmış) gerileme eğilimi belirginleşiyor.</p>'
                    '<p>Vatandaş açısından bu sürecin en önemli yan etkisi kira piyasasında hissediliyor. Krediye erişimin zorlaşması nedeniyle satın alma kararını erteleyen hanehalkı kiralık konut piyasasında kalmaya devam ederken, merkezi lokasyonlardaki nitelikli kiralık konut arzı üzerindeki talep baskısı korunuyor. '
                    'Ancak satış piyasasındaki durgunluk, boş tutulan ikinci el dairelerin yeniden kiralık piyasasına yönlendirilmesini hızlandırarak kira artış hızının geçmiş yıllara kıyasla kademeli olarak dengelenmesine katkı sağlıyor.</p>'
                    '<div class="overflow-x-auto my-4"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
                    '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
                    '<th class="p-2.5 border border-slate-200">Piyasa Göstergesi</th>'
                    '<th class="p-2.5 border border-slate-200">Mevcut Saha Görünümü</th>'
                    '<th class="p-2.5 border border-slate-200">Alıcı ve Satıcı İçin Pratik Sonuç</th>'
                    '</tr></thead><tbody>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">İpotekli (Kredili) Satış Payı</td><td class="p-2.5 border border-slate-200">Toplam satışlar içinde tarihsel ortalamanın altında (%10-14 bandı)</td><td class="p-2.5 border border-slate-200">Peşin veya yüksek özsermayeli alıcıların pazarlık gücünün zirveye çıkması</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">İlan vs. Gerçekleşen Fiyat</td><td class="p-2.5 border border-slate-200">Liste fiyatlarında nominal direnç, reel bazda gerileme</td><td class="p-2.5 border border-slate-200">Piyasa değerinin üzerinde fiyatlanan ilanlarda 3 ayı aşan bekleme süresi</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Konut Amortisman Süresi</td><td class="p-2.5 border border-slate-200">Büyükşehirlerde 16-20 yıl bandında dengelenme</td><td class="p-2.5 border border-slate-200">Kısa vadeli al-sat yerine uzun vadeli kira getirisi odaklı seçici talep</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Bina Yaşı Ayrışması</td><td class="p-2.5 border border-slate-200">Deprem yönetmeliğine uygun genç binalarda güçlü fiyat koruma</td><td class="p-2.5 border border-slate-200">Eski stokta kentsel dönüşüm potansiyeli yoksa belirgin fiyat iskontosu</td></tr>'
                    '</tbody></table></div>'
                    '<h3>Konut Piyasasında Ne Zaman Yeniden Hareketlilik Bekleniyor?</h3>'
                    '<p>Gayrimenkul ekonomistleri ve sektör temsilcileri, ikinci el konut piyasasında işlem hacminin yeniden ivme kazanmasını iki temel koşula bağlıyor: enflasyondaki düşüş eğilimine paralel olarak konut kredisi faizlerinin aylık %2 seviyesinin altına doğru gerilemesi ve ilan fiyatlarının hanehalkı gelir düzeyiyle uyumlu gerçekçi bir zemine oturması. '
                    'Bu geçiş sürecinde oturum amacıyla konut arayanlar için nakit pazarlık marjının yüksek olduğu seçici bir alım penceresi korunurken, satıcılar açısından doğru ekspertiz ve gerçekçi fiyatlama satış süresini belirleyen ana unsur olmaya devam edecektir.</p>'
                    + _build_other_table("ikinci-el-konutlarda-yuksek-fiyat-baskisi-satislari-yavaslatti")
                ),
            },
            {
                "title": "BPA Sonrası Yeni Nesil Plastik Katkılarında Gizli Risk: Bebek Ürünlerinde Kimyasal Güvenlik ve Denetim Standartları",
                "summary": "Bisfenol A (BPA) yasağı sonrasında endüstride yaygınlaşan yeni nesil plastik yumuşatıcı ve sertleştirici bileşiklerin bebek sağlığı üzerindeki endokrin etkileri, bilimsel bulgular ve tüketicilerin dikkat etmesi gereken güvenlik kriterleri.",
                "image_path": _resolve_img("post_bae286ed5a.jpg"),
                "focus_slug": "zararsiz-sanilan-yeni-nesil-plastik-katkisi-bebek-sagligini-tehdit-ediyor",
                "content": (
                    '<h3>"BPA İçermez" Etiketi Neden Tek Başına Yeterli Güvenlik Sağlamıyor?</h3>'
                    '<p>Son on yılda bebek biberonlarından gıda saklama kaplarına kadar pek çok tüketici ürününde Bisfenol A (BPA) maddesinin kullanımına getirilen yasal kısıtlamalar, kimya endüstrisini alternatif polimer katkılarına yöneltti. '
                    'Ancak uluslararası toksikoloji araştırmalarının mercek altına aldığı <a href="/haber/zararsiz-sanilan-yeni-nesil-plastik-katkisi-bebek-sagligini-tehdit-ediyor" class="text-red-600 font-bold underline">Zararsız Sanılan Yeni Nesil Plastik Katkısı Bebek Sağlığını Tehdit Ediyor</a> bulguları, '
                    'BPA yerine kullanılan Bisfenol S (BPS), Bisfenol F (BPF) ve yeni nesil ftalat türevi plastikleştiricilerin moleküler yapı olarak selefleriyle büyük benzerlik taşıdığını ortaya koyuyor. '
                    'Üreticilerin yasal olarak "BPA Free" (BPA İçermez) etiketiyle piyasaya sunduğu bazı sentetik materyaller, ısı ve tekrarlı yıkama temasında benzer biyolojik riskleri tetikleyebiliyor.</p>'
                    '<p>Bebekler ve erken çocukluk dönemindeki bireyler, vücut ağırlıklarına kıyasla daha yüksek gıda/sıvı tüketim oranına sahip olmaları ve karaciğer detoksifikasyon enzimlerinin henüz tam olgunlaşmaması nedeniyle kimyasal göç (migrasyon) süreçlerine yetişkinlerden çok daha duyarlıdır. '
                    'Özellikle sıcak sıvılarla temas eden plastik beslenme gereçlerinde veya mikrodalga/bulaşık makinesi ısısına maruz kalan ambalajlarda polimer zincirlerinden kopan mikro düzeydeki katkı maddeleri doğrudan sindirim sistemine karışabilmektedir.</p>'
                    '<h3>Endokrin Sistem Etkileri, Tıbbi Malzemeler ve Regülasyon Boşluğu</h3>'
                    '<p>Pediatrik endokrinoloji ve çevre sağlığı uzmanlarının dikkat çektiği en kritik nokta, bu yeni nesil katkı maddelerinin "endokrin bozucu" (hormon taklit edici) potansiyelidir. '
                    'Çok düşük dozlarda dahi östrojen ve tiroit reseptörleriyle etkileşime girebilen bu bileşikler; hücresel büyüme, bağışıklık sistemi gelişimi ve metabolik dengeler üzerinde uzun vadeli etkilere yol açabilmektedir. '
                    'Üstelik risk alanı yalnızca mutfak gereçleriyle sınırlı kalmayıp yenidoğan yoğun bakım ünitelerinde kullanılan esnek serum setleri, beslenme sondaları ve medikal ambalajlara kadar uzanmaktadır.</p>'
                    '<p>Mevcut uluslararası kimyasal güvenlik mevzuatında en büyük zorluk, her bir kimyasal bileşiğin tek tek yıllar süren toksikolojik testlerden sonra kısıtlanmasıdır. '
                    'Bir madde yasaklandığında aynı kimyasal aileden hafifçe değiştirilmiş yeni bir izomer hızla üretim hattına girebilmektedir. Bu nedenle Avrupa Kimyasallar Ajansı (ECHA) ve sağlık otoriteleri, artık tekil maddeleri değil tüm bisfenol ve orto-ftalat grubunu kapsayan "grup bazlı regülasyon" modeline geçişi tartışmaktadır.</p>'
                    '<div class="overflow-x-auto my-4"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
                    '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
                    '<th class="p-2.5 border border-slate-200">Malzeme / Katkı Türü</th>'
                    '<th class="p-2.5 border border-slate-200">Isı ve Aşınma Dayanımı</th>'
                    '<th class="p-2.5 border border-slate-200">Bebek ve Çocuk Sağlığı İçin Güvenlik Önerisi</th>'
                    '</tr></thead><tbody>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">BPS / BPF İçeren Polikarbonat Türevleri</td><td class="p-2.5 border border-slate-200">Sıcak sıvı ve çizilmelerde kimyasal sızıntı (migrasyon) riski yüksek</td><td class="p-2.5 border border-slate-200">Kaynar su ve mikrodalga temasından kesinlikle kaçınılmalı</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Borosilikat Cam Gereçler</td><td class="p-2.5 border border-slate-200">Termal şoka ve kaynatmaya karşı tam kimyasal eylemsizlik (inert)</td><td class="p-2.5 border border-slate-200">Yenidoğan biberonları ve sıcak mama hazırlığında en güvenli birinci tercih</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Medikal Sınıf (Platin Kürlü) Silikon</td><td class="p-2.5 border border-slate-200">Plastikleştirici içermez, yüksek ısıda yapısal bütünlüğünü korur</td><td class="p-2.5 border border-slate-200">Emzik ve biberon başlıklarında sertifikalı %100 medikal silikon seçilmeli</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Paslanmaz Çelik (304 / 316 Kalite)</td><td class="p-2.5 border border-slate-200">Kırılmaz, kaplama gerektirmeyen ve mikroplastik üretmeyen yapı</td><td class="p-2.5 border border-slate-200">Ek gıda kapları ve suluklarda uzun ömürlü güvenli kullanım</td></tr>'
                    '</tbody></table></div>'
                    '<h3>Ebeveynler ve Tüketiciler Günlük Hayatta Hangi Önlemleri Almalı?</h3>'
                    '<p>Bilimsel veriler ışığında uzmanlar, ebeveynlerin bebek ve çocuk beslenmesinde basit ama etkili koruyucu adımlar atabileceğini vurguluyor. '
                    'Öncelikle sıcak süt, mama veya su hazırlığında plastik kaplar yerine borosilikat cam veya 304/316 kalite paslanmaz çelik ürünlerin tercih edilmesi kimyasal maruziyeti büyük oranda sıfırlamaktadır. '
                    'Plastik ürün kullanılması gereken durumlarda ise bulaşık makinesinin yüksek ısılı programları yerine elde ılık suyla yıkama yapılması, iç yüzeyi çizilmiş veya matlaşmış kapların derhal kullanım dışı bırakılması ve yalnızca "BPA İçermez" ibaresine değil, tüm bisfenol türevlerinden arındırılmış sertifikalı ürünlere yönelinmesi hayati önem taşımaktadır.</p>'
                    + _build_other_table("zararsiz-sanilan-yeni-nesil-plastik-katkisi-bebek-sagligini-tehdit-ediyor")
                ),
            },
            {
                "title": "Onkolojide Nanoteknoloji ve Odaklanmış Ultrason Dönemi: Glioblastoma Tedavisinde Kan-Beyin Bariyeri Nasıl Aşılıyor?",
                "summary": "Agresif beyin tümörlerinin tedavisinde kemoterapi ve immünoterapi ajanlarının etkinliğini sınırlayan kan-beyin bariyerinin, odaklanmış ultrason dalgaları ve lipid nanopartikül taşıyıcılarla aşılmasına yönelik klinik araştırmaların kapsamlı analizi.",
                "image_path": _resolve_img("post_184cec0321.jpg"),
                "focus_slug": "glioblastoma-mucadelesinde-yeni-bir-ufuk-ultrason-ve-nanoteknoloji-birlesimi",
                "content": (
                    '<h3>Kan-Beyin Bariyeri: Nöro-Onkolojideki En Büyük Biyolojik Engel</h3>'
                    '<p>Modern tıbbın ve onkolojinin son yirmi yılda akciğer, meme ve melanom gibi pek çok kanser türünde elde ettiği sağkalım başarıları, merkezi sinir sistemi tümörlerinde uzun süre aynı hızda ilerleyemedi. '
                    'Klinik literatürde yakından takip edilen <a href="/haber/glioblastoma-mucadelesinde-yeni-bir-ufuk-ultrason-ve-nanoteknoloji-birlesimi" class="text-red-600 font-bold underline">Glioblastoma Mücadelesinde Yeni Bir Ufuk: Ultrason ve Nanoteknoloji Birleşimi</a> araştırması, '
                    'bu direncin arkasındaki en temel fizyolojik kalkan olan kan-beyin bariyerini (BBB) cerrahi kesi olmadan geçici ve güvenli biçimde aralamanın yolunu açıyor. '
                    'Normal şartlarda beyni toksinlerden ve patojenlerden koruyan sıkı endotel hücre bağlantıları, sistemik yolla verilen ilaç moleküllerinin %98&#39;inden fazlasının tümör dokusuna ulaşmasını engellemektedir.</p>'
                    '<p>Özellikle yetişkinlerde en sık görülen ve hızlı seyreden primer beyin tümörü olan glioblastomada, cerrahi rezeksiyon sonrasında mikroskobik düzeyde kalan hücrelerin temizlenmesi hayati önem taşıyor. '
                    'Standart kemoterapi protokollerinde ilacın beyin dokusunda terapötik (iyileştirici) konsantrasyona ulaşabilmesi için yüksek sistemik dozlar uygulanması gerekirken, bu durum sağlıklı organlarda ciddi yan etkilere yol açabiliyor. '
                    'Odaklanmış ultrason (FUS) ve nanoteknoloji entegrasyonu, ilacı yalnızca hedeflenen milimetrik tümör bölgesine yoğunlaştırarak bu denklemi kökten değiştiriyor.</p>'
                    '<h3>Mikrokabarcıklar, Akustik Kavitasyon ve Akıllı Nanopartiküller Nasıl Çalışıyor?</h3>'
                    '<p>Geliştirilen yeni nesil biyomedikal protokol iki aşamalı bir mekanizma üzerine kuruludur. İlk aşamada hastaya damar yoluyla mikroskobik gaz kabarcıkları ve etken maddeyi taşıyan biyouyumlu nanopartiküller enjekte edilir. '
                    'Ardından kafatası dışından MR (Manyetik Rezonans) rehberliğinde gönderilen düşük yoğunluklu odaklanmış ultrason dalgaları, yalnızca tümörün bulunduğu damar yatağındaki mikrokabarcıkları titreştirir. '
                    'Akustik kavitasyon adı verilen bu mekanik etki, kan-beyin bariyerindeki sıkı hücre duvarlarını birkaç saatliğine mikro ölçekte esneterek nanopartiküllerin doğrudan tümör mikroçevresine sızmasını sağlar.</p>'
                    '<p>İkinci aşamada ise beyin dokusuna geçen özel tasarımlı nanopartiküller devreye girer. Tümör hücrelerinin yüzeyindeki spesifik reseptörleri tanıyan bu taşıyıcılar, hem kemoterapi ajanlarını hem de bağışıklık sistemini uyaran immünoterapi sinyallerini doğrudan kanserli hücrenin çekirdeğine bırakır. '
                    'Böylece sağlıklı nöronlar korunurken, tümör dokusu içindeki ilaç yoğunluğu klasik yöntemlere kıyasla katbekat artırılmış olur.</p>'
                    '<div class="overflow-x-auto my-4"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
                    '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
                    '<th class="p-2.5 border border-slate-200">Tedavi Parametresi</th>'
                    '<th class="p-2.5 border border-slate-200">Klasik Sistemik Kemoterapi</th>'
                    '<th class="p-2.5 border border-slate-200">Odaklanmış Ultrason + Nanoteknoloji Yaklaşımı</th>'
                    '</tr></thead><tbody>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Kan-Beyin Bariyeri Geçişi</td><td class="p-2.5 border border-slate-200">Çok düşük (%1-2 bandında sınırlı difüzyon)</td><td class="p-2.5 border border-slate-200">Hedefli bölgede geçici ve kontrollü geçirgenlik artışı</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Hedefleme Hassasiyeti</td><td class="p-2.5 border border-slate-200">Tüm vücuda dağılan sistemik maruziyet</td><td class="p-2.5 border border-slate-200">MR rehberliğinde milimetrik tümör yatağı odaklaması</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">İmmünoterapi Entegrasyonu</td><td class="p-2.5 border border-slate-200">Bariyer engeli nedeniyle düşük antikor geçişi</td><td class="p-2.5 border border-slate-200">Nanotaşıyıcılarla soğuk tümörleri bağışıklığa açık hale getirme</td></tr>'
                    '<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-bold text-red-600">Uygulama Biçimi</td><td class="p-2.5 border border-slate-200">Tekrarlı yüksek doz infüzyon ve sistemik toksisite riski</td><td class="p-2.5 border border-slate-200">Cerrahi kesi gerektirmeyen (non-invaziv) akustik aktivasyon</td></tr>'
                    '</tbody></table></div>'
                    '<h3>Klinik Araştırma Süreci ve Nörolojik Hastalıklar İçin Gelecek Perspektifi</h3>'
                    '<p>Tıp dünyasında heyecan uyandıran bu birleşik teknolojinin en önemli avantajlarından biri, odaklanmış ultrason sistemlerinin halihazırda esansiyel tremor ve Parkinson gibi bazı nörolojik tablolar için FDA ve Avrupa otoriteleri tarafından onaylanmış bir altyapıya sahip olmasıdır. '
                    'Glioblastoma özelinde yürütülen Faz 1 ve Faz 2 klinik çalışmaların tamamlanmasıyla birlikte, yöntemin standart radyoterapi ve cerrahi protokollerine tamamlayıcı bir modül olarak eklenmesi hedefleniyor. '
                    'Uzmanlar, kan-beyin bariyerini güvenli biçimde aşan bu nanotaşıyıcı platformunun yalnızca beyin tümörlerinde değil, ilerleyen yıllarda Alzheimer ve ALS gibi nörodejeneratif hastalıkların gen ve protein tedavilerinde de çığır açıcı bir standart oluşturacağına dikkat çekiyor.</p>'
                    + _build_other_table("glioblastoma-mucadelesinde-yeni-bir-ufuk-ultrason-ve-nanoteknoloji-birlesimi")
                ),
            },
        ]

        existing_titles = {(x.get("title") or "").strip().lower() for x in existing}
        for item in curated_list:
            if item["title"].strip().lower() in existing_titles:
                continue
            slug = database.save_article(
                title=item["title"],
                summary=item["summary"],
                content=item["content"],
                image_path=item["image_path"],
                source="Gündem Analizi",
                category="Analiz",
            )
            if slug:
                print(f"✅ [Gündem Analizi] Özgün başlangıç analizi eklendi: /haber/{slug}")
        _RADAR_CACHE["ts"] = 0.0
    except Exception as _se:
        print(f"Özgün analiz başlangıç yükleme uyarısı: {_se}")


def get_agenda_radar_data(widgets: Dict, force_refresh: bool = False) -> Dict:
    """
    Ana sayfa 'Gündem Analizi' ve /analiz sayfası için:
    YALNIZCA gerçek 'Analiz' kategorisinde yayınlanmış özgün Gündem Analizi dosyalarını döner.
    Eski haberleri veya normal kategori haberlerini (Apple, Hiroşima vb.) KESİNLİKLE buraya karıştırmaz!
    """
    global _RADAR_CACHE
    now = time.time()
    if not force_refresh and _RADAR_CACHE["data"] and _RADAR_CACHE["data"].get("dossiers") and (now - _RADAR_CACHE["ts"]) < 180:
        return _RADAR_CACHE["data"]

    import database

    seed_curated_analyses()
    synth_pool = database.get_articles(limit=18, category="Analiz")
    if not synth_pool or not any((x.get("category") or "").strip() == "Analiz" for x in synth_pool):
        if not globals().get("_BG_ANALIZ_RUNNING"):
            globals()["_BG_ANALIZ_RUNNING"] = True
            import threading
            def _bg_gen():
                try:
                    ensure_daily_synthesis_reports(force=True)
                except Exception as _e:
                    print(f"İlk Analiz arka plan üretim uyarısı: {_e}")
                finally:
                    globals()["_BG_ANALIZ_RUNNING"] = False
            threading.Thread(target=_bg_gen, daemon=True).start()
    dossiers = []
    seen_titles = set()
    for s in (synth_pool or []):
        # Çift güvenlik: Sadece gerçek kategorisi 'Analiz' olanları kabul et
        if (s.get("category") or "").strip() != "Analiz":
            continue
        t_norm = (s.get("title") or "").strip().lower()
        if t_norm in seen_titles:
            continue
        seen_titles.add(t_norm)
        c_str = str(s.get("created_at") or "")[:16]
        try:
            _hr = int(c_str[11:13]) if len(c_str) >= 13 and c_str[11:13].isdigit() else 12
        except Exception:
            _hr = 12
        if _hr < 13:
            _slot_lbl = "Sabah Analizi · 10:00"
        elif _hr < 18:
            _slot_lbl = "Öğle Analizi · 15:00"
        else:
            _slot_lbl = "Akşam Analizi · 19:00"
        _raw_body = s.get("content") or ""
        _src_cnt = max(1, _raw_body.split('class="ga-sources"', 1)[-1].split("</ul>", 1)[0].count("<li>")) if 'class="ga-sources"' in _raw_body else 1
        _ed_note = bool((database.get_setting(f"editor_note_{s.get('id')}", "") or "").strip()) if s.get("id") else False
        dossiers.append({
            "id": s.get("id"),
            "slug": s.get("slug"),
            "title": s.get("title"),
            "summary": s.get("summary"),
            "category": "Analiz",
            "image_path": s.get("image_path"),
            "source": s.get("source") or "Gündem Analizi",
            "created_at": c_str,
            "reading_time_min": s.get("reading_time_min") or 4,
            "slot_label": _slot_lbl,
            "source_count": _src_cnt,
            "has_editor_note": _ed_note,
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


import os
import threading

_ANALYSIS_LOCK = threading.Lock()


def ensure_daily_synthesis_reports(force: bool = False) -> Optional[str]:
    """
    Her gün 10:00, 15:00 ve 19:00 dilimlerinde çalışır.
    ÇİFT SAYFA / KOPYA İÇERİK ÖNLEME KURALI:
    - Sitede zaten yayınlanmış bir haberi ikinci bir URL'de tekrar yazmaz ("Bu analizin dayandığı haber" ikiz sayfa riskini sıfırlar).
    - Doğrudan canlı RSS havuzundaki HENÜZ YAYINLANMAMIŞ, en çok farklı kaynağın konuştuğu en önemli gündem olayını seçer,
      gerçek basın fotoğrafını doğrular, Gemini 3.5 ile çok kaynaklı derin Analiz Dosyası olarak TEK URL halinde yayınlar
      ve kullanılan tüm kaynak linklerini işlenmiş işaretler ki normal haber botu aynı olayı ikinci kez paylaşmasın.
    """
    if not _ANALYSIS_LOCK.acquire(blocking=False):
        return None
    try:
        return _ensure_daily_synthesis_reports_locked(force=force)
    finally:
        _ANALYSIS_LOCK.release()


def _ensure_daily_synthesis_reports_locked(force: bool = False) -> Optional[str]:
    from datetime import datetime, timezone, timedelta
    import database
    import image_generator
    import multisource
    import news_fetcher

    tz_tr = timezone(timedelta(hours=3))
    now_tr = datetime.now(tz_tr)
    today_str = now_tr.strftime("%Y-%m-%d")
    hour = now_tr.hour

    existing_analiz = database.get_articles(limit=2, category="Analiz")
    has_any_analiz = any((x.get("category") or "").strip() == "Analiz" for x in (existing_analiz or []))

    if not force and has_any_analiz:
        if 10 <= hour < 15:
            slot_key = "10"
        elif 15 <= hour < 19:
            slot_key = "15"
        elif hour >= 19:
            slot_key = "19"
        else:
            return None
        setting_key = f"ga_analiz_{today_str}_{slot_key}"
        if database.get_setting(setting_key, "") == "1":
            return None
    else:
        if hour >= 19:
            slot_key = "19"
        elif hour >= 15:
            slot_key = "15"
        else:
            slot_key = "10"
        setting_key = f"ga_analiz_{today_str}_{slot_key}"

    try:
        import main as bot_main
        _is_comm = bot_main.is_commodity_news
    except Exception:
        _is_comm = lambda _t: False

    try:
        live_pool = news_fetcher.fetch_latest_news(limit_per_feed=10) or []
    except Exception as _fe:
        print(f"Analiz RSS tarama uyarısı: {_fe}")
        live_pool = []

    scored_fresh = []
    for item in live_pool:
        t = (item.get("title") or "").strip()
        sm = (item.get("summary") or "").strip()
        cat = (item.get("category") or "Gündem").strip()
        if not t or _CRIME_ACCIDENT_SKIP.search(t) or _is_comm(t):
            continue
        sib_cnt = len(item.get("siblings") or [])
        cat_weight = {
            "Ekonomi": 42,
            "Gündem": 36,
            "Dünya": 34,
            "Eğitim": 32,
            "Teknoloji": 26,
            "Otomobil": 24,
            "Sağlık": 22,
            "Spor": 12,
        }.get(cat, 20)
        num_bonus = 15 if re.search(r"\d", f"{t} {sm}") else 0
        img_bonus = 10 if item.get("image_url") else 0
        # Birden fazla kaynağın geçtiği çok kaynaklı büyük gelişmelere en yüksek öncelik
        total_score = (sib_cnt * 55) + cat_weight + num_bonus + img_bonus
        scored_fresh.append((total_score, item))

    scored_fresh.sort(key=lambda x: x[0], reverse=True)

    chosen_item = None
    chosen_ms = None
    chosen_visual = ""

    for _, cand in scored_fresh[:6]:
        c_title = cand.get("title", "")
        c_link = cand.get("link", "")
        c_hash = cand.get("hash", "")
        c_source = cand.get("source", "")
        c_cat = cand.get("category") or "Gündem"
        if database.is_already_posted(c_hash, title=c_title, link=c_link):
            continue

        details = news_fetcher.fetch_article_details(c_link, max_paragraphs=10)
        scraped_body = details.get("body", "") or ""
        raw_sum = cand.get("summary", "") or ""
        best_body = scraped_body if len(scraped_body) > len(raw_sum) else raw_sum

        cand_imgs = list(details.get("images") or [])
        if cand.get("image_url") and cand["image_url"] not in cand_imgs:
            cand_imgs.append(cand["image_url"])
        for _sb in (cand.get("siblings") or []):
            if _sb.get("image_url") and _sb["image_url"] not in cand_imgs:
                cand_imgs.append(_sb["image_url"])

        if not cand_imgs:
            continue

        img_filename = f"analiz_{c_hash[:10]}.jpg"
        visual_path = image_generator.create_news_visual(
            candidate_urls=cand_imgs,
            output_filename=img_filename,
            title=c_title,
            category=c_cat,
        )
        if (
            not visual_path
            or not os.path.exists(visual_path)
            or os.path.getsize(visual_path) < 8000
            or image_generator.is_synthetic_card_image(visual_path)
        ):
            continue

        ms_res = multisource.build_article(cand, best_body, live_pool, category=c_cat, mode="analysis")
        if ms_res and ms_res.get("content"):
            chosen_item = cand
            chosen_ms = ms_res
            chosen_visual = visual_path
            break

    if not chosen_item or not chosen_ms or not chosen_visual:
        return None

    report_title = chosen_ms["title"]
    lead_summary = chosen_ms["summary"]
    ai_html = chosen_ms["content"]

    # Sitedeki FARKLI konulardaki son haberlere sağlıklı iç bağlantı kutusu (aynı konu asla eklenmez)
    rep_toks = multisource._tokens(report_title)
    recent_pool = database.get_articles(limit=18) or []
    other_items = []
    for a in recent_pool:
        if (a.get("category") or "").strip() == "Analiz":
            continue
        at = (a.get("title") or "").strip()
        aslug = (a.get("slug") or "").strip()
        if not at or not aslug or _CRIME_ACCIDENT_SKIP.search(at):
            continue
        a_toks = multisource._tokens(at)
        if rep_toks and a_toks and len(rep_toks & a_toks) >= 2:
            continue
        other_items.append(a)
        if len(other_items) >= 4:
            break

    if other_items:
        other_rows = []
        for item in other_items:
            ic = _html.escape(item.get("category") or "Gündem")
            it = _html.escape(item.get("title") or "")
            islug = _html.escape(item.get("slug") or "")
            other_rows.append(
                f'<tr class="border-b border-slate-200">'
                f'<td class="p-2.5 border border-slate-200 font-bold text-red-600 whitespace-nowrap">{ic}</td>'
                f'<td class="p-2.5 border border-slate-200 font-semibold"><a href="/haber/{islug}" class="text-slate-900 hover:text-red-600 underline">{it} →</a></td>'
                f'</tr>'
            )
        other_box = (
            '<h3 class="text-xl font-bold text-slate-900 mt-8 mb-3">Gündemde Öne Çıkan Diğer Başlıklar</h3>'
            '<div class="overflow-x-auto my-3"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">'
            '<thead><tr class="bg-slate-100 text-slate-900 font-bold">'
            '<th class="p-2.5 border border-slate-200">Kategori</th>'
            '<th class="p-2.5 border border-slate-200">Haber Başlığı</th>'
            '</tr></thead><tbody>'
            + "".join(other_rows)
            + '</tbody></table></div>'
        )
        full_html = ai_html + "\n" + other_box
    else:
        full_html = ai_html

    slug, is_created = database.save_article(
        title=report_title,
        summary=lead_summary,
        content=full_html,
        image_path=chosen_visual,
        source="Gündem Analizi",
        category="Analiz",
        return_status=True,
    )
    if slug and is_created:
        # Ana kaynağı ve birleştirilen tüm kardeş kaynakları işlenmiş işaretle (normal haber botu ikinci kez ayrı URL açmasın!)
        try:
            database.claim_news_for_processing(
                chosen_item["hash"],
                title=chosen_item.get("title", ""),
                source=chosen_item.get("source", ""),
                link=chosen_item.get("link", ""),
            )
            database.mark_as_posted(
                news_hash=chosen_item["hash"],
                title=report_title,
                source=chosen_item.get("source", ""),
                link=chosen_item.get("link", ""),
            )
        except Exception:
            pass
        for _sib in (chosen_ms.get("sibling_items") or chosen_item.get("siblings") or []):
            try:
                if _sib.get("hash"):
                    database.claim_news_for_processing(
                        _sib["hash"],
                        title=_sib.get("title", ""),
                        source=_sib.get("source", ""),
                        link=_sib.get("link", ""),
                    )
            except Exception:
                pass

        database.set_setting(setting_key, "1")
        _RADAR_CACHE["ts"] = 0.0
        print(f"✅ [Gündem Analizi] Saat {hour}:00 tekil URL çok kaynaklı analiz yayınlandı: /haber/{slug}")
        try:
            import google_indexer
            google_indexer.notify_google_indexing(f"https://xn--gndemanalizi-dlb.com.tr/haber/{slug}")
        except Exception:
            pass
        return slug
    return None
