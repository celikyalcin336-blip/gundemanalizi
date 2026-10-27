"""
Gündem Analizi Canlı Servisler Motoru:
- 81 İl Canlı Nöbetçi Eczaneler (Bugünün Gerçek Nöbetçi Eczaneleri)
- Trendyol Süper Lig Canlı Puan Durumu & Güncel Haftanın Maçları (TFF Resmi Verisi)
- RAM Önbelleği ile Sıfır Gecikme (0 ms)
"""

import urllib.request
import ssl
import re
import time
import bs4
from typing import Dict, List, Optional

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# RAM Önbellekleri
_PHARMACY_CACHE: Dict[str, dict] = {}  # {city: {"data": [...], "ts": 12345}}
_SUPERLIG_CACHE: Dict[str, dict] = {"data": None, "ts": 0}

CITY_SLUGS = {
    "adana": "adana", "adıyaman": "adiyaman", "afyonkarahisar": "afyon", "ağrı": "agri",
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
    2 saat boyunca RAM'de saklar.
    """
    clean_city = city.lower().strip()
    slug = CITY_SLUGS.get(clean_city, clean_city)
    slug = slug.replace('ı', 'i').replace('ö', 'o').replace('ü', 'u').replace('ş', 's').replace('ç', 'c').replace('ğ', 'g')

    now = time.time()
    cached = _PHARMACY_CACHE.get(slug)
    if cached and (now - cached["ts"]) < 7200 and cached["data"]:
        return cached["data"]

    url = f"https://www.eczaneler.gen.tr/nobetci-{slug}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
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

                if name and (address or phone):
                    results.append({
                        "name": name,
                        "city": clean_city.capitalize(),
                        "district": district or clean_city.capitalize(),
                        "address": address or "Adres bilgisi için arayınız",
                        "phone": phone or "Belirtilmedi"
                    })
    except Exception as e:
        print(f"⚠️ Canlı eczane çekme hatası ({clean_city}): {e}")

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
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            html = r.read().decode("utf-8", errors="ignore")
            soup = bs4.BeautifulSoup(html, "html.parser")
            tables = soup.find_all("table")

            # 1. Puan Durumu Tablosu (Table 15 veya Puan Cetveli içeren tablo)
            standings = []
            t_standings = None
            for t in tables:
                txt = t.text
                if "Puan Cetveli" in txt and "GALATASARAY" in txt and "AV" in txt:
                    t_standings = t
                    break
            if not t_standings and len(tables) > 15:
                t_standings = tables[15]

            if t_standings:
                for row in t_standings.find_all("tr"):
                    cells = [c.text.strip() for c in row.find_all(["td", "th"]) if c.text.strip()]
                    if len(cells) >= 8:
                        match_rank = re.match(r'^(\d+)\.\s*(.*)', cells[0])
                        if match_rank:
                            rank = int(match_rank.group(1))
                            raw_team = match_rank.group(2)
                            if "Devre" in raw_team:
                                continue
                            team = clean_team_name(raw_team)
                            standings.append({
                                "rank": rank,
                                "team": team,
                                "p": cells[1],
                                "w": cells[2],
                                "d": cells[3],
                                "l": cells[4],
                                "gf": cells[5],
                                "ga": cells[6],
                                "gd": cells[7],
                                "pts": cells[8] if len(cells) > 8 else cells[-1]
                            })

            # 2. Aktif Hafta Gelecek Maçları (Table 5 veya Detaylar içeren maç tablosu)
            matches = []
            seen_pairs = set()
            t_matches = None
            for t in tables:
                txt = t.text
                if "Detaylar" in txt and ("GALATASARAY" in txt or "FENERBAHÇE" in txt) and len(t.find_all("tr")) < 30:
                    t_matches = t
                    break
            if not t_matches and len(tables) > 5:
                t_matches = tables[5]

            if t_matches:
                for row in t_matches.find_all("tr"):
                    txt = row.text.strip()
                    m = re.search(r'(\d{2}\.\d{2}\.\d{4})\s*(\d{2}:\d{2})\s*(.*?)\s*-\s*(.*?)(?:Detaylar|$)', txt, re.DOTALL)
                    if m:
                        m_date = m.group(1).strip()
                        m_time = m.group(2).strip()
                        t1 = clean_team_name(m.group(3).strip())
                        t2 = clean_team_name(m.group(4).strip())
                        pair_key = f"{t1}_{t2}"
                        if pair_key not in seen_pairs and len(t1) > 2 and len(t2) > 2:
                            seen_pairs.add(pair_key)
                            matches.append({
                                "date": m_date,
                                "time": m_time,
                                "home": t1,
                                "away": t2,
                                "score": "-:-"
                            })

            week_match = re.search(r'(\d+)\.\s*Hafta', html)
            current_week = int(week_match.group(1)) if week_match else 10

            payload = {
                "ok": True,
                "current_week": current_week,
                "standings": standings,
                "matches": matches,
                "updated_at": "Canlı TFF"
            }

            if standings and matches:
                _SUPERLIG_CACHE["data"] = payload
                _SUPERLIG_CACHE["ts"] = now
                return payload

    except Exception as e:
        print(f"⚠️ Canlı Süper Lig çekme hatası: {e}")

    if _SUPERLIG_CACHE.get("data"):
        return _SUPERLIG_CACHE["data"]

    return {
        "ok": False,
        "current_week": 10,
        "standings": [],
        "matches": [],
        "updated_at": "Veri Bekleniyor"
    }
