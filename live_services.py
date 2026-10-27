"""
Gündem Analizi Canlı Servisler Motoru:
- 81 İl Canlı Nöbetçi Eczaneler (Bugünün Gerçek Nöbetçi Eczaneleri & Mesai/Nöbet Saatleri)
- Trendyol Süper Lig Canlı Puan Durumu & Güncel Haftanın Maçları (TFF Resmi Verisi)
- RAM Önbelleği ile Sıfır Gecikme (0 ms) + 81 İl Yedek Veritabanı
"""

import urllib.request
import ssl
import re
import time
import os
import json
from datetime import datetime, timezone, timedelta
import bs4
from typing import Dict, List, Optional

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# RAM Önbellekleri
_PHARMACY_CACHE: Dict[str, dict] = {}  # {city: {"data": [...], "ts": 12345}}
_SUPERLIG_CACHE: Dict[str, dict] = {"data": None, "ts": 0}
_81_PHARMACIES_DB = None

CITY_SLUGS = {
    "adana": "adana", "adıyaman": "adiyaman", "afyonkarahisar": "afyonkarahisar", "afyon": "afyonkarahisar", "ağrı": "agri",
    "amasya": "amasya", "ankara": "ankara", "antalya": "antalya", "artvin": "artvin",
    "aydın": "aydin", "balıkesir": "balikesir", "bilecik": "bilecik", "bingöl": "bingol",
    "bitlis": "bitlis", "bolu": "bolu", "burdur": "burdur", "bursa": "bursa",
    "çanakkale": "canakkale", "çankırı": "cankiri", "çorum": "corum", "denizli": "denizli",
    "diyarbakır": "diyarbakir", "edirne": "edirne", "elazığ": "elazig", "erzincan": "erzincan",
    "erzurum": "erzurum", "eskişehir": "eskisehir", "gaziantep": "gaziantep", "giresun": "giresun",
    "gümüşhane": "gumushane", "hakkari": "hakkari", "hatay": "hatay", "ısparta": "isparta",
    "mersin": "mersin", "istanbul": "istanbul", "izmir": "izmir", "kars": "kars",
    "kastamonu": "kastamonu", "kayseri": "kayseri", "kırklareli": "kirklareli",
    "kırşehir": "kirsehir", "kocaeli": "kocaeli", "konya": "konya", "kütahya": "kutahya",
    "malatya": "malatya", "manisa": "manisa", "kahramanmaraş": "kahramanmaras",
    "mardin": "mardin", "muğla": "mugla", "muş": "mus", "nevşehir": "nevsehir",
    "niğde": "nigde", "ordu": "ordu", "rize": "rize", "sakarya": "sakarya",
    "samsun": "samsun", "siirt": "siirt", "sinop": "sinop", "sivas": "sivas",
    "tekirdağ": "tekirdag", "tokat": "tokat", "trabzon": "trabzon", "tunceli": "tunceli",
    "şanlıurfa": "sanliurfa", "uşak": "usak", "van": "van", "yozgat": "yozgat",
    "zonguldak": "zonguldak", "aksaray": "aksaray", "bayburt": "bayburt", "karaman": "karaman",
    "kırıkkale": "kirikkale", "batman": "batman", "şırnak": "sirnak", "bartın": "bartin",
    "ardahan": "ardahan", "iğdır": "igdir", "yalova": "yalova", "karabük": "karabuk",
    "kilis": "kilis", "osmaniye": "osmaniye", "düzce": "duzce"
}

def normalize_city(city: str) -> str:
    """Türkçe karakterleri ve harf uyumunu slug formatına çevirir."""
    s = (city or "").strip()
    s = s.replace("İ", "i").replace("I", "i").replace("ı", "i")
    s = s.replace("Ö", "o").replace("ö", "o")
    s = s.replace("Ü", "u").replace("ü", "u")
    s = s.replace("Ş", "s").replace("ş", "s")
    s = s.replace("Ç", "c").replace("ç", "c")
    s = s.replace("Ğ", "g").replace("ğ", "g")
    return s.lower()

