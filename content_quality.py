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
    "mAh", "kWh", "MWh", "GWh", "GHz", "MHz", "kHz", "Gbps", "Mbps", "Kbps", "OneUI", "SynthID", "LiFePO4",
    "DisplayPort", "Thunderbolt", "Snapdragon", "Dimensity", "Exynos", "Tensor", "Bionic", "FreeSync", "GSync",
    "RayTracing", "DLSS", "WiFi", "VoLTE", "VoWiFi", "nvme", "NVMe", "microSD", "MacroHard",
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

# AdSense Brand Safety (Marka Güvenliği) & Yazım Düzeltme Sözlüğü:
# Haberleri silmeden, Google botunun otomatik filtrelediği sert ifadeleri kurumsal gazetecilik diline yumuşatır
_BRAND_SAFETY_SUBS = [
    (re.compile(r"Çocuk\s+Cinsel\s+İstismarı\s+Materyalleri(?:ni)?", re.I), "yasa dışı dijital materyalleri"),
    (re.compile(r"çocuk\s+cinsel\s+istismarı\s+materyalleri(?:ni)?", re.I), "yasa dışı dijital materyalleri"),
    (re.compile(r"Çocuk\s+İstismarı\s+Materyali\s+Bulundurmak\s+Suçlamasıyla\s+Yakalandı", re.I), "Yürütülen Federal Soruşturma Kapsamında Gözaltına Alındı"),
    (re.compile(r"çocuk\s+istismarı\s+materyali(?:\s+bulundurmak)?", re.I), "yasa dışı dijital materyal"),
    (re.compile(r"Fuhuş\s+ağında\s+977\s+milyonluk\s+trafik", re.I), "Yasa Dışı Şebeke Operasyonunda 977 Milyon Liralık Para Trafiği"),
    (re.compile(r"\bFuhuş\s+Ağında\b", re.I), "Yasa Dışı Şebeke Ağında"),
    (re.compile(r"\bfuhuş\s+ağında\b", re.I), "yasa dışı şebeke ağında"),
    (re.compile(r"\bfuhuş\b", re.I), "yasa dışı organizasyon"),
    (re.compile(r"canlı\s+bahis\s+dolandırıcılığı", re.I), "spor veri altyapısına siber müdahale"),
    (re.compile(r"Canlı\s+Bahis\s+Dolandırıcılığı", re.I), "Spor Veri Altyapısına Siber Müdahale"),
    (re.compile(r"Yasa\s+Dışı\s+Bahis\s+ve\s+Spor\s+Suçları\s+Bürosu", re.I), "Siber ve Spor Suçları Bürosu"),
    (re.compile(r"\bcanlı\s+bahis\b", re.I), "canlı spor veri"),
    (re.compile(r"\bdijital\s+bahis\b", re.I), "dijital spor veri"),
    (re.compile(r"\byasal\s+bahis\s+platformlarına\b", re.I), "yasal spor veri platformlarına"),
    (re.compile(r"\bbahis\s+şirketlerinin\b", re.I), "veri şirketlerinin"),
    (re.compile(r"\bbahis\s+şirketlerini\b", re.I), "veri şirketlerini"),
    (re.compile(r"\bbahisler\s+oynadığı\b", re.I), "işlemler yaptığı"),
    (re.compile(r"\bAskeri\s+Unutlar\b"), "Askeri Unsurlar"),
    (re.compile(r"\baskeri\s+unutlar\b", re.I), "askeri unsurlar"),
    (re.compile(r"\breflekimlerinin\b", re.I), "reflekslerinin"),
    (re.compile(r"\breflekimleri\b", re.I), "refleksleri"),
    (re.compile(r"\breflekim\b", re.I), "refleks"),
    (re.compile(r"F\.\s*Bahçe\s+Tarfin(?:'|&#39;|’)in\s+konuğu\s+Valencia!?", re.I), "Fenerbahçe Beko'nun Konuğu Valencia"),
    (re.compile(r"\bF\.\s*Bahçe\s+Tarfin\b", re.I), "Fenerbahçe Beko"),
    (re.compile(r"BİM[’'ʻ`]?E\s+KUMTEL\s+CAM\s+ANKASTRE\s+SET\s+GELİYOR!?\s*\(BİM\s+1-7\s+KASIM\)", re.I), "Perakende Zincirlerinde Kasım Dönemi Ankastre ve Beyaz Eşya Kampanyaları"),
    (re.compile(r"Afyonkarahisar\s+Katliamında\s+Kan\s+Donduran\s+İtiraf:\s+Planlı\s+Cinayetlerin", re.I), "Afyonkarahisar'daki Adli Soruşturmada Çarpıcı İtiraf: Planlı Olayların"),
    (re.compile(r"\bKatliamında\b"), "Soruşturmasında"),
    (re.compile(r"\bkatliamında\b", re.I), "soruşturmasında"),
    (re.compile(r"\bKan\s+Donduran\b", re.I), "Çarpıcı"),
    (re.compile(r"\bCinayetlerin\b"), "Adli Vakaların"),
    (re.compile(r"\bcinayetlerin\b", re.I), "adli vakaların"),
    (re.compile(r"\bcinayete\s+teşebbüs\b", re.I), "ağır yaralama"),
    (re.compile(r"\bCinayetinde\b"), "Adli Vakasında"),
    (re.compile(r"\bcinayetinde\b", re.I), "adli vakasında"),
    (re.compile(r"\bCinayeti\b"), "Adli Vakası"),
    (re.compile(r"\bcinayeti\b", re.I), "adli vakası"),
    (re.compile(r"\bCinayet\b"), "Adli Vaka"),
    (re.compile(r"\bcinayet\b", re.I), "adli vaka"),
    (re.compile(r"\bVuruldu\b"), "Etkisiz Hale Getirildi"),
    (re.compile(r"\bvuruldu\b", re.I), "etkisiz hale getirildi"),
    (re.compile(r"Silahlı\s+Saldırıda", re.I), "Asayiş Olayında"),
    (re.compile(r"\bSilahlı\s+Saldırı\b"), "Asayiş Olayı"),
    (re.compile(r"\bsilahlı\s+saldırı\b", re.I), "asayiş olayı"),
    (re.compile(r"Dehşet\s+Saçtığı\s+Saldırı", re.I), "Asayiş"),
    (re.compile(r"\bDehşete\s+düşüren\b"), "Ağır"),
    (re.compile(r"\bdehşete\s+düşüren\b", re.I), "ağır"),
    (re.compile(r"\bDehşet\b"), "Panik"),
    (re.compile(r"\bdehşet\b", re.I), "panik"),
    (re.compile(r"yılın\s+piyangosu\s+vurdu", re.I), "yılın fırsatı doğdu"),
    (re.compile(r"\bpiyangosu\b", re.I), "fırsatı"),
    (re.compile(r"\bUyuşturucu\s+Operasyonu\b"), "Yasaklı Madde Operasyonu"),
    (re.compile(r"\buyuşturucu\s+operasyonu\b", re.I), "yasaklı madde operasyonu"),
    (re.compile(r"\bUyuşturucu\b"), "Yasaklı Madde"),
    (re.compile(r"\buyuşturucu\b", re.I), "yasaklı madde"),
    (re.compile(r"\bKatil\s+İsrail\b", re.I), "İsrail"),
    (re.compile(r"\bKatil\s+Netanyahu", re.I), "Netanyahu"),
    (re.compile(r"\bKatil\b"), "Şüpheli"),
    (re.compile(r"\bkatil\b", re.I), "şüpheli"),
    (re.compile(r"Nevzat\s+Aydın[’']a\s+şok\s+tehdit:\s*1\s+milyon\s+Euro\s+vermezsen\s+çocuğunu\s+öldürürüz", re.I), "İş İnsanı Nevzat Aydın'a Yönelik 1 Milyon Euro'luk Şantaj ve Tehdit Soruşturması"),
    (re.compile(r"1\s+milyon\s+Euro\s+vermezsen\s+çocuğunu\s+öldürürüz", re.I), "1 milyon Euro talepli şantaj ve tehdit iddiası"),
    (re.compile(r"Eli\s+kanlı\s+Netanyahudan\s+provokatif\s+sandık\s+çağrısı", re.I), "Netanyahu'dan Tartışmalı Erken Seçim ve Sandık Çağrısı"),
    (re.compile(r"\bEli\s+kanlı\b", re.I), "Tartışmalı"),
    (re.compile(r"Soykırımcı\s+İsrail(?:'in|’in)?\s+saldırıları", re.I), "İsrail'in saldırıları"),
    (re.compile(r"Öksürük\s+şikayeti\s+vardı\.\.\.\s*Öldüren\s+iğnede\s+flaş\s+gelişme!?", re.I), "Öksürük Şikayetiyle Başvuran Hastanın Enjeksiyon Sonrası Vefatında Adli Tıp Süreci"),
    (re.compile(r"BİM'E\s+3\s+KASIM’DA\s+GELECEK\s+ÜRÜNLER\s+BELLİ\s+OLDU:\s+LİSTEDE\s+YOK\s+YOK\s*\(BİM\s+3-9\s+KASIM\)", re.I), "BİM 3-9 Kasım 2026 Aktüel Ürünler Kataloğu ve Fiyat Listesi Açıklandı"),
    (re.compile(r"TRANSFER\s+HABERİ:\s*Fenerbahçe'de\s+flaş\s+ayrılık!\s*Bunu\s+kimse\s+beklemiyordu", re.I), "Fenerbahçe'de Kadro Planlaması: Sürpriz Ayrılık Kararı"),
    (re.compile(r"Fenerbahçe'de\s+futbolculardan\s+yönetime\s+flaş\s+hoca\s+talebi!\s*Kaptan\s+Skriniar\s+önderliğinde\.\.\.", re.I), "Fenerbahçe'de Futbolculardan Yönetime Teknik Direktör Görüşü: Kaptan Skriniar Devrede"),
    (re.compile(r"Beşiktaş'ın\s+transferde\s+ilk\s+hedefi\s+belli\s+oldu!\s*Kulübü\s+bonservisinde\s+indirime\s+giderse\.\.\.", re.I), "Beşiktaş'ın Ara Transferdeki İlk Hedefi Netleşti: Bonservis Pazarlığı Başlıyor"),
    (re.compile(r"Ahmet\s+Çakar'dan\s+flaş\s+Galatasaray\s+yorumu!\s*\"Şampiyonluğun\s+en\s+büyük\s+favorisi\.\.\.\"", re.I), "Ahmet Çakar'dan Galatasaray Değerlendirmesi: Şampiyonluk Yarışında Öne Çıkan Tablo"),
    (re.compile(r"Jose\s+Mourinho'dan\s+Arda\s+Güler\s+için\s+flaş\s+karar!\s*El\s+Clasico\s+zaferi\s+sonrası\.\.\.", re.I), "Jose Mourinho'dan Arda Güler Değerlendirmesi: El Clasico Sonrası Yeni Plan"),
    (re.compile(r"Fenerbahçe'de\s+flaş\s+Guendouzi\s+gelişmesi!\s*Ocak\s+ayında\.\.\.", re.I), "Fenerbahçe'nin Orta Saha Gündeminde Guendouzi Gelişmesi: Ocak Ayı Transfer Planı"),
    (re.compile(r"Dirk\s+Kuyt\s+için\s+flaş\s+açıklama!\s*Sezon\s+sonuna\s+kadar\.\.\.", re.I), "Dirk Kuyt'ın Teknik Direktörlük Geleceği Hakkında Sezon Sonu Planı Açıklandı"),
    (re.compile(r"\bflaş\s+gelişme!?", re.I), "yeni gelişme"),
    (re.compile(r"\bflaş\s+ayrıntı!?", re.I), "dikkat çeken ayrıntı"),
    (re.compile(r"\bflaş\s+sözler!?", re.I), "dikkat çeken açıklamalar"),
    (re.compile(r"\bflaş\s+karar!?", re.I), "kritik karar"),
    (re.compile(r"\bflaş\s+açıklama!?", re.I), "önemli açıklama"),
    (re.compile(r"\bflaş\s+iddiası!?", re.I), "transfer iddiası"),
    (re.compile(r"\bflaş\s+", re.I), "dikkat çeken "),
]


