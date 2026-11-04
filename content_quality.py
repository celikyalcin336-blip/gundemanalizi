"""
İçerik Kalitesi Yardımcıları (AdSense uyumu)

- fix_brand_splits(): Otomatik temizleyicinin böldüğü marka adlarını düzeltir ("You Tube" -> "YouTube").
- protect_brands()/restore_brands(): Yapışık kelime ayırıcısı çalışmadan önce marka adlarını korur.
- clean_article_html(): Yayındaki (eski) haberlerden şablon "değerlendirme" kutusunu, her habere eklenen
  hazır dolgu paragraflarını, kırık linkleri ve tekrar eden cümleleri GÖSTERİM ANINDA temizler.
  (Veritabanındaki kayıt değiştirilmez.)
- visible_word_count() / is_thin(): Haberin okunabilir kelime sayısını ölçer; kısa haberler noindex alır.
"""
import html as _html
import re

# Büyük/küçük harf karışık yazılan, otomatik temizleyicinin yanlışlıkla böldüğü marka adları
BRANDS = [
    "YouTube", "iPhone", "iPad", "iPadOS", "iOS", "macOS", "MacBook", "iMac", "iCloud", "AirPods", "AirTag",
    "watchOS", "visionOS", "TikTok", "WhatsApp", "PlayStation", "OpenAI", "ChatGPT", "DeepSeek", "DeepMind",
    "LinkedIn", "PayPal", "SpaceX", "McLaren", "McDonald", "GitHub", "PowerPoint", "OneDrive", "OnePlus",
    "GeForce", "FedEx", "BlackRock", "JPMorgan", "BioNTech", "HarmonyOS", "HyperOS", "MediaTek", "TotalEnergies",
    "eSIM", "eDevlet", "eBay", "SoftBank", "AstraZeneca", "GlaxoSmithKline", "ExxonMobil", "BlackBerry",
    "CoinMarketCap", "CoinGecko", "MicroStrategy", "BeIN", "beIN", "NextSosyal", "HepsiBurada", "Hepsiburada",
    "TOGG", "DeFi", "NFTs", "AliExpress", "DoorDash", "WeChat", "TechCrunch", "XPeng", "NIO", "BYD", "ZEEKR",
    "MiniMax", "xAI", "SpaceX", "StarLink", "Starlink", "FaceTime", "AppleCare", "GoPro", "PlayStation",
    "SmartThings", "ThinkPad", "IdeaPad", "ZenBook", "VivoBook", "ROG", "SteamOS", "PCIe", "LPDDR", "GDDR",
]
_BRAND_SPLIT_RE = []
for _b in sorted(set(BRANDS), key=len, reverse=True):
    # "YouTube" -> "You Tube" bölünmesini yakala (büyük harf öncesine boşluk girmiş halleri)
    parts = re.findall(r"[A-ZÇĞİÖŞÜ]?[a-zçğıöşü]+|[A-ZÇĞİÖŞÜ]+(?![a-zçğıöşü])|\d+", _b)
    if len(parts) >= 2:
        pat = r"\b" + r"\s+".join(re.escape(p) for p in parts) + r"(?=[\W\d_]|['’]|$)"
        _BRAND_SPLIT_RE.append((re.compile(pat), _b))


def fix_brand_splits(text: str) -> str:
    if not text:
        return text
    for rx, brand in _BRAND_SPLIT_RE:
        text = rx.sub(brand, text)
    return text


def protect_brands(text: str):
    """Yapışık kelime ayırıcısından önce marka adlarını yer tutucuya alır."""
    mapping = {}
    if not text:
        return text, mapping
    for i, b in enumerate(sorted(set(BRANDS), key=len, reverse=True)):
        if b in text:
            key = f"\u2063BRAND{i}\u2063"
            mapping[key] = b
            text = text.replace(b, key)
    return text, mapping


def restore_brands(text: str, mapping: dict) -> str:
    for k, v in mapping.items():
        text = text.replace(k, v)
    return text


