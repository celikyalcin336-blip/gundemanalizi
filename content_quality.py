"""
İçerik Kalitesi Yardımcıları (AdSense uyumu)

- fix_brand_splits(): Otomatik temizleyicinin böldüğü marka adlarını düzeltir ("You Tube" -> "YouTube").
- protect_brands()/restore_brands(): Yapışık kelime ayırıcısı çalışmadan önce marka adlarını korur.
- clean_article_html(): Yayındaki (eski) haberlerden şablon "değerlendirme" kutusunu, her habere eklenen
  hazır dolgu paragraflarını, kırık linkleri, ham HTML belge sızıntılarını (<!DOCTYPE html>, <style>, <!-- Giriş -->)
  ve tekrar eden cümle/paragrafları GÖSTERİM ANINDA ve VERİTABANI TEMİZLİĞİNDE temizler.
- visible_word_count() / is_thin(): Haberin okunabilir kelime sayısını ölçer; kısa haberler noindex alır.
"""
import difflib
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


def clean_title_text(text: str) -> str:
    """Başlık ve özetlerdeki dekoratif sembolleri (📌, ▬ vb.), markdown kalıntılarını ve bölünmüş marka adlarını temizler."""
    if not text:
        return text
    t = text
    t = re.sub(r"[📌▬▭▮▰🔴🚨⚡💥📢▶️▪️▫️•✦✧★☆]+", " ", t)
    t = re.sub(r"```[a-zA-Z0-9_-]*", "", t).replace("```", "").replace("**", "")
    t = fix_brand_splits(t)
    t = re.sub(r"\s+", " ", t).strip(" -–—|:;,")
    return t.strip()


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
    "Konuyla ilgili resmi mercilerin ve ilgili kurumların değerlendirmeleri",
    "Spor kamuoyunun yakından takip ettiği gelişmeyle ilgili resmi açıklamaların",
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _is_generic(text: str) -> bool:
    t = _norm(text)
    return any(t.startswith(g) for g in _GENERIC_STARTS)


def _strip_raw_html_document_leak(content: str) -> str:
    """
    AI modelinin yanlışlıkla tam HTML belgesi (```html <!DOCTYPE html> <head><style>...</style></head>
    <body><h1>...</h1><!-- Giriş --><div class="editor-comment">...</div><div class="source-info">...</div></body></html> ```)
    döndürdüğü makalelerdeki tüm yapısal ve şablonsal kalıntıları kökünden temizler.
    """
    if not content:
        return ""
    c = content

    # 0) Eğer makalede ham HTML sızıntısı (<!DOCTYPE, <html, ```html) varsa ve başına database.py tarafından
    # yapay bir <p class="lead..."> eklenmişse, gerçek giriş paragrafıyla mükerrer olmaması için yapay lead'i kaldır
    if re.search(r"<!\s*DOCTYPE|<html\b|```html|<!--\s*Giriş", c, flags=re.I):
        c = re.sub(r"^\s*<p\s+class=\"lead[^\"]*\"[^>]*>.*?</p>\s*", "", c, count=1, flags=re.S | re.I)

    # 1) Markdown kod çitleri (```html, ```xml, ```)
    c = re.sub(r"```[a-zA-Z0-9_-]*\s*", "", c)
    c = c.replace("```", "")

    # 2) İç içe sızmış <head>, <style>, <script>, <title> blokları
    c = re.sub(r"<head\b[^>]*>.*?</head>", "", c, flags=re.S | re.I)
    c = re.sub(r"<style\b[^>]*>.*?</style>", "", c, flags=re.S | re.I)
    c = re.sub(r"<script\b[^>]*>.*?</script>", "", c, flags=re.S | re.I)
    c = re.sub(r"<title\b[^>]*>.*?</title>", "", c, flags=re.S | re.I)

    # 3) Belge sarmalayıcı etiketler (<!DOCTYPE>, <html>, <body>, <meta>, <link>, <article>, <section>, <main>, <header>, <footer>)
    c = re.sub(r"<!\s*DOCTYPE[^>]*>", "", c, flags=re.I)
    c = re.sub(r"</?(?:html|body|meta|link|article|section|main|header|footer)\b[^>]*>", "", c, flags=re.I)

    # 4) AI şablon yorum satırları (<!-- Giriş -->, <!-- Gelişme - Paragraf 1 -->, <!-- Gündem Analizi Yorumu --> vb.)
    c = re.sub(r"<!--.*?-->", "", c, flags=re.S)

    # 5) Makale gövdesi içindeki mükerrer <h1>...</h1> başlığı (sayfa şablonunda zaten <h1> var)
    c = re.sub(r"<h1\b[^>]*>.*?</h1>", "", c, flags=re.S | re.I)

    # 6) AI şablon "Gündem Analizi Yorumu / Değerlendirmesi" ve "source-info" kutuları
    c = re.sub(
        r'<div\b[^>]*class="[^"]*(?:editor-comment|source-info|article-meta|meta-info)[^"]*"[^>]*>.*?</div>',
        "",
        c,
        flags=re.S | re.I,
    )
    c = re.sub(
        r'<div\b[^>]*>\s*<h[2-5][^>]*>[^<]*(?:Gündem\s+Analizi\s+(?:Yorumu|Değerlendirmesi|Analizi|Notu)|Editör(?:ün)?\s+(?:Yorumu|Notu|Değerlendirmesi))[^<]*</h[2-5]>.*?</div>',
        "",
        c,
        flags=re.S | re.I,
    )
    c = re.sub(
        r'<h[2-5][^>]*>[^<]*(?:Gündem\s+Analizi\s+(?:Yorumu|Değerlendirmesi|Analizi|Notu)|Editör(?:ün)?\s+(?:Yorumu|Notu|Değerlendirmesi))[^<]*</h[2-5]>\s*(?:<p[^>]*>.*?</p>)?',
        "",
        c,
        flags=re.S | re.I,
    )

    # 7) Alt kısımda kalan tekil "Kaynak: ..." ve "Kategori: ..." satırları
    c = re.sub(
        r"<p[^>]*>\s*(?:<(?:strong|b)>)?\s*(?:Kaynak|Kategori|Haber\s+Kaynağı|Etiketler)\s*:\s*(?:</(?:strong|b)>)?\s*[^<]{1,120}</p>",
        "",
        c,
        flags=re.I,
    )
    return c.strip()


