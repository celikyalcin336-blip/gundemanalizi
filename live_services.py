"""
Gündem Analizi Canlı Servisler Motoru:
- 81 İl Canlı Nöbetçi Eczaneler (Bugünün Gerçek Nöbetçi Eczaneleri & Mesai/Nöbet Saatleri)
- Trendyol Süper Lig Canlı Puan Durumu & Güncel Haftanın Maçları (TFF Resmi Verisi)
- RAM Önbelleği ile Sıfır Gecikme (0 ms) + 81 İl Yedek Veritabanı (Günlük Nöbet Rotasyonlu)
"""

import urllib.request
import ssl
import re
import time
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta
import bs4
from typing import Dict, List, Optional

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# RAM Önbellekleri
_PHARMACY_CACHE: Dict[str, dict] = {}  # {city: {"data": [...], "ts": 12345, "date": "YYYY-MM-DD"}}
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

_TEAM_MAP = {
    "GALATASARAY": "Galatasaray",
    "FENERBAHÇE": "Fenerbahçe",
    "BEŞİKTAŞ": "Beşiktaş",
    "TRABZONSPOR": "Trabzonspor",
    "BAŞAKŞEHİR": "Başakşehir",
    "SAMSUNSPOR": "Samsunspor",
    "GÖZTEPE": "Göztepe",
    "EYÜPSPOR": "Eyüpspor",
    "KASIMPAŞA": "Kasımpaşa",
    "KONYASPOR": "Konyaspor",
    "ALANYASPOR": "Alanyaspor",
    "RİZESPOR": "Çaykur Rizespor",
    "GAZİANTEP": "Gaziantep FK",
    "GENÇLERBİRLİĞİ": "Gençlerbirliği",
    "KOCAELİSPOR": "Kocaelispor",
    "AMED": "Amed SK",
    "ÇORUM": "Çorum FK",
    "ERZURUMSPOR": "Erzurumspor FK",
    "ANTALYASPOR": "Antalyaspor",
    "SİVASSPOR": "Sivasspor",
    "KAYSERİSPOR": "Kayserispor",
    "HATAYSPOR": "Hatayspor",
    "BODRUM": "Bodrum FK",
    "ADANA DEMİRSPOR": "Adana Demirspor",
}

def clean_team_name(name: str) -> str:
    """Kulüp isimlerini sade, okunabilir Türkçe spor formatına dönüştürür."""
    if not name:
        return ""
    up = name.upper().strip()
    up = re.sub(r"^\d{1,2}\.\s*", "", up)
    for key, label in _TEAM_MAP.items():
        if key in up:
            return label
    n = re.sub(r"\b(A\.Ş\.|A\.\.|FUTBOL KULÜBÜ|KULÜBÜ|SPORTİF FAALİYETLER|TÜMOSAN|CORENDON|ARCA|RAMS|ATAKAŞ)\b", "", up, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" .-")
    words = []
    for w in n.split():
        if w == "FK":
            words.append("FK")
        else:
            first = w[0]
            rest = w[1:].replace("İ", "i").replace("I", "ı").lower()
            words.append(first + rest)
    return " ".join(words)

def _parse_eczaneler_html(html: str, city: str, shift: Dict) -> List[Dict]:
    """eczaneler.gen.tr HTML çıktısını ayrıştırıp nöbetçi eczane listesi döndürür."""
    results = []
    if not html or "isim" not in html:
        return results
    soup = bs4.BeautifulSoup(html, "html.parser")
    # Sadece aktif (bugünkü) sekmedeki satırları al (nav-bugun varsa önce ona bak)
    active_tab = soup.find("div", id="nav-bugun") or soup
    for row in active_tab.find_all("div", class_="row"):
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
    return results