# Eski yedek moddan gelen, her habere aynı eklenen hazır cümlelerin ayırt edici başlangıçları
_GENERIC_STARTS = [
    "Gelişmenin piyasalar ve kamuoyu üzerindeki yansımaları",
    "Piyasalardaki fiyatlamalar, tüketici hakları ve makroekonomik dengeler",
    "Öğrenci, veli ve eğitim camiasını ilgilendiren resmi kılavuzlar",
    "Müsabaka takvimi ve spor kamuoyunun nabzı",
    "Piyasalarda ve ekonomi çevrelerinde geniş yankı uyandıran",
    "Önümüzdeki günlerde sürecin resmiyet kazanması",
    "Spor kamuoyunda ve taraftarlar arasında büyük heyecan",
    "Müsabaka takvimi ve resmi sözleşme süreçlerinde",
    "Teknoloji dünyasında ve dijital ekosistemde dengeleri",
    "Teknoloji otoriteleri, yeni modelin yaygınlaşmasıyla",
    "Sağlık otoriteleri ve tıp uzmanları, doğru bilgilendirmenin",
    "Sağlıklı yaşam standartları ve koruyucu hekimlik",
    "Otomotiv sektöründe dikkat çeken model ve fiyat dinamikleri",
    "Türkiye pazarındaki bulunabilirlik, satış koşulları",
    "Öğrencileri, öğretmenleri ve velileri yakından ilgilendiren bu gelişmeyle",
    "Eğitim camiasındaki güncel beklentiler ve başvuru takvimine",
    "Bölgesel ve uluslararası dengeleri yakından ilgilendiren olay",
    "Bölgedeki aktörlerin atacağı yeni adımlar",
    "Gelişmeyle ilgili resmi makamlar ve yetkili mercilerden gelecek",
    "Konuya ilişkin kurumlar arası koordinasyon ve sahadaki yansımalar",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _is_generic(text: str) -> bool:
    t = _norm(text)
    return any(t.startswith(g) for g in _GENERIC_STARTS)


def clean_article_html(content: str) -> str:
    """Gösterim anında eski şablon kalıntılarını temizler. Gemini ile yazılmış yeni haberlere zarar vermez."""
    if not content:
        return content
    c = content

    # 1) Şablon "GÜNDEM ANALİZİ DEĞERLENDİRMESİ" kutusu: içi hazır metinse tamamen kaldır
    def _drop_eval_box(m):
        return "" if _is_generic(m.group(0).split("</h4>", 1)[-1]) else m.group(0)
    c = re.sub(r'<div[^>]*>\s*<h4[^>]*>.*?DEĞERLENDİRMESİ\s*</h4>.*?</div>', _drop_eval_box, c, flags=re.S | re.I)

    # 2) Her habere eklenen hazır dolgu paragrafları
    c = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: "" if _is_generic(m.group(1)) else m.group(0), c, flags=re.S)

    # 3) Kırık/çıplak linkler (https://t.co/mlo NYjm Va3 gibi) ve marka bölünmeleri
    def _fix_p(m):
        inner = m.group(2)
        inner = re.sub(r"https?://t\.co/[\w]+(?:\s+[\w]{2,6}){0,4}", "", inner)
        inner = re.sub(r"(?<![\"'=])https?://[^\s<]+", "", inner)
        inner = re.sub(r"pic\.twitter\.com/\S+", "", inner)
        # Kaynak siteden paragraf başına/içine karışmış BÜYÜK HARFLİ ara başlık kalıntılarını temizle (örn: DEV TESİSİN ODAĞINDA BÜYÜK SUV MODELLERİ YER ALIYOR)
        inner = re.sub(r"^(?:[A-ZÇĞİÖŞÜ0-9'’\-]+\s+){4,}[A-ZÇĞİÖŞÜ0-9'’\-]+\s*", "", inner.strip())
        inner = fix_brand_splits(inner)
        return f"{m.group(1)}{inner}</p>"
    c = re.sub(r"(<p[^>]*>)(.*?)</p>", _fix_p, c, flags=re.S)

    # 4) Paragraflar arası tekrar eden cümleler
    seen_text = [""]

    def _dedupe(m):
        inner = m.group(2)
        sents = re.split(r"(?<=[.!?])\s+", inner)
        keep = []
        for s in sents:
            key = re.sub(r"\W+", "", _norm(s).lower())
            # Daha önce (alıntı içinde bile) geçmiş uzun cümleyi tekrar yazma
            if len(key) > 40 and len(_norm(s).split()) >= 8 and key in seen_text[0]:
                continue
            seen_text[0] += key + "|"
            keep.append(s)
        return f"{m.group(1)}{' '.join(keep)}</p>"
    c = re.sub(r"(<p[^>]*>)(.*?)</p>", _dedupe, c, flags=re.S)

    # 5) Boş kalan paragraflar ve altı boş kalan "Gelişmenin Ayrıntıları" başlığı
    c = re.sub(r"<p[^>]*>\s*</p>", "", c)
    c = re.sub(r"<h3[^>]*>[^<]*</h3>\s*(?=(<div|$|<h3))", "", c.strip())

    # 6) Alt başlıklara (<h3>) Google Arama Jump-Link SEO id etiketi ekle
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    used_ids = set()

    def _add_h3_id(m):
        attrs, inner = m.group(1), m.group(2)
        if "id=" in attrs.lower():
            return m.group(0)
        base_id = re.sub(r"[^a-z0-9]+", "-", _norm(inner).translate(tr_map).lower()).strip("-")[:64] or "bolum"
        hid = base_id
        idx = 2
        while hid in used_ids:
            hid = f"{base_id}-{idx}"
            idx += 1
        used_ids.add(hid)
        return f'<h3{attrs} id="{hid}">{inner}</h3>'

    c = re.sub(r"<h3([^>]*)>(.*?)</h3>", _add_h3_id, c, flags=re.S | re.I)
    return c