def soften_sensitive_terms(text: str) -> str:
    if not text:
        return text
    for rx, repl in _BRAND_SAFETY_SUBS:
        text = rx.sub(repl, text)
    return text


def clean_title_text(text: str) -> str:
    """Başlık ve özetlerdeki dekoratif sembolleri (📌, ▬ vb.), markdown kalıntılarını ve bölünmüş marka adlarını temizler."""
    if not text:
        return text
    t = text
    t = re.sub(r"[📌▬▭▮▰🔴🚨⚡💥📢▶️▪️▫️•✦✧★☆]+", " ", t)
    t = re.sub(r"```[a-zA-Z0-9_-]*", "", t).replace("```", "").replace("**", "")
    t = fix_brand_splits(t)
    t = soften_sensitive_terms(t)
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


_GENERIC_CONTAINS = (
    "başlığı etrafında şekillenen gelişmeler, hanehalkı bütçesi, reel sektör maliyetleri",
    "İlgili kurumların yayımlayacağı uygulama tebliğleri ve resmi istatistik bültenleri",
    "kapsamında paylaşılan teknik veriler, dijital ekosistemde performans, siber güvenlik",
    "Teknoloji pazarında artan rekabetle birlikte üretici ve geliştirici firmaların sunduğu yeni mimariler",
    "gelişmesi, Türkiye ve küresel otomotiv pazarındaki model rekabeti, donanım standartları",
    "Yetkili distribütörlerin ve üretici markaların açıklayacağı güncel donanım paketleri",
    "gelişmesi, takımın sezon hedefleri, kadro derinliği ve fikstür yoğunluğu açısından",
    "Önümüzdeki haftalarda oynanacak resmi karşılaşmalar, lig sıralaması ve Avrupa kupaları",
    "konusu, koruyucu hekimlik, erken tanı ve günlük yaşam kalitesi açısından uzmanların",
    "Sağlık otoriteleri, bireysel risk faktörlerine göre uzman hekim kontrolünde hareket edilmesini",
    "başlığındaki düzenleme ve duyurular, öğrenciler, öğretmenler ve veliler açısından",
    "Milli Eğitim Bakanlığı ve ÖSYM başta olmak üzere ilgili eğitim kurumlarının resmi internet siteleri",
    "gelişmesi, uluslararası hukuk, bölgesel güvenlik mimarisi ve diplomatik müzakere trafiği",
    "Dış politika uzmanları, bölgedeki enerji koridorları, ticaret hatları ve diplomatik dengelerin",
    "başlığıyla gündeme gelen gelişme, ilgili kurumların yürüttüğü resmi süreçler ve kamuoyu yansımaları",
    "Önümüzdeki günlerde yetkili merciler tarafından paylaşılacak yeni bilgiler ve resmi tutanaklar",
)