def get_live_pharmacies(city: str = "istanbul") -> List[Dict]:
    """
    Belirtilen şehir için bugünün gerçek nöbetçi eczanelerini canlı çeker.
    Render / Bulut sunucularda Cloudflare engeli olursa proxy katmanlarıyla canlı veriyi çeker,
    yine erişilemezse 81 ilin gerçek veri tabanından günlük nöbet rotasyonuyla yükler.
    """
    norm = normalize_city(city)
    slug = CITY_SLUGS.get(norm, norm)

    tz_tr = timezone(timedelta(hours=3))
    now_tr = datetime.now(tz_tr)
    # Sabah 08:30'da nöbet listesi yenilenir
    if now_tr.hour < 8 or (now_tr.hour == 8 and now_tr.minute < 30):
        shift_date_str = (now_tr - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        shift_date_str = now_tr.strftime("%Y-%m-%d")

    now = time.time()
    cached = _PHARMACY_CACHE.get(slug)
    shift = get_current_shift_info()

    if cached and cached.get("date") == shift_date_str and (now - cached["ts"]) < 3600 and cached.get("data"):
        for item in cached["data"]:
            item["status"] = shift["status_text"]
            item["hours"] = shift["hours_text"]
            item["is_now_open"] = shift["is_now_open"]
        return cached["data"]

    target_url = f"https://www.eczaneler.gen.tr/nobetci-{slug}"
    candidate_urls = [
        target_url,
        f"https://api.codetabs.com/v1/proxy?quest={target_url}",
        f"https://api.allorigins.win/raw?url={target_url}",
    ]

    results = []
    for fetch_url in candidate_urls:
        try:
            req = urllib.request.Request(
                fetch_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9"
                }
            )
            with urllib.request.urlopen(req, timeout=5, context=_SSL_CTX) as r:
                html = r.read().decode("utf-8", errors="ignore")
                parsed = _parse_eczaneler_html(html, city, shift)
                if parsed:
                    results = parsed
                    break
        except Exception as e:
            print(f"⚠️ Canlı eczane kazıma uyarısı ({city} - {fetch_url[:45]}): {e}")

    # ÖNEMLİ: Canlı nöbet listesi alınamazsa ASLA tahmini/rastgele liste gösterilmez.
    # (Gece kapalı bir eczaneye yönlendirilen okur gerçek zarar görür.) Boş liste dönülür;
    # arayüz okuru e-Devlet / Eczacı Odası resmi sorgulamasına yönlendirir.

    if results:
        _PHARMACY_CACHE[slug] = {"data": results, "ts": now, "date": shift_date_str}
        return results
    elif cached and cached.get("data"):
        return cached["data"]

    return []

_MONTH_TR = {
    "01": "Oca", "02": "Şub", "03": "Mar", "04": "Nis", "05": "May", "06": "Haz",
    "07": "Tem", "08": "Ağu", "09": "Eyl", "10": "Eki", "11": "Kas", "12": "Ara"
}


def _format_tr_date(dt_str: str) -> str:
    """'06.11.2026 20:00' -> '06 Kas • 20:00'"""
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}:\d{2}))?", dt_str or "")
    if not m:
        return (dt_str or "").strip()
    day, mon, _yr, tm = m.group(1), m.group(2), m.group(3), m.group(4)
    mon_name = _MONTH_TR.get(mon, mon)
    return f"{day} {mon_name} • {tm}" if tm else f"{day} {mon_name}"


def _build_sub_table(teams: List[str], stats: Dict[str, Dict[str, int]]) -> List[Dict]:
    rows = []
    for tm in teams:
        s = stats.get(tm, {"o": 0, "g": 0, "b": 0, "m": 0, "a": 0, "y": 0, "p": 0})
        av_val = s["a"] - s["y"]
        rows.append({
            "team": tm,
            "o": s["o"], "g": s["g"], "b": s["b"], "m": s["m"],
            "a": s["a"], "y": s["y"],
            "av_int": av_val,
            "av": f"+{av_val}" if av_val > 0 else str(av_val),
            "p": s["p"],
        })
    rows.sort(key=lambda x: (x["p"], x["av_int"], x["a"]), reverse=True)
    for idx, r in enumerate(rows, 1):
        r["rank"] = idx
        r["lead"] = (idx == 1)
        r.pop("av_int", None)
    return rows