_THIN_WORD_MEMO = {}


def visible_word_count(content: str) -> int:
    return len(_norm(content).split())


def _fast_clean_for_word_count(content: str) -> str:
    if not content:
        return ""
    c = content

    def _drop_eval_box(m):
        return "" if _is_generic(m.group(0).split("</h4>", 1)[-1]) else m.group(0)

    c = re.sub(r'<div[^>]*>\s*<h4[^>]*>.*?DEĞERLENDİRMESİ\s*</h4>.*?</div>', _drop_eval_box, c, flags=re.S | re.I)
    c = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: "" if _is_generic(m.group(1)) else m.group(0), c, flags=re.S)

    def _fix_p_fast(m):
        inner = m.group(2)
        inner = re.sub(r"https?://t\.co/[\w]+(?:\s+[\w]{2,6}){0,4}", "", inner)
        inner = re.sub(r"(?<![\"'=])https?://[^\s<]+", "", inner)
        inner = re.sub(r"pic\.twitter\.com/\S+", "", inner)
        inner = re.sub(r"^(?:[A-ZÇĞİÖŞÜ0-9'’\-]+\s+){4,}[A-ZÇĞİÖŞÜ0-9'’\-]+\s*", "", inner.strip())
        return f"{m.group(1)}{inner}</p>"

    c = re.sub(r"(<p[^>]*>)(.*?)</p>", _fix_p_fast, c, flags=re.S)

    seen_text = [""]

    def _dedupe(m):
        inner = m.group(2)
        sents = re.split(r"(?<=[.!?])\s+", inner)
        keep = []
        for s in sents:
            key = re.sub(r"\W+", "", _norm(s).lower())
            if len(key) > 40 and len(_norm(s).split()) >= 8 and key in seen_text[0]:
                continue
            seen_text[0] += key + "|"
            keep.append(s)
        return f"{m.group(1)}{' '.join(keep)}</p>"

    c = re.sub(r"(<p[^>]*>)(.*?)</p>", _dedupe, c, flags=re.S)
    c = re.sub(r"<p[^>]*>\s*</p>", "", c)
    c = re.sub(r"<h3[^>]*>[^<]*</h3>\s*(?=(<div|$|<h3))", "", c.strip())
    return c


def is_thin(content: str, threshold: int = 300) -> bool:
    if not content:
        return True
    key = (len(content), content[:80], content[-80:])
    wc = _THIN_WORD_MEMO.get(key)
    if wc is None:
        if len(_THIN_WORD_MEMO) > 5000:
            _THIN_WORD_MEMO.clear()
        wc = visible_word_count(_fast_clean_for_word_count(content))
        _THIN_WORD_MEMO[key] = wc
    return wc < threshold


