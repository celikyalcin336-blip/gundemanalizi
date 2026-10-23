import os
import time
import threading
import requests
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, Response, PlainTextResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import database
import config
import main

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

def bot_background_worker():
    """
    Arka planda 7/24 kesintisiz çalışan otonom haber robotu:
    - İlk açılışta sitede haber yoksa hemen 5-6 haber çeker.
    - Her CHECK_INTERVAL_MINUTES dakikada bir otomatik haber tarayıp siteye ve Telegram'a atar.
    """
    time.sleep(3)
    print("🚀 [Otonom Bot] Arka plan haber tarayıcısı aktif edildi.")
    try:
        articles = database.get_articles(limit=10)
        if len(articles) < 5:
            print("🌱 [Otonom Bot] Site için başlangıç haberleri yükleniyor...")
            main.run_bot(max_items=5)
    except Exception as e:
        print(f"❌ Başlangıç bot hatası: {e}")

    while True:
        try:
            time.sleep(config.CHECK_INTERVAL_MINUTES * 60)
            print("🔄 [Otonom Bot] Periyodik haber taraması başlatılıyor...")
            main.run_bot(max_items=1)
            database.cleanup_old_images(days=180)
        except Exception as e:
            print(f"⚠️ [Otonom Bot] Döngü hatası: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    # Otonom haber botunu arka planda başlat
    worker_thread = threading.Thread(target=bot_background_worker, daemon=True)
    worker_thread.start()
    yield

ADMIN_PIN = os.getenv("ADMIN_PIN", "1453")
PANEL_SECRET_SLUG = os.getenv("PANEL_SECRET_SLUG", "yonetim-71453").strip("/ ")

app = FastAPI(title="Gündem Analizi Web Portalı", lifespan=lifespan)

@app.exception_handler(404)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        # Eğer istek bir API sorgusuysa JSON dön
        if request.url.path.startswith("/api/"):
            return JSONResponse(status_code=404, content={"detail": exc.detail or "Not Found"})
        # Web kullanıcısıysa şık markalı HTML 404 şablonu dön
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={},
            status_code=404
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.middleware("http")
async def track_visitors_middleware(request: Request, call_next):
    path = request.url.path
    # 1. Panel, yönetim sayfaları ve tüm API çağrılarını sayaca ASLA dahil etme
    is_api_or_admin = (
        path.startswith("/api/") or
        path == "/panel" or
        path.startswith(f"/{PANEL_SECRET_SLUG}") or
        "yonetim" in path
    )
    # 2. Statik dosyaları ve sistem uçlarını sayaca dahil etme
    is_static_or_system = (
        path.startswith("/assets") or
        path.startswith("/images") or
        path.startswith("/.well-known") or
        path in ("/favicon.ico", "/ads.txt", "/robots.txt", "/sitemap.xml", "/news-sitemap.xml", "/rss.xml", "/health", "/manifest.json", "/sw.js")
    )
    if not (is_api_or_admin or is_static_or_system):
        try:
            ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
            ip = ip.split(",")[0].strip()
            ua = request.headers.get("user-agent", "")
            import hashlib
            vis_hash = hashlib.md5(f"{ip}_{ua[:60]}".encode()).hexdigest()[:16]

            ua_low = ua.lower()
            if any(m in ua_low for m in ("mobile", "android", "iphone", "ipod")):
                device = "Mobil"
            elif "ipad" in ua_low or "tablet" in ua_low:
                device = "Tablet"
            else:
                device = "Masaüstü"

            ref = request.headers.get("referer", "").lower()
            if "google." in ref:
                source = "Google"
            elif "t.me" in ref or "telegram" in ref:
                source = "Telegram"
            elif "instagram.com" in ref:
                source = "Instagram"
            elif "tiktok.com" in ref:
                source = "TikTok"
            elif "facebook.com" in ref or "fb.com" in ref:
                source = "Facebook"
            elif "twitter.com" in ref or "t.co" in ref or "x.com" in ref:
                source = "X (Twitter)"
            elif "whatsapp" in ref or "wa.me" in ref:
                source = "WhatsApp"
            elif ref:
                source = "Diğer Web"
            else:
                source = "Doğrudan"

            country = request.headers.get("cf-ipcountry", "TR")
            city = request.headers.get("cf-ipcity", "")
            database.log_visitor(vis_hash, path, source, device, country, city)
        except Exception:
            pass
    return await call_next(request)

# Statik Dosya Dizinleri
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

@app.get("/images/{filename}")
async def serve_image(filename: str):
    """Haber görselini önce diskte, yoksa kalıcı veritabanında arar."""
    safe_name = os.path.basename(filename)
    local_path = os.path.join(OUTPUT_DIR, safe_name)
    if os.path.exists(local_path):
        return FileResponse(local_path)
    data = database.get_image(safe_name)
    if data:
        return Response(content=data, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800"})
    raise HTTPException(status_code=404, detail="Görsel bulunamadı")

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    """Uptime izleme servisleri için (sunucunun uyumasını engeller)."""
    return PlainTextResponse("ok")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

def get_site_ad_settings() -> dict:
    """Tüm reklam, AdSense, Google Search Console ve Analytics ayarlarını çeker."""
    try:
        return {
            "google_site_verification": database.get_setting("google_site_verification", ""),
            "adsense_client_id": database.get_setting("adsense_client_id", "") or "ca-pub-1415664741128989",
            "ga_tracking_id": database.get_setting("ga_tracking_id", ""),
            "ads_enabled": database.get_setting("ads_enabled", "1") == "1",
            "ads_txt_content": database.get_setting("ads_txt_content", "") or "google.com, pub-1415664741128989, DIRECT, f08c47fec0942fa0",
            "ad_slot_top": database.get_setting("ad_slot_top", ""),
            "ad_slot_article_top": database.get_setting("ad_slot_article_top", ""),
            "ad_slot_article_bottom": database.get_setting("ad_slot_article_bottom", ""),
        }
    except Exception:
        return {
            "google_site_verification": "",
            "adsense_client_id": "ca-pub-1415664741128989",
            "ga_tracking_id": "",
            "ads_enabled": True,
            "ads_txt_content": "google.com, pub-1415664741128989, DIRECT, f08c47fec0942fa0",
            "ad_slot_top": "",
            "ad_slot_article_top": "",
            "ad_slot_article_bottom": "",
        }

_MARKET_CACHE = {
    "ts": 0.0,
    "data": None
}

def get_market_rates() -> dict:
    """
    Canlı Finans & Piyasa Kurları (Altın, Dolar, Euro, Bitcoin):
    Truncgil & Binance üzerinden 60 saniyede bir güncellenir.
    Gerçek piyasa değişim oranlarını (% artış/azalış) yansıtır.
    Hafızada önbelleğe alındığı için siteyi ve sunucuyu asla yormaz, 0.001 saniyede döner.
    """
    global _MARKET_CACHE
    now = time.time()
    if _MARKET_CACHE["data"] and (now - _MARKET_CACHE["ts"]) < 60:
        return _MARKET_CACHE["data"]

    # Varsayılan / Yedek Kurlar
    rates = [
        {"key": "altin", "name": "Gram Altın", "symbol": "ALTIN", "icon": "🟡", "price": "6.430", "unit": "TL", "change": 0.15, "direction": "up"},
        {"key": "dolar", "name": "Dolar", "symbol": "USD/TRY", "icon": "💵", "price": "49,70", "unit": "TL", "change": 0.10, "direction": "up"},
        {"key": "euro", "name": "Euro", "symbol": "EUR/TRY", "icon": "💶", "price": "55,70", "unit": "TL", "change": -0.15, "direction": "down"},
        {"key": "btc", "name": "Bitcoin", "symbol": "BTC/USD", "icon": "🪙", "price": "$81.750", "unit": "", "change": 0.10, "direction": "up"},
    ]

    try:
        def parse_truncgil_num(s):
            if not s:
                return 0.0
            clean = str(s).replace(".", "").replace(",", ".").replace("$", "").replace("%", "").strip()
            return float(clean)

        altin_p, altin_c = None, None
        usd_p, usd_c = None, None
        eur_p, eur_c = None, None

        # 1. Truncgil API (Türkiye Serbest Piyasa & Kapalıçarşı Anlık Kurları)
        try:
            r_tr = requests.get("https://finans.truncgil.com/today.json", headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()
            if "gram-altin" in r_tr:
                g = r_tr["gram-altin"]
                satis = g.get("Satış") or g.get("Sat") or list(g.values())[2]
                degisim = g.get("Değişim") or list(g.values())[3]
                altin_p = parse_truncgil_num(satis)
                altin_c = parse_truncgil_num(degisim)
            if "USD" in r_tr:
                u = r_tr["USD"]
                satis = u.get("Satış") or u.get("Sat") or list(u.values())[2]
                degisim = u.get("Değişim") or list(u.values())[3]
                usd_p = parse_truncgil_num(satis)
                usd_c = parse_truncgil_num(degisim)
            if "EUR" in r_tr:
                e = r_tr["EUR"]
                satis = e.get("Satış") or e.get("Sat") or list(e.values())[2]
                degisim = e.get("Değişim") or list(e.values())[3]
                eur_p = parse_truncgil_num(satis)
                eur_c = parse_truncgil_num(degisim)
        except Exception:
            pass

        # 2. Binance BTC & Gerekirse Dolar/Euro/Altın Yedekleri
        r_btc = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT", timeout=3).json()
        btc_p = float(r_btc["lastPrice"])
        btc_c = float(r_btc["priceChangePercent"])

        if usd_p is None or usd_c is None:
            r_usdt = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=USDTTRY", timeout=3).json()
            usd_p = float(r_usdt["lastPrice"])
            usd_c = float(r_usdt["priceChangePercent"])

        if eur_p is None or eur_c is None:
            r_eur = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=EURUSDT", timeout=3).json()
            eur_usd = float(r_eur["lastPrice"])
            eur_p = eur_usd * usd_p
            eur_usd_c = float(r_eur["priceChangePercent"])
            eur_c = ((1 + eur_usd_c / 100.0) * (1 + usd_c / 100.0) - 1.0) * 100.0

        if altin_p is None or altin_c is None:
            try:
                r_paxg = requests.get("https://api.binance.com/api/v3/ticker/24hr?symbol=PAXGUSDT", timeout=3).json()
                ounce = float(r_paxg["lastPrice"])
                gold_usd_c = float(r_paxg["priceChangePercent"])
                altin_p = (ounce / 31.1034768) * usd_p
                altin_c = ((1 + gold_usd_c / 100.0) * (1 + usd_c / 100.0) - 1.0) * 100.0
            except Exception:
                r_gold = requests.get("https://api.gold-api.com/price/XAU", timeout=3).json()
                ounce = float(r_gold["price"])
                altin_p = (ounce / 31.1034768) * usd_p
                altin_c = usd_c

        rates = [
            {
                "key": "altin",
                "name": "Gram Altın",
                "symbol": "ALTIN",
                "icon": "🟡",
                "price": f"{altin_p:,.0f}".replace(",", "."),
                "unit": "TL",
                "change": round(altin_c, 2),
                "direction": "up" if altin_c >= 0 else "down"
            },
            {
                "key": "dolar",
                "name": "Dolar",
                "symbol": "USD/TRY",
                "icon": "💵",
                "price": f"{usd_p:.2f}".replace(".", ","),
                "unit": "TL",
                "change": round(usd_c, 2),
                "direction": "up" if usd_c >= 0 else "down"
            },
            {
                "key": "euro",
                "name": "Euro",
                "symbol": "EUR/TRY",
                "icon": "💶",
                "price": f"{eur_p:.2f}".replace(".", ","),
                "unit": "TL",
                "change": round(eur_c, 2),
                "direction": "up" if eur_c >= 0 else "down"
            },
            {
                "key": "btc",
                "name": "Bitcoin",
                "symbol": "BTC/USD",
                "icon": "🪙",
                "price": f"${btc_p:,.0f}".replace(",", "."),
                "unit": "",
                "change": round(btc_c, 2),
                "direction": "up" if btc_c >= 0 else "down"
            },
        ]
        result = {
            "ok": True,
            "rates": rates,
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")
        }
        _MARKET_CACHE["ts"] = now
        _MARKET_CACHE["data"] = result
        return result
    except Exception as e:
        if _MARKET_CACHE["data"]:
            return _MARKET_CACHE["data"]
        return {
            "ok": True,
            "rates": rates,
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")
        }

@app.get("/api/market-rates")
async def api_market_rates():
    """Canlı altın, dolar, euro ve bitcoin fiyatlarını JSON olarak döner."""
    return JSONResponse(get_market_rates())

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(request: Request, kategori: str = None, q: str = None, sayfa: int = 1):
    database.record_visit("home_visits")
    import math
    import urllib.parse
    page = max(1, sayfa)
    limit = 24
    offset = (page - 1) * limit

    if q and q.strip():
        q_low = q.strip().lower()
        all_arts = database.get_articles(limit=150)
        matched = [
            a for a in all_arts
            if q_low in (a.get("title") or "").lower() or q_low in (a.get("summary") or "").lower()
        ]
        total_count = len(matched)
        articles = matched[offset:offset + limit]
        canonical_url = f"{config.SITE_URL}/"
    else:
        articles = database.get_articles(limit=limit, category=kategori, offset=offset)
        total_count = database.get_articles_total_count(category=kategori)
        if kategori:
            canonical_url = f"{config.SITE_URL}/?kategori={urllib.parse.quote(kategori)}"
        else:
            canonical_url = f"{config.SITE_URL}/"

    total_pages = max(1, math.ceil(total_count / limit))

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "articles": articles,
            "active_category": kategori,
            "search_query": q.strip() if q else "",
            "ad_settings": get_site_ad_settings(),
            "market_rates": get_market_rates()["rates"],
            "canonical_url": canonical_url,
            "current_page": page,
            "total_pages": total_pages,
            "total_articles": total_count
        }
    )

@app.get("/panel", response_class=HTMLResponse)
async def admin_panel_decoy(request: Request):
    """Eski veya tahmin edilen /panel adresine gelenlere sahte 404 gösterir."""
    return HTMLResponse(
        status_code=404,
        content="""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="UTF-8"><title>404 - Sayfa Bulunamadı</title>
<style>body{background:#0a0e17;color:#94a3b8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;text-align:center;}h1{color:#ef4444;font-size:3rem;margin:0;}p{margin:10px 0 20px;}a{color:#38bdf8;text-decoration:none;font-weight:bold;}</style>
</head>
<body>
<h1>404</h1>
<p>Aradığınız sayfa mevcut değil veya taşınmış olabilir.</p>
<a href="/">← Ana Sayfaya Dön</a>
</body>
</html>"""
    )

@app.get(f"/{PANEL_SECRET_SLUG}", response_class=HTMLResponse)
@app.get("/yonetim-71453", response_class=HTMLResponse)
async def admin_panel(request: Request):
    stats = database.get_dashboard_summary()
    stats["gemini_active"] = bool(config.GEMINI_API_KEY)
    stats["telegram_active"] = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
    stats["check_interval"] = config.CHECK_INTERVAL_MINUTES
    return templates.TemplateResponse(
        request=request,
        name="panel.html",
        context={"stats": stats, "panel_slug": PANEL_SECRET_SLUG, "ad_settings": get_site_ad_settings()}
    )

@app.post("/api/panel/fetch-now")
async def panel_fetch_now(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    threading.Thread(target=main.run_bot, kwargs={"max_items": 1}, daemon=True).start()
    return {"ok": True, "message": "Yeni haber taraması başlatıldı! 15-20 saniye içinde siteye ve Telegram'a düşecek."}

@app.post("/api/panel/publish-breaking")
async def panel_publish_breaking(
    request: Request,
    title: str = Form(...),
    summary: str = Form(""),
    content: str = Form(""),
    category: str = Form("Gündem"),
    source: str = Form("Gündem Analizi"),
    image_url: str = Form(None)
):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")

    img_path = ""
    if image_url:
        try:
            r = requests.get(image_url, timeout=10)
            if r.status_code == 200:
                import hashlib
                fname = f"post_{hashlib.md5(title.encode()).hexdigest()[:10]}.jpg"
                img_path = os.path.join(OUTPUT_DIR, fname)
                with open(img_path, "wb") as f:
                    f.write(r.content)
        except Exception as e:
            print(f"Görsel indirme hatası: {e}")

    slug = database.save_article(
        title=title.strip(),
        summary=summary.strip(),
        content=content.strip(),
        image_path=img_path,
        source=source.strip(),
        category=category.strip()
    )
    site_url = f"{config.SITE_URL}/haber/{slug}"

    try:
        tg_text = f"🚨 <b>{title}</b>\n\n{summary}"
        if img_path and os.path.exists(img_path):
            telegram_notifier.send_telegram_news(img_path, tg_text, site_url)
        else:
            telegram_notifier.send_telegram_message(f"{tg_text}\n\n🔗 Haberin Detayı: {site_url}")
    except Exception as e:
        print(f"Telegram bildirim hatası: {e}")

    return {"ok": True, "slug": slug, "url": site_url}

@app.post("/api/panel/delete/{article_id}")
async def panel_delete_article(article_id: int, request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    deleted = database.delete_article(article_id)
    return {"ok": deleted}

@app.get("/api/panel/article/{article_id}")
async def panel_get_article(article_id: int, request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    art = database.get_article_by_id(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Haber bulunamadı")
    return {"ok": True, "article": art}

@app.post("/api/panel/edit/{article_id}")
async def panel_edit_article(
    article_id: int,
    request: Request,
    title: str = Form(...),
    summary: str = Form(""),
    content: str = Form(""),
    category: str = Form("Gündem")
):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    updated = database.update_article(
        article_id=article_id,
        title=title.strip(),
        summary=summary.strip(),
        content=content.strip(),
        category=category.strip()
    )
    return {"ok": updated, "message": "Haber başarıyla güncellendi!"}

@app.get("/api/panel/radar-videos")
def get_radar_videos(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi")
    import video_scout
    import sqlite3
    video_scout.init_scout_db()
    conn = sqlite3.connect(video_scout.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url, title, source, created_at FROM seen_videos ORDER BY rowid DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return [{"url": r[0], "title": r[1], "source": r[2], "date": r[3]} for r in rows]

@app.post("/api/panel/radar-scan")
def trigger_radar_scan(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi")
    import video_scout
    count = video_scout.run_scout_cycle()
    return {"ok": True, "count": count}

VIDEO_JOBS = {}

def _process_viral_video_job(
    job_id: str,
    raw_path: str,
    out_filename: str,
    video_url: str,
    has_uploaded_file: bool,
    title: str,
    summary: str,
    category: str,
    start_sec: float,
    max_dur_sec: float,
    wm_pos: str,
    audio_mode: str,
    ticker_text: str,
    pub_site: bool,
    pub_tg: bool,
    pub_fb: bool,
    pub_ig: bool = False,
    pub_x: bool = False,
    source: str = "Gündem Analizi"
):
    import video_generator
    import ai_writer
    import telegram_notifier
    import meta_poster

    job = VIDEO_JOBS[job_id]
    try:
        # ADIM 1: İndirme / Yükleme Kontrolü
        job.update({
            "step": 1,
            "percent": 15,
            "eta_sec": 22,
            "step_text": "📥 1/5: Ham video kaynağı indiriliyor ve doğrulanıyor..."
        })
        if not has_uploaded_file:
            video_generator.download_social_video(video_url, raw_path)

        # ADIM 2: FFmpeg ile Tam Ekran Logolama & Filigran & Kırpma
        job.update({
            "step": 2,
            "percent": 42,
            "eta_sec": 15,
            "step_text": "🎨 2/5: Tam ekran Gündem Analizi logosu, kayan bant ve filigran işleniyor..."
        })
        auto_ticker = ticker_text.strip() or (f"{title} • {summary}" if summary else title)
        res = video_generator.brand_raw_video(
            raw_video_path=raw_path,
            title=title,
            category=category,
            output_filename=out_filename,
            start_sec=start_sec,
            max_dur_sec=max_dur_sec,
            wm_pos=wm_pos,
            audio_mode=audio_mode,
            ticker_text=auto_ticker,
            source=source
        )

        # ADIM 3: Yapay Zeka Haber & Sosyal Medya Metni
        job.update({
            "step": 3,
            "percent": 68,
            "eta_sec": 9,
            "step_text": "🤖 3/5: Gemini AI ile haber makalesi ve Reels/TikTok açıklaması hazırlanıyor..."
        })
        base_summary = summary or title
        ai_cap = ai_writer.generate_social_caption(title, base_summary, source or "Gündem Analizi Özel")
        article_data = ai_writer.generate_full_article(title, base_summary, source or "Gündem Analizi Özel")

        # Sosyal medya metnine kaynak ekle (Hukuki güvence) - Tek seferlik ekleme garantisi
        clean_src = source.strip() if source else ""
        if clean_src and clean_src.lower() not in ("gündem analizi", "özel", "yok", ""):
            if "kaynak:" not in ai_cap["caption"].lower():
                ai_cap["caption"] = f"{ai_cap['caption']}\n\n📌 Kaynak: {clean_src}"

        slug = None
        site_url = config.SITE_URL
        article_id = None

        # ADIM 4: Web Sitesinde Yayınlama
        if pub_site:
            job.update({
                "step": 4,
                "percent": 84,
                "eta_sec": 5,
                "step_text": "🌐 4/5: Haber ve video gündemanalizi.com.tr üzerinde yayınlanıyor..."
            })
            video_html = f"""
            <div class="my-6 rounded-2xl overflow-hidden border border-red-600/40 bg-black shadow-2xl relative select-none">
                <video controls playsinline controlsList="nodownload noplaybackrate" disablePictureInPicture oncontextmenu="return false;" class="w-full max-h-[640px] mx-auto" poster="/images/{os.path.basename(res['thumb_path'])}">
                    <source src="/images/{out_filename}" type="video/mp4">
                </video>
            </div>
            """
            full_content = video_html + article_data["content"]
            slug = database.save_article(
                title=title,
                summary=article_data["summary"],
                content=full_content,
                image_path=res["thumb_path"],
                source=source.strip() or "Gündem Analizi",
                category=category
            )
            site_url = f"{config.SITE_URL}/haber/{slug}"
            art_obj = database.get_article_by_slug(slug)
            if art_obj:
                article_id = art_obj.get("id")

        # ADIM 5: Seçilen Sosyal Medya Kanallarına Gönderim
        share_report = []
        if pub_tg or pub_fb or pub_ig or pub_x:
            job.update({
                "step": 5,
                "percent": 90,
                "eta_sec": 20 if pub_ig else 4,
                "step_text": "📲 5/5: Logolu video seçtiğin sosyal medya hesaplarında paylaşılıyor..."
            })
            if pub_tg:
                vid_caption = ai_cap["caption"]
                if "instagram.com" not in vid_caption:
                    vid_caption += "\n\n📸 Instagram'da İzle & Takip Et: https://www.instagram.com/gundem_analiz/"
                ok = telegram_notifier.send_telegram_video(res["video_path"], vid_caption, site_url)
                share_report.append("📲 Telegram: ✅" if ok is not False else "📲 Telegram: ❌")
            if pub_fb:
                r_fb = meta_poster.post_video_to_facebook(res["video_path"], ai_cap["caption"], site_url)
                share_report.append(f"📘 Facebook: {'✅' if r_fb.get('status') == 'success' else '❌ ' + str(r_fb.get('status'))}")
            if pub_x:
                import x_poster
                job.update({"step_text": "🐦 X (Twitter) paylaşımı yapılıyor..."})
                r_x = x_poster.post_video_to_x(res["video_path"], title, site_url)
                x_st = r_x.get("status")
                share_report.append("🐦 X: ✅" if x_st == "success" else "🐦 X: ↗️ Hazır")
            if pub_ig:
                job.update({"step_text": "📸 Instagram Reels (@gundem_analiz) yükleniyor (20-45 sn sürebilir)..."})
                public_url = f"{config.PUBLIC_MEDIA_BASE}/images/{out_filename}"
                ig_caption = f"{ai_cap['caption']}\n\n🌐 Detaylar profildeki linkte: gündemanalizi.com.tr"
                r_ig = meta_poster.post_reel_to_instagram(res["video_path"], ig_caption, public_url)
                share_report.append(f"📸 Instagram: {'✅' if r_ig.get('status') == 'success' else '❌ ' + str(r_ig.get('status'))}")

        if os.path.exists(raw_path):
            os.remove(raw_path)

        social_pack = f"{ai_cap['caption']}\n\n🌐 Detaylar: {site_url}"
        job.update({
            "status": "done",
            "step": 5,
            "percent": 100,
            "eta_sec": 0,
            "step_text": "✅ Tamamlandı! " + (" • ".join(share_report) if share_report else "Video hazır."),
            "download_url": f"/images/{out_filename}",
            "thumb_url": f"/images/{os.path.basename(res['thumb_path'])}",
            "article_url": f"/haber/{slug}" if slug else "",
            "article_id": article_id,
            "social_caption": social_pack
        })
    except Exception as e:
        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except Exception:
                pass
        job.update({
            "status": "error",
            "eta_sec": 0,
            "step_text": f"❌ Hata oluştu: {e}",
            "error": str(e)
        })

@app.post("/api/panel/viral-video")
async def panel_viral_video(
    request: Request,
    title: str = Form(...),
    summary: str = Form(""),
    category: str = Form("Gündem"),
    video_url: str = Form(""),
    start_sec: float = Form(0.0),
    max_dur_sec: float = Form(45.0),
    wm_pos: str = Form("center"),
    audio_mode: str = Form("original"),
    ticker_text: str = Form(""),
    pub_site: str = Form("true"),
    pub_tg: str = Form("true"),
    pub_fb: str = Form("true"),
    pub_ig: str = Form("false"),
    pub_x: str = Form("false"),
    source: str = Form("Gündem Analizi"),
    video_file: UploadFile = File(None)
):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")

    import hashlib
    vid_id = hashlib.md5(f"{title}_{time.time()}".encode("utf-8")).hexdigest()[:10]
    raw_path = os.path.join(OUTPUT_DIR, f"raw_{vid_id}.mp4")
    out_filename = f"viral_{vid_id}.mp4"

    has_uploaded_file = False
    if video_file and video_file.filename:
        content = await video_file.read()
        with open(raw_path, "wb") as f:
            f.write(content)
        has_uploaded_file = True
    elif not video_url.strip():
        raise HTTPException(status_code=400, detail="Lütfen bir video dosyası seçin veya video linki girin.")

    VIDEO_JOBS[vid_id] = {
        "job_id": vid_id,
        "status": "running",
        "step": 1,
        "percent": 8,
        "eta_sec": 25,
        "step_text": "🚀 Video stüdyosu başlatıldı, sıraya alındı...",
        "started_at": time.time()
    }

    t = threading.Thread(
        target=_process_viral_video_job,
        args=(
            vid_id,
            raw_path,
            out_filename,
            video_url.strip(),
            has_uploaded_file,
            title.strip(),
            summary.strip(),
            category.strip(),
            float(start_sec or 0),
            float(max_dur_sec or 45),
            wm_pos.strip(),
            audio_mode.strip(),
            ticker_text.strip(),
            pub_site.lower() == "true",
            pub_tg.lower() == "true",
            pub_fb.lower() == "true",
            pub_ig.lower() == "true",
            pub_x.lower() == "true",
            source.strip() or "Gündem Analizi"
        ),
        daemon=True
    )
    t.start()
    return {"ok": True, "job_id": vid_id}

@app.get("/api/panel/video-job/{job_id}")
async def panel_video_job_status(job_id: str, request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    job = VIDEO_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="İşlem bulunamadı")
    elapsed = round(time.time() - job.get("started_at", time.time()), 1)
    return {"ok": True, "elapsed_sec": elapsed, **job}

@app.get("/manifest.json")
async def pwa_manifest():
    return JSONResponse({
        "name": "Gündem Analizi Yönetim Paneli",
        "short_name": "GA Panel",
        "description": "Gündem Analizi Canlı Haber ve Sosyal Medya Yönetim Stüdyosu",
        "start_url": f"/{PANEL_SECRET_SLUG}",
        "display": "standalone",
        "background_color": "#0a0d14",
        "theme_color": "#dc2626",
        "icons": [
            {
                "src": "/assets/logo.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/assets/logo.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.get("/api/panel/live-stats")
async def panel_live_stats(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    stats = database.get_dashboard_summary()
    return {
        "ok": True,
        "active_now": stats.get("active_now", 1),
        "today_uniques": stats.get("today_uniques", 0),
        "first_time_today": stats.get("first_time_today", 0),
        "returning_today": stats.get("returning_today", 0),
        "total_views": stats.get("total_views", 0),
        "total_all_hits": stats.get("total_all_hits", 0),
        "live_visitors": stats.get("live_visitors", [])[:8],
        "total_revenue": stats.get("total_revenue", 0.0)
    }

@app.post("/api/panel/revenue")
async def panel_add_revenue(
    request: Request,
    source: str = Form(...),
    amount: float = Form(...),
    date: str = Form(""),
    notes: str = Form("")
):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    if not date:
        date = time.strftime("%Y-%m-%d")
    ok = database.add_revenue_record(source, amount, date, notes)
    return {"ok": bool(ok), "message": "Gelir kaydı başarıyla eklendi."}

@app.post("/api/panel/delete-revenue/{rec_id}")
async def panel_del_revenue(rec_id: int, request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    database.delete_revenue_record(rec_id)
    return {"ok": True, "message": "Gelir kaydı silindi."}

@app.get("/api/panel/ad-settings")
async def get_panel_ad_settings(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    return {"ok": True, "settings": get_site_ad_settings()}

@app.post("/api/panel/ad-settings")
async def save_panel_ad_settings(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim")
    try:
        data = await request.json()
    except Exception:
        data = {}
    keys = [
        "google_site_verification",
        "adsense_client_id",
        "ga_tracking_id",
        "ads_enabled",
        "ads_txt_content",
        "ad_slot_top",
        "ad_slot_article_top",
        "ad_slot_article_bottom"
    ]
    for k in keys:
        if k in data:
            database.set_setting(k, str(data[k]))
    return {"ok": True, "message": "Reklam ve Google ayarları başarıyla kaydedildi!"}

@app.post("/api/ihbar")
async def submit_ihbar(
    message: str = Form(...),
    contact: str = Form(""),
    media_file: UploadFile = File(None)
):
    if not message or len(message.strip()) < 5:
        raise HTTPException(status_code=400, detail="Lütfen ihbar detayını yazın.")

    import hashlib
    import telegram_notifier
    ihbar_id = hashlib.md5(f"{message}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    saved_path = ""
    media_type = ""
    studio_link_line = ""

    if media_file and media_file.filename:
        fname = media_file.filename.lower()
        content = await media_file.read()
        if len(content) <= 50 * 1024 * 1024:  # Maks 50 MB
            if any(fname.endswith(ext) for ext in (".mp4", ".mov", ".webm", ".mkv", ".avi")) or (media_file.content_type or "").startswith("video"):
                out_name = f"ihbar_{ihbar_id}.mp4"
                saved_path = os.path.join(OUTPUT_DIR, out_name)
                media_type = "video"
                studio_link_line = f"\n\n🎬 Panelde Logolamak İçin Video Linki:\n{config.PUBLIC_MEDIA_BASE}/images/{out_name}"
            else:
                out_name = f"ihbar_{ihbar_id}.jpg"
                saved_path = os.path.join(OUTPUT_DIR, out_name)
                media_type = "photo"
                studio_link_line = f"\n\n🖼️ Görsel Linki:\n{config.PUBLIC_MEDIA_BASE}/images/{out_name}"
            with open(saved_path, "wb") as f:
                f.write(content)

    report_text = (
        f"🚨 [YENİ OKUYUCU İHBARI GELDİ!]\n\n"
        f"📍 İhbar Detayı:\n{message.strip()}\n\n"
        f"👤 Gönderen / Link: {contact.strip() or 'Anonim Okuyucu'}"
        f"{studio_link_line}"
    )

    def _bg_send():
        telegram_notifier.send_admin_ihbar(report_text, saved_path, media_type)

    threading.Thread(target=_bg_send, daemon=True).start()
    return {"ok": True, "message": "İhbarınız ve medyanız Haber Merkezimize başarıyla iletildi! Teşekkür ederiz."}

@app.api_route("/haber/{slug}", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def article_detail(request: Request, slug: str):
    article = database.get_article_by_slug(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Haber bulunamadı")

    other_articles = [a for a in database.get_articles(limit=6) if a["slug"] != slug][:5]
    canonical_url = f"https://xn--gndemanalizi-dlb.com.tr/haber/{slug}"
    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": article,
            "other_articles": other_articles,
            "ad_settings": get_site_ad_settings(),
            "market_rates": get_market_rates()["rates"],
            "canonical_url": canonical_url
        }
    )

@app.get("/hakkimizda", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html", context={})

@app.get("/kunye", response_class=HTMLResponse)
async def kunye_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html", context={})

@app.get("/gizlilik-politikasi", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={})

@app.get("/iletisim", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html", context={})

@app.get("/api/articles")
async def api_articles(limit: int = 10):
    return database.get_articles(limit=limit)

@app.get("/api/stats")
async def api_stats():
    return database.get_storage_stats()

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path, media_type="image/png")
    raise HTTPException(status_code=404)

@app.get("/google51414ee4e22f8aa5.html", response_class=PlainTextResponse)
async def google_verification():
    return PlainTextResponse("google-site-verification: google51414ee4e22f8aa5.html")

@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    custom = database.get_setting("ads_txt_content", "").strip()
    if custom:
        return PlainTextResponse(content=custom + "\n")
    return PlainTextResponse(content="google.com, pub-1415664741128989, DIRECT, f08c47fec0942fa0\n")

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots(request: Request):
    host = request.headers.get("host", "xn--gndemanalizi-dlb.com.tr")
    base_url = f"https://{host}"
    content = f"""User-agent: *
Allow: /
Disallow: /panel
Disallow: /{PANEL_SECRET_SLUG}
Disallow: /yonetim*
Disallow: /api/panel/
Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/news-sitemap.xml
"""
    return PlainTextResponse(content=content)

@app.get("/sitemap.xml")
async def sitemap(request: Request):
    articles = database.get_articles(limit=300)
    host = request.headers.get("host", "xn--gndemanalizi-dlb.com.tr")
    base_url = f"https://{host}"
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    xml.append(f'  <url><loc>{base_url}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>')
    import urllib.parse
    for cat in ("Gündem", "Ekonomi", "Dünya", "Spor", "Asayiş", "Son Dakika"):
        cat_enc = urllib.parse.quote(cat)
        xml.append(f'  <url><loc>{base_url}/?kategori={cat_enc}</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>')
    xml.append(f'  <url><loc>{base_url}/hakkimizda</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')
    xml.append(f'  <url><loc>{base_url}/kunye</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')
    xml.append(f'  <url><loc>{base_url}/iletisim</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')
    xml.append(f'  <url><loc>{base_url}/gizlilik-politikasi</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')
    for a in articles:
        xml.append(f'  <url><loc>{base_url}/haber/{a["slug"]}</loc><lastmod>{a["created_at"][:10]}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>')
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml")

@app.get("/news-sitemap.xml")
async def news_sitemap(request: Request):
    """Google Haberler (Google News & Top Stories) özel XML site haritası."""
    from xml.sax.saxutils import escape
    articles = database.get_articles(limit=100)
    host = request.headers.get("host", "xn--gndemanalizi-dlb.com.tr")
    base_url = f"https://{host}"
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">')
    for a in articles:
        raw_dt = (a.get("created_at") or "").strip().replace(" ", "T")
        if len(raw_dt) == 16:
            raw_dt += ":00+03:00"
        elif "+" not in raw_dt and "Z" not in raw_dt:
            raw_dt = raw_dt[:19] + "+03:00"
        title_esc = escape(a.get("title") or "")
        xml.append(f"""  <url>
    <loc>{base_url}/haber/{a["slug"]}</loc>
    <news:news>
      <news:publication>
        <news:name>Gündem Analizi</news:name>
        <news:language>tr</news:language>
      </news:publication>
      <news:publication_date>{raw_dt}</news:publication_date>
      <news:title>{title_esc}</news:title>
    </news:news>
  </url>""")
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml")

@app.get("/rss.xml")
async def rss_feed(request: Request):
    from xml.sax.saxutils import escape
    articles = database.get_articles(limit=30)
    host = request.headers.get("host", "xn--gndemanalizi-dlb.com.tr")
    base_url = f"https://{host}"
    items_xml = []
    for a in articles:
        img_name = (a.get("image_path") or "").replace("\\", "/").split("/")[-1]
        img_url = f"{base_url}/images/{img_name}" if img_name else f"{base_url}/assets/logo.png"
        items_xml.append(f"""    <item>
      <title>{escape(a["title"])}</title>
      <link>{base_url}/haber/{a["slug"]}</link>
      <guid>{base_url}/haber/{a["slug"]}</guid>
      <description>{escape(a.get("summary") or a["title"])}</description>
      <category>{escape(a.get("category") or "Gündem")}</category>
      <enclosure url="{img_url}" type="image/jpeg"/>
    </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Gündem Analizi | Doğru Haber • Tarafsız Analiz</title>
    <link>{base_url}/</link>
    <description>Türkiye ve dünyadan son dakika gelişmeleri ve tarafsız analizler.</description>
    <language>tr-TR</language>
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    return HTMLResponse(content=rss, media_type="application/rss+xml")

def start_server(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run("web_server:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    start_server()