def clean_article_html(content: str) -> str:
    """Gösterim anında ve veritabanı bakımında eski şablon kalıntılarını ve ham HTML sızıntılarını temizler."""
    if not content:
        return content
    c = _strip_raw_html_document_leak(content)

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
        # Kaynak siteden paragraf başına/içine karışmış BÜYÜK HARFLİ ara başlık kalıntılarını temizle
        inner = re.sub(r"^(?:[A-ZÇĞİÖŞÜ0-9'’\-]+\s+){4,}[A-ZÇĞİÖŞÜ0-9'’\-]+\s*", "", inner.strip())
        inner = fix_brand_splits(inner)
        return f"{m.group(1)}{inner}</p>"
    c = re.sub(r"(<p[^>]*>)(.*?)</p>", _fix_p, c, flags=re.S)

    # 3.5) Ara başlıklardaki (h2/h3) marka bölünmelerini ve sembolleri düzelt
    def _fix_heading(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        inner = clean_title_text(inner)
        return f"<{tag}{attrs}>{inner}</{tag}>"
    c = re.sub(r"<(h[23])([^>]*)>(.*?)</\1>", _fix_heading, c, flags=re.S | re.I)

    # 4) Paragraflar arası tekrar eden cümleler ve mükerrer giriş (lead) paragrafı
    seen_text = [""]
    seen_paras = []

    def _dedupe(m):
        inner = m.group(2)
        p_norm = _norm(inner).lower()
        p_words = {w for w in re.findall(r"\w+", p_norm) if len(w) >= 4}
        if p_norm and len(p_words) >= 6:
            for prev_norm, prev_words in seen_paras:
                if difflib.SequenceMatcher(None, p_norm, prev_norm).ratio() >= 0.62:
                    return ""
                if prev_words and min(len(p_words), len(prev_words)) >= 8:
                    if len(p_words & prev_words) / min(len(p_words), len(prev_words)) >= 0.65:
                        return ""
            seen_paras.append((p_norm, p_words))

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

    # 5) Boş kalan paragraflar ve altı boş kalan ara başlıklar
    c = re.sub(r"<p[^>]*>\s*</p>", "", c)
    c = re.sub(r"<h[23][^>]*>[^<]*</h[23]>\s*(?=(<div|$|<h[23]))", "", c.strip())

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
    c = _strip_raw_html_document_leak(content)

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
    seen_paras = []

    def _dedupe(m):
        inner = m.group(2)
        p_norm = _norm(inner).lower()
        p_words = {w for w in re.findall(r"\w+", p_norm) if len(w) >= 4}
        if p_norm and len(p_words) >= 6:
            for prev_norm, prev_words in seen_paras:
                if difflib.SequenceMatcher(None, p_norm, prev_norm).ratio() >= 0.62:
                    return ""
                if prev_words and min(len(p_words), len(prev_words)) >= 8:
                    if len(p_words & prev_words) / min(len(p_words), len(prev_words)) >= 0.65:
                        return ""
            seen_paras.append((p_norm, p_words))

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
    c = re.sub(r"<h[23][^>]*>[^<]*</h[23]>\s*(?=(<div|$|<h[23]))", "", c.strip())
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


def clean_summary_text(summary: str, fallback_title: str = "") -> str:
    """
    Özet (summary / meta description) metnini temizler; eski haberlerdeki 500-1500 karakterlik
    ham kazınmış metin yığınlarını 1-2 cümlelik (<= 210 karakter) temiz özete indirger.
    """
    s = clean_title_text(summary or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 220:
        cut = s[:215]
        last_dot = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        if last_dot >= 70:
            s = cut[:last_dot + 1].strip()
        else:
            last_sp = cut.rfind(" ")
            s = (cut[:last_sp] if last_sp > 60 else cut).rstrip(" ,;:-") + "..."
    if len(s) < 25 and fallback_title:
        s = clean_title_text(fallback_title)
    return s