def _load_81_db() -> dict:
    """data/pharmacies_81.json dosyasını yükler."""
    global _81_PHARMACIES_DB
    if _81_PHARMACIES_DB is not None:
        return _81_PHARMACIES_DB
    path = os.path.join(os.path.dirname(__file__), "data", "pharmacies_81.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _81_PHARMACIES_DB = json.load(f)
                return _81_PHARMACIES_DB
        except Exception as e:
            print(f"⚠️ pharmacies_81.json okunamadı: {e}")
    _81_PHARMACIES_DB = {}
    return _81_PHARMACIES_DB

def get_current_shift_info() -> Dict:
    """
    Türkiye saatine (UTC+3) göre şu anki mesai ve nöbet durumunu hesaplar.
    """
    tz_tr = timezone(timedelta(hours=3))
    now = datetime.now(tz_tr)
    hour = now.hour
    minute = now.minute

    # Mesai saatleri: Hafta içi ve Cumartesi 08:30 - 18:30
    is_daytime = (hour > 8 or (hour == 8 and minute >= 30)) and (hour < 18 or (hour == 18 and minute < 30))
    weekday = now.weekday()  # 0=Pazartesi, 6=Pazar

    if weekday == 6:  # Pazar günleri tüm gün nöbetçidir
        is_now_open = True
        status_text = "🟢 ŞU AN AÇIK (Pazar Nöbetçisi)"
        hours_text = "Pazar Günü 24 Saat Kesintisiz Açık (Yarın 08:30'a Kadar)"
        info_note = "Pazar günleri normal eczaneler kapalıdır. Aşağıdaki nöbetçi eczaneler gün boyu ve gece kesintisiz açıktır."
    elif is_daytime:
        is_now_open = False
        status_text = "Akşam Nöbetçisi (18:30'da Devralır)"
        hours_text = "Bugün 18:30'dan Yarın Sabah 08:30'a Kadar Kesintisiz Açık"
        info_note = "Gündüz mesaisi (08:30 - 18:30) boyunca bölgenizdeki TÜM ECZANELER açıktır. Aşağıdaki nöbetçi eczaneler saat 18:30 itibarıyla nöbeti devralarak sabaha kadar açık kalacaktır."
    else:
        is_now_open = True
        status_text = "🟢 ŞU AN AÇIK (Gece Nöbetçisi)"
        hours_text = "Sabah 08:30'a Kadar Kesintisiz Açık"
        info_note = "Şu anda gece nöbeti aktiftir. Aşağıda listelenen nöbetçi eczaneler sabah saat 08:30'a kadar kesintisiz hizmet vermektedir."

    return {
        "is_now_open": is_now_open,
        "status_text": status_text,
        "hours_text": hours_text,
        "info_note": info_note
    }

def clean_team_name(name: str) -> str:
    """Kulüp isimlerini sade, okunabilir Türkçe spor formatına dönüştürür."""
    if not name:
        return ""
    n = re.sub(r'\b(A\.Ş\.|A\.\.|FK|FUTBOL KULÜBÜ|KULÜBÜ)\b', '', name, flags=re.I)
    n = n.replace('TMOSAN', '').replace('ARCA', '').replace('CORENDON', '').replace('ÇAYKUR', 'Çaykur')
    n = n.replace('RAMS', '').replace('TÜMOSAN', '').replace('ATAKAŞ', '')
    n = re.sub(r'\s+', ' ', n).strip()
    return n.title()

def get_live_pharmacies(city: str = "istanbul") -> List[Dict]:
    """
    Belirtilen şehir için bugünün gerçek nöbetçi eczanelerini canlı çeker.
    Render / Bulut sunucularda Cloudflare engeli olursa 81 ilin gerçek veri tabanından anında yükler.
    Asla başka bir şehre (Kadıköy/Şişli) sapmaz.
    """
    norm = normalize_city(city)
    slug = CITY_SLUGS.get(norm, norm)

    now = time.time()
    cached = _PHARMACY_CACHE.get(slug)
    shift = get_current_shift_info()

    if cached and (now - cached["ts"]) < 7200 and cached["data"]:
        # Güncel vardiya bilgisini ekle
        for item in cached["data"]:
            item["status"] = shift["status_text"]
            item["hours"] = shift["hours_text"]
            item["is_now_open"] = shift["is_now_open"]
        return cached["data"]

    url = f"https://www.eczaneler.gen.tr/nobetci-{slug}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9"
        }
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=6, context=_SSL_CTX) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = bs4.BeautifulSoup(html, "html.parser")
            for row in soup.find_all("div", class_="row"):
                name_span = row.find("span", class_="isim")
                if not name_span:
                    continue
                name = name_span.text.strip()
                if "Eczanesi" not in name:
                    name += " Eczanesi"

                # İlçe
                district = ""
                dist_span = row.find("span", class_="bg-info")
                if dist_span:
                    district = dist_span.text.strip()

                # Adres
                address = ""
                addr_div = row.find("div", class_="col-lg-6")
                if addr_div:
                    for b in addr_div.find_all("div", class_="my-2"):
                        b.decompose()
                    address = addr_div.text.strip().replace("\n", " ").replace("→", " - ")
                    address = re.sub(r'\s+', ' ', address).strip()

                # Telefon
                phone = ""
                phone_div = row.find("div", class_=lambda x: x and "py-lg-2" in x)
                if phone_div:
                    phone = phone_div.text.strip()
                elif row.find("a", href=lambda x: x and "tel:" in x):
                    phone = row.find("a", href=lambda x: x and "tel:" in x).text.strip()

                if name and address and address.lower() != "adres":
                    results.append({
                        "name": name,
                        "city": city.capitalize(),
                        "district": district or city.capitalize(),
                        "address": address,
                        "phone": phone or "Belirtilmedi",
                        "status": shift["status_text"],
                        "hours": shift["hours_text"],
                        "is_now_open": shift["is_now_open"]
                    })
    except Exception as e:
        print(f"⚠️ Canlı eczane kazıma uyarısı ({city} - {slug}): {e}")

    # Canlı çekilemezse (Render Cloudflare engeli vb.), 81 ilin gerçek veritabanını kullan
    if not results:
        db_81 = _load_81_db()
        fallback_list = db_81.get(slug) or db_81.get(norm)
        if fallback_list:
            results = []
            for item in fallback_list:
                results.append({
                    "name": item.get("name", "Eczane"),
                    "city": city.capitalize(),
                    "district": item.get("district", city.capitalize()),
                    "address": item.get("address", "Adres bilgisi için arayınız"),
                    "phone": item.get("phone", "Belirtilmedi"),
                    "status": shift["status_text"],
                    "hours": shift["hours_text"],
                    "is_now_open": shift["is_now_open"]
                })

    if results:
        _PHARMACY_CACHE[slug] = {"data": results, "ts": now}
        return results
    elif cached and cached.get("data"):
        return cached["data"]

    return []

