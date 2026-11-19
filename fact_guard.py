# -*- coding: utf-8 -*-
"""
Gündem Analizi - Doğruluk ve Üslup Kalkanı (fact_guard.py)

1) Sayı koruması: Yapay zekânın yazdığı metindeki her sayı kaynak metinlerde aranır.
   Kaynakta olmayan sayı = uydurma riski -> metin yeniden yazdırılır veya o cümle çıkarılır.
2) Abartı koruması: "tarihi, dev, şok, rekor..." gibi kelimeler kaynakta yoksa başlıkta kullanılamaz.
3) Türkçe başlık düzeni: İngilizce "Her Kelimesi Büyük" başlıkları Türk basını usulü cümle düzenine çevirir
   (özel isimler kaynakta büyük harfle geçtiği için korunur).
4) Kaynak çöpü temizliği: Kaynak sitelerden sızan borsa bandı vb. ("%-0,09 %-0,46 e geldi.") satır başı kalıntıları.
"""
import re
from typing import Iterable, List, Set, Tuple

_ALWAYS_OK_YEARS = {"2025", "2026", "2027"}

_BIN_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*bin\s*(\d{1,3})?(?!\d)", re.I)


def _variants(raw: str) -> Set[str]:
    """Bir sayının olası yazımlarını üretir: 1.500 -> 1500 ; 21,2 -> 21.2 ; 28.075 -> 28075"""
    r = raw.strip()
    out = {r}
    no_thousands = r.replace(".", "")
    out.add(no_thousands)
    out.add(no_thousands.replace(",", "."))
    out.add(r.replace(",", "."))
    # 21,0 -> 21 ; 3.50 -> 3.5
    for v in list(out):
        if re.fullmatch(r"\d+\.\d+", v):
            out.add(v.rstrip("0").rstrip("."))
    return {v for v in out if v}


def extract_numbers(text: str) -> List[str]:
    t = text or ""
    found = []
    for m in re.finditer(r"\d+(?:[.,]\d+)*", t):
        found.append(m.group(0).strip(".,"))
    return [f for f in found if f]


def source_number_set(texts: Iterable[str]) -> Set[str]:
    allowed: Set[str] = set()
    for t in texts:
        t = t or ""
        for n in extract_numbers(t):
            allowed |= _variants(n)
        # "28 bin 75" -> 28075 ; "36 bin" -> 36000 ; "1,5 bin" -> 1500
        for m in _BIN_RE.finditer(t):
            try:
                base = float(m.group(1).replace(",", "."))
                tail = int(m.group(2)) if m.group(2) else 0
                val = int(round(base * 1000)) + tail
                allowed |= _variants(str(val))
                allowed |= _variants(f"{val:,}".replace(",", "."))
            except Exception:
                pass
    return allowed


def unverified_numbers(text: str, allowed: Set[str]) -> List[str]:
    bad = []
    for n in extract_numbers(text):
        vs = _variants(n)
        if vs & allowed:
            continue
        if n in _ALWAYS_OK_YEARS:
            continue
        # 0-10 arası küçük sayılar (sıra, adet anlatımı) yazıyla/rakamla karışık geçebilir
        try:
            if float(n.replace(".", "").replace(",", ".")) <= 10 and len(n) <= 2:
                continue
        except Exception:
            pass
        bad.append(n)
    # tekrarı kaldır, sırayı koru
    seen, out = set(), []
    for b in bad:
        if b not in seen:
            seen.add(b)
            out.append(b)
    return out


def drop_unverified_sentences(text: str, allowed: Set[str]) -> str:
    """Kaynakta olmayan sayı içeren cümleleri metinden çıkarır (son çare kurtarma)."""
    if not text:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    kept = [p for p in parts if not unverified_numbers(p, allowed)]
    return " ".join(kept).strip()


# ---------------------------------------------------------------------------
# Abartı kelimeleri
# ---------------------------------------------------------------------------
_HYPE_WORDS = [
    "tarihi", "tarihsel", "dev", "şok", "şoke", "sarsıcı", "sarstı", "sarsıldı", "rekor", "bomba",
    "flaş", "kritik", "deprem etkisi", "çılgın", "inanılmaz", "olay yaratan", "herkesi şaşırttı",
    "felaket", "kıyamet", "efsane",
]