def diversify_article_layout(content: str, article_id: int = 0) -> str:
    """
    Mevcut ve yeni haberlerin tekdüze (her haberde 5 adet <h3>) görünmesini önler;
    haber ID'sine göre 3 farklı editoryal mizanpaj (<h2>, <blockquote>, birleştirilmiş akıcı paragraflar) uygular.
    """
    if not content:
        return content
    c = content
    mode = (article_id or 0) % 3

    if mode == 0:
        c = re.sub(
            r"<h3([^>]*)>(.*?)</h3>",
            r'<h2 class="text-lg sm:text-xl font-extrabold text-slate-900 mt-7 mb-3"\1>\2</h2>',
            c,
            flags=re.S | re.I,
        )
        if "<blockquote" not in c.lower():
            p_idx = [0]
            def _p_to_bq(m):
                p_idx[0] += 1
                inner = m.group(1).strip()
                if p_idx[0] == 3 and 90 <= len(_norm(inner)) <= 480:
                    return f'<blockquote class="my-6 pl-4 border-l-4 border-red-600 italic text-slate-700 bg-slate-50/80 py-3 pr-4 rounded-r-xl">{inner}</blockquote>'
                return m.group(0)
            c = re.sub(r"<p[^>]*>(.*?)</p>", _p_to_bq, c, flags=re.S | re.I)

    elif mode == 1:
        h_idx = [0]
        def _selective_h2(m):
            h_idx[0] += 1
            if h_idx[0] in (1, 3):
                return f'<h2 class="text-lg sm:text-xl font-extrabold text-slate-900 mt-7 mb-3"{m.group(1)}>{m.group(2)}</h2>'
            return ""
        if c.lower().count("<h3") >= 3:
            c = re.sub(r"<h3([^>]*)>(.*?)</h3>", _selective_h2, c, flags=re.S | re.I)

    else:
        h_idx = [0]
        def _trim_extra_h3(m):
            h_idx[0] += 1
            if h_idx[0] in (2, 5):
                return ""
            return m.group(0)
        if c.lower().count("<h3") >= 4:
            c = re.sub(r"<h3([^>]*)>(.*?)</h3>", _trim_extra_h3, c, flags=re.S | re.I)
        if "<blockquote" not in c.lower() and (article_id or 0) % 2 == 0:
            p_idx = [0]
            def _p4_to_bq(m):
                p_idx[0] += 1
                inner = m.group(1).strip()
                if p_idx[0] == 4 and 90 <= len(_norm(inner)) <= 480:
                    return f'<blockquote class="my-6 pl-4 border-l-4 border-red-600 italic text-slate-700 bg-slate-50/80 py-3 pr-4 rounded-r-xl">{inner}</blockquote>'
                return m.group(0)
            c = re.sub(r"<p[^>]*>(.*?)</p>", _p4_to_bq, c, flags=re.S | re.I)

    return c


def clean_source_name(source: str) -> str:
    """
    RSS beslemelerinin sonundaki iç kategori eklerini ('ShiftDelete Yapay Zeka' -> 'ShiftDelete',
    'Motor1 Otomobil' -> 'Motor1', 'Log.com.tr Teknoloji' -> 'Log', 'Habertürk Dünya' -> 'Habertürk' vb.)
    temizleyerek yayın kuruluşunun yalnızca gerçek kurumsal adını döndürür.
    """
    s = (source or "").strip()
    if not s:
        return "Basın Kaynakları"
    if s.lower() in ("a spor", "trt spor", "otomobil haber"):
        return s
    # Alan adı uzantısını sadeleştir ('Log.com.tr Teknoloji' -> 'Log Teknoloji')
    s = re.sub(r"\.com\.tr\b", "", s, flags=re.I)
    # RSS kategori soneklerini kaldır (gerçek yayın adını korur)
    s = re.sub(
        r"\s+(?:Otomobil|Teknoloji|Yapay\s+Zeka|AI\s*&\s*İnovasyon|Ekonomi|Finans|Sağlık|Eğitim|Dünya|Gündem)\s*$",
        "",
        s,
        flags=re.I,
    ).strip()
    # 'TRT Haber Spor' -> 'TRT Haber', 'Habertürk Spor' -> 'Habertürk' ('A Spor' ve 'TRT Spor' hariç)
    if re.search(r"\s+Spor$", s, flags=re.I) and s.lower() not in ("a spor", "trt spor"):
        s = re.sub(r"\s+Spor$", "", s, flags=re.I).strip()
    return s or "Basın Kaynakları"