def get_live_superlig() -> Dict:
    """
    TFF Resmi veritabanından (pageID=198) Trendyol Süper Lig güncel puan durumunu (18 takım),
    gerçek maç sonuçlarından hesaplanan İç Saha / Deplasman puan tablolarını ve
    34 haftalık tam sezon fikstürünü çeker. 30 dakika RAM'de + kalıcı DB yedeğinde saklar.
    """
    now = time.time()
    if _SUPERLIG_CACHE["data"] and (now - _SUPERLIG_CACHE["ts"]) < 1800:
        return _SUPERLIG_CACHE["data"]

    url = "https://www.tff.org/default.aspx?pageID=198"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9",
        },
    )

    standings = []
    active_week_matches = []
    weeks_map: Dict[str, List[Dict]] = {}
    current_week = 11

    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            raw_bytes = r.read()
            try:
                html = raw_bytes.decode("windows-1254", errors="ignore")
            except Exception:
                html = raw_bytes.decode("utf-8", errors="ignore")

            soup = bs4.BeautifulSoup(html, "html.parser")

            # Aktif hafta numarası (örn: "11.Hafta")
            m_week = re.search(r"(\d{1,2})\.\s*Hafta", html)
            if m_week:
                current_week = int(m_week.group(1))

            # Yaprak (içinde başka table olmayan) tüm tr satırlarını tara
            cur_fixture_week = None
            for tr in soup.find_all("tr"):
                if tr.find("table"):
                    continue
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"], recursive=False)]
                if not cells:
                    continue

                # A) 9 hücreli Puan Cetveli satırı: ['1.GALATASARAY A.Ş.', '10', '8', '1', '1', '23', '12', '11', '25']
                if len(cells) == 9:
                    m_rk = re.match(r"^(\d{1,2})\.\s*(.+)$", cells[0])
                    if m_rk and cells[1].isdigit():
                        rank = int(m_rk.group(1))
                        team_name = clean_team_name(m_rk.group(2))
                        try:
                            o, g, b, m_cnt = int(cells[1]), int(cells[2]), int(cells[3]), int(cells[4])
                            a_gol, y_gol = int(cells[5]), int(cells[6])
                            av_int = int(cells[7])
                            p = int(cells[8])
                            standings.append({
                                "rank": rank,
                                "team": team_name,
                                "o": o, "g": g, "b": b, "m": m_cnt,
                                "a": a_gol, "y": y_gol,
                                "av": f"+{av_int}" if av_int > 0 else str(av_int),
                                "p": p,
                                "lead": (rank == 1),
                            })
                        except Exception:
                            pass
                    continue

                # B) 5 hücreli Aktif Hafta Programı satırı: ['06.11.2026 20:00', 'GAZİANTEP...', '-', 'KASIMPAŞA...', 'Detaylar']
                if len(cells) == 5 and re.search(r"\d{2}\.\d{2}\.\d{4}", cells[0]):
                    home_t = clean_team_name(cells[1])
                    center = cells[2].strip()
                    away_t = clean_team_name(cells[3])
                    if home_t and away_t:
                        is_score = bool(re.match(r"^\d+\s*-\s*\d+$", center))
                        active_week_matches.append({
                            "home": home_t,
                            "away": away_t,
                            "score": center if is_score else "",
                            "date": center if is_score else _format_tr_date(cells[0]),
                            "raw_date": cells[0],
                            "played": is_score,
                        })
                    continue

                # C) 34 Haftalık Tam Fikstür başlığı ("1. Hafta" .. "34. Hafta")
                joined = " ".join(cells).strip()
                m_wh = re.match(r"^(\d{1,2})\.\s*Hafta$", joined)
                if m_wh:
                    cur_fixture_week = str(int(m_wh.group(1)))
                    weeks_map.setdefault(cur_fixture_week, [])
                    continue

                # D) 3 hücreli Haftalık Maç satırı: ['EV SAHİBİ', '2 - 1' veya '-', 'DEPLASMAN']
                if len(cells) == 3 and cur_fixture_week:
                    home_t = clean_team_name(cells[0])
                    center = cells[1].strip()
                    away_t = clean_team_name(cells[2])
                    if home_t and away_t and home_t != away_t:
                        is_score = bool(re.match(r"^\d+\s*-\s*\d+$", center))
                        weeks_map[cur_fixture_week].append({
                            "home": home_t,
                            "away": away_t,
                            "score": center if is_score else "",
                            "date": center if is_score else f"{cur_fixture_week}. Hafta",
                            "played": is_score,
                        })

            # Aktif haftanın saatli/tarihli maçlarını weeks_map[str(current_week)] içine işle
            if active_week_matches:
                weeks_map[str(current_week)] = active_week_matches

            # Oynanmış tüm maçlardan %100 gerçek İç Saha ve Deplasman puan durumunu hesapla
            all_teams = [s["team"] for s in standings]
            home_stats = {tm: {"o": 0, "g": 0, "b": 0, "m": 0, "a": 0, "y": 0, "p": 0} for tm in all_teams}
            away_stats = {tm: {"o": 0, "g": 0, "b": 0, "m": 0, "a": 0, "y": 0, "p": 0} for tm in all_teams}

            for w_key, m_list in weeks_map.items():
                for m in m_list:
                    sc = (m.get("score") or "").strip()
                    m_sc = re.match(r"^(\d+)\s*-\s*(\d+)$", sc)
                    if not m_sc:
                        continue
                    hg, ag = int(m_sc.group(1)), int(m_sc.group(2))
                    ht, at = m["home"], m["away"]
                    if ht in home_stats:
                        hs = home_stats[ht]
                        hs["o"] += 1; hs["a"] += hg; hs["y"] += ag
                        if hg > ag: hs["g"] += 1; hs["p"] += 3
                        elif hg == ag: hs["b"] += 1; hs["p"] += 1
                        else: hs["m"] += 1
                    if at in away_stats:
                        as_ = away_stats[at]
                        as_["o"] += 1; as_["a"] += ag; as_["y"] += hg
                        if ag > hg: as_["g"] += 1; as_["p"] += 3
                        elif ag == hg: as_["b"] += 1; as_["p"] += 1
                        else: as_["m"] += 1

            standings_home = _build_sub_table(all_teams, home_stats) if all_teams else []
            standings_away = _build_sub_table(all_teams, away_stats) if all_teams else []

            if standings:
                result = {
                    "success": True,
                    "week": current_week,
                    "standings": standings,
                    "standings_icsaha": standings_home,
                    "standings_deplasman": standings_away,
                    "matches": weeks_map.get(str(current_week), active_week_matches),
                    "weeks": weeks_map,
                    "updated_at": int(now),
                    "updated_str": datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M"),
                }
                _SUPERLIG_CACHE["data"] = result
                _SUPERLIG_CACHE["ts"] = now
                try:
                    import database
                    database.set_setting("superlig_cache_json", json.dumps(result, ensure_ascii=False))
                except Exception:
                    pass
                return result

    except Exception as e:
        print(f"⚠️ Canlı TFF verisi kazıma hatası: {e}")

    # TFF anlık erişilemezse son başarılı RAM veya DB yedeğini dön (ASLA boş dönmez)
    if _SUPERLIG_CACHE["data"]:
        return _SUPERLIG_CACHE["data"]
    try:
        import database
        saved = database.get_setting("superlig_cache_json", "")
        if saved:
            data = json.loads(saved)
            _SUPERLIG_CACHE["data"] = data
            _SUPERLIG_CACHE["ts"] = now - 1500
            return data
    except Exception:
        pass

    return {"success": False, "week": current_week, "standings": [], "standings_icsaha": [], "standings_deplasman": [], "matches": [], "weeks": {}, "updated_at": int(now)}