def _tr_lower(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


def hype_violations(title: str, source_text: str) -> List[str]:
    tl = _tr_lower(title)
    sl = _tr_lower(source_text)
    bad = []
    for w in _HYPE_WORDS:
        if re.search(rf"(?<![a-zçğıöşü]){re.escape(w)}", tl) and not re.search(rf"(?<![a-zçğıöşü]){re.escape(w)}", sl):
            bad.append(w)
    return bad


# ---------------------------------------------------------------------------
# Türkçe başlık düzeni
# ---------------------------------------------------------------------------
def _tr_lower_word(w: str) -> str:
    if not w:
        return w
    return _tr_lower(w[0]) + w[1:]


def title_case_ratio(title: str) -> float:
    words = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü][\wçğıöşüÇĞİÖŞÜ'’\-]*", title or "") if len(w) > 3]
    if len(words) < 3:
        return 0.0
    return sum(1 for w in words[1:] if w[0].isupper()) / max(1, len(words) - 1)


def restore_acronyms(title: str, source_text: str) -> str:
    """Kaynakta TAMAMI BÜYÜK geçen kısaltmaları (ABD, AB, TCMB, NATO, KPSS) başlıkta da aynı yazar: 'Abd'de' -> 'ABD'de'."""
    if not title or not source_text:
        return title
    # Yalnızca normal (küçük harfli) cümle içinde büyük geçen kısaltmalar: "SON DAKİKA" gibi büyük harfli
    # başlık kalıntıları kısaltma sayılmaz.
    toks = source_text.split()
    acr = set()
    for i, tk in enumerate(toks):
        stem = re.split(r"['’.,:;!?()\"]", tk)[0]
        if not re.fullmatch(r"[A-ZÇĞİÖŞÜ]{2,6}", stem):
            continue
        prev_ok = i > 0 and re.search(r"[a-zçğıöşü]", toks[i - 1])
        next_ok = i + 1 < len(toks) and re.search(r"[a-zçğıöşü]", toks[i + 1])
        if prev_ok or next_ok:
            acr.add(stem)

    def _up(s: str) -> str:
        return s.replace("i", "İ").replace("ı", "I").upper()

    def fix(m):
        w = m.group(0)
        u = _up(w)
        return u if (u in acr and w != u) else w
    return re.sub(r"(?<![\wçğıöşüÇĞİÖŞÜ])[A-Za-zÇĞİÖŞÜçğıöşü]{2,6}(?=['’\s:,.!?]|$)", fix, title)


_KNOWN_PROPER = {
    "Türkiye", "Türk", "İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana", "Konya", "Gaziantep",
    "Şanlıurfa", "Kocaeli", "Mersin", "Diyarbakır", "Hatay", "Manisa", "Kayseri", "Samsun", "Balıkesir",
    "Kahramanmaraş", "Van", "Aydın", "Denizli", "Sakarya", "Tekirdağ", "Muğla", "Eskişehir", "Mardin",
    "Trabzon", "Malatya", "Erzurum", "Ordu", "Afyonkarahisar", "Sivas", "Zonguldak", "Çanakkale", "Osmaniye",
    "Giresun", "Rize", "Edirne", "Bolu", "Düzce", "Yalova", "KKTC", "Kıbrıs",
    "Avrupa", "Asya", "Afrika", "Amerika", "Almanya", "Fransa", "İngiltere", "İtalya", "İspanya", "Hollanda",
    "Belçika", "Avusturya", "İsviçre", "Yunanistan", "Bulgaristan", "Rusya", "Ukrayna", "Çin", "Japonya",
    "Hindistan", "İran", "Irak", "Suriye", "İsrail", "Filistin", "Gazze", "Lübnan", "Ürdün", "Mısır", "Katar",
    "Azerbaycan", "Gürcistan", "Ermenistan", "Polonya", "Krakow", "Okinawa", "Washington", "Moskova", "Brüksel",
    "Londra", "Paris", "Berlin", "Tahran", "Pekin", "Tokyo",
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    "Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir", "Süper", "Lig", " Şampiyonlar",
    "Euroleague", "Premier", "UEFA", "FIFA",
    "Erdoğan", "Recep", "Tayyip", "Şimşek", "Mehmet", "Fidan", "Hakan", "Yılmaz", "Cevdet", "Tekin", "Yusuf",
    "Kurum", "Murat", "Memişoğlu", "Kemal", "Trump", "Putin", "Zelenski", "Biden", "Netanyahu",
    "Merkez", "Bankası", "Yargıtay", "Danıştay", "Anayasa", "Mahkemesi", "Meclis", "Resmî", "Resmi", "Gazete",
    "Bakanlığı", "Bakanı", "Cumhurbaşkanı", "Cumhurbaşkanlığı", "Üniversitesi", "Belediyesi",
    "Google", "Apple", "Microsoft", "Meta", "Amazon", "Tesla", "Nvidia", "Samsung", "Xiaomi", "Redmi",
    "Huawei", "Intel", "Qualcomm", "OpenAI", "Anthropic", "Claude", "Gemini", "Volkswagen", "Mercedes",
    "Toyota", "Hyundai", "Renault", "Peugeot", "Fiat", "Skoda", "Volvo", "Nissan", "Chery", "Lexus", "Porsche",
    "Ferrari", "General", "Motors", "Corvette", "UniCredit", "Commerzbank", "Siemens", "Stellantis", "Nokia",
    "Euro", "Dolar", "Lira", "Lirası", "Bitcoin", "Brent",
}


def to_turkish_sentence_case(title: str, source_text: str = "") -> str:
    """
    'Volkswagen Performans Odaklı Yeni T-Roc R Modelini Tanıttı'
      -> 'Volkswagen performans odaklı yeni T-Roc R modelini tanıttı'
    Kural: Başlıktaki kelime kaynakta cümle ortasında BÜYÜK harfle geçiyorsa veya bilinen özel isimse
    korunur; kesme işareti alan kelimeler (Ankara'da) özel isimdir korunur; kısaltmalar korunur.
    """
    if title:
        title = restore_acronyms(title, source_text or "")
    if not title or title_case_ratio(title) < 0.6:
        return title
    src = re.sub(r"<[^>]+>", " ", source_text or "")
    # Kaynakta cümle ortasında büyük harfle geçen kelimeler (özel isim adayları)
    proper: Set[str] = set(_KNOWN_PROPER)
    for m in re.finditer(r"(?<=[a-zçğıöşü0-9,;'’\"”)]\s)([A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ\-]*)", src):
        proper.add(m.group(1).split("'")[0].split("’")[0])
    tokens = re.split(r"(\s+)", title.strip())
    out = []
    first_word_done = False
    after_colon = False
    for tok in tokens:
        if not tok or tok.isspace():
            out.append(tok)
            continue
        core = re.sub(r"^[\"“‘(]+", "", tok)
        has_apostrophe = ("'" in core or "’" in core)
        stem = re.split(r"['’]", core)[0]
        keep = False
        if not first_word_done or after_colon:
            keep = True
        elif has_apostrophe and stem and stem[0].isupper():
            keep = True  # Kesme işareti alan büyük harfli kelimeler Türkçe'de özel isimdir (Osmaniye'de, AB'den)
        elif not stem or not stem[0].isupper():
            keep = True
        elif len(stem) > 1 and (stem.isupper() or sum(1 for c in stem if c.isupper()) >= 2):
            keep = True  # AB, ABD, TCMB, T-Roc, iPhone gibi
        elif any(ch.isdigit() for ch in stem):
            keep = True
        elif stem in proper or stem.rstrip(".,:;!?") in proper:
            keep = True
        out.append(tok if keep else tok.replace(core, _tr_lower_word(core), 1) if core else tok)
        first_word_done = True
        after_colon = tok.endswith(":")
    return "".join(out).strip()


# ---------------------------------------------------------------------------
# Kaynak çöpü
# ---------------------------------------------------------------------------
_TICKER_HEAD_RE = re.compile(r"^\s*(?:(?:%\s*[-+]?\d+[.,]\d+|[-+]?\d+[.,]\d+\s*%)\s*){2,}")


def strip_source_junk(text: str) -> str:
    """Metin başındaki borsa bandı kalıntısını ('%-0,09 %-0,46 e geldi. ...') temizler."""
    if not text:
        return text
    s = text.lstrip()
    m = _TICKER_HEAD_RE.match(s)
    if not m:
        return text
    rest = s[m.end():]
    dot = rest.find(". ")
    if 0 <= dot <= 30:
        rest = rest[dot + 2:]
    return rest.strip() or text
