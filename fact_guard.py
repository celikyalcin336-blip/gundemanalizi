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
# Türkçe başlık ve ara başlık imla motoru (cümle düzeni + özel isim/kısaltma koruması)
# ---------------------------------------------------------------------------
def _tr_upper(s: str) -> str:
    return (s or "").replace("i", "İ").replace("ı", "I").upper()


def _tr_lower_word(w: str) -> str:
    if not w:
        return w
    return _tr_lower(w[0]) + _tr_lower(w[1:])


def _tr_cap_word(w: str) -> str:
    if not w:
        return w
    return _tr_upper(w[0]) + _tr_lower(w[1:])


def title_case_ratio(title: str) -> float:
    words = [w for w in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü][\wçğıöşüÇĞİÖŞÜ'’\-]*", title or "") if len(w) > 3]
    if len(words) < 3:
        return 0.0
    return sum(1 for w in words[1:] if w[0].isupper()) / max(1, len(words) - 1)


_ALWAYS_ACRONYMS = {
    "ABD", "AB", "TBMM", "TCMB", "TÜİK", "KPSS", "ÖSYM", "YKS", "LGS", "ALES", "DGS", "YDS", "YÖKDİL",
    "MEB", "YÖK", "SGK", "GSS", "EYT", "BES", "KYK", "AFAD", "NATO", "BM", "UNESCO", "UNICEF", "IMF",
    "FED", "ECB", "FDA", "DSÖ", "WHO", "UEFA", "FIFA", "TFF", "PFDK", "MHK", "FIBA", "ATP", "WTA", "NBA", "UFC",
    "BDDK", "SPK", "EPDK", "RTÜK", "BTK", "KVKK", "TMSF", "MASAK", "THY", "TCDD", "PTT", "TOKİ", "İBB", "ABB",
    "EGO", "İETT", "İSKİ", "ASKİ", "DMM", "MİT", "TSK", "MSB", "EGM", "KGM", "MGM", "İŞKUR", "KOSGEB",
    "TÜBİTAK", "ASELSAN", "ROKETSAN", "TUSAŞ", "HAVELSAN", "BAYKAR", "TOGG", "BYD", "BMW", "SUV", "KDV",
    "ÖTV", "MTV", "GSYH", "TÜFE", "ÜFE", "BIST", "DXY", "OPEC", "BRICS", "APEC", "G7", "G20", "KAAN",
    "İHA", "SİHA", "TİHA", "TCK", "CMK", "TMK", "HSK", "AYM", "AİHM", "PKK", "YPG", "PYD", "DEAŞ", "IŞİD",
    "FETÖ", "CIA", "FBI", "BBC", "CNN", "TRT", "AA", "DHA", "İHA", "ANKA", "RT", "AP", "AFP", "LNG", "LPG",
    "DNA", "RNA", "MR", "BT", "KOAH", "SMA", "AIDS", "HIV", "HPV", "USB", "SSD", "RAM", "GPU", "CPU", "AI",
    "CEO", "CFO", "CTO", "IPO", "ETF", "NFT", "KKTC", "BAE", "Katar",
}
_ACRONYM_ASCII_FIX = {
    "tuik": "TÜİK", "osym": "ÖSYM", "yok": None, "iskur": "İŞKUR", "tubitak": "TÜBİTAK",
    "rtuk": "RTÜK", "dso": "DSÖ", "toki": "TOKİ", "ibb": "İBB", "mit": "MİT",
    "siha": "SİHA", "tiha": "TİHA", "aihm": "AİHM", "feto": "FETÖ", "kdv": "KDV", "otv": "ÖTV", "tufe": "TÜFE",
}
# "AB", "BM", "AA", "AP", "BT", "MR", "AI", "RT" gibi çok kısa kısaltmalar küçük yazıldığında Türkçe kelime/ek ile
# karışabileceği için ("ab" nadir ama "mr", "ai") yalnızca net olanları zorla büyüt:
_SAFE_LOWER_TO_UPPER_ACR = _ALWAYS_ACRONYMS - {"AA", "AP", "BT", "MR", "AI", "RT", "YÖK", "Katar", "GS"}


def restore_acronyms(title: str, source_text: str = "") -> str:
    """Kaynakta büyük geçen veya bilinen kısaltmaları (ABD, FED, TCMB, NATO, KPSS, MG7) başlıkta da büyük yazar."""
    if not title:
        return title
    acr = set(_SAFE_LOWER_TO_UPPER_ACR)
    if source_text:
        clean_src = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", " ", source_text, flags=re.I | re.S)
        clean_src = re.sub(r"<[^>]+>", " ", clean_src)
        toks = clean_src.split()
        for i, tk in enumerate(toks):
            stem = re.split(r"['’.,:;!?()\"]", tk)[0]
            if not re.fullmatch(r"[A-ZÇĞİÖŞÜ]{2,6}", stem):
                continue
            prev_ok = i > 0 and re.search(r"[a-zçğıöşü]", toks[i - 1])
            next_ok = i + 1 < len(toks) and re.search(r"[a-zçğıöşü]", toks[i + 1])
            if prev_ok or next_ok:
                acr.add(stem)

    def fix(m):
        w = m.group(1)
        suf = m.group(2) or ""
        lw = _tr_lower(w)
        if lw in _ACRONYM_ASCII_FIX and _ACRONYM_ASCII_FIX[lw]:
            return _ACRONYM_ASCII_FIX[lw] + _tr_lower(suf)
        u = _tr_upper(w)
        if u in acr:
            return u + (_tr_lower(suf) if suf else "")
        # Model kodları: Mg7 -> MG7, Gt3 -> GT3, Id.4 -> ID.4, F-35 -> F-35
        if re.fullmatch(r"[A-Za-z]{1,3}\d{1,3}[A-Za-z]?", w):
            return w.upper() + (_tr_lower(suf) if suf else "")
        return m.group(0)

    return re.sub(
        r"(?<![\wçğıöşüÇĞİÖŞÜ])([A-Za-zÇĞİÖŞÜçğıöşü]{2,7}|[A-Za-z]{1,3}\d{1,3}[A-Za-z]?)(['’][A-Za-zÇĞİÖŞÜçğıöşü]+)?(?![\wçğıöşüÇĞİÖŞÜ])",
        fix,
        title,
    )


# Her koşulda özel isim olan (küçük yazılsa bile büyütülmesi güvenli olan) kelimeler:
_UNAMBIGUOUS_PROPER = {
    # Ülkeler, kıtalar, bölgeler, şehirler
    "Türkiye", "Türk", "İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Adana", "Konya", "Gaziantep",
    "Şanlıurfa", "Kocaeli", "Mersin", "Diyarbakır", "Hatay", "Manisa", "Kayseri", "Samsun", "Balıkesir",
    "Kahramanmaraş", "Van", "Denizli", "Sakarya", "Tekirdağ", "Muğla", "Eskişehir", "Mardin", "Trabzon",
    "Malatya", "Erzurum", "Ordu", "Afyonkarahisar", "Sivas", "Zonguldak", "Çanakkale", "Osmaniye", "Giresun",
    "Rize", "Edirne", "Bolu", "Düzce", "Yalova", "Hakkari", "Şırnak", "Tunceli", "Bingöl", "Muş", "Bitlis",
    "Ağrı", "Kars", "Iğdır", "Ardahan", "Artvin", "Gümüşhane", "Bayburt", "athena", "Kıbrıs", "Balkan", "Balkanlar",
    "Anadolu", "Trakya", "Ege", "Akdeniz", "Karadeniz", "Marmara",
    "Avrupa", "Asya", "Afrika", "Amerika", "Almanya", "Fransa", "İngiltere", "İtalya", "İspanya", "Hollanda",
    "Belçika", "Avusturya", "İsviçre", "İsveç", "Norveç", "Danimarka", "Finlandiya", "Polonya", "Macaristan",
    "Romanya", "Çekya", "Portekiz", "Yunanistan", "Bulgaristan", "Sırbistan", "Bosna", "Hersek", "Arnavutluk",
    "Kosova", "Karadağ", "Hırvatistan", "Rusya", "Ukrayna", "Belarus", "Moldova", "Çin", "Japonya", "Kore",
    "Hindistan", "Pakistan", "Endonezya", "Malezya", "Tayland", "Vietnam", "Filipinler", "Avustralya", "Kanada",
    "Meksika", "Brezilya", "Arjantin", "Şili", "Kolombiya", "Venezuela", "İran", "Irak", "Suriye", "İsrail",
    "Filistin", "Gazze", "Lübnan", "Ürdün", "Mısır", "Suudi", "Arabistan", "Katar", "Kuveyt", "Umman", "Yemen",
    "Libya", "Tunus", "Cezayir", "Fas", "Sudan", "Somali", "Nijerya", "Azerbaycan", "Gürcistan", "Ermenistan",
    "Kazakistan", "Özbekistan", "Türkmenistan", "Kırgızistan", "Tacikistan", "Afganistan",
    "Krakow", "Okinawa", "Washington", "Moskova", "Brüksel", "Londra", "Paris", "Berlin", "Roma", "Madrid",
    "Atina", "Sofya", "Varşova", "Budapeşte", "Viyana", "Cenevre", "Zürih", "Amsterdam", "stokholm", "Tahran",
    "Bağdat", "Şam", "Beyrut", "Kudüs", "Kahire", "Riyad", "Doha", " Bakü", "Tiflis", "Erivan", "Pekin",
    "Tokyo", "Seul", "Şanghay", "Shenzhen", "Tayvan", "Kırım", "Donbas",
    # Ulus / uyruk / dil adları (TDK kuralı: büyük harfle başlar)
    "Alman", "Fransız", "İngiliz", "İtalyan", "İspanyol", "Hollandalı", " Rus ", "Rusyalı", "Ukraynalı",
    "Çinli", "Japon", "Koreli", "Hintli", "İranlı", "Iraklı", "Suriyeli", "İsrailli", "Filistinli", "Lübnanlı",
    "Ürdünlü", "Mısırlı", "Libyalı", "Yunan", "Bulgar", "Polonyalı", "Macar", "Amerikalı", "Amerikan", "Avrupalı",
    "İngilizce", "Türkçe", "Almanca", "Fransızca", "Arapça", "Rusça",
    # Liderler, siyasetçiler, sık geçen özel kişiler
    "Atatürk", "Erdoğan", "Recep", "Tayyip", "Şimşek", "Fidan", "Cevdet", "Yusuf", "Memişoğlu", "Özgür",
    "Bahçeli", "Devlet", "İmamoğlu", "Ekrem", "Mansur", "Trump", "Donald", "Putin", "Vladimir", "Zelenski",
    "Biden", "Macron", "Scholz", "Merz", "Starmer", "Meloni", "Orban", "Tusk", "Netanyahu", "Pezeşkiyan",
    "Hamaney", "Şara", "Dibeybe", "Hafter", "Sisi", "Miçotakis", "Aliyev", "Paşinyan", "Modi", "Jinping",
    "Witkoff", "Kushner", "Lavrov", "Rubio", "Musk", "Elon", "Markle",
    # Spor kulüpleri, ligler, sporcular, teknik direktörler
    "Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir", "Samsunspor", "Göztepe", "Eyüpspor",
    "Konyaspor", "Antalyaspor", "Alanyaspor", "Sivasspor", "Kasımpaşa", "Rizespor", "Gaziantepspor", "Kayserispor",
    "Bodrumspor", "Hatayspor", "Adana", "Bursaspor", "Ankaragücü", "Gençlerbirliği", "Kocaelispor", "Sakaryaspor",
    "Euroleague", "EuroLeague", "Premier", "Bundesliga", "Serie", "Liga", "Wimbledon", "Wushu",
    "Mourinho", "Jose", "Osimhen", "Icardi", "Immobile", "Skriniar", "Talisca", "Dzeko", "Tadic", "Muslera",
    "Montella", "Ancelotti", "Guardiola", "Mbappe", "Haaland", "Salah", "Ronaldo", "Messi",
    # Teknoloji, otomobil ve küresel şirket markaları
    "Google", "Apple", "Microsoft", "Meta", "Amazon", "Tesla", "Nvidia", "Samsung", "Xiaomi", "Redmi", "Poco",
    "Huawei", "Honor", "Oppo", "Vivo", "Realme", "Intel", "AMD", "Qualcomm", "Broadcom", "Oracle", "Cisco",
    "IBM", "Sony", "Nintendo", "Netflix", "Spotify", "Uber", "Airbnb", "Adobe", "Salesforce", "Anthropic",
    "Claude", "Gemini", "Android", "Windows", "Linux", "Java4Shell",
    "Volkswagen", "Mercedes", "Benz", "Toyota", "Hyundai", "Kia", "Renault", "Peugeot", "Citroen", "Opel",
    "Fiat", "Alfa", "Romeo", "Skoda", "Seat", "Cupra", "Volvo", "Polestar", "Nissan", "Honda", "Mazda",
    "Suzuki", "Subaru", "Mitsubishi", "Chery", "Omoda", "Jaecoo", "Geely", "Zeekr", "Lexus", "Porsche",
    "Ferrari", "Lamborghini", "Maserati", "Bentley", "Bugatti", "Audi", "Ford", "Chevrolet", "Buick", "Electra",
    "Cadillac", "Jeep", "Dacia", "Tofaş", "Corvette", "UniCredit", "Commerzbank", "Siemens", "Stellantis",
    "Nokia", "Ericsson", "Boeing", "Airbus", "SpaceX", "Starlink", "Bitcoin", "Ethereum", "Brent", "Habertürk",
    "Trugo", "Kızılelma", "Zelenskiy",
}
_UNAMBIGUOUS_PROPER = {w.strip() for w in _UNAMBIGUOUS_PROPER if w.strip() and w.strip()[0].isupper()}

# Büyük yazıldığında korunan ama küçük yazıldığında cins isim de olabilen (otomatik büyütülmeyen) kelimeler:
_CONTEXTUAL_PROPER = {
    "Aydın", "ordu", "Süper", "Lig", "Ligi", "Şampiyonlar", "Merkez", "Bankası", "Yargıtay", "Danıştay",
    "Anayasa", "Mahkemesi", "Sayıştay", "Meclis", "Resmî", "Resmi", "Gazete", "Bakanlığı", "Bakanı",
    "Başbakanı", "Cumhurbaşkanı", "Cumhurbaşkanlığı", "Üniversitesi", "Belediyesi", "Dairesi", "Kurumu",
    "Kurulu", "Fonu", "Örgütü", "Birliği", "Senatosu", "Kongresi", "Mehmet", "Hakan", "Yılmaz", "Tekin",
    "Kurum", "Murat", "Kemal", "Ali", "Ahmet", "Mustafa", "Fatih", "Emre", "Arda", "Güler", "Kenan", "Yıldız",
    "Okan", "Buruk", "Şenol", "Güneş", "Sergen", "Yalçın", "Derya", "Baykal", "İlayda", "Yaşar", "Thomas", "Reis",
    "General", "Motors", "Solar", "Roof", "Dolar", "Euro", "Lira", "Lirası",
}
_CONTEXTUAL_PROPER = {w for w in _CONTEXTUAL_PROPER if w[0].isupper()}

_MONTHS_CAP = {"Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"}
_MONTHS_LOW_TO_CAP = {_tr_lower(m): m for m in _MONTHS_CAP}

# Küçük harfle yazıldığında hem cins isim hem özel ad olabilen kelimeler (prose_proper yüzünden yanlış büyütülmesin):
_AMBIGUOUS_LOWER_WORDS = {
    "altın", "demir", "kaya", "güneş", "yıldız", "ay", "dünya", "barış", "savaş", "zafer", "umut", "güven",
    "özgür", "hayat", "deniz", "ırmak", "pazar", "cuma", "salı", "başkan", "başkanı", "bakan", "bakanı",
    "başbakan", "başbakanı", "merkez", "birlik", "birliği", "kurum", "kurumu", "kurul", "kurulu", "mahkeme",
    "mahkemesi", "üniversite", "üniversitesi", "belediye", "belediyesi", "devlet", "milli", "ulusal", "küresel",
    "uluslararası", "genel", "özel", "yüksek", "büyük", "yeni", "eski", "ilk", "son", "orta", "doğu", "batı",
    "kuzey", "güney", "anadolu", "avrupa'da", "ordu", "aydın", "ümit", "ışık", "çiçek", "toprak", "bulut",
    "şahin", "doğan", "kartal", "aslan", "koç", "polat", "çelik", "akın", "eren", "emre", "can", "cem",
}

# Türkçe'de cümle ortasında asla özel isim olmayan yaygın haber kelimeleri (kaynakta yanlışlıkla büyük geçse bile küçültülür):
_COMMON_NON_PROPER_LOWER = {
    "dinlenme", "destek", "sınavı", "sınav", "erken", "odaklı", "sınır", "yerel", "servis", "rüşvet", "diyabet",
    "enflasyon", "organize", "seri", "hakikat", "hukuki", "yürütülen", "soruşturma", "soruşturması", "gücü",
    "piyasasında", "piyasası", "uyarısı", "uyarı", "hamlesi", "kararı", "karar", "açıklaması", "açıklama",
    "operasyonu", "operasyon", "krizi", "kriz", "projesi", "projesinde", "sistemi", "sistemleri", "bütçe",
    "teklifi", "ekipler", "ekibi", "engel", "kolaylığı", "yolsuzluk", "hastalığı", "hastalığıyla", "tahmini",
    "tahminini", "suç", "örgütü", "elebaşı", "galibiyet", "galibiyetlerle", "arayışı", "arayışına", "federal",
    "gözaltı", "gözaltına", "tutuklama", "indirim", "zam", "artış", "düşüş", "yükseliş", "rekor", "tarihi",
    "kritik", "önemli", "büyük", "küçük", "resmi", "yeni", "güncel", "son", "ilk", "ortaöğretim", "ilköğretim",
    "yükseköğretim", "başvuru", "başvuruları", "sonuçları", "takvimi", "rehberi", "tablosu", "listesi", "raporu",
    "verisi", "verileri", "oranı", "oranları", "fiyatı", "fiyatları", "maaş", "maaşı", "ücret", "ücreti",
    "emekli", "memur", "işçi", "çalışan", "vatandaş", "uzman", "uzmanlar", "uzmanlardan", "doktor", "hekim",
    "mahkeme", "mahkemeden", "polis", "jandarma", "asker", "askeri", "ekonomi", "ekonomik", "siyasi", "sosyal",
    "dijital", "teknoloji", "otomobil", "araç", "model", "modeli", "şirket", "şirketi", "banka", "bankası",
    "kredi", "faiz", "vergi", "ceza", "yasası", "kanunu", "yönetmelik", "tebliğ", "genelge",
    "iklim", "zirvesi", "zirvesinde", "komisyonu", "oturumu",
}

# Çok kelimeli kurumsal / coğrafi özel ad kalıpları (ASCII yazım hataları dahil düzeltilir):
_COMPOUND_PROPER_SUBS = [
    (re.compile(r"\bavrupa\s+birli[gğ]i['’]?nden\b", re.I), "Avrupa Birliği'nden"),
    (re.compile(r"\bavrupa\s+birli[gğ]i['’]?ne\b", re.I), "Avrupa Birliği'ne"),
    (re.compile(r"\bavrupa\s+birli[gğ]i['’]?nin\b", re.I), "Avrupa Birliği'nin"),
    (re.compile(r"\bavrupa\s+birli[gğ]i['’]?nde\b", re.I), "Avrupa Birliği'nde"),
    (re.compile(r"\bavrupa\s+birli[gğ]i\b", re.I), "Avrupa Birliği"),
    (re.compile(r"\bbirleşmiş\s+milletler\b", re.I), "Birleşmiş Milletler"),
    (re.compile(r"\buluslararası\s+para\s+fonu\b", re.I), "Uluslararası Para Fonu"),
    (re.compile(r"\bdünya\s+sağlık\s+örgütü\b", re.I), "Dünya Sağlık Örgütü"),
    (re.compile(r"\bdünya\s+bankası\b", re.I), "Dünya Bankası"),
    (re.compile(r"\bmerkez\s+bankası\b", re.I), "Merkez Bankası"),
    (re.compile(r"\bresm[iî]\s+gazete\b", re.I), "Resmî Gazete"),
    (re.compile(r"\bdezenformasyonla\s+mücadele\s+merkezi\b", re.I), "Dezenformasyonla Mücadele Merkezi"),
    (re.compile(r"\bABD\s+gıda\s+ve\s+ilaç\s+dairesi(\w*)\b", re.I), r"ABD Gıda ve İlaç Dairesi\1"),
    (re.compile(r"\bsüper\s+lig(['’]\w+)?\b", re.I), lambda m: "Süper Lig" + _tr_lower(m.group(1) or "")),
    (re.compile(r"\bşampiyonlar\s+ligi(['’]\w+)?\b", re.I), lambda m: "Şampiyonlar Ligi" + _tr_lower(m.group(1) or "")),
    (re.compile(r"\borta\s+doğu\b", re.I), "Orta Doğu"),
    (re.compile(r"\buzak\s+doğu\b", re.I), "Uzak Doğu"),
    (re.compile(r"\bkuzey\s+kore\b", re.I), "Kuzey Kore"),
    (re.compile(r"\bgüney\s+kore\b", re.I), "Güney Kore"),
    (re.compile(r"\bgüney\s+afrika\b", re.I), "Güney Afrika"),
    (re.compile(r"\bsuudi\s+arabistan\b", re.I), "Suudi Arabistan"),
    (re.compile(r"\bbirleşik\s+krallık\b", re.I), "Birleşik Krallık"),
    (re.compile(r"\bbirleşik\s+arap\s+emirlikleri\b", re.I), "Birleşik Arap Emirlikleri"),
    (re.compile(r"\bdışişleri\s+bakanı\b", re.I), "Dışişleri Bakanı"),
    (re.compile(r"\biçişleri\s+bakanı\b", re.I), "İçişleri Bakanı"),
    (re.compile(r"\badalet\s+bakanı\b", re.I), "Adalet Bakanı"),
    (re.compile(r"\bsağlık\s+bakanı\b", re.I), "Sağlık Bakanı"),
    (re.compile(r"\bmilli\s+eğitim\s+bakanı\b", re.I), "Milli Eğitim Bakanı"),
    (re.compile(r"\bmilli\s+savunma\s+bakanı\b", re.I), "Milli Savunma Bakanı"),
    (re.compile(r"\bhazine\s+ve\s+maliye\s+bakanı\b", re.I), "Hazine ve Maliye Bakanı"),
    (re.compile(r"\bmaçı\s+sonrasi\b", re.I), "maçı sonrası"),
    (re.compile(r"\bsatış\s+sonrasi\b", re.I), "satış sonrası"),
    (re.compile(r"\bistanbul\s+fuar\s+merkezi", re.I), "İstanbul Fuar Merkezi"),
]


def _extract_prose_proper_nouns(source_text: str) -> Set[str]:
    """
    Kaynak metindeki <p> düz yazı cümlelerinin ORTASINDA büyük harfle geçen, aynı metinde küçük harfle
    hiç geçmeyen gerçek özel isimleri (Tusk, Dibeybe, Alihan, Kuriş, Wushu, Electra vb.) çıkarır.
    <h3> ara başlıkları ve Her Kelimesi Büyük (TitleCase) satırlar bilerek dışlanır.
    """
    if not source_text:
        return set()
    # Ara başlıkları ve kaynak kutularını çıkar ki TitleCase ara başlık kelimeleri özel isim sanılmasın
    s = re.sub(r"<h[1-6][^>]*>.*?</h[1-6]>", ". ", source_text, flags=re.I | re.S)
    s = re.sub(r'<div[^>]*class="[^"]*ga-box-title[^"]*"[^>]*>.*?</div>', ". ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return set()

    lower_seen = {
        _tr_lower(m.group(0))
        for m in re.finditer(r"(?<![A-Za-zÇĞİÖŞÜçğıöşü])[a-zçğıöşü]{3,}(?![A-Za-zÇĞİÖŞÜçğıöşü])", s)
    }
    found: Set[str] = set()
    for sent in re.split(r"[.!?]+\s+|\n+", s):
        words = re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü][\wçğıöşüÇĞİÖŞÜ'’\-]*", sent)
        if len(words) < 4:
            continue
        # Eğer cümledeki kelimelerin %70'inden fazlası büyük harfle başlıyorsa bu bir TitleCase başlıktır -> atla
        cap_cnt = sum(1 for w in words[1:] if w[0].isupper())
        if len(words) >= 5 and cap_cnt / max(1, len(words) - 1) > 0.70:
            continue
        # Cümle ortasında küçük harfli kelimeden veya virgülden sonra gelen Büyük Harfli kelimeleri topla
        for m in re.finditer(r"(?<=[a-zçğıöşü0-9,;)\"”’']\s)([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})(?=['’\s,.:;!?)]|$)", sent):
            cand = m.group(1)
            cl = _tr_lower(cand)
            if cl in lower_seen or cl in _COMMON_NON_PROPER_LOWER:
                continue
            found.add(cand)
    return found


def _match_unambiguous_proper(stem_low: str, proper_map: dict) -> str:
    """Türkçe çekim eki almış ülke/şehir/kişi adlarını ('rusyadan' -> 'Rusyadan', 'yargıtaydan' -> 'Yargıtaydan') yakalar."""
    if stem_low in proper_map:
        return proper_map[stem_low]
    return ""


def to_turkish_sentence_case(title: str, source_text: str = "") -> str:
    """
    Tüm başlıkları ve ara başlıkları (oran şartı olmaksızın) Türk basını cümle düzenine getirir:
    - Kısaltmaları (ABD, FED, TCMB, MG7...) büyük yazar.
    - Kaynak düz yazısında veya özel isim sözlüğünde geçen kişi/ülke/kurum adlarını (Donald Tusk, Putin, Alihan Kuriş)
      küçük yazılmış olsalar bile büyük harfle başlatır.
    - Cümle ortasında yanlışlıkla büyük kalan cins isimleri ('ve Dinlenme uyarısı', 'iş Gücü') küçültür.
    """
    if not title:
        return title
    title = restore_acronyms(title.strip(), source_text or "")
    prose_proper = _extract_prose_proper_nouns(source_text or "")

    # Birebir küçük->Büyük eşleme tablosu (yalnızca anlam karışıklığı olmayan net özel isimler için)
    force_cap_map = {_tr_lower(w): w for w in _UNAMBIGUOUS_PROPER}
    for w in prose_proper:
        wl = _tr_lower(w)
        if wl not in _AMBIGUOUS_LOWER_WORDS and wl not in _COMMON_NON_PROPER_LOWER:
            force_cap_map.setdefault(wl, w)

    keep_if_already_cap = _UNAMBIGUOUS_PROPER | _CONTEXTUAL_PROPER | prose_proper

    tokens = re.split(r"(\s+)", title)
    non_space_indices = [i for i, t in enumerate(tokens) if t and not t.isspace()]
    out = list(tokens)

    first_word_done = False
    after_punct_break = False

    for pos, idx in enumerate(non_space_indices):
        tok = tokens[idx]
        m_lead = re.match(r'^([\"“‘(\[]*)(.*?)([\"”’)\],.:;!?]*)$', tok)
        lead, core, trail = (m_lead.group(1), m_lead.group(2), m_lead.group(3)) if m_lead else ("", tok, "")
        if not core:
            continue

        has_apostrophe = ("'" in core or "’" in core)
        parts_ap = re.split(r"(['’])", core, maxsplit=1)
        stem = parts_ap[0]
        ap_sep = parts_ap[1] if len(parts_ap) > 1 else ""
        ap_suf = parts_ap[2] if len(parts_ap) > 2 else ""
        stem_low = _tr_lower(stem)

        # Yanında gün veya yıl rakamı var mı? (TDK: "14 Aralık", "Ocak 2027", "3-9 Kasım" büyük; "kasım ayında" küçük)
        prev_tok = tokens[non_space_indices[pos - 1]] if pos > 0 else ""
        next_tok = tokens[non_space_indices[pos + 1]] if pos + 1 < len(non_space_indices) else ""
        adj_has_num = bool(re.search(r"\d", prev_tok) or re.search(r"\d", next_tok))

        new_core = None

        # 1) Kısaltma / tam büyük kelime / iç büyük harfli marka (ABD, TÜİK, iPhone, YouTube, T-Roc, Java4Shell)
        if len(stem) > 1 and (
            stem.isupper()
            or sum(1 for c in stem if c.isupper()) >= 2
            or any(ch.isdigit() for ch in stem)
            or (stem[0].islower() and any(c.isupper() for c in stem[1:]))
        ):
            new_core = stem + (ap_sep + _tr_lower(ap_suf) if has_apostrophe else "")
        # 2) Kesme işareti alan özel isim (Osmaniye'de, BBC'den, EYT'lilerin)
        elif has_apostrophe and len(stem) >= 2:
            fixed_stem = force_cap_map.get(stem_low) or (stem if stem[0].isupper() else _tr_cap_word(stem))
            new_core = fixed_stem + ap_sep + _tr_lower(ap_suf)
        # 3) Ay adları: yanında sayı varsa Büyük, yoksa (cümle başı değilse) küçük
        elif stem_low in _MONTHS_LOW_TO_CAP:
            if not first_word_done or after_punct_break or adj_has_num:
                new_core = _MONTHS_LOW_TO_CAP[stem_low]
            else:
                new_core = stem_low
        # 4) Cümle başı veya ':', '.', '!', '?' sonrası ilk kelime
        elif not first_word_done or after_punct_break:
            if stem_low in force_cap_map:
                new_core = force_cap_map[stem_low]
            elif stem and stem[0].islower():
                new_core = _tr_cap_word(stem)
            else:
                new_core = stem
        # 5) Cümle ortası kelimeler
        else:
            matched_prop = _match_unambiguous_proper(stem_low, force_cap_map)
            if matched_prop:
                new_core = matched_prop
            elif stem_low in _COMMON_NON_PROPER_LOWER:
                new_core = _tr_lower_word(stem)
            elif "-" in stem:
                # ABD-Japonya, T-Roc, Bağ-Kur gibi tireli yapılar
                h_parts = stem.split("-")
                fixed_h = []
                for hp in h_parts:
                    hpl = _tr_lower(hp)
                    if hpl in force_cap_map:
                        fixed_h.append(force_cap_map[hpl])
                    elif hp.isupper() or hp in keep_if_already_cap:
                        fixed_h.append(hp)
                    else:
                        fixed_h.append(_tr_lower_word(hp))
                new_core = "-".join(fixed_h)
            elif stem and stem[0].isupper() and stem in keep_if_already_cap:
                new_core = stem
            else:
                new_core = _tr_lower_word(stem) if stem else core

        out[idx] = f"{lead}{new_core}{trail}"
        first_word_done = True
        after_punct_break = bool(trail and any(p in trail for p in (":", ".", "!", "?")))

    res = "".join(out).strip()
    for rx, repl in _COMPOUND_PROPER_SUBS:
        res = rx.sub(repl, res)
    # Ülke/Devlet adından hemen sonra gelen "Başbakanı / Cumhurbaşkanı / Devlet Başkanı / Merkez Bankası" unvanlarını koru
    res = re.sub(
        r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s+(başbakanı|cumhurbaşkanı|kralı|prensi)(\s+[A-ZÇĞİÖŞÜ])",
        lambda m: f"{m.group(1)} {_tr_cap_word(m.group(2))}{m.group(3)}",
        res,
    )
    # Cümlenin en ilk harfinin her zaman büyük kalmasını garanti et
    if res and res[0].islower():
        res = _tr_upper(res[0]) + res[1:]
    return res


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