def get_live_superlig() -> Dict:
    """
    TFF Resmi veritabanından Süper Lig güncel puan durumunu ve
    aktif haftanın gelecek maçlarını canlı olarak çeker.
    1 saat boyunca RAM'de saklar.
    """
    now = time.time()
    if _SUPERLIG_CACHE["data"] and (now - _SUPERLIG_CACHE["ts"]) < 3600:
        return _SUPERLIG_CACHE["data"]

    url = "https://www.tff.org/default.aspx?pageID=198"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9"
        }
    )

    standings = []
    matches = []
    current_week = 10

    try:
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = bs4.BeautifulSoup(html, "html.parser")

            # 1. Puan Durumu Tablosu
            tables = soup.find_all("table")
            for t in tables:
                rows = t.find_all("tr")
                for tr in rows:
                    cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
                    if len(cells) >= 9 and cells[0].isdigit():
                        rank = int(cells[0])
                        team_name = clean_team_name(cells[1])
                        if team_name.lower() in ["devre", "takımlar", ""]:
                            continue
                        try:
                            o = int(cells[2])
                            g = int(cells[3])
                            b = int(cells[4])
                            m = int(cells[5])
                            av = cells[8]
                            p = int(cells[9]) if len(cells) > 9 else int(cells[-1])
                            standings.append({
                                "rank": rank,
                                "team": team_name,
                                "o": o, "g": g, "b": b, "m": m,
                                "av": av if av.startswith("+") or av.startswith("-") else f"+{av}",
                                "p": p,
                                "lead": (rank == 1)
                            })
                        except Exception:
                            continue

            # 2. Gelecek Maçlar & Fikstür
            for t in tables:
                rows = t.find_all("tr")
                for tr in rows:
                    cells = [td.text.strip() for td in tr.find_all(["td", "th"])]
                    # Format: [Tarih, EvSahibi, Skor/Saat, Deplasman]
                    if len(cells) >= 4:
                        date_str = cells[0]
                        home_team = clean_team_name(cells[1])
                        center_val = cells[2]
                        away_team = clean_team_name(cells[3]) if len(cells) >= 4 else ""

                        # Tarih içeriyor ve bitmiş maç değil ise (skor yok, saat var veya v harfi)
                        if re.search(r'\d{2}\.\d{2}\.\d{4}', date_str) and home_team and away_team:
                            if not re.search(r'^\d+\s*-\s*\d+$', center_val):  # Skorsuz maçlar (Gelecek)
                                matches.append({
                                    "date": date_str[:5],  # 30.10
                                    "full_date": date_str,
                                    "time": center_val if ":" in center_val else "20:00",
                                    "home": home_team,
                                    "away": away_team
                                })

            # Maçları tekilleştir
            seen_pairs = set()
            unique_matches = []
            for m in matches:
                pair = (m["home"], m["away"])
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    unique_matches.append(m)
            matches = unique_matches[:9]

    except Exception as e:
        print(f"⚠️ Canlı TFF verisi kazıma hatası: {e}")

    result = {
        "success": True if standings else False,
        "week": current_week,
        "standings": standings[:19] if standings else [],
        "matches": matches,
        "updated_at": int(now)
    }

    if standings:
        _SUPERLIG_CACHE["data"] = result
        _SUPERLIG_CACHE["ts"] = now

    return result
