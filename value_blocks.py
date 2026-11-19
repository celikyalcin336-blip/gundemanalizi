# -*- coding: utf-8 -*-
"""
Gündem Analizi - Haber Değer Katmanı (value_blocks.py)

Her haber sayfasına, haberin KONUSUNA göre, kaynak haberde olmayan ve bize ait veri blokları ekler:
  1) Konu kronolojisi: kendi arşivimizden aynı olayın önceki gelişmeleri (tarih sırasıyla)
  2) Piyasa verisi: döviz/altın/faiz haberlerinde sayfanın oluşturulduğu andaki kur tablosu
  3) Süper Lig: haberde adı geçen takımların güncel puan durumu satırları
  4) Deprem: deprem haberlerinde AFAD/Kandilli son depremler listesi
  5) Hesaplayıcı: maaş / kıdem / emekli zammı haberlerinde ilgili hesaplama aracı
  6) Birincil kaynak: haberde geçen resmi kurumun resmi sitesi

Kurallar:
- Sadece önbellekteki veriler kullanılır; sayfa açılışı asla ağ isteği beklemez.
- Konuyla eşleşmeyen habere blok eklenmez (her sayfaya aynı kutu basılmaz).
"""
import html as _html
import re
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

_TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _e(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def _low(s: str) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


def _plain(content: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", content or ""))).strip()


def _tr_date(dt_str: str) -> str:
    try:
        d = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d")
        return f"{d.day} {_TR_MONTHS[d.month - 1]} {d.year}"
    except Exception:
        return str(dt_str)[:10]


def _box(title: str, inner: str, link_href: str = "", link_text: str = "", note: str = "") -> str:
    link = (
        f'<a href="{_e(link_href)}" class="text-[11px] font-bold text-red-600 hover:underline shrink-0">{_e(link_text)}</a>'
        if link_href else ""
    )
    note_html = f'<p class="text-[10px] text-slate-500 mt-2 mb-0">{note}</p>' if note else ""
    return (
        '<div class="ga-value not-prose my-6 p-4 sm:p-5 rounded-2xl bg-slate-50 border border-slate-200">'
        '<div class="flex items-center justify-between gap-3 mb-3">'
        f'<span class="text-xs font-black text-slate-900 uppercase tracking-wide">{title}</span>{link}'
        '</div>'
        f'{inner}{note_html}'
        '</div>'
    )


# ---------------------------------------------------------------------------
# 1) Konu kronolojisi
# ---------------------------------------------------------------------------
def chronology_block(article: Dict, index_rows: List[Dict], max_items: int = 5) -> str:
    try:
        import multisource
    except Exception:
        return ""
    title = article.get("title") or ""
    my_tok = multisource._tokens(title)
    if len(my_tok) < 3:
        return ""
    my_id = article.get("id")
    my_slug = article.get("slug")
    try:
        my_dt = datetime.strptime(str(article.get("created_at") or "")[:10], "%Y-%m-%d")
    except Exception:
        my_dt = datetime.now()
    window = timedelta(days=45)
    scored = []
    for r in index_rows or []:
        if r.get("id") == my_id or r.get("slug") == my_slug:
            continue
        try:
            r_dt = datetime.strptime(str(r.get("created_at") or "")[:10], "%Y-%m-%d")
        except Exception:
            continue
        if abs(r_dt - my_dt) > window:
            continue
        r_tok = multisource._tokens(r.get("title") or "")
        if len(r_tok) < 3:
            continue
        inter = len(my_tok & r_tok)
        ratio = inter / max(1, min(len(my_tok), len(r_tok)))
        if inter >= 3 and ratio >= 0.45:
            scored.append((r.get("created_at") or "", inter + ratio, r))
    if len(scored) < 1:
        return ""
    best = sorted(scored, key=lambda x: -x[1])[:max_items]
    best.sort(key=lambda x: x[0], reverse=True)
    items = "".join(
        '<li class="flex gap-3 py-1.5 border-b border-slate-200 last:border-0">'
        f'<span class="shrink-0 w-24 text-[11px] font-bold text-slate-500">{_e(_tr_date(c))}</span>'
        f'<a href="/haber/{_e(r.get("slug"))}" class="text-xs sm:text-sm font-semibold text-slate-800 hover:text-red-600">{_e(r.get("title"))}</a>'
        '</li>'
        for c, _, r in best
    )
    return _box("🗂️ Bu konudaki önceki gelişmeler", f'<ul class="m-0 p-0 list-none">{items}</ul>',
                note="Gündem Analizi arşivinden, aynı konudaki haberlerimiz tarih sırasıyla.")


# ---------------------------------------------------------------------------
# 2) Piyasa verisi
# ---------------------------------------------------------------------------
_MARKET_RE = re.compile(r"\b(dolar|euro|avro|döviz|kur(?:lar)?|altın|gram altın|faiz|merkez bankası|tcmb|enflasyon|borsa|bist)\b")


def market_block(text_low: str, market: Optional[Dict]) -> str:
    if not market or not _MARKET_RE.search(text_low):
        return ""
    rates = {r.get("key"): r for r in (market.get("rates") or [])}
    cells = ""
    for k, lbl in (("dolar", "Dolar/TL"), ("euro", "Euro/TL"), ("altin", "Gram Altın")):
        r = rates.get(k)
        if not r or not r.get("price"):
            continue
        try:
            ch = float(r.get("change") or 0)
        except Exception:
            ch = 0.0
        up = ch >= 0
        cells += (
            '<div class="p-3 rounded-xl bg-white border border-slate-200">'
            f'<span class="block text-[10px] font-extrabold text-slate-500 uppercase">{_e(lbl)}</span>'
            f'<strong class="block text-base font-black text-slate-900 font-mono">{_e(r.get("price"))} {_e(r.get("unit") or "")}</strong>'
            f'<span class="text-[11px] font-bold {"text-emerald-700" if up else "text-red-700"}">{"▲" if up else "▼"} %{_e(abs(round(ch, 2)))}</span>'
            '</div>'
        )
    if not cells:
        return ""
    upd = _e(market.get("updated_at") or "")
    return _box("📊 Piyasalarda son durum", f'<div class="grid grid-cols-3 gap-2">{cells}</div>',
                "/piyasalar", "Tüm kurlar ve çevirici →",
                note=f"Serbest piyasa verileri{(' • ' + upd + ' itibarıyla') if upd else ''}. Yatırım tavsiyesi değildir.")


# ---------------------------------------------------------------------------
# 3) Süper Lig
# ---------------------------------------------------------------------------
_TEAM_GENERIC = {"spor", "kulübü", "futbol", "kulubu", "anonim", "şirketi", "jimnastik"}


def _team_keys(name: str) -> List[str]:
    n = _low(name)
    n = re.sub(r"\b(a\.ş\.|fk|sk|spor kulübü|futbol kulübü|rams|corendon|ikas|zecorner|tümosan|hesap\.com|natura dünyası|atakaş|bitexen|çaykur)\b", " ", n)
    return [w[:6] for w in re.findall(r"[a-zçğıöşü]+", n) if len(w) >= 5 and w not in _TEAM_GENERIC]


def superlig_block(title_low: str, category: str, superlig: Optional[Dict]) -> str:
    if not superlig or category != "Spor":
        return ""
    standings = superlig.get("standings") or []
    if not standings:
        return ""
    hits = []
    for t in standings:
        keys = _team_keys(t.get("team") or "")
        if any(re.search(rf"(?<![a-zçğıöşü]){re.escape(k)}", title_low) for k in keys):
            hits.append(t)
    if not hits:
        return ""
    rows = "".join(
        '<tr class="border-b border-slate-200">'
        f'<td class="py-1.5 pr-2 font-black text-slate-900">{int(t.get("rank") or 0)}.</td>'
        f'<td class="py-1.5 pr-2 font-bold text-slate-800">{_e(t.get("team"))}</td>'
        f'<td class="py-1.5 px-1 text-center">{_e(t.get("o"))}</td><td class="py-1.5 px-1 text-center">{_e(t.get("g"))}</td>'
        f'<td class="py-1.5 px-1 text-center">{_e(t.get("b"))}</td><td class="py-1.5 px-1 text-center">{_e(t.get("m"))}</td>'
        f'<td class="py-1.5 px-1 text-center">{_e(t.get("av"))}</td><td class="py-1.5 pl-1 text-center font-black text-red-600">{_e(t.get("p"))}</td>'
        '</tr>'
        for t in hits[:4]
    )
    table = (
        '<div class="overflow-x-auto"><table class="w-full text-xs">'
        '<thead><tr class="text-[10px] uppercase text-slate-500"><th class="text-left">Sıra</th><th class="text-left">Takım</th>'
        '<th>O</th><th>G</th><th>B</th><th>M</th><th>AV</th><th>P</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )
    week = superlig.get("week")
    return _box(f"🏆 Süper Lig puan durumu{(' • ' + str(week) + '. hafta') if week else ''}", table,
                "/super-lig-puan-durumu", "18 takım tam tablo →",
                note="Haberde adı geçen takımların güncel lig sıralaması.")


# ---------------------------------------------------------------------------
# 4) Deprem
# ---------------------------------------------------------------------------
_QUAKE_RE = re.compile(r"\b(deprem\w*|sarsıntı\w*|afad|kandilli|artçı\w*)\b")


def quake_block(title_low: str, quakes: Optional[List[Dict]]) -> str:
    if not _QUAKE_RE.search(title_low) or not quakes:
        return ""
    sel = [q for q in quakes if (q.get("mag") or 0) >= 3.0][:6] or quakes[:6]
    rows = "".join(
        '<tr class="border-b border-slate-200">'
        f'<td class="py-1.5 pr-2 font-black {"text-red-600" if (q.get("mag") or 0) >= 4 else "text-slate-900"}">{_e(q.get("mag"))}</td>'
        f'<td class="py-1.5 pr-2 text-slate-800">{_e(q.get("place"))}</td>'
        f'<td class="py-1.5 pr-2 text-slate-500 whitespace-nowrap">{_e(q.get("date"))} {_e(q.get("time"))}</td>'
        f'<td class="py-1.5 text-slate-500 whitespace-nowrap">{_e(q.get("depth"))}</td>'
        '</tr>'
        for q in sel
    )
    table = (
        '<div class="overflow-x-auto"><table class="w-full text-xs">'
        '<thead><tr class="text-[10px] uppercase text-slate-500 text-left"><th>Büyüklük</th><th>Yer</th><th>Tarih / Saat</th><th>Derinlik</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )
    return _box("🌍 Son depremler (AFAD / Kandilli)", table, "/son-depremler", "Canlı deprem listesi →",
                note="Resmi kurum verilerinden derlenen son kayıtlar. Resmi açıklamalar için afad.gov.tr'yi takip edin.")


# ---------------------------------------------------------------------------
# 5) Hesaplayıcı
# ---------------------------------------------------------------------------
_CALCS = [
    (re.compile(r"kıdem tazminat"), "/hesaplama/kidem-tazminati", "/dosya/kidem-tazminati", "Kıdem tazminatı hesaplama",
     "Çalışma sürenize ve brüt maaşınıza göre kıdem tazminatınızı hesaplayın."),
    (re.compile(r"emekli (?:zam|maaş|aylı)|memur zam|memur maaş|ssk|bağ-kur|bağkur"), "/hesaplama/emekli-zammi", "/dosya/emekli-ve-memur-zammi", "Emekli ve memur zammı hesaplama",
     "Mevcut maaşınıza ve zam oranına göre yeni maaşınızı hesaplayın."),
    (re.compile(r"asgari ücret|net maaş|brüt maaş|maaş hesap|bordro"), "/hesaplama/maas", "/dosya/asgari-ucret", "Maaş hesaplama (brütten nete)",
     "Brüt maaşınızdan net ele geçen tutarı, kesintileriyle birlikte hesaplayın."),
]


def calculator_block(text_low: str) -> str:
    for rx, href, hub_href, label, desc in _CALCS:
        if rx.search(text_low):
            inner = (
                '<a href="' + _e(href) + '" class="flex items-center justify-between gap-3 p-3 rounded-xl bg-white border border-slate-200 hover:border-red-400 transition">'
                f'<span><strong class="block text-sm font-black text-slate-900">{_e(label)}</strong>'
                f'<span class="text-xs text-slate-600">{_e(desc)}</span></span>'
                '<span class="shrink-0 px-3 py-1.5 rounded-lg bg-red-600 text-white text-[11px] font-bold">Hesapla →</span></a>'
            )
            return _box("🧮 Kendi hesabınızı yapın", inner, hub_href, "Kapsamlı rehber ve kronoloji →")
    return ""


# ---------------------------------------------------------------------------
# 6) Birincil (resmi) kaynak
# ---------------------------------------------------------------------------
_OFFICIAL = [
    (r"resmi gazete", "Resmî Gazete", "https://www.resmigazete.gov.tr/"),
    (r"ösym|kpss|yks|ales|dgs|yds", "ÖSYM", "https://www.osym.gov.tr/"),
    (r"\bmeb\b|milli eğitim bakanlığı|\blgs\b", "Millî Eğitim Bakanlığı", "https://www.meb.gov.tr/"),
    (r"\bsgk\b|sosyal güvenlik kurumu", "SGK", "https://www.sgk.gov.tr/"),
    (r"tüik|türkiye istatistik kurumu", "TÜİK", "https://www.tuik.gov.tr/"),
    (r"\btcmb\b|merkez bankası", "TCMB", "https://www.tcmb.gov.tr/"),
    (r"\bafad\b", "AFAD", "https://www.afad.gov.tr/"),
    (r"\bkap\b|kamuyu aydınlatma platformu", "KAP", "https://www.kap.org.tr/"),
    (r"\bspk\b|sermaye piyasası kurulu", "SPK", "https://spk.gov.tr/"),
    (r"\bbddk\b", "BDDK", "https://www.bddk.org.tr/"),
    (r"meteoroloji|\bmgm\b", "Meteoroloji Genel Müdürlüğü", "https://www.mgm.gov.tr/"),
    (r"sağlık bakanlığı", "Sağlık Bakanlığı", "https://www.saglik.gov.tr/"),
    (r"\btff\b|türkiye futbol federasyonu", "TFF", "https://www.tff.org/"),
    (r"\bgib\b|gelir idaresi", "Gelir İdaresi Başkanlığı", "https://www.gib.gov.tr/"),
    (r"\bkyk\b|kredi ve yurtlar", "GSB / KYK", "https://www.gsb.gov.tr/"),
]


def official_block(text_low: str) -> str:
    found = []
    for rx, name, url in _OFFICIAL:
        if re.search(rx, text_low) and all(f[0] != name for f in found):
            found.append((name, url))
        if len(found) >= 3:
            break
    if not found:
        return ""
    links = " ".join(
        f'<a href="{_e(u)}" target="_blank" rel="noopener" class="inline-flex items-center px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-xs font-bold text-slate-800 hover:border-red-400 hover:text-red-600">{_e(n)} ↗</a>'
        for n, u in found
    )
    hub_link = "/dosya/sinav-takvimi" if re.search(r"\b(ösym|kpss|yks|lgs|ales|dgs)\b", text_low) else ""
    hub_txt = "Sınav dosyası ve kronoloji →" if hub_link else ""
    return _box("🏛️ Resmi kaynak", f'<div class="flex flex-wrap gap-2">{links}</div>', hub_link, hub_txt,
                note="Haberde adı geçen kurumun resmi internet sitesi. Kesin bilgi ve duyurular için birincil kaynağı kontrol edin.")


# ---------------------------------------------------------------------------
# Ana giriş
# ---------------------------------------------------------------------------
def build(article: Dict, raw_content: str, index_rows: List[Dict], market: Optional[Dict] = None,
          superlig: Optional[Dict] = None, quakes: Optional[List[Dict]] = None) -> str:
    """Habere uygun değer bloklarını HTML olarak döner (uygun blok yoksa boş string)."""
    try:
        title = article.get("title") or ""
        category = article.get("category") or ""
        title_low = _low(title)
        text_low = _low(title + " " + _plain(raw_content)[:1500])
        blocks = []
        for fn in (
            lambda: superlig_block(title_low, category, superlig),
            lambda: quake_block(title_low, quakes),
            lambda: market_block(_low(title + " " + _plain(raw_content)[:600]), market) if category in ("Ekonomi", "Analiz", "Gündem", "Dünya") else "",
            lambda: calculator_block(text_low),
            lambda: official_block(text_low),
            lambda: chronology_block(article, index_rows),
        ):
            try:
                b = fn()
                if b:
                    blocks.append(b)
            except Exception as e:
                print(f"Değer bloğu atlandı: {e}")
        return "\n".join(blocks)
    except Exception as e:
        print(f"Değer katmanı hatası: {e}")
        return ""