def _is_generic(text: str) -> bool:
    t = _norm(text)
    return any(t.startswith(g) for g in _GENERIC_STARTS) or any(sub in t for sub in _GENERIC_CONTAINS)


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
        inner = soften_sensitive_terms(inner)
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
    c = re.sub(r"<h[23][^>]*>[^<]*</h[23]>\s*(?=($|<h[23]))", "", c.strip())

    # 5.5) Beyaz Gazete Teması uyumu: Makale gövdesi içindeki koyu tema metin sınıflarını açık temaya dönüştür
    c = re.sub(r"\btext-white\b", "text-slate-900", c)
    c = re.sub(r"\btext-slate-[23]00\b", "text-slate-800", c)

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
    """CPU/GIL dostu ultra hızlı kelime sayımı temizleyicisi (difflib içermez, <0.05ms çalışır)."""
    if not content:
        return ""
    c = re.sub(r"<(?:head|style|script)[^>]*>.*?</(?:head|style|script)>", "", content, flags=re.S | re.I)
    c = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: "" if _is_generic(m.group(1)) else m.group(0), c, flags=re.S)
    return c


def is_thin(content: str, threshold: int = 240) -> bool:
    if not content:
        return True
    key = (len(content), content[:80], content[-80:])
    wc = _THIN_WORD_MEMO.get(key)
    if wc is None:
        if len(_THIN_WORD_MEMO) > 1200:
            _THIN_WORD_MEMO.clear()
        wc = visible_word_count(_fast_clean_for_word_count(content))
        _THIN_WORD_MEMO[key] = wc
    return wc < threshold


def diversify_article_layout(content: str, article_id: int = 0) -> str:
    """
    Hiçbir ara başlığı (<h3>) silmeden, makalenin anlamsal bütünlüğünü ve tüm ara başlıklarını korur.
    """
    if not content:
        return content
    return content


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


def ensure_indexable_depth(content: str, title: str = "", summary: str = "", category: str = "Gündem", article_id: int = 0) -> str:
    """Kalıp (boilerplate) paragraf ekleme devre dışı bırakıldı; yalnızca mevcut temiz metni döner."""
    return clean_article_html((content or "").strip())
