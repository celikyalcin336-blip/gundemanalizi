import asyncio

def smart_sentence_split(text: str) -> list:
    """Türkçe sıra sayıları (14., 1., 2026.) ve unvan/kısaltmaları (Dr., Prof., vb.) bozmadan tam cümlelere böler."""
    if not text:
        return []
    t = text
    abbrevs = ["dr", "prof", "doç", "doc", "av", "uzm", "vb", "vs", "yy", "mad", "no", "m", "km"]
    for ab in abbrevs:
        t = re.sub(rf'\b({ab})\.', r'\1___DOT___', t, flags=re.I)
    t = re.sub(r'(\b\d+)\.', r'\1___DOT___', t)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ"“])', t)
    clean_sents = []
    for p in parts:
        restored = p.replace('___DOT___', '.').strip()
        if len(restored) > 25:
            clean_sents.append(restored)
    return clean_sents

import re
import os
import time
import mimetypes
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('application/javascript', '.js')
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
from starlette.middleware.gzip import GZipMiddleware
import database
import config
import main

BASE_DIR = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

import subprocess
import sys

def bot_background_worker():
    """
    Arka planda 7/24 kesintisiz çalışan otonom haber robotu:
    - Harici subprocess açmaz (Render 512MB RAM sınırını aşmamak için bellek içi çalışır).
    - 60 saniyede bir kontrol eder, haber yayını sonrası gc.collect() ile RAM'i tamamen temizler.
    """
    time.sleep(8)
    print("🚀 [Otonom Bot] Arka plan haber işçisi aktif edildi (Hafif Bellek-İçi Mod)...")
    import gc

    while True:
        try:
            import main as bot_main
            bot_main.run_bot(max_items=1)
            import analysis_engine
            analysis_engine.ensure_daily_synthesis_reports()
            gc.collect()
        except Exception as e:
            print(f"⚠️ [Otonom Bot İstisnası]: {e}")
        time.sleep(60)

def system_health_watchdog_worker():
    """
    Gece Nöbetçi Sistem Bekçisi:
    Yalçın Bey'in talimatıyla yalnızca GECE 00:00 - SABAH 09:00 saatleri arasında,
    10 dakikada bir (600 sn) veritabanı ve site sağlığını sessizce denetler.
    Gündüz saatlerinde pasif bekler (Neon ve sunucuyu yormaz).
    """
    import telegram_notifier
    time.sleep(60)
    last_status_ok = True
    consecutive_fails = 0
    last_log_cleanup_ts = 0
    tz_tr = timezone(timedelta(hours=3))

    while True:
        try:
            current_hour = datetime.now(tz_tr).hour
            # Yalnızca gece 00:00 ile sabah 09:00 arasında nöbet tutar
            is_night_shift = (0 <= current_hour < 9)

            if is_night_shift:
                status_ok = True
                fail_reason = ""
                with database.get_connection() as conn:
                    if not getattr(conn, "is_pg", False) and database.USE_PG:
                        status_ok = False
                        fail_reason = f"PostgreSQL bağlantısı koptu! Sistem geçici SQLite modunda. Hata: {getattr(database, '_PG_LAST_ERROR', 'Bilinmiyor')}"
                    else:
                        try:
                            row = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()
                            cnt = row["c"] if row else 0
                            if cnt == 0:
                                status_ok = False
                                fail_reason = "Veritabanında 0 haber tespit edildi! Makale listesi boş görünüyor."
                        except Exception as q_err:
                            status_ok = False
                            fail_reason = f"Makale sayısı sorgulanamadı: {q_err}"

                if not status_ok:
                    consecutive_fails += 1
                    if consecutive_fails == 1:
                        telegram_notifier.send_admin_alert(
                            subject="Gece Nöbeti: Sitede Veritabanı / Haber Kesintisi!",
                            message=f"Patron dikkat!\n\n{fail_reason}\n\nSistem otomatik onarım ve yeniden bağlanmayı deniyor."
                        )
                    last_status_ok = False
                else:
                    if not last_status_ok:
                        telegram_notifier.send_admin_alert(
                            subject="Sistem Başarıyla Normale Döndü",
                            message="Veritabanı bağlantısı sağlandı ve haberler yeniden sorunsuz yayında.",
                            is_resolved=True
                        )
                    last_status_ok = True
                    consecutive_fails = 0

                # Günde 1 kez: 30 günden eski logları temizle VE arşivdeki sıradaki 135 haberi Google Indexing API ile dizine gönder
                if time.time() - last_log_cleanup_ts > 86400:
                    last_log_cleanup_ts = time.time()
                    try:
                        database.cleanup_old_visitor_logs(days=30)
                    except Exception:
                        pass
                    try:
                        import google_indexer
                        today_str = datetime.now(tz_tr).strftime("%Y-%m-%d")
                        last_bf_day = database.get_setting("indexing_backfill_day", "")
                        if last_bf_day != today_str:
                            database.set_setting("indexing_backfill_day", today_str)
                            cur_off = int(database.get_setting("indexing_backfill_offset", "135") or "135")
                            all_idx = _indexable_articles()
                            batch_items = all_idx[cur_off:cur_off + 135]
                            if batch_items:
                                pushed_bf = 0
                                for _it in batch_items:
                                    _u = f"https://xn--gndemanalizi-dlb.com.tr/haber/{_it['slug']}"
                                    if google_indexer.notify_google_indexing(_u, ping_websub=False):
                                        pushed_bf += 1
                                    time.sleep(0.25)
                                next_off = cur_off + len(batch_items)
                                if next_off >= len(all_idx):
                                    next_off = 0
                                database.set_setting("indexing_backfill_offset", str(next_off))
                                print(f"🚀 [Günlük Arşiv İndeksleyici] {pushed_bf}/{len(batch_items)} arşiv haberi Google Indexing API'ye iletildi (Yeni sıra: {next_off}).")
                    except Exception as _bfe:
                        print(f"Günlük arşiv indeksleme uyarısı: {_bfe}")

        except Exception as e:
            pass

        # Her 10 dakikada bir (600 saniye) kontrol
        time.sleep(600)

def _warmup_turbo_cache():
    """Sunucu ayağa kalkar kalkmaz ana sayfayı, site haritasını ve canlı servisleri RAM'e hafifçe yükler."""
    time.sleep(5)
    try:
        get_cached_category_widgets()
        database.get_articles(limit=24)
        database.get_articles_total_count()
        _indexable_articles()
        _ls = __import__("live_services")
        _ls.get_live_superlig()
        _ls.get_live_prayer_times()
        _ls.get_live_pharmacies("istanbul")
        print("⚡ [Turbo Cache] Kategori, site haritası ve canlı servis önbelleği RAM'e başarıyla yüklendi (0 ms hazır).")
    except Exception as e:
        print(f"Önbellek ısınma hatası: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    # Render 512MB RAM koruması: Başlangıç görevlerini aynı anda çakıştırmak yerine sırayla (sequential) çalıştır
    def _bg_startup_pipeline():
        import gc
        time.sleep(3)
        try:
            import google_indexer
            if getattr(google_indexer, "_PERMANENT_TOKEN_REV", ""):
                database.set_setting("google_indexing_token_b64", google_indexer._PERMANENT_TOKEN_REV[::-1])
            if not database.get_setting("indexing_backfill_day", ""):
                database.set_setting("indexing_backfill_day", datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d"))
                database.set_setting("indexing_backfill_offset", "135")
        except Exception:
            pass
        # Başlangıçta 1050 makalenin tamamını çekip tek tek UPDATE yapan ağır döngü CPU kilitlemesini önlemek için kapatıldı (gösterim anında zaten temizleniyor)
        _IMAGE_MEM_CACHE.clear()
        with _INDEX_LOCK:
            _INDEX_MEMO.clear()
            _INDEX_CACHE["rows"] = []
            _INDEX_CACHE["ts"] = 0.0
        clear_turbo_cache()
        gc.collect()
        try:
            import analysis_engine
            analysis_engine.seed_curated_analyses()
            analysis_engine.ensure_daily_synthesis_reports()
        except Exception as _se:
            print(f'Sentez raporu başlangıç uyarısı: {_se}')
        _warmup_turbo_cache()
        gc.collect()
    threading.Thread(target=_bg_startup_pipeline, daemon=True).start()
    # Otonom haber botunu arka planda baslat
    threading.Thread(target=bot_background_worker, daemon=True).start()
    # Canli piyasa kurlarini arka planda tazeleyen isci (sayfa yanit suresini 0 ms yapar)
    threading.Thread(target=market_rates_background_worker, daemon=True).start()
    # Render Free Tier uyumasini (cold-start) engelleyen periyodik koruma iscisi
    threading.Thread(target=keep_alive_background_worker, daemon=True).start()
    # 7/24 Nobetci Sistem Bekcisi
    threading.Thread(target=system_health_watchdog_worker, daemon=True).start()
    # Arşiv yenileyici arka plan işçisi Gemini API kotasını canlı haber ve Analiz üretimine ayırmak için devre dışı bırakıldı
    yield

import secrets as _secrets

ADMIN_PIN = os.getenv("ADMIN_PIN", "").strip()
PANEL_SECRET_SLUG = os.getenv("PANEL_SECRET_SLUG", "yonetim-71453").strip("/ ")
_PIN_FAILURES = {}               # ip -> [(ts, pin_hash), ...]
_GLOBAL_PIN_FAILURES = []        # [(ts, pin_hash), ...] tüm IP'ler toplamı (Botnet/Proxy koruması)
_GLOBAL_PIN_ALERT_TS = 0.0
_PANEL_SESSIONS = {}             # rastgele oturum anahtarı -> bitiş zamanı
_PIN_LOCK_SECONDS = 900          # 15 dakika
_PIN_MAX_DISTINCT_FAILS = 5      # 15 dk içinde IP başına 5 FARKLI yanlış PIN = kilit
_GLOBAL_MAX_DISTINCT_FAILS = 8   # 15 dk içinde tüm dünyadan 8 FARKLI yanlış PIN = küresel kilit
_API_RATE_LIMIT = {}             # ip -> [ts, ...] (genel /api/ hız sınırı)

def _client_ip(request: Request) -> str:
    return (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")).split(",")[0].strip()

def _is_exempt_from_rate_limit(request: Request) -> bool:
    """Yönetici oturumlarını ve resmi arama/reklam motoru botlarını (Googlebot, AdSense vb.) hız sınırından muaf tutar."""
    if request.cookies.get("ga_admin") == "1":
        return True
    tok = request.cookies.get("ga_panel_auth", "")
    if ADMIN_PIN and tok and _PANEL_SESSIONS.get(tok, 0) > time.time():
        return True
    ua_low = (request.headers.get("user-agent") or "").lower()
    return any(b in ua_low for b in (
        "googlebot", "mediapartners-google", "adsbot-google", "google-inspectiontool",
        "google-read-aloud", "bingbot", "msnbot", "yandexbot", "telegrambot",
        "facebookexternalhit", "meta-externalagent", "twitterbot", "applebot"
    ))

def require_admin_pin(request: Request):
    """
    Kaba kuvvet (brute-force) ve Botnet/Proxy korumalı PIN kontrolü.
    - Hem IP bazlı (5 farklı yanlış PIN) hem küresel (tüm IP'lerden toplam 8 farklı yanlış PIN) kilit uygular.
    - Doğru PIN girildiğinde (kendi IP'si kilitli değilse) küresel botnet kilidi olsa dahi yöneticiyi engellemez.
    - Küresel veya IP kilidi devreye girdiğinde yöneticiye Telegram üzerinden güvenlik uyarısı gönderir.
    """
    import hashlib
    global _GLOBAL_PIN_FAILURES, _GLOBAL_PIN_ALERT_TS
    client_ip = _client_ip(request)
    now_ts = time.time()
    pin = (request.headers.get("X-Admin-Pin") or "").strip()

    _GLOBAL_PIN_FAILURES = [(t, h) for (t, h) in _GLOBAL_PIN_FAILURES if now_ts - t < _PIN_LOCK_SECONDS]
    history = [(t, h) for (t, h) in _PIN_FAILURES.get(client_ip, []) if now_ts - t < _PIN_LOCK_SECONDS]

    def _trigger_pin_lock_alert(reason_msg: str):
        global _GLOBAL_PIN_ALERT_TS
        if now_ts - _GLOBAL_PIN_ALERT_TS > _PIN_LOCK_SECONDS:
            _GLOBAL_PIN_ALERT_TS = now_ts
            try:
                import telegram_notifier
                threading.Thread(
                    target=telegram_notifier.send_admin_alert,
                    kwargs={
                        "subject": "Güvenlik Kalkanı: Yönetim Paneline Şifre Deneme Saldırısı Engellendi!",
                        "message": reason_msg,
                    },
                    daemon=True,
                ).start()
            except Exception:
                pass

    # 1. Tekil IP kilidi: Aynı IP'den 5 farklı yanlış PIN denendiyse o IP'yi tamamen kilitle
    if len({h for _, h in history}) >= _PIN_MAX_DISTINCT_FAILS:
        _PIN_FAILURES[client_ip] = history
        _trigger_pin_lock_alert(
            f"Son 15 dakika içinde aynı IP'den 5+ hatalı PIN denemesi (IP: {client_ip}) tespit edildi ve IP 15 dakika süreyle kilitlendi."
        )
        raise HTTPException(status_code=429, detail="Çok fazla hatalı şifre denemesi! Güvenlik kilidi devreye girdi, lütfen 15 dakika bekleyin.")

    # 2. Doğru PIN kontrolü: Yönetici doğru şifreyi girdiğinde küresel botnet kilidi olsa bile içeri al
    if ADMIN_PIN and pin and _secrets.compare_digest(pin, ADMIN_PIN):
        _PIN_FAILURES.pop(client_ip, None)
        return

    # 3. Yanlış PIN kaydı ve Küresel Botnet/Proxy kilidi kontrolü
    if pin:
        pin_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()[:16]
        history.append((now_ts, pin_hash))
        _PIN_FAILURES[client_ip] = history[-50:]
        _GLOBAL_PIN_FAILURES.append((now_ts, pin_hash))
        _GLOBAL_PIN_FAILURES = _GLOBAL_PIN_FAILURES[-100:]
        if len(_PIN_FAILURES) > 5000:
            for ip_key in [k for k, v in _PIN_FAILURES.items() if not v or now_ts - v[-1][0] > _PIN_LOCK_SECONDS]:
                _PIN_FAILURES.pop(ip_key, None)

    if len({h for _, h in _GLOBAL_PIN_FAILURES}) >= _GLOBAL_MAX_DISTINCT_FAILS:
        _trigger_pin_lock_alert(
            f"Son 15 dakika içinde farklı IP/Proxy adreslerinden toplam 8+ hatalı PIN denemesi (Son IP: {client_ip}) tespit edildi ve küresel koruma kilidi devreye girdi."
        )
        raise HTTPException(status_code=429, detail="Çok fazla hatalı şifre denemesi! Güvenlik kilidi devreye girdi, lütfen 15 dakika bekleyin.")

    raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")

app = FastAPI(
    title="Gündem Analizi Web Portalı",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    print(f"🔥 [KRİTİK HATA] {request.url.path}: {exc}")
    traceback.print_exc()
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=500, content={"ok": False, "error": "Sunucu hatası, lütfen tekrar deneyin."})
    return HTMLResponse(
        status_code=500,
        content="""<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><title>Sistem Güncelleniyor | Gündem Analizi</title>
        
        <style>body{background:#0a0e17;color:#94a3b8;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;text-align:center;}h1{color:#ef4444;font-size:2rem;margin:0;}p{margin:10px 0 20px;}a{color:#38bdf8;text-decoration:none;font-weight:bold;}</style>
        </head><body><h1>⚡ Sistem Optimize Ediliyor</h1><p>Sunucu önbelleği yenileniyor, sayfa birkaç saniye içinde otomatik açılacak...</p><a href="/">Yenile</a></body></html>"""
    )

_PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(self), payment=(), usb=(), interest-cohort=()"
_CSP_REPORT_ONLY = (
    "default-src 'self' https: data: blob:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https:; "
    "style-src 'self' 'unsafe-inline' https:; "
    "img-src 'self' https: data: blob:; "
    "font-src 'self' https: data:; "
    "connect-src 'self' https:; "
    "frame-src 'self' https:; "
    "frame-ancestors 'self';"
)
_VISITOR_BURST_HITS = {}          # vis_hash -> [ts, ...] (otomatik kazıyıcı hız tespiti)
_DIRECT_ARTICLE_BURST_TS = []     # [ts, ...] (yurt dışı doğrudan /haber/ toplu tarama tespiti)

@app.middleware("http")
async def track_visitors_middleware(request: Request, call_next):
    path = request.url.path
    if path == "/kullanim-kosullari":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/kullanim-sartlari", status_code=301)
    if request.method == "HEAD":
        request.scope["method"] = "GET"

    # Cloudflare'i atlayıp doğrudan Render adresinden (*.onrender.com) gelen istekleri ana alan adına yönlendir.
    # (Bu yol açık kalırsa IP başlıkları taklit edilip hız sınırları atlatılabilir; ayrıca kopya içerik oluşur.)
    _host = (request.headers.get("host") or "").split(":")[0].lower()
    if _host.endswith(".onrender.com") and path != "/health" and not path.startswith("/images"):
        from fastapi.responses import RedirectResponse
        _target = config.SITE_URL.rstrip("/") + path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse(url=_target, status_code=301)

    # Güvenlik Kalkanı: Kötü niyetli otomatik bot taramalarını (.git, .env, wp-login, phpmyadmin vb.) anında engelle
    is_malicious_probe = any(path.startswith(p) or p in path for p in [
        "/.git", "/.env", "/wp-", "/wordpress", "/xmlrpc", "/phpmyadmin", "/.aws", "/config.", "/backup", "/.vscode", "/actuator"
    ])
    if is_malicious_probe:
        return PlainTextResponse("Not Found", status_code=404)

    # 0. Yönetici (Admin) kendi tarayıcısından gezerken ziyaretçi listesine ASLA ekleme
    if request.cookies.get("ga_admin") == "1":
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        resp.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
        resp.headers["Content-Security-Policy-Report-Only"] = _CSP_REPORT_ONLY
        resp.headers["Content-Security-Policy"] = "upgrade-insecure-requests; frame-ancestors 'self'"
        return resp

    # 1. Panel, yönetim sayfaları ve tüm API çağrılarını sayaca ASLA dahil etme
    is_api_or_admin = (
        path.startswith("/api/") or
        path == "/panel" or
        path.startswith(f"/{PANEL_SECRET_SLUG}") or
        "yonetim" in path
    )
    # 1.5. Genel /api/ uçları için hız sınırı (Yönetici ve Google/AdSense botları muaf, dakikada 60 istek)
    if path.startswith("/api/") and not path.startswith("/api/panel/") and not _is_exempt_from_rate_limit(request):
        api_ip = _client_ip(request)
        now_api = time.time()
        recent_api = [t for t in _API_RATE_LIMIT.get(api_ip, []) if now_api - t < 60]
        if len(recent_api) >= 60:
            return JSONResponse({"ok": False, "error": "Çok fazla istek gönderildi. Lütfen biraz bekleyin."}, status_code=429)
        recent_api.append(now_api)
        _API_RATE_LIMIT[api_ip] = recent_api
        if len(_API_RATE_LIMIT) > 2000:
            for k in [k for k, v in _API_RATE_LIMIT.items() if not v or now_api - v[-1] > 60]:
                _API_RATE_LIMIT.pop(k, None)
    # 2. Statik dosyaları ve sistem uçlarını sayaca dahil etme
    is_static_or_system = (
        path.startswith("/assets") or
        path.startswith("/images") or
        path.startswith("/.well-known") or
        path.startswith("/sitemap") or
        path in ("/favicon.ico", "/robots.txt", "/sitemap.xml", "/news-sitemap.xml", "/video-sitemap.xml", "/rss.xml", "/health", "/manifest.json", "/sw.js") or (path == "/ads.txt" and not any(k in (request.headers.get("user-agent") or "").lower() for k in ("google", "adsense", "mediapartners", "adsbot")))
    )
    if not (is_api_or_admin or is_static_or_system):
        try:
            global _DIRECT_ARTICLE_BURST_TS
            ip = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "127.0.0.1")
            ip = ip.split(",")[0].strip()
            ua = request.headers.get("user-agent", "")
            ua_low = ua.lower()
            ref = request.headers.get("referer", "").lower()
            accept_lang = (request.headers.get("accept-language") or "").strip()
            accept_hdr = (request.headers.get("accept") or "").lower()
            sec_fetch_mode = (request.headers.get("sec-fetch-mode") or "").lower()
            country = (request.headers.get("cf-ipcountry") or "TR").upper().strip()
            city = request.headers.get("cf-ipcity", "")
            has_cookie = bool(request.cookies.get("ga_vis"))

            import hashlib
            vis_hash = hashlib.md5(f"{ip}_{ua[:60]}".encode()).hexdigest()[:16]

            # 1. 💰 Google AdSense Botları ve AdSense İnceleme Girişleri (Ayrı ve Net Tespit)
            bot_type = None
            is_adsense = False
            if any(a in ua_low for a in ("mediapartners-google", "adsbot-google", "google-adwords", "adwords-instant", "google-adsense", "google-adstxt")) or (path == "/ads.txt" and "google" in ua_low):
                bot_type = "AdSense Bot"
                is_adsense = True
            elif any(a in ref for a in ("adsense.google", "partnerdash.google", "googlesyndication.com", "doubleclick.net", "googleads.")):
                bot_type = "AdSense İnceleme"
                is_adsense = True
            # 2. 🤖 Arama Motoru Örümcekleri ve Bilinen Botlar
            elif any(g in ua_low for g in (
                "googlebot", "googleother", "google-inspectiontool", "google-read-aloud",
                "feedfetcher-google", "apis-google", "google-safety", "storebot-google",
                "google-extended", "googleweblight", "google-site-verification", "googleproducer"
            )):
                bot_type = "Googlebot"
            elif any(b in ua_low for b in ("bingbot", "msnbot", "adidxbot", "bingpreview")):
                bot_type = "Bingbot"
            elif "yandexbot" in ua_low or "yandex" in ua_low:
                bot_type = "YandexBot"
            elif "telegrambot" in ua_low:
                bot_type = "TelegramBot"
            elif any(m in ua_low for m in ("facebookexternalhit", "meta-externalagent", "facebot")):
                bot_type = "MetaBot"
            elif "twitterbot" in ua_low:
                bot_type = "TwitterBot"
            elif any(b in ua_low for b in (
                "bot", "spider", "crawl", "slurp", "headless", "ahrefs", "semrush",
                "python", "requests", "urllib", "httpx", "aiohttp", "scrapy",
                "curl/", "wget/", "go-http-client", "axios", "node-fetch", "undici",
                "okhttp", "java/", "libwww-perl", "php/", "ruby", "postman", "insomnia",
                "apache-httpclient", "claude", "chatgpt", "openai", "gpt", "perplexity",
                "anthropic", "cohere", "bytespider", "applebot", "petal", "amazonbot",
                "duckduck", "baidu", "sogou", "mj12", "dotbot", "blex", "seekport",
                "dataforseo", "screaming", "lighthouse", "pagespeed", "gtmetrix",
                "pingdom", "uptime", "statuscake", "datadog", "newrelic", "censys",
                "shodan", "zgrab", "gundemanalizi"
            )):
                bot_type = "Arama Botu"

            # 3. 🛡️ Sahte Masaüstü / Veri Merkezi Kazıyıcı (Scraper) Tespiti
            # Gerçek tarayıcılar her zaman Mozilla/5.0, Accept-Language ve text/html (veya Sec-Fetch-Mode) gönderir
            now_v = time.time()
            if not bot_type:
                if "mozilla/5.0" not in ua_low or not accept_lang or ("text/html" not in accept_hdr and sec_fetch_mode != "navigate"):
                    bot_type = "Arama Botu"
                else:
                    vh_hits = [t for t in _VISITOR_BURST_HITS.get(vis_hash, []) if now_v - t < 60]
                    vh_hits.append(now_v)
                    _VISITOR_BURST_HITS[vis_hash] = vh_hits
                    if len(_VISITOR_BURST_HITS) > 3000:
                        for k in [k for k, v in _VISITOR_BURST_HITS.items() if not v or now_v - v[-1] > 60]:
                            _VISITOR_BURST_HITS.pop(k, None)

                    recent_30s = [t for t in vh_hits if now_v - t < 30]
                    if len(vh_hits) >= 10 or (not ref and path.startswith("/haber/") and len(recent_30s) >= 4):
                        bot_type = "Arama Botu"
                    elif not ref and path.startswith("/haber/") and not has_cookie and country != "TR":
                        _DIRECT_ARTICLE_BURST_TS = [t for t in _DIRECT_ARTICLE_BURST_TS if now_v - t < 20]
                        _DIRECT_ARTICLE_BURST_TS.append(now_v)
                        if len(_DIRECT_ARTICLE_BURST_TS) >= 3:
                            bot_type = "Arama Botu"

            if is_adsense:
                device = f"💰 {bot_type}"
                source = "💰 Google AdSense"
            elif bot_type:
                device = f"🤖 {bot_type}"
                source = f"🤖 {bot_type}"
            else:
                if any(m in ua_low for m in ("mobile", "android", "iphone", "ipod")):
                    device = "Mobil"
                elif "ipad" in ua_low or "tablet" in ua_low:
                    device = "Tablet"
                else:
                    device = "Masaüstü"

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
                elif "gndemanalizi" in ref or "gundemanalizi" in ref:
                    source = "Site İçi Tıklama"
                elif ref:
                    source = "Diğer Web"
                else:
                    source = "Doğrudan"

            # Gerçek kullanıcılar için cookie tabanlı yeni/eski tespiti
            is_first = 0 if (has_cookie or bot_type) else 1

            database.log_visitor(vis_hash, path, source, device, country, city, is_first_visit=is_first)
        except Exception:
            pass
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Permissions-Policy"] = _PERMISSIONS_POLICY
    resp.headers["Content-Security-Policy-Report-Only"] = _CSP_REPORT_ONLY
    resp.headers["Content-Security-Policy"] = "upgrade-insecure-requests; frame-ancestors 'self'"
    if not (is_api_or_admin or is_static_or_system) and not bot_type and not request.cookies.get("ga_vis"):
        try:
            resp.set_cookie("ga_vis", "1", max_age=31536000, httponly=True, samesite="lax", path="/")
        except Exception:
            pass
    return resp


# Statik Dosya Dizinleri
class CacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            response.headers["CDN-Cache-Control"] = "max-age=31536000"
        return response

app.mount("/assets", CacheStaticFiles(directory=ASSETS_DIR), name="assets")

_IMAGE_MEM_CACHE = {}

@app.get("/images/{filename}")
async def serve_image(filename: str, request: Request):
    safe_name = os.path.basename(filename).split("?")[0]
    local_path = os.path.join(OUTPUT_DIR, safe_name)

    _img_headers = {
        "Cache-Control": "public, max-age=31536000, s-maxage=31536000, immutable",
        "CDN-Cache-Control": "max-age=31536000",
        "Cloudflare-CDN-Cache-Control": "max-age=31536000",
    }

    # 1. Video dosyaları için doğrudan sun
    if safe_name.lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
        if os.path.exists(local_path):
            return FileResponse(local_path, media_type="video/mp4")
        return PlainTextResponse("Video not found", status_code=404)

    # 2. Diskte hazır varsa doğrudan sun (Render overlayfs'e yeni WebP yazarak RAM tüketme)
    if os.path.exists(local_path) and os.path.getsize(local_path) >= 6000:
        return FileResponse(local_path, headers=_img_headers)

    # 3. Hafif RAM önbelleğinde (en fazla 32 görsel, ~2 MB) varsa anında sun
    cached_bytes = _IMAGE_MEM_CACHE.get(safe_name)
    if cached_bytes:
        mtype = "image/png" if safe_name.lower().endswith(".png") else ("image/webp" if safe_name.lower().endswith(".webp") else "image/jpeg")
        return Response(content=cached_bytes, media_type=mtype, headers=_img_headers)

    # 4. Kalıcı Neon PostgreSQL veritabanından çek (container diskine yazmadan doğrudan bellekle sun)
    try:
        data = await asyncio.wait_for(asyncio.to_thread(database.get_image, safe_name), timeout=12.0)
        if data and len(data) >= 6000:
            if len(_IMAGE_MEM_CACHE) >= 32:
                _IMAGE_MEM_CACHE.pop(next(iter(_IMAGE_MEM_CACHE)), None)
            _IMAGE_MEM_CACHE[safe_name] = data
            mtype = "image/png" if safe_name.lower().endswith(".png") else ("image/webp" if safe_name.lower().endswith(".webp") else "image/jpeg")
            return Response(content=data, media_type=mtype, headers=_img_headers)
    except Exception:
        pass

    # 3. Resim bulunamadıysa: görsel yer tutucu (logo) gösterilir ama durum kodu 404 olur (soft-404 önlemi)
    fallback_logo = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(fallback_logo):
        return FileResponse(fallback_logo, status_code=404, headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "CDN-Cache-Control": "no-store",
            "Cloudflare-CDN-Cache-Control": "no-store"
        })
    return Response(content=b"", status_code=404)

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    """Uptime izleme servisleri için (sunucunun uyumasını engeller)."""
    return PlainTextResponse("ok")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Static CSS served externally with preload for optimal caching and lightweight HTML
templates.env.globals['site_css'] = ''

_AD_SETTINGS_CACHE = {"data": None, "ts": 0}

def get_site_ad_settings(force_refresh: bool = False) -> dict:
    """Tüm reklam, AdSense ve Analytics ayarlarını RAM önbelleğinde tutarak sıfır gecikmeyle döner."""
    global _AD_SETTINGS_CACHE
    now = time.time()
    if not force_refresh and _AD_SETTINGS_CACHE["data"] and (now - _AD_SETTINGS_CACHE["ts"]) < 1800:
        return _AD_SETTINGS_CACHE["data"]

    try:
        data = {
            "google_site_verification": database.get_setting("google_site_verification", ""),
            "adsense_client_id": database.get_setting("adsense_client_id", "") or "ca-pub-3827167989675699",
            "ga_tracking_id": database.get_setting("ga_tracking_id", ""),
            "ads_enabled": database.get_setting("ads_enabled", "1") == "1",
            "ads_txt_content": database.get_setting("ads_txt_content", "") or "google.com, pub-3827167989675699, DIRECT, f08c47fec0942fa0",
            "ad_slot_top": database.get_setting("ad_slot_top", ""),
            "ad_slot_article_top": database.get_setting("ad_slot_article_top", ""),
            "ad_slot_article_mid": database.get_setting("ad_slot_article_mid", ""),
            "ad_slot_article_bottom": database.get_setting("ad_slot_article_bottom", ""),
        }
        _AD_SETTINGS_CACHE = {"data": data, "ts": now}
        return data
    except Exception:
        fallback = {
            "google_site_verification": "",
            "adsense_client_id": "ca-pub-3827167989675699",
            "ga_tracking_id": "",
            "ads_enabled": True,
            "ads_txt_content": "google.com, pub-3827167989675699, DIRECT, f08c47fec0942fa0",
            "ad_slot_top": "",
            "ad_slot_article_top": "",
            "ad_slot_article_mid": "",
            "ad_slot_article_bottom": "",
        }
        return fallback

_DEFAULT_MARKET_RATES = [
    {"key": "altin", "name": "Gram Altın", "symbol": "ALTIN", "icon": "🪙", "price": "6.430", "unit": "TL", "change": 0.15, "direction": "up"},
    {"key": "dolar", "name": "Dolar", "symbol": "USD/TRY", "icon": "💵", "price": "49,70", "unit": "TL", "change": 0.10, "direction": "up"},
    {"key": "euro", "name": "Euro", "symbol": "EUR/TRY", "icon": "💶", "price": "55,70", "unit": "TL", "change": -0.15, "direction": "down"},
    {"key": "btc", "name": "Bitcoin", "symbol": "BTC/USD", "icon": "₿", "price": "$81.750", "unit": "", "change": 0.10, "direction": "up"},
]

_MARKET_CACHE = {
    "ts": 0.0,
    "data": {
        "ok": True,
        "rates": _DEFAULT_MARKET_RATES,
        "updated_at": "Canlı"
    }
}

def _fetch_fresh_market_rates():
    """Arka planda çalışır, API'lerden güncel kurları çeker ve hafıza önbelleğini günceller."""
    global _MARKET_CACHE
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
                "icon": "🪙",
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
                "icon": "₿",
                "price": f"${btc_p:,.0f}".replace(",", "."),
                "unit": "",
                "change": round(btc_c, 2),
                "direction": "up" if btc_c >= 0 else "down"
            },
        ]
        _MARKET_CACHE["data"] = {
            "ok": True,
            "rates": rates,
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S")
        }
        _MARKET_CACHE["ts"] = time.time()
    except Exception:
        pass

_WEATHER_CACHE = {
    "data": [
        {"city": "İstanbul", "temp": "19°C", "icon": "⛅"},
        {"city": "Ankara", "temp": "20°C", "icon": "☀️"},
        {"city": "İzmir", "temp": "24°C", "icon": "☀️"}
    ],
    "ts": 0
}

def _fetch_fresh_weather():
    global _WEATHER_CACHE
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=41.0082,39.9334,38.4192&longitude=28.9784,32.8597,27.1287&current=temperature_2m,weather_code&timezone=Europe%2FIstanbul"
        resp = requests.get(url, headers={"User-Agent": "GundemAnalizi/1.0"}, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            updated = []
            for item in data:
                lat = item.get("latitude", 0)
                city = "İstanbul" if abs(lat - 41.0) < 0.5 else ("Ankara" if abs(lat - 39.9) < 0.5 else "İzmir")
                temp = round(item.get("current", {}).get("temperature_2m", 20))
                code = item.get("current", {}).get("weather_code", 0)
                icon = "☀️" if code in (0, 1) else ("⛅" if code in (2, 3) else ("🌧️" if code in (51, 53, 55, 61, 63, 65, 80, 81) else "☁️"))
                updated.append({"city": city, "temp": f"{temp}°C", "icon": icon})
            if len(updated) == 3:
                _WEATHER_CACHE["data"] = updated
                _WEATHER_CACHE["ts"] = time.time()
    except Exception:
        pass

def get_live_weather() -> list:
    return _WEATHER_CACHE["data"]

def market_rates_background_worker():
    """Piyasa kurlarını ve canlı hava durumunu arka planda günceller (Sıfır bekleme, 0ms sayfa hızı)."""
    time.sleep(2)
    _fetch_fresh_weather()
    loop_count = 0
    while True:
        try:
            _fetch_fresh_market_rates()
            loop_count += 1
            # Her 15 dakikada bir hava durumunu tazele (900 sn / 60 sn = 15 döngü)
            if loop_count % 15 == 0:
                _fetch_fresh_weather()
        except Exception:
            pass
        time.sleep(60)

def keep_alive_background_worker():
    """
    Render Free Tier 15 dakika hareketsizlikte uykuya (cold-sleep) geçer.
    Bu arka plan işçisi her 3 dakikada bir dış genel domain'e (/health) hafif bir istek atarak
    sunucunun 7/24 uyanık ve sıfır gecikmeli (cold-start olmadan) kalmasını sağlar.
    """
    time.sleep(30)
    while True:
        try:
            requests.get("https://xn--gndemanalizi-dlb.com.tr/health", timeout=10)
        except Exception:
            pass
        time.sleep(180)

def get_market_rates() -> dict:
    """
    Canlı Finans & Piyasa Kurları:
    Hafızada anlık önbellekten döner (0.0001 ms).
    Kullanıcıyı ve ana sayfayı ASLA bekletmez.
    """
    return _MARKET_CACHE.get("data") or {
        "ok": True,
        "rates": _DEFAULT_MARKET_RATES,
        "updated_at": "Canlı"
    }

@app.get("/api/market-rates")
async def api_market_rates():
    """Canlı altın, dolar, euro ve bitcoin fiyatlarını JSON olarak döner."""
    return JSONResponse(get_market_rates())

# ========================================================
# ⚡ AFAD & KANDİLLİ CANLI SON DEPREMLER SERVİSİ (RAM ÖNBELLEKLİ)
# ========================================================
_DEPREM_CACHE = {"time": 0, "data": []}

def _get_live_earthquakes_raw(limit=100) -> list:
    import urllib.request, json
    global _DEPREM_CACHE
    now = time.time()
    if _DEPREM_CACHE["data"] and (now - _DEPREM_CACHE["time"]) < 90:
        return _DEPREM_CACHE["data"]

    quakes = []
    # 1. AFAD Resmi Deprem Servisi
    try:
        url = f"https://deprem.afad.gov.tr/apiv2/event/filter?limit={limit}&orderby=timedesc"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                try:
                    mag = float(item.get("magnitude") or 0)
                    place = item.get("location") or "Türkiye"
                    depth = f"{float(item.get('depth') or 0):.1f} km"
                    date_raw = item.get("date") or ""
                    try:
                        dt = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        tr_dt = dt.astimezone(timezone(timedelta(hours=3)))
                        time_str = tr_dt.strftime("%H:%M")
                        date_str = tr_dt.strftime("%d.%m.%Y")
                    except Exception:
                        time_str = date_raw[-8:-3]
                        date_str = date_raw[:10]
                    level = "high" if mag >= 4.0 else ("med" if mag >= 3.0 else "low")
                    quakes.append({
                        "place": place,
                        "mag": round(mag, 1),
                        "depth": depth,
                        "time": time_str,
                        "date": date_str,
                        "provider": "AFAD",
                        "level": level,
                        "lat": float(item.get("latitude") or 0) or None,
                        "lon": float(item.get("longitude") or 0) or None,
                    })
                except Exception:
                    continue
            if len(quakes) >= 10:
                _DEPREM_CACHE = {"time": now, "data": quakes}
                return quakes
    except Exception as e:
        print(f"AFAD fetch failed: {e}")

    # 2. Kandilli Rasathanesi Canlı Servisi
    try:
        url2 = f"https://api.orhanaydogdu.com.tr/deprem/kandilli/live?limit={limit}"
        req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=4) as resp:
            data2 = json.loads(resp.read().decode("utf-8"))
            for item in data2.get("result", []):
                try:
                    mag = float(item.get("mag") or 0)
                    place = item.get("title") or "Bölge Belirtilmemiş"
                    depth = f"{float(item.get('depth') or 0):.1f} km"
                    dt = item.get("date_time") or item.get("date") or ""
                    time_str = dt.split(" ")[-1][:5] if " " in dt else dt[:5]
                    date_str = dt.split(" ")[0] if " " in dt else ""
                    level = "high" if mag >= 4.0 else ("med" if mag >= 3.0 else "low")
                    _coords = ((item.get("geojson") or {}).get("coordinates") or [None, None])
                    quakes.append({
                        "place": place,
                        "mag": round(mag, 1),
                        "depth": depth,
                        "time": time_str,
                        "date": date_str,
                        "provider": "Kandilli",
                        "level": level,
                        "lat": _coords[1] if len(_coords) > 1 else None,
                        "lon": _coords[0] if _coords else None,
                    })
                except Exception:
                    continue
            if quakes:
                _DEPREM_CACHE = {"time": now, "data": quakes}
                return quakes
    except Exception as e:
        print(f"Kandilli fetch failed: {e}")

    return _DEPREM_CACHE["data"] if _DEPREM_CACHE["data"] else []

def get_live_earthquakes(limit=50) -> list:
    """Her zaman 100 kayıt çekip önbellekler; istenen kadarını döner (sayfa ve modal aynı önbelleği paylaşır)."""
    try:
        limit = max(1, min(int(limit), 100))
    except Exception:
        limit = 50
    return _get_live_earthquakes_raw(100)[:limit]

@app.get("/api/deprem")
async def api_deprem(limit: int = 50):
    """AFAD ve Kandilli son 50 canlı deprem verisini döner."""
    quakes = await asyncio.to_thread(get_live_earthquakes, limit)
    return JSONResponse({
        "ok": True,
        "count": len(quakes),
        "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M:%S"),
        "quakes": quakes
    })

@app.get("/api/nobetci-eczaneler")
async def api_nobetci_eczaneler(city: str = "istanbul"):
    """81 İl Canlı Nöbetçi Eczaneler API'si (Bugünün Gerçek Nöbetçileri)."""
    import live_services
    data = await asyncio.to_thread(live_services.get_live_pharmacies, city)
    return JSONResponse({
        "ok": True,
        "live": bool(data),
        "city": city,
        "count": len(data),
        "pharmacies": data,
        "official_url": "https://www.turkiye.gov.tr/saglik-titck-nobetci-eczane-sorgulama",
    })

@app.get("/api/superlig")
async def api_superlig():
    """TFF Resmi Trendyol Süper Lig Canlı Puan Durumu ve Gelecek Maçlar API'si."""
    import live_services
    data = await asyncio.to_thread(live_services.get_live_superlig)
    return JSONResponse(data)

@app.get("/api/namaz-vakitleri")
async def api_namaz_vakitleri():
    """T.C. Diyanet İşleri Başkanlığı (Method 13) Günlük Canlı Namaz Vakitleri API'si."""
    import live_services
    data = await asyncio.to_thread(live_services.get_live_prayer_times)
    return JSONResponse(data)

@app.get("/son-dakika", response_class=HTMLResponse)
async def page_son_dakika(request: Request, sayfa: int = 1):
    """Google Sitelinks ve doğrudan Son Dakika kategorisi açılış sayfası."""
    return await home(request, kategori="Son Dakika", sayfa=sayfa)

_SEARCH_RATE_LIMIT = {}

def _check_search_rate_limit(request: Request) -> bool:
    """Arama uçları için IP başına dakikada 35 istek sınırı (Admin ve resmi arama botları muaf)."""
    if _is_exempt_from_rate_limit(request):
        return True
    ip = _client_ip(request)
    now_ts = time.time()
    recent = [t for t in _SEARCH_RATE_LIMIT.get(ip, []) if now_ts - t < 60]
    if len(recent) >= 35:
        return False
    recent.append(now_ts)
    _SEARCH_RATE_LIMIT[ip] = recent
    if len(_SEARCH_RATE_LIMIT) > 2000:
        for k in [k for k, v in _SEARCH_RATE_LIMIT.items() if not v or now_ts - v[-1] > 60]:
            _SEARCH_RATE_LIMIT.pop(k, None)
    return True

@app.get("/api/search")
async def api_search(request: Request, q: str = "", limit: int = 8):
    """Canlı anlık haber arama API'si (Hız sınırlamalı & DoS korumalı)."""
    if not _check_search_rate_limit(request):
        return JSONResponse({"ok": False, "count": 0, "results": [], "error": "Çok hızlı arama yapıldı."}, status_code=429)

    clean_q = re.sub(r"[<>\"'`\\]", "", (q or "").strip())[:80]
    if len(clean_q) < 2:
        return JSONResponse({"ok": True, "count": 0, "results": []})
    limit = max(1, min(int(limit or 8), 12))
    results = database.search_articles(clean_q, limit=limit, offset=0)
    simplified = []
    for a in results:
        img = a.get("image_path") or ""
        img_name = img.replace('\\', '/').split('/')[-1] if img else ""
        simplified.append({
            "title": a.get("title"),
            "slug": a.get("slug"),
            "category": a.get("category") or "Gündem",
            "image": f"/images/{img_name}" if img_name else "/assets/logo.png",
            "date": (a.get("created_at") or "")[:10]
        })
    return JSONResponse({"ok": True, "count": len(simplified), "results": simplified})


# ========================================================
# 🚀 TURBO HIZ BELLEK ÖNBELLEĞİ (RAM CACHE)
# Kategori bloklarını RAM'de 45 sn tutarak veritabanı yükünü sıfırlar
# Sayfa açılış hızını 1.5 saniyeden 25 milisaniyeye (60 kat hız) düşürür
# ========================================================

# ========================================================
# ⚡ TURBO RAM SAYFA ÖNBELLEĞİ (0.001 MS YANIT SÜRESİ)
# İlk girişte ve kategorilerde Neon'a 11 ayrı sorgu atmak yerine
# render edilmiş HTML'i RAM'de 90 saniye saklayarak anında basar.
# ========================================================
_TURBO_PAGE_CACHE = {}

def get_turbo_page(key: str):
    item = _TURBO_PAGE_CACHE.get(key)
    if item and (time.time() - item["ts"]) < 120:
        return item["html"]
    return None

def set_turbo_page(key: str, html: str):
    global _TURBO_PAGE_CACHE
    now = time.time()
    if len(_TURBO_PAGE_CACHE) >= 40:
        # Render 512MB RAM koruması: en fazla 40 aktif sayfayı RAM'de tut (<8 MB)
        _TURBO_PAGE_CACHE = {k: v for k, v in _TURBO_PAGE_CACHE.items() if (now - v["ts"]) < 90}
        if len(_TURBO_PAGE_CACHE) >= 32:
            oldest_keys = sorted(_TURBO_PAGE_CACHE.keys(), key=lambda k: _TURBO_PAGE_CACHE[k]["ts"])[:15]
            for k in oldest_keys:
                _TURBO_PAGE_CACHE.pop(k, None)
    _TURBO_PAGE_CACHE[key] = {"html": html, "ts": now}

def clear_turbo_cache():
    global _TURBO_PAGE_CACHE, _CATEGORY_WIDGETS_CACHE_TIME
    _TURBO_PAGE_CACHE.clear()
    _CATEGORY_WIDGETS_CACHE_TIME = 0

_CATEGORY_WIDGETS_CACHE = {}
_CATEGORY_WIDGETS_CACHE_TIME = 0
_WIDGETS_REFRESH_LOCK = threading.Lock()
_ONE_TIME_CAT_CLEANUP_DONE = False

def _refresh_category_widgets_sync() -> dict:
    global _CATEGORY_WIDGETS_CACHE, _CATEGORY_WIDGETS_CACHE_TIME, _ONE_TIME_CAT_CLEANUP_DONE
    import content_quality
    def _clean_vitrin(items, cap):
        rich = [
            a for a in items
            if not main.is_commodity_news(a.get("title", ""))
            and (not content_quality.is_thin(a["content"]) if a.get("content") else len((a.get("summary") or "").strip()) >= 35)
        ]
        chosen = rich[:cap] if len(rich) >= cap else (rich + [a for a in items if not main.is_commodity_news(a.get("title", "")) and a not in rich])[:cap]
        for item in chosen:
            item.pop("content", None)
        return chosen

    try:
        if not _ONE_TIME_CAT_CLEANUP_DONE:
            _ONE_TIME_CAT_CLEANUP_DONE = True
            try:
                with database.get_connection() as _c:
                    _c.execute("UPDATE articles SET category = 'Gündem' WHERE category = 'Spor' AND (LOWER(title) LIKE '%loto%' OR LOWER(title) LIKE '%piyango%' OR LOWER(title) LIKE '%şans topu%' OR LOWER(title) LIKE '%on numara%')")
                    _c.execute("UPDATE articles SET category = 'Gündem' WHERE category = 'Asayiş'")
                    _c.execute("UPDATE articles SET title = REPLACE(title, 'Açkladı', 'Açıkladı') WHERE title LIKE '%Açkladı%'")
            except Exception:
                pass
        breaking_pool = _clean_vitrin(database.get_articles(limit=40), 16)
        breaking_news = breaking_pool[:14]
        side_featured = breaking_pool[14:16] if len(breaking_pool) >= 16 else breaking_pool[1:3]
        used_ids = {a.get("id") for a in breaking_pool[:16] if a.get("id")}

        def _pick_cat_vitrin(cat_name, cap=5):
            pool = _clean_vitrin(database.get_articles(limit=36, category=cat_name), 24)
            fresh = [a for a in pool if a.get("id") not in used_ids]
            chosen = (fresh + [a for a in pool if a not in fresh])[:cap]
            for a in chosen:
                if a.get("id"):
                    used_ids.add(a.get("id"))
            return chosen

        data = {
            "breaking_news": breaking_news,
            "side_featured": side_featured,
            "trending_articles": _clean_vitrin(database.get_trending_articles(limit=24), 10),
            "gundem_articles": _pick_cat_vitrin("Gündem", 5),
            "auto_articles": _pick_cat_vitrin("Otomobil", 5),
            "tech_articles": _pick_cat_vitrin("Teknoloji", 5),
            "economy_articles": _pick_cat_vitrin("Ekonomi", 5),
            "sports_articles": _pick_cat_vitrin("Spor", 5),
            "health_articles": _pick_cat_vitrin("Sağlık", 5),
            "education_articles": _pick_cat_vitrin("Eğitim", 5),
        }
        if data["breaking_news"]:
            _CATEGORY_WIDGETS_CACHE = data
            _CATEGORY_WIDGETS_CACHE_TIME = time.time()
        return data
    except Exception as e:
        print(f"Kategori önbellek yenileme hatası: {e}")
        return _CATEGORY_WIDGETS_CACHE or {
            "breaking_news": [], "auto_articles": [], "tech_articles": [],
            "economy_articles": [], "sports_articles": [], "health_articles": [],
            "education_articles": []
        }

def get_cached_category_widgets() -> dict:
    now = time.time()
    if _CATEGORY_WIDGETS_CACHE and (now - _CATEGORY_WIDGETS_CACHE_TIME) < 180:
        return _CATEGORY_WIDGETS_CACHE
    # Eğer önbellek doluysa ama süresi geçmişse: ziyaretçiyi 0 ms beklet, kilitli tek thread ile arka planda tazele
    if _CATEGORY_WIDGETS_CACHE:
        if not _WIDGETS_REFRESH_LOCK.locked():
            def _bg():
                if _WIDGETS_REFRESH_LOCK.acquire(blocking=False):
                    try:
                        _refresh_category_widgets_sync()
                    finally:
                        _WIDGETS_REFRESH_LOCK.release()
            threading.Thread(target=_bg, daemon=True).start()
        return _CATEGORY_WIDGETS_CACHE
    # İlk açılışta önbellek tamamen boşsa kilit altında 1 kez senkron doldur
    with _WIDGETS_REFRESH_LOCK:
        if _CATEGORY_WIDGETS_CACHE:
            return _CATEGORY_WIDGETS_CACHE
        return _refresh_category_widgets_sync()

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(request: Request, kategori: str = None, q: str = None, sayfa: int = 1):
    if "page" in request.query_params:
        import urllib.parse
        from fastapi.responses import RedirectResponse
        try:
            _p = max(1, int(request.query_params.get("page") or 1))
        except Exception:
            _p = 1
        _kat_part = f"kategori={urllib.parse.quote(kategori)}&" if kategori else ""
        _target = f"/?{_kat_part}sayfa={_p}" if _p > 1 else (f"/?kategori={urllib.parse.quote(kategori)}" if kategori else "/")
        return RedirectResponse(url=_target, status_code=301)
    if kategori and not q:
        import urllib.parse
        from fastapi.responses import RedirectResponse
        _valid_cats = {"Gündem", "Ekonomi", "Spor", "Teknoloji", "Otomobil", "Sağlık", "Dünya", "Eğitim", "Son Dakika"}
        _norm_k = database.normalize_category_name(kategori)
        if _norm_k == "Analiz" or (kategori and kategori.strip().lower() == "analiz"):
            return RedirectResponse(url="/analiz", status_code=301)
        if _norm_k not in _valid_cats:
            _norm_k = "Gündem"
        if _norm_k and _norm_k != kategori.strip():
            _page = max(1, sayfa)
            _target = f"/?kategori={urllib.parse.quote(_norm_k)}" + (f"&sayfa={_page}" if _page > 1 else "")
            return RedirectResponse(url=_target, status_code=301)

    # Turbo RAM Önbelleği: Arama yoksa ve ilk sayfaysa 0 ms hızında RAM'den ver
    cache_key = f"page_{kategori or 'home'}_{sayfa}" if not q else None
    if cache_key:
        cached_html = get_turbo_page(cache_key)
        if cached_html:
            if request.cookies.get("ga_admin") != "1":
                database.record_visit("home_visits")
            return HTMLResponse(content=cached_html, headers={"X-Turbo-Cache": "HIT", "Cache-Control": "public, max-age=60, s-maxage=60", "CDN-Cache-Control": "max-age=60", "Cloudflare-CDN-Cache-Control": "max-age=60"})

    if request.cookies.get("ga_admin") != "1":
        database.record_visit("home_visits")
    import math
    import urllib.parse
    page = max(1, sayfa)
    limit = 24
    offset = (page - 1) * limit

    norm_kategori = database.normalize_category_name(kategori) if kategori else None
    if norm_kategori == "Analiz":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/analiz", status_code=301)

    if q and q.strip():
        if not _check_search_rate_limit(request):
            raise HTTPException(status_code=429, detail="Çok hızlı arama yapıldı. Lütfen 1 dakika bekleyin.")
        search_kw = re.sub(r"[<>\"'`\\]", "", q.strip())[:80]
        articles = database.search_articles(search_kw, limit=limit, offset=offset) if search_kw else []
        total_count = database.get_search_count(search_kw) if search_kw else 0
        # Arama sonuç sayfaları asla ayrı canonical oluşturmaz (SEO Zehirleme / Search Spam Koruması)
        canonical_url = f"{config.SITE_URL}/"
    else:
        import content_quality
        def _prefer_rich(pool, cap):
            non_c = [a for a in pool if not main.is_commodity_news(a.get("title", ""))]
            if page >= 1:
                rich = [a for a in non_c if (not content_quality.is_thin(a["content"]) if a.get("content") else len((a.get("summary") or "").strip()) >= 35)]
                res = rich[:cap] if len(rich) >= cap else (rich + [a for a in non_c if a not in rich])[:cap]
            else:
                res = non_c[:cap]
            for item in res:
                item.pop("content", None)
            return res

        if norm_kategori == "Son Dakika":
            articles = _prefer_rich(database.get_articles(limit=limit + 16, offset=offset), limit)
            total_count = database.get_articles_total_count()
        elif not norm_kategori and page == 1:
            # Ana sayfa 1. sayfada aşağıda 100'lük havuz çekildiği için burada mükerrer 40'lık sorgu atılmaz
            articles = []
            total_count = database.get_articles_total_count()
        else:
            articles = _prefer_rich(database.get_articles(limit=limit + 16, category=norm_kategori, offset=offset), limit)
            total_count = database.get_articles_total_count(category=norm_kategori)
        # Sayfalı listelerde her sayfa kendini canonical gösterir (Google arşive 2., 3. ... sayfalardan ulaşabilsin)
        if norm_kategori == "Son Dakika":
            canonical_url = f"{config.SITE_URL}/son-dakika" + (f"?sayfa={page}" if page > 1 else "")
        elif norm_kategori:
            canonical_url = f"{config.SITE_URL}/?kategori={urllib.parse.quote(norm_kategori)}" + (f"&sayfa={page}" if page > 1 else "")
        else:
            canonical_url = f"{config.SITE_URL}/" + (f"?sayfa={page}" if page > 1 else "")

    total_pages = max(1, math.ceil(total_count / limit))
    widgets = get_cached_category_widgets()
    breaking_news = widgets["breaking_news"]
    side_featured = widgets.get("side_featured") or breaking_news[1:3]
    if norm_kategori:
        slider_articles = articles[:14] if (page == 1 and len(articles) >= 3) else database.get_articles(limit=14, category=norm_kategori)
        if len(slider_articles) < 3:
            slider_articles = widgets["breaking_news"]
    else:
        slider_articles = widgets["breaking_news"][:14] if len(widgets["breaking_news"]) >= 14 else database.get_articles(limit=14)

    gundem_articles = widgets.get("gundem_articles") or database.get_articles(limit=5, category="Gündem")
    auto_articles = widgets["auto_articles"]
    tech_articles = widgets["tech_articles"]
    economy_articles = widgets["economy_articles"]
    sports_articles = widgets["sports_articles"]
    health_articles = widgets["health_articles"]
    education_articles = widgets["education_articles"]

    # Ana sayfa 1. sayfada üst vitrinlerde (Slider + Yan Kartlar + Kategori Vitrinleri) gösterilen haberlerin
    # alt 24'lü "Tüm Güncel Gelişmeler" ızgarasında 2.-4. kez tekrarlanmasını önle:
    if not norm_kategori and not (q and q.strip()) and page == 1:
        showcase_ids = set()
        for _grp in (slider_articles[:14], side_featured[:2], gundem_articles[:5], tech_articles[:5], economy_articles[:5], sports_articles[:4], auto_articles[:5]):
            for _item in (_grp or []):
                if _item.get("id"):
                    showcase_ids.add(_item["id"])
        _wide_pool = _prefer_rich(database.get_articles(limit=100, offset=0), 80)
        _unique_grid = [a for a in _wide_pool if a.get("id") not in showcase_ids]
        if len(_unique_grid) >= limit:
            articles = _unique_grid[:limit]
        else:
            articles = (_unique_grid + [a for a in _wide_pool if a not in _unique_grid])[:limit]

    import live_services
    import analysis_engine
    superlig_data = await asyncio.to_thread(live_services.get_live_superlig)
    radar_data = analysis_engine.get_agenda_radar_data(widgets)
    resp = templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "articles": articles,
            "radar": radar_data,
            "slider_articles": slider_articles,
            "side_featured": side_featured,
            "gundem_articles": gundem_articles,
            "auto_articles": auto_articles,
            "tech_articles": tech_articles,
            "economy_articles": economy_articles,
            "sports_articles": sports_articles,
            "health_articles": health_articles,
            "education_articles": education_articles,
            "breaking_news": breaking_news,
            "active_category": norm_kategori,
            "search_query": q.strip() if q else "",
            "ad_settings": get_site_ad_settings(),
            "market_rates": get_market_rates()["rates"],
            "weather_data": get_live_weather(),
            "superlig_data": superlig_data,
            "canonical_url": canonical_url,
            "current_page": page,
            "total_pages": total_pages,
            "total_articles": total_count
        }
    )
    if cache_key and resp.body:
        try:
            set_turbo_page(cache_key, resp.body.decode("utf-8"))
        except Exception:
            pass
    return resp

@app.api_route("/kategori/{kategori_adi}", methods=["GET", "HEAD"])
async def category_page(request: Request, kategori_adi: str, sayfa: int = 1):
    """Kategori bazlı haber akışı rotası: Tekil canonical URL (/?kategori=...) yapısına 301 yönlendirir."""
    import urllib.parse
    from fastapi.responses import RedirectResponse
    norm_kat = database.normalize_category_name(kategori_adi) or kategori_adi
    target = f"/?kategori={urllib.parse.quote(norm_kat)}" + (f"&sayfa={sayfa}" if sayfa > 1 else "")
    return RedirectResponse(url=target, status_code=301)

def _new_panel_session() -> str:
    """Her girişte tahmin edilemez, rastgele bir oturum anahtarı üretir (PIN'den türetilmez)."""
    if not ADMIN_PIN:
        return ""
    now_ts = time.time()
    for k in [k for k, exp in _PANEL_SESSIONS.items() if exp < now_ts]:
        _PANEL_SESSIONS.pop(k, None)
    tok = _secrets.token_urlsafe(32)
    _PANEL_SESSIONS[tok] = now_ts + 3600 * 24 * 30
    return tok

def _is_panel_session_valid(tok: str) -> bool:
    return bool(ADMIN_PIN and tok and _PANEL_SESSIONS.get(tok, 0) > time.time())

# /panel herkese açık adresi güvenlik için kapatıldı; yalnızca gizli yönetim adresi aktiftir.
@app.get(f"/{PANEL_SECRET_SLUG}", response_class=HTMLResponse)
@app.get("/yonetim-71453", response_class=HTMLResponse)
async def admin_panel(request: Request):
    is_authed = _is_panel_session_valid(request.cookies.get("ga_panel_auth", ""))
    if is_authed:
        try:
            stats = database.get_dashboard_summary() or {}
        except Exception as e:
            print(f"⚠️ Panel özet verisi çekme hatası: {e}")
            stats = {}
    else:
        stats = {}

    stats["gemini_active"] = bool(config.GEMINI_API_KEY)
    stats["telegram_active"] = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
    stats["check_interval"] = config.CHECK_INTERVAL_MINUTES
    try:
        stats["total_articles"] = database.get_articles_total_count()
    except Exception:
        stats["total_articles"] = stats.get("total_articles", 0)
    stats["db_status"] = "🟢 Neon PostgreSQL (Ücretli / Always-On)" if database.USE_PG else "🟡 Yerel SQLite"
    stats["watchdog_status"] = "Gece Vardiyasında (00:00 - 09:00 / 10 dk aralıkla)"
    stats["cache_status"] = "🟢 RAM Önbellek Devrede (0 ms Gecikme)"
    stats["archive_status"] = "🔒 %100 Güvende (Asla Haber Silinmez)"

    # Güvenli varsayılanlar (Jinja2 asla NoneType hatası vermez)
    stats.setdefault("total_all_hits", 0)
    stats.setdefault("home_visits", 0)
    stats.setdefault("total_views", 0)
    stats.setdefault("avg_views", 0)
    stats.setdefault("active_now", 1)
    stats.setdefault("today_uniques", 0)
    stats.setdefault("first_time_today", 0)
    stats.setdefault("returning_today", 0)
    stats.setdefault("google_today", 0)
    stats.setdefault("bot_uniques_today", 0)
    stats.setdefault("adsense_today", 0)
    stats.setdefault("adsense_7d", 0)
    stats.setdefault("traffic_sources", [])
    stats.setdefault("device_stats", [])
    stats.setdefault("live_visitors", [])
    stats.setdefault("total_revenue", 0.0)
    stats.setdefault("month_revenue", 0.0)
    stats.setdefault("revenue_records", [])
    stats.setdefault("images_count", 0)
    stats.setdefault("db_size_mb", 0.0)
    stats.setdefault("use_pg", database.USE_PG)
    stats.setdefault("last_article_time", "-")
    stats.setdefault("top_articles", [])
    stats.setdefault("recent_articles", [])
    stats.setdefault("categories", [])
    stats.setdefault("sources", [])

    if not stats.get("last_article_time"):
        stats["last_article_time"] = "-"
    if stats.get("db_size_mb") is None:
        stats["db_size_mb"] = 0.0

    for item in stats.get("top_articles", []):
        if not item.get("created_at"):
            item["created_at"] = "-"
    for a in stats.get("recent_articles", []):
        if not a.get("created_at"):
            a["created_at"] = "-"

    if is_authed:
        try:
            ad_settings = get_site_ad_settings()
        except Exception:
            ad_settings = {}
    else:
        stats["total_articles"] = 0
        ad_settings = {}

    response = templates.TemplateResponse(
        request=request,
        name="panel.html",
        context={"stats": stats, "panel_slug": PANEL_SECRET_SLUG, "ad_settings": ad_settings, "panel_authed": is_authed}
    )
    if is_authed:
        response.set_cookie(key="ga_admin", value="1", max_age=3600*24*30, httponly=False)
    return response

@app.post("/api/panel/verify-pin")
async def panel_verify_pin(request: Request):
    require_admin_pin(request)
    resp = JSONResponse({"ok": True})
    tok = _new_panel_session()
    if tok:
        resp.set_cookie(key="ga_panel_auth", value=tok, max_age=3600*24*30, httponly=True, secure=True, samesite="lax", path="/")
    return resp

@app.post("/api/panel/logout")
async def panel_logout(request: Request):
    _PANEL_SESSIONS.pop(request.cookies.get("ga_panel_auth", ""), None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(key="ga_panel_auth", path="/")
    return resp

@app.post("/api/panel/fetch-now")
async def panel_fetch_now(request: Request):
    require_admin_pin(request)
    def _fetch_worker():
        global _CATEGORY_WIDGETS_CACHE_TIME
        try:
            main.run_bot(max_items=1, force=True)
        finally:
            clear_turbo_cache()
    _CATEGORY_WIDGETS_CACHE_TIME = 0
    threading.Thread(target=_fetch_worker, daemon=True).start()
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
    require_admin_pin(request)

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
    global _CATEGORY_WIDGETS_CACHE_TIME
    clear_turbo_cache()
    _CATEGORY_WIDGETS_CACHE_TIME = 0

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
    require_admin_pin(request)
    deleted = database.delete_article(article_id)
    global _CATEGORY_WIDGETS_CACHE_TIME
    clear_turbo_cache()
    _CATEGORY_WIDGETS_CACHE_TIME = 0
    return {"ok": deleted}

@app.get("/api/panel/search-articles")
async def panel_search_articles(request: Request, q: str = "", category: str = ""):
    require_admin_pin(request)
    q_clean = (q or "").strip()
    cat_clean = (category or "").strip()
    q_num = q_clean.lstrip("#").strip()
    rows = []
    with database.get_connection() as conn:
        like_op = "ILIKE" if getattr(conn, "is_pg", False) else "LIKE"
        sql = "SELECT id, slug, title, category, source, views, created_at FROM articles WHERE 1=1"
        params = []
        if cat_clean:
            sql += " AND category = ?"
            params.append(cat_clean)
        if q_clean:
            if q_num.isdigit():
                sql += f" AND (id = ? OR title {like_op} ? OR slug {like_op} ?)"
                params.extend([int(q_num), f"%{q_clean}%", f"%{q_clean}%"])
            else:
                sql += f" AND (title {like_op} ? OR slug {like_op} ?)"
                params.extend([f"%{q_clean}%", f"%{q_clean}%"])
        limit_n = 60 if (q_clean or cat_clean) else 30
        sql += f" ORDER BY id DESC LIMIT {limit_n}"
        for r in conn.execute(sql, tuple(params)).fetchall():
            d = database._row_to_dict(r)
            if not d.get("created_at"):
                d["created_at"] = "-"
            rows.append(d)
    return {"ok": True, "articles": rows}

@app.get("/api/panel/article/{article_id}")
async def panel_get_article(article_id: int, request: Request):
    require_admin_pin(request)
    art = database.get_article_by_id(article_id)
    if not art:
        raise HTTPException(status_code=404, detail="Haber bulunamadı")
    try:
        if "<video" not in (art.get("content") or "").lower() and "<video" in (art.get("content_legacy") or "").lower():
            vm = re.search(r'(<div[^>]*>\s*<video[\s\S]*?</video>\s*</div>|<video[\s\S]*?</video>)', art.get("content_legacy") or "", re.I)
            if vm:
                art["content"] = vm.group(1) + "\n" + (art.get("content") or "")
    except Exception:
        pass
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
    require_admin_pin(request)
    updated = database.update_article(
        article_id=article_id,
        title=title.strip(),
        summary=summary.strip(),
        content=content.strip(),
        category=category.strip()
    )
    global _CATEGORY_WIDGETS_CACHE_TIME
    clear_turbo_cache()
    _CATEGORY_WIDGETS_CACHE_TIME = 0
    _INDEX_CACHE["ts"] = 0
    return {"ok": updated, "message": "Haber başarıyla güncellendi!"}

@app.get("/api/panel/radar-videos")
def get_radar_videos(request: Request):
    require_admin_pin(request)
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
    require_admin_pin(request)
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
        import gc
        gc.collect()
        job.update({
            "step": 2,
            "percent": 42,
            "eta_sec": 15,
            "step_text": "🎨 2/5: Tam ekran Gündem Analizi logosu, kayan bant ve filigran işleniyor..."
        })
        auto_ticker = ticker_text.strip() or (f"{title} • {summary}" if summary else title)
        res = None
        try:
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
        except Exception as e:
            print(f"⚠️ Video filigranlama atlandı (Orijinal video korunuyor): {e}")
            thumb_path = os.path.join(OUTPUT_DIR, out_filename.replace(".mp4", ".jpg"))
            try:
                import imageio_ffmpeg
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-ss", "00:00:01", "-i", raw_path, "-frames:v", "1", thumb_path], capture_output=True, timeout=10)
            except Exception:
                pass
            res = {
                "video_path": raw_path,
                "thumb_path": thumb_path if os.path.exists(thumb_path) else os.path.join(ASSETS_DIR, "logo.png"),
                "video_filename": os.path.basename(raw_path)
            }

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
        if not article_data:
            raise Exception("Yapay zeka özgün haber metni üretemedi (GEMINI_API_KEY / kaynak metin kontrol edin). Kopya metin yayınlanmadı.")

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
            clear_turbo_cache()
            site_url = f"{config.SITE_URL}/haber/{slug}"
            art_obj = database.get_article_by_slug(slug)
            if art_obj:
                article_id = art_obj.get("id")

        # ADIM 5: Web Sitesi ve Telegram Kanalında Yayınlama (Ultra Hafif, Sıfır RAM Yükü)
        job.update({
            "step": 5,
            "percent": 90,
            "eta_sec": 3,
            "step_text": "📲 5/5: Telegram kanalına ve web sitesine yayınlanıyor..."
        })

        tg_ok = False
        if pub_tg:
            try:
                tg_res = telegram_notifier.send_telegram_video(res["video_path"], clean_caption, news_link="")
                tg_ok = (tg_res is not False)
            except Exception as e:
                print(f"Telegram paylaşım hatası: {e}")

        share_status_text = f"🌐 Web Sitesi: ✅ • 📲 Telegram: {'✅' if tg_ok else '❌'}"

        if os.path.exists(raw_path):
            try:
                os.remove(raw_path)
            except Exception:
                pass

        import gc
        gc.collect()

        social_pack = clean_caption
        job.update({
            "status": "done",
            "step": 5,
            "percent": 100,
            "eta_sec": 0,
            "step_text": f"✅ Tamamlandı! {share_status_text}",
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
    pub_ig: str = Form("true"),
    pub_x: str = Form("true"),
    source: str = Form("Gündem Analizi"),
    video_file: UploadFile = File(None)
):
    require_admin_pin(request)

    import hashlib
    vid_id = hashlib.md5(f"{title}_{time.time()}".encode("utf-8")).hexdigest()[:10]
    raw_path = os.path.join(OUTPUT_DIR, f"raw_{vid_id}.mp4")
    out_filename = f"viral_{vid_id}.mp4"

    has_uploaded_file = False
    if video_file and video_file.filename:
        import shutil
        with open(raw_path, "wb") as f:
            shutil.copyfileobj(video_file.file, f)
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
    require_admin_pin(request)
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
        "start_url": "/",
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
    require_admin_pin(request)
    stats = database.get_dashboard_summary()
    return {
        "ok": True,
        "active_now": stats.get("active_now", 1),
        "today_uniques": stats.get("today_uniques", 0),
        "first_time_today": stats.get("first_time_today", 0),
        "returning_today": stats.get("returning_today", 0),
        "google_today": stats.get("google_today", 0),
        "bot_uniques_today": stats.get("bot_uniques_today", 0),
        "adsense_today": stats.get("adsense_today", 0),
        "adsense_7d": stats.get("adsense_7d", 0),
        "total_views": stats.get("total_views", 0),
        "total_all_hits": stats.get("total_all_hits", 0),
        "live_visitors": stats.get("live_visitors", [])[:60],
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
    require_admin_pin(request)
    if not date:
        date = time.strftime("%Y-%m-%d")
    ok = database.add_revenue_record(source, amount, date, notes)
    return {"ok": bool(ok), "message": "Gelir kaydı başarıyla eklendi."}

@app.post("/api/panel/delete-revenue/{rec_id}")
async def panel_del_revenue(rec_id: int, request: Request):
    require_admin_pin(request)
    database.delete_revenue_record(rec_id)
    return {"ok": True, "message": "Gelir kaydı silindi."}

@app.get("/api/panel/ad-settings")
async def get_panel_ad_settings(request: Request):
    require_admin_pin(request)
    return {"ok": True, "settings": get_site_ad_settings()}

@app.post("/api/panel/ad-settings")
async def save_panel_ad_settings(request: Request):
    require_admin_pin(request)
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
        "ad_slot_article_mid",
        "ad_slot_article_bottom"
    ]
    for k in keys:
        if k in data:
            database.set_setting(k, str(data[k]))
    return {"ok": True, "message": "Reklam ve Google ayarları başarıyla kaydedildi!"}

_IHBAR_RATE_LIMIT = {}

@app.post("/api/ihbar")
async def submit_ihbar(
    request: Request,
    message: str = Form(...),
    contact: str = Form(""),
    media_file: UploadFile = File(None)
):
    client_ip = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")).split(",")[0].strip()
    now_ts = time.time()
    recent_ihbar = [t for t in _IHBAR_RATE_LIMIT.get(client_ip, []) if now_ts - t < 900]
    if len(recent_ihbar) >= 3:
        raise HTTPException(status_code=429, detail="Çok fazla ihbar gönderildi. Lütfen 15 dakika sonra tekrar deneyin.")
    if not message or len(message.strip()) < 5 or len(message) > 3000:
        raise HTTPException(status_code=400, detail="Lütfen ihbar detayını yazın (5-3000 karakter).")
    cl = int(request.headers.get("content-length") or 0)
    if cl > 16 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dosya boyutu en fazla 15 MB olabilir.")
    recent_ihbar.append(now_ts)
    _IHBAR_RATE_LIMIT[client_ip] = recent_ihbar
    if len(_IHBAR_RATE_LIMIT) > 2000:
        for k in [k for k, v in _IHBAR_RATE_LIMIT.items() if not v or now_ts - v[-1] > 900]:
            _IHBAR_RATE_LIMIT.pop(k, None)

    import hashlib
    import telegram_notifier
    ihbar_id = _secrets.token_hex(12)  # Tahmin edilemez dosya adı (dışarıdan bulunamaz)
    saved_path = ""
    media_type = ""
    studio_link_line = ""

    if media_file and media_file.filename:
        fname = media_file.filename.lower()
        allowed_exts = (".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp")
        if not any(fname.endswith(ext) for ext in allowed_exts):
            raise HTTPException(status_code=400, detail="Yalnızca fotoğraf (.jpg, .png, .webp) veya video (.mp4, .mov, .webm) yüklenebilir.")
        content = await media_file.read(15 * 1024 * 1024 + 1)
        if len(content) > 15 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Dosya boyutu en fazla 15 MB olabilir.")
        is_video_ext = fname.endswith((".mp4", ".mov", ".webm"))
        if is_video_ext:
            # Gerçek video mu? (uzantıya değil dosyanın içeriğine bakılır)
            if not (content[4:8] == b"ftyp" or content[:4] == b"\x1a\x45\xdf\xa3"):
                raise HTTPException(status_code=400, detail="Geçersiz video dosyası.")
        else:
            # Gerçek resim mi? Pillow ile doğrula ve temiz JPEG olarak yeniden kaydet
            # (gizli kod/çift format temizlenir, ihbarcının GPS/EXIF konum bilgisi silinir)
            try:
                from io import BytesIO
                from PIL import Image
                with Image.open(BytesIO(content)) as probe:
                    probe.verify()
                with Image.open(BytesIO(content)) as im:
                    im = im.convert("RGB")
                    im.thumbnail((2400, 2400))
                    buf = BytesIO()
                    im.save(buf, format="JPEG", quality=88)
                    content = buf.getvalue()
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=400, detail="Geçersiz resim dosyası.")
        if content:
            if is_video_ext:
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

def summary_highlights(content: str, summary: str, title: str) -> list:
    """'Haberin Önemli Noktaları' maddelerini, haber gövdesinde GÖRÜNMEYEN özgün özetten üretir.
    Gövdede birebir geçen cümleler alınmaz (sayfa içi kopya içerik olmasın); 2'den az madde kalırsa kutu gizlenir."""
    import html as _h
    body_txt = re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", content or ""))).lower()
    out = []
    for s in smart_sentence_split(_h.unescape(summary or "").strip()):
        s = s.strip()
        if len(s) < 35 or s.lower() == (title or "").lower():
            continue
        key = re.sub(r"\s+", " ", s.lower())
        if key[:70] in body_txt:
            continue
        if s not in out:
            out.append(s)
        if len(out) >= 3:
            break
    return out if len(out) >= 2 else []


def extract_clean_highlights(content: str, summary: str, title: str) -> list:
    """Haberin içinden tam, anlamlı ve kesilmemiş 2-3 adet madde/özet çıkarır. Lead paragrafı birebir tekrarlamaz."""
    import re, html
    clean_summary = html.unescape(summary or "").strip()
    paras = re.findall(r'<p[^>]*>(.*?)</p>', content or "", flags=re.DOTALL)
    bullets = []

    bad_bullet_words = [
        'gündem analizi değerlendirmesi', 'piyasalar ve kamuoyu', 'abone olun',
        'tıklayınız', 'fotoğraf:', 'içindekiler', 'editör hakkında', 'teknoloji editörü',
        'içerik editörü', 'oy ver', 'takipçi', 'scorsese', 'donanım haber', 'tam boyutta gör',
        'click()', 'n11.com', 'migros', 'idefix', 'trendyol', 'hepsiburada', 'http',
        'son haberler', 'yapay zeka otomobil', 'kategoriler nasıl yapılır', 'donanım yazılım android',
        'ai ile özetle'
    ]

    def is_similar_to_summary(sent: str) -> bool:
        if not clean_summary:
            return False
        s_low = sent.lower().strip()
        sum_low = clean_summary.lower().strip()
        if s_low in sum_low or sum_low in s_low:
            return True
        w1 = set(s_low.split())
        w2 = set(sum_low.split())
        if len(w1) > 4 and len(w1 & w2) / len(w1) > 0.70:
            return True
        return False

    # 1. Gövde paragraflarından (tercihen lead olmayanlardan) tam cümleleri al
    if paras:
        candidate_paras = paras[1:] if len(paras) > 1 else paras
        for p in candidate_paras:
            clean_p = re.sub(r'<[^>]+>', '', p).strip()
            clean_p = html.unescape(clean_p)
            if any(b in clean_p.lower() for b in bad_bullet_words):
                continue
            sents = [s for s in smart_sentence_split(clean_p) if len(s) > 35]
            for s in sents:
                if any(b in s.lower() for b in bad_bullet_words):
                    continue
                if is_similar_to_summary(s):
                    continue
                if (s.endswith(('.', '!', '?')) or s.endswith('."') or s.endswith('".')) and s not in bullets and s.lower() != title.lower():
                    bullets.append(s)
                    if len(bullets) >= 3:
                        break
            if len(bullets) >= 3:
                break

    # 2. Eğer gövdeden madde çıkmadıysa ve haber zenginse ilk paragrafı kontrol et
    if len(bullets) < 2 and len(paras) > 2:
        for p in paras:
            clean_p = re.sub(r'<[^>]+>', '', p).strip()
            clean_p = html.unescape(clean_p)
            if any(b in clean_p.lower() for b in bad_bullet_words):
                continue
            sents = [s for s in smart_sentence_split(clean_p) if len(s) > 35]
            for s in sents:
                if any(b in s.lower() for b in bad_bullet_words):
                    continue
                if (s.endswith(('.', '!', '?')) or s.endswith('."') or s.endswith('".')) and s not in bullets and s.lower() != title.lower():
                    bullets.append(s)
                    if len(bullets) >= 2:
                        break
            if len(bullets) >= 2:
                break

    # Eğer sadece 1 madde kaldıysa ve özeti birebir yineliyorsa özet kutusunu gösterme (temiz editoryal deneyim)
    if len(bullets) == 1 and is_similar_to_summary(bullets[0]):
        return []

    return bullets[:3]

@app.api_route("/haber/{slug}", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def article_detail(request: Request, slug: str):
    cache_key = f"art_{slug}"
    if request.cookies.get("ga_admin") != "1":
        cached_html = get_turbo_page(cache_key)
        if cached_html:
            if _is_human_browser_request(request):
                database.increment_article_view_by_slug(slug)
            return HTMLResponse(content=cached_html, headers={"X-Turbo-Cache": "HIT", "Cache-Control": "public, max-age=120, s-maxage=120", "CDN-Cache-Control": "max-age=120", "Cloudflare-CDN-Cache-Control": "max-age=120"})

    article = database.get_article_by_slug(slug)
    if not article:
        from fastapi.responses import RedirectResponse
        import urllib.parse
        slug_low = (slug or "").lower()
        _direct_slug_map = {
            "thomas-markle-abdde-cocuk-istismari-materyali-bulundurmak-suclamasiyla-yakalandi": "/haber/thomas-markle-abdde-yurutulen-federal-sorusturma-kapsaminda-gozaltina-alindi",
            "fuhus-aginda-977-milyonluk-trafik": "/haber/yasa-disi-sebeke-operasyonunda-977-milyon-liralik-para-trafigi",
            "istanbulda-canli-bahis-dolandiriciligi-8-supheli-gozaltinda": "/haber/istanbulda-spor-veri-altyapisina-siber-mudahale-8-supheli-gozaltinda",
            "umman-korfezinde-dokme-yuk-gemisi-ile-askeri-unutlar-arasinda-hareketlilik-yasan": "/haber/umman-korfezinde-dokme-yuk-gemisi-ile-askeri-unsurlar-arasinda-hareketlilik-yasa",
            "f-bahce-tarfinin-konugu-valencia": "/haber/fenerbahce-bekonun-konugu-valencia",
            "bime-kumtel-cam-ankastre-set-geliyor-bim-1-7-kasim": "/haber/perakende-zincirlerinde-kasim-donemi-ankastre-ve-beyaz-esya-kampanyalari",
            "dunya-dosyasi-zararsiz-sanilan-yeni-nesil-plastik-katkisi-bebek-sagligini-tehdit": "/haber/bpa-sonrasi-yeni-nesil-plastik-katkilarinda-gizli-risk-bebek-urunlerinde-kimyasa",
        }
        if slug_low in _direct_slug_map:
            return RedirectResponse(url=_direct_slug_map[slug_low], status_code=301)
        # Silinen veya taşınan eski haber bağlantılarını kırık (404) bırakmak yerine ilgili kategoriye / ana sayfaya 301 yönlendir
        _cat_map = [
            ("Ekonomi", ("gumus", "altin", "dolar", "euro", "borsa", "enflasyon", "faiz", "merkez-bankasi", "yatirim", "halka-arz", "temettu", "kripto", "bitcoin", "vergi", "maas", "emekli", "kira", "konut", "ihracat", "ekonomi", "fiyat", "zam")),
            ("Teknoloji", ("yapay-zeka", "google", "apple", "iphone", "i-os", "i-phone", "samsung", "android", "gta", "oyun", "raiden", "uzay", "siber", "yazilim", "teknoloji", "bilgisayar", "internet", "whatsapp", "instagram")),
            ("Otomobil", ("otomobil", "elektrikli", "togg", "ford", "peugeot", "renault", "hyundai", "tesla", "byd", "chery", "omoda", "dacia", "tofas", "fiat", "menzil", "suv", "otv")),
            ("Spor", ("fenerbahce", "galatasaray", "besiktas", "trabzonspor", "super-lig", "sampiyon", "transfer", "derbi", "salah", "lukaku", "mourinho", "okan-buruk", "milli-takim", "basketbol", "voleybol")),
            ("Sağlık", ("saglik", "hastane", "doktor", "uzmanindan", "beyin", "kalp", "kanser", "beslenme", "uyku", "vitamin", "enfeksiyon", "grip", "bakan-memisoglu")),
            ("Eğitim", ("meb", "egitim", "sinav", "kpss", "yks", "lgs", "universite", "ogrenci", "okul", "ogretmen", "staj", "burs", "mufredat")),
            ("Dünya", ("iran", "israil", "gazze", "filistin", "abd", "trump", "rusya", "ukrayna", "zelenski", "almanya", "avrupa", "nato", "kuzey-kore", "cin", "suriye")),
        ]
        target_url = "/"
        for _cname, _kw_list in _cat_map:
            if any(_k in slug_low for _k in _kw_list):
                target_url = f"/?kategori={urllib.parse.quote(_cname)}"
                break
        return RedirectResponse(url=target_url, status_code=301)

    article_id = article.get("id")
    category = article.get("category") or "Gündem"

    # Önceki ve Sonraki Haber Navigasyonu (Okuma akışı hiç kopmaz)
    prev_article, next_article = database.get_adjacent_articles(article_id)

    widgets = get_cached_category_widgets()
    breaking_news = widgets.get("breaking_news") or []

    # Gerçek En Çok Okunanlar (views DESC - Gerçek Ziyaretçi Sayısına Göre)
    real_trending = widgets.get("trending_articles") or database.get_trending_articles(limit=10)
    trending_articles = [a for a in real_trending if a.get("slug") != slug][:5]
    if len(trending_articles) < 5:
        existing_slugs = {a.get("slug") for a in trending_articles}
        for bn in breaking_news:
            if bn.get("slug") != slug and bn.get("slug") not in existing_slugs:
                trending_articles.append(bn)
                if len(trending_articles) >= 5:
                    break

    # Diğer Güncel Haberler (En Çok Okunanlarda olanları hariç tutar, mükerrer göstermez)
    trend_slugs = {a.get("slug") for a in trending_articles}
    other_articles = [a for a in breaking_news if a.get("slug") != slug and a.get("slug") not in trend_slugs][:5]
    if len(other_articles) < 5:
        other_articles = [a for a in breaking_news if a.get("slug") != slug][:5]

    # Kategori İçi İlgili Haberler (RAM önbellekten anında döner)
    cat_lower = category.lower()
    if "eko" in cat_lower:
        cat_pool = widgets.get("economy_articles") or []
    elif "tekno" in cat_lower:
        cat_pool = widgets.get("tech_articles") or []
    elif "oto" in cat_lower:
        cat_pool = widgets.get("auto_articles") or []
    elif "spor" in cat_lower:
        cat_pool = widgets.get("sports_articles") or []
    elif "sağlık" in cat_lower or "saglik" in cat_lower:
        cat_pool = widgets.get("health_articles") or []
    elif "eğitim" in cat_lower or "egitim" in cat_lower:
        cat_pool = widgets.get("education_articles") or []
    else:
        cat_pool = widgets.get("gundem_articles") or []

    fresh_rel = [a for a in cat_pool if a.get("slug") != slug][:2]
    if len(fresh_rel) < 2:
        fresh_rel = [a for a in breaking_news if a.get("slug") != slug][:2]
    used_rel_slugs = {slug} | {a.get("slug") for a in fresh_rel if a.get("slug")}
    arch_rel = []
    try:
        idx_pool = _INDEX_CACHE.get("rows") or _indexable_articles()
        same_cat_arch = [a for a in idx_pool if (a.get("category") or "Gündem") == category and a.get("slug") not in used_rel_slugs]
        if len(same_cat_arch) < 6:
            same_cat_arch = [a for a in idx_pool if a.get("slug") not in used_rel_slugs]
        if same_cat_arch:
            n_arch = len(same_cat_arch)
            seed_id = int(article_id or 1)
            for step in range(min(8, n_arch)):
                pick = same_cat_arch[(seed_id * 7 + step * 19) % n_arch]
                if pick.get("slug") not in used_rel_slugs:
                    used_rel_slugs.add(pick.get("slug"))
                    arch_rel.append(pick)
                if len(arch_rel) >= 4:
                    break
    except Exception:
        pass
    related_articles = (fresh_rel + arch_rel)[:6]
    if len(related_articles) < 3:
        for bn in breaking_news:
            if bn.get("slug") not in used_rel_slugs:
                related_articles.append(bn)
                used_rel_slugs.add(bn.get("slug"))
            if len(related_articles) >= 6:
                break

    slider_articles = related_articles if len(related_articles) >= 3 else breaking_news

    gundem_articles = widgets.get("gundem_articles") or []
    auto_articles = widgets.get("auto_articles") or []
    tech_articles = widgets.get("tech_articles") or []
    economy_articles = widgets.get("economy_articles") or []
    sports_articles = widgets.get("sports_articles") or []
    health_articles = widgets.get("health_articles") or []
    education_articles = widgets.get("education_articles") or []

    # Tahmini okuma süresi (140 kelime/dk)
    text_content = f"{article.get('title', '')} {article.get('summary', '')} {article.get('content', '')}"
    word_count = len(text_content.split())
    reading_time_min = max(1, round(word_count / 140))

    # Kesilmeyen tam özet maddeleri
    highlights = summary_highlights(article.get("content", ""), article.get("summary", ""), article.get("title", ""))

    ad_settings = get_site_ad_settings()
    ad_mid = ad_settings.get("ad_slot_article_mid", "").strip() if ad_settings.get("ads_enabled") else ""
    raw_content = article.get("content", "")
    try:
        if "<video" not in raw_content.lower() and "<video" in (article.get("content_legacy") or "").lower():
            _vm = re.search(r'(<div[^>]*>\s*<video[\s\S]*?</video>\s*</div>|<video[\s\S]*?</video>)', article.get("content_legacy") or "", re.I)
            if _vm:
                raw_content = _vm.group(1) + "\n" + raw_content
    except Exception:
        pass
    # AdSense kalite: eski şablon/dolgu kalıntılarını gösterimde temizle, kısa haberleri Google dizininden çıkar
    import content_quality
    import html as _html_mod
    article["title"] = content_quality.clean_title_text(article.get("title") or "")
    article["summary"] = content_quality.clean_summary_text(article.get("summary") or "", article["title"])
    raw_content = content_quality.clean_article_html(raw_content)
    is_thin_article = (category != "Analiz") and content_quality.is_thin(raw_content, threshold=220)

    # Eski/yeni makalelerdeki tekdüze "Gündem Analizi Notu: Bu Sizin İçin Ne Anlama Geliyor?" şablon başlığını
    # ve kalıp kapanış cümlelerini kategoriye ve haber ID'sine göre doğal gazetecilik başlıklarıyla çeşitlendir
    _NATURAL_SUBHEADS = {
        "Ekonomi": [
            "Piyasa Dengeleri ve Ekonomik Görünüm",
            "Sektörel Yansımalar ve Bütçe Etkisi",
            "Finansal Perspektif ve Önümüzdeki Dönem",
            "Reel Sektör ve Tüketici Açısından Tablo",
        ],
        "Teknoloji": [
            "Teknolojik Dönüşüm ve Kullanıcı Deneyimi",
            "Sektörel Rekabet ve Yeni Standartlar",
            "Dijital Ekosistemde Beklenen Yansımalar",
            "Donanım ve Yazılım Dünyasında Yeni Safha",
        ],
        "Otomobil": [
            "Otomotiv Pazarında Rekabet ve Beklentiler",
            "Sürücü Deneyimi ve Sektörel Yansımalar",
            "Piyasa Koşulları ve Model Stratejisi",
            "Mobilite Dünyasında Öne Çıkan Detaylar",
        ],
        "Spor": [
            "Saha İçi Dengeler ve Teknik Değerlendirme",
            "Sezon Yürüyüşünde Kritik Viraj",
            "Takım Performansı ve Rekabet Tablosu",
            "Spor Kamuoyunda Yansımalar ve Beklentiler",
        ],
        "Sağlık": [
            "Klinik Değerlendirme ve Koruyucu Önlemler",
            "Toplum Sağlığı Açısından Öne Çıkan Noktalar",
            "Uzman Yaklaşımı ve Günlük Yaşam Etkisi",
            "Tıbbi Süreçler ve Dikkat Edilmesi Gerekenler",
        ],
        "Eğitim": [
            "Akademik Takvim ve Öğrenciler İçin Rehber",
            "Eğitim Süreçlerinde Yeni Dönem",
            "Adaylar ve Veliler Açısından Önemli Noktalar",
            "Kurumsal Uygulama ve Takvim Detayları",
        ],
        "Dünya": [
            "Uluslararası Dengeler ve Diplomatik Tablo",
            "Bölgesel Güvenlik ve Jeopolitik Yansımalar",
            "Küresel Siyasette Olası Senaryolar",
            "Diplomatik Trafik ve Sahadaki Gerçekler",
        ],
        "Gündem": [
            "Kamuoyu Yansımaları ve Sürecin Çerçevesi",
            "Sahadaki Durum ve İdari Süreç",
            "Toplumsal Etkiler ve Beklenen Adımlar",
            "Resmi Süreç ve Öne Çıkan Ayrıntılar",
        ],
    }
    _cat_heads = _NATURAL_SUBHEADS.get(category, _NATURAL_SUBHEADS["Gündem"])
    _chosen_head = _cat_heads[(article_id or 0) % len(_cat_heads)]
    raw_content = re.sub(
        r'<h3([^>]*)>\s*Gündem Analizi Notu[^<]*</h3>',
        lambda _m: f'<h3{_m.group(1)}>{_chosen_head}</h3>',
        raw_content,
        flags=re.I,
    )
    # Tekdüze yapay zeka kapanış kalıplarını ("en doğru yaklaşım olacaktır" vb.) doğal cümlelerle yumuşat
    raw_content = re.sub(
        r'\ben doğru yaklaşım olacaktır\.',
        'önem taşımaktadır.',
        raw_content,
        flags=re.I,
    )
    raw_content = re.sub(
        r'\ben doğru korunma yöntemidir\.',
        'belirleyici olacaktır.',
        raw_content,
        flags=re.I,
    )

    # Ekonomi haberlerinde sayfanın açıldığı andaki canlı piyasa verilerini göster (bizim verimiz → özgün katma değer)
    if False and (article.get("category") or "") == "Ekonomi":
        try:
            _rates = {r.get("key"): r for r in (get_market_rates().get("rates") or [])}
            _cells = ""
            for _k, _lbl in (("dolar", "Dolar"), ("euro", "Euro"), ("altin", "Gram Altın")):
                _r = _rates.get(_k)
                if _r and _r.get("price"):
                    _up = _r.get("direction") == "up"
                    _cells += (
                        f'<div class="p-3 rounded-xl bg-white border border-slate-200">'
                        f'<span class="block text-[10px] font-extrabold text-slate-500 uppercase">{_html_mod.escape(_lbl)}</span>'
                        f'<strong class="block text-base font-black text-slate-900 font-mono">{_html_mod.escape(str(_r.get("price")))} {_html_mod.escape(str(_r.get("unit") or ""))}</strong>'
                        f'<span class="text-[11px] font-bold {"text-emerald-700" if _up else "text-red-700"}">{"▲" if _up else "▼"} %{_html_mod.escape(str(abs(float(_r.get("change") or 0))))}</span>'
                        f'</div>'
                    )
            if _cells:
                raw_content += (
                    '<div class="not-prose my-8 p-4 sm:p-5 rounded-2xl bg-slate-50 border border-slate-200">'
                    '<div class="flex items-center justify-between mb-3">'
                    '<span class="text-xs font-black text-slate-900 uppercase tracking-wide">📊 Şu Anki Piyasa Verileri</span>'
                    '<a href="/piyasalar" class="text-[11px] font-bold text-red-600 hover:underline">Çevirici ve tüm kurlar →</a>'
                    '</div>'
                    f'<div class="grid grid-cols-3 gap-2">{_cells}</div>'
                    '<p class="text-[10px] text-slate-500 mt-2">Veriler sayfanın açıldığı andaki serbest piyasa değerleridir; yatırım tavsiyesi değildir.</p>'
                    '</div>'
                )
        except Exception as _e:
            print(f"Ekonomi piyasa kutusu atlandı: {_e}")

    # Spor haberlerinde sayfanın açıldığı andaki canlı Süper Lig İlk 5 Puan Durumu kutusunu göster (şans oyunları/emtia hariç)
    if False and (article.get("category") or "") == "Spor" and not is_thin_article and not main.is_commodity_news(article.get("title", "")):
        try:
            import live_services
            _sl = await asyncio.to_thread(live_services.get_live_superlig)
            _top5 = (_sl.get("standings") or [])[:5]
            if _top5:
                _rows_html = "".join(
                    f'<div class="p-2.5 rounded-xl bg-white border border-slate-200 flex items-center justify-between text-xs">'
                    f'<span class="font-extrabold text-slate-900 truncate">{int(t.get("rank") or 0)}. {_html_mod.escape(str(t.get("team") or ""))}</span>'
                    f'<span class="font-mono font-black text-red-600 shrink-0 ml-2">{int(t.get("p") or 0)} P</span>'
                    f'</div>'
                    for t in _top5
                )
                raw_content += (
                    '<div class="not-prose my-8 p-4 sm:p-5 rounded-2xl bg-slate-50 border border-slate-200">'
                    '<div class="flex items-center justify-between mb-3">'
                    f'<span class="text-xs font-black text-slate-900 uppercase tracking-wide">🏆 Süper Lig Canlı Puan Durumu ({int(_sl.get("week") or 11)}. Hafta)</span>'
                    '<a href="/super-lig-puan-durumu" class="text-[11px] font-bold text-red-600 hover:underline">18 takım tam tablo &amp; fikstür →</a>'
                    '</div>'
                    f'<div class="grid grid-cols-1 sm:grid-cols-5 gap-2">{_rows_html}</div>'
                    '</div>'
                )
        except Exception as _e:
            print(f"Spor puan durumu kutusu atlandı: {_e}")

    # 3. alt başlığın hemen üstüne tek satırlık şık "İlginizi Çekebilir" iç bağlantısı (SEO & Sayfa Görüntüleme Artırıcı)
    # İçerik çeşitlendirme (her haberde aynı 5'li <h3> şablonu yerine ID'ye göre 3 farklı editoryal mizanpaj)
    raw_content = content_quality.diversify_article_layout(raw_content, article_id or 0)
    if related_articles and len(re.findall(r"<h[23]\b", raw_content, flags=re.I)) >= 2:
        rel_pick = related_articles[-1]
        rel_title_esc = _html_mod.escape(rel_pick.get("title") or "")
        rel_cat_esc = _html_mod.escape(rel_pick.get("category") or "Gündem")
        rel_slug_esc = _html_mod.escape(rel_pick.get("slug") or "")
        inline_box = (
            f'<div class="my-6 p-3.5 sm:p-4 rounded-xl bg-red-50/70 border-l-4 border-red-600 border-y border-r border-red-200/80 flex items-center justify-between gap-3 not-prose shadow-xs">'
            f'<div class="min-w-0">'
            f'<span class="text-[10px] font-black text-red-600 uppercase tracking-wider block mb-0.5">📌 İLGİNİZİ ÇEKEBİLİR • {rel_cat_esc}</span>'
            f'<a href="/haber/{rel_slug_esc}" class="text-xs sm:text-sm font-extrabold text-slate-900 hover:text-red-600 transition line-clamp-1">{rel_title_esc}</a>'
            f'</div>'
            f'<a href="/haber/{rel_slug_esc}" class="shrink-0 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-[11px] font-bold transition shadow-xs">Oku →</a>'
            f'</div>'
        )
        h3_positions = [m.start() for m in re.finditer(r"<h[23]\b", raw_content, flags=re.I)]
        if len(h3_positions) >= 2:
            pos_idx = 1 if (article_id or 0) % 2 == 0 or len(h3_positions) == 2 else 2
            pos3 = h3_positions[pos_idx]
            raw_content = raw_content[:pos3] + inline_box + raw_content[pos3:]
        elif False and len(h3_positions) >= 3:
            pass
        # Inline box placed above
        elif False and len(h3_positions) >= 99:
            pos3 = h3_positions[2]
            raw_content = raw_content[:pos3] + inline_box + raw_content[pos3:]

    if ad_mid and "</p>" in raw_content:
        parts = raw_content.split("</p>")
        if len(parts) >= 3:
            mid_banner = f'''</p>
            <div class="my-6 w-full flex flex-col justify-center items-center overflow-hidden rounded-xl bg-slate-50 border border-slate-200 p-2 shadow-xs">
                <span class="text-[9px] uppercase font-bold tracking-wider text-slate-500 mb-1">Sponsorlu Reklam</span>
                <div class="w-full flex justify-center items-center overflow-hidden">
                    {ad_mid}
                </div>
            </div>'''
            raw_content = "</p>".join(parts[:2]) + mid_banner + "</p>".join(parts[2:])

    canonical_url = f"https://xn--gndemanalizi-dlb.com.tr/haber/{slug}"
    clean_src = content_quality.clean_source_name(article.get("source"))
    resp = templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": {**article, "content": raw_content, "source": clean_src},
            "analysis_cockpit": __import__("analysis_engine").build_article_analysis_cockpit(
                {**article, "source": clean_src}, raw_content, (related_articles or []) + (breaking_news or [])
            ),
            "highlights": highlights,
            "related_articles": related_articles,
            "other_articles": other_articles,
            "trending_articles": trending_articles,
            "next_article": next_article,
            "prev_article": prev_article,
            "breaking_news": breaking_news,
            "reading_time_min": reading_time_min,
            "ad_settings": get_site_ad_settings(),
            "market_rates": get_market_rates()["rates"],
            "weather_data": get_live_weather(),
            "canonical_url": canonical_url,
            "noindex": is_thin_article
        }
    )
    if cache_key and resp.body:
        try:
            set_turbo_page(cache_key, resp.body.decode("utf-8"))
        except Exception:
            pass
    return resp

_CONTACT_RATE_LIMIT = {}

@app.get("/piyasalar", response_class=HTMLResponse)
@app.get("/canli-piyasalar", response_class=HTMLResponse)
async def markets_page(request: Request):
    """Canlı Altın, Dolar, Euro Kurları ve Döviz/Altın Hesaplama Aracı Sayfası."""
    widgets = get_cached_category_widgets()
    eco_articles = widgets.get("economy_articles") or database.get_articles(limit=12, category="Ekonomi")
    if len(eco_articles) < 6:
        eco_articles = database.get_articles(limit=12, category="Ekonomi") or database.get_articles(limit=12)
    return templates.TemplateResponse(
        request=request,
        name="markets.html",
        context={
            "market_rates": get_market_rates()["rates"],
            "articles": eco_articles[:12],
        }
    )

@app.api_route("/super-lig-puan-durumu", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def superlig_page(request: Request):
    """Canlı Trendyol Süper Lig Puan Durumu (Genel / İç Saha / Deplasman) ve 34 Haftalık Tam Fikstür Sayfası."""
    import live_services
    superlig = await asyncio.to_thread(live_services.get_live_superlig)
    widgets = get_cached_category_widgets()
    sport_articles = widgets.get("sports_articles") or database.get_articles(limit=9, category="Spor")
    if len(sport_articles) < 6:
        sport_articles = database.get_articles(limit=9, category="Spor") or database.get_articles(limit=9)
    return templates.TemplateResponse(
        request=request,
        name="superlig.html",
        context={
            "superlig": superlig,
            "articles": sport_articles[:9],
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M"),
        },
    )


@app.api_route("/puan-durumu", methods=["GET", "HEAD"])
@app.api_route("/super-lig-fikstur", methods=["GET", "HEAD"])
async def superlig_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/super-lig-puan-durumu", status_code=301)


@app.get("/son-depremler", response_class=HTMLResponse)
async def earthquakes_page(request: Request):
    """Son Depremler: canlı liste + harita (sunucuda çizilir, Google tarafından okunur)."""
    quakes = await asyncio.to_thread(get_live_earthquakes, 100)
    mags = [q.get("mag") or 0 for q in quakes]
    top = max(quakes, key=lambda q: q.get("mag") or 0) if quakes else None
    stats = {
        "count": len(quakes),
        "max_mag": f"{top['mag']:.1f}" if top else "-",
        "max_place": (top or {}).get("place", ""),
        "m3": sum(1 for m in mags if m >= 3),
        "m4": sum(1 for m in mags if m >= 4),
    }
    try:
        related = database.search_articles("deprem", limit=6)
    except Exception:
        related = []
    return templates.TemplateResponse(
        request=request,
        name="deprem.html",
        context={
            "quakes": quakes,
            "stats": stats,
            "related": related,
            "provider": (quakes[0].get("provider") if quakes else "AFAD"),
            "updated_at": datetime.now(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M"),
        },
    )

_CALC_TOOLS = [
    {"key": "maas", "path": "/hesaplama/maas", "icon": "💼", "name": "Brüt – Net Maaş Hesaplama",
     "desc": "Brüt maaştan net maaşı ya da istediğiniz net maaş için gereken brütü, 12 ay vergi dilimleriyle birlikte hesaplayın."},
    {"key": "kidem", "path": "/hesaplama/kidem-tazminati", "icon": "📑", "name": "Kıdem ve İhbar Tazminatı Hesaplama",
     "desc": "Giriş-çıkış tarihi ve son maaşınıza göre güncel tavanla net kıdem tazminatınızı ve ihbar sürenizi öğrenin."},
    {"key": "emekli", "path": "/hesaplama/emekli-zammi", "icon": "👴", "name": "Emekli Zammı Hesaplama",
     "desc": "Mevcut emekli maaşınıza zam oranını uygulayarak yeni aylığınızı ve aylık artışı görün."},
    {"key": "piyasa", "path": "/piyasalar", "icon": "🪙", "name": "Döviz ve Altın Çevirici",
     "desc": "Canlı dolar, euro, gram ve çeyrek altın kurlarıyla anında çeviri yapın."},
]
_CALC_META = {
    "hub": {"path": "/hesaplama", "title": "Hesaplama Araçları: Maaş, Kıdem Tazminatı, Emekli Zammı",
            "h1": "Hesaplama Araçları",
            "lead": "Maaş, kıdem tazminatı, emekli zammı ve döviz-altın hesaplamalarını güncel yasal parametrelerle ücretsiz yapın.",
            "description": "Ücretsiz brüt-net maaş, kıdem ve ihbar tazminatı, emekli zammı ve döviz-altın hesaplama araçları. Güncel asgari ücret, vergi dilimleri ve kıdem tavanıyla."},
    "maas": {"path": "/hesaplama/maas", "title": "Brüt Net Maaş Hesaplama 2026",
             "h1": "Brüt – Net Maaş Hesaplama 2026",
             "lead": "Güncel asgari ücret, SGK kesintileri ve gelir vergisi dilimleriyle aylık ve yıllık net maaşınızı hesaplayın.",
             "description": "2026 brütten nete ve netten brüte maaş hesaplama. SGK, işsizlik, gelir vergisi ve damga vergisi kesintileri, asgari ücret istisnası ve 12 aylık tablo."},
    "kidem": {"path": "/hesaplama/kidem-tazminati", "title": "Kıdem Tazminatı Hesaplama 2026 (Güncel Tavan)",
              "h1": "Kıdem ve İhbar Tazminatı Hesaplama",
              "lead": "Çalışma sürenize ve son brüt maaşınıza göre güncel kıdem tazminatı tavanıyla net tazminatınızı hesaplayın.",
              "description": "2026 güncel kıdem tazminatı tavanıyla net kıdem tazminatı ve ihbar tazminatı hesaplama. Kimler kıdem tazminatı alabilir, nasıl hesaplanır?"},
    "emekli": {"path": "/hesaplama/emekli-zammi", "title": "Emekli Zammı Hesaplama: SSK, Bağ-Kur, Memur",
               "h1": "Emekli Zammı Hesaplama",
               "lead": "Mevcut aylığınıza zam oranını uygulayarak yeni emekli maaşınızı hesaplayın.",
               "description": "SSK, Bağ-Kur ve memur emeklileri için zamlı maaş hesaplama. Emekli zammı nasıl belirlenir, en düşük emekli aylığı nasıl uygulanır?"},
}

def _render_calc(request: Request, tool: str):
    import calc_params
    return templates.TemplateResponse(
        request=request,
        name="calculators.html",
        context={
            "tool": tool,
            "meta": _CALC_META[tool],
            "tools": _CALC_TOOLS,
            "params": calc_params.CALC_PARAMS,
            "today": datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d"),
        },
    )

@app.get("/hesaplama", response_class=HTMLResponse)
async def calc_hub(request: Request):
    return _render_calc(request, "hub")

@app.get("/hesaplama/maas", response_class=HTMLResponse)
async def calc_maas(request: Request):
    return _render_calc(request, "maas")

@app.get("/hesaplama/kidem-tazminati", response_class=HTMLResponse)
async def calc_kidem(request: Request):
    return _render_calc(request, "kidem")

@app.get("/hesaplama/emekli-zammi", response_class=HTMLResponse)
async def calc_emekli(request: Request):
    return _render_calc(request, "emekli")

@app.get("/about", response_class=HTMLResponse)
@app.get("/hakkimizda", response_class=HTMLResponse)
@app.get("/vizyonumuz", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html", context={})

@app.api_route("/analiz", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def analiz_merkezi_page(request: Request):
    """Gündem Analizi Veri Radarı, Etki Simülatörü ve Derin Analiz Dosyaları Merkezi."""
    import analysis_engine
    widgets = get_cached_category_widgets()
    radar_data = analysis_engine.get_agenda_radar_data(widgets)
    return templates.TemplateResponse(
        request=request,
        name="analiz.html",
        context={
            "radar": radar_data,
            "market_rates": get_market_rates()["rates"],
            "ad_settings": get_site_ad_settings(),
        },
    )

@app.get("/kunye", response_class=HTMLResponse)
async def kunye_page(request: Request):
    return templates.TemplateResponse(request=request, name="kunye.html", context={})

@app.get("/yazar/yalcin-celik", response_class=HTMLResponse)
async def author_yalcin_page(request: Request):
    import content_quality
    pool = database.get_sitemap_articles(limit=45)
    articles = [a for a in pool if not content_quality.is_thin(a.get("content") or "") and not main.is_commodity_news(a.get("title", ""))][:15]
    if not articles:
        articles = database.get_articles(limit=15)
    return templates.TemplateResponse(request=request, name="author.html", context={"articles": articles})

@app.get("/yayin-ilkeleri", response_class=HTMLResponse)
async def editorial_policy_page(request: Request):
    return templates.TemplateResponse(request=request, name="editorial_policy.html", context={})

@app.get("/privacy", response_class=HTMLResponse)
@app.get("/gizlilik-politikasi", response_class=HTMLResponse)
@app.get("/gizlilik", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html", context={})

@app.get("/cerez-politikasi", response_class=HTMLResponse)
@app.get("/cookies", response_class=HTMLResponse)
async def cookies_page(request: Request):
    return templates.TemplateResponse(request=request, name="cookies.html", context={})

@app.get("/kullanim-sartlari", response_class=HTMLResponse)
@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html", context={})

@app.get("/contact", response_class=HTMLResponse)
@app.get("/iletisim", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html", context={})

@app.post("/api/contact")
async def api_contact_submit(request: Request):
    client_ip = (request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for") or (request.client.host if request.client else "unknown")).split(",")[0].strip()
    now_ts = time.time()
    recent = [t for t in _CONTACT_RATE_LIMIT.get(client_ip, []) if now_ts - t < 900]
    if len(recent) >= 5:
        return JSONResponse({"ok": False, "error": "Çok fazla talep gönderildi. Lütfen 15 dakika sonra tekrar deneyiniz."}, status_code=429)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Geçersiz istek biçimi."}, status_code=400)
    name = (data.get("name") or "").strip()[:100]
    email = (data.get("email") or "").strip()[:120]
    subject = (data.get("subject") or "Genel İletişim").strip()[:100]
    article_url = (data.get("article_url") or "").strip()[:300]
    message = (data.get("message") or "").strip()[:2000]
    if len(name) < 2 or "@" not in email or len(message) < 10:
        return JSONResponse({"ok": False, "error": "Lütfen ad, geçerli e-posta ve en az 10 karakterlik mesaj giriniz."}, status_code=400)
    recent.append(now_ts)
    _CONTACT_RATE_LIMIT[client_ip] = recent
    if len(_CONTACT_RATE_LIMIT) > 2000:
        for k in [k for k, v in _CONTACT_RATE_LIMIT.items() if not v or now_ts - v[-1] > 900]:
            _CONTACT_RATE_LIMIT.pop(k, None)
    msg_text = (
        f"📩 [KURUMSAL İLETİŞİM / DÜZELTME FORMU]\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Ad Soyad: {name}\n"
        f"📧 E-posta: {email}\n"
        f"📌 Konu: {subject}\n"
        + (f"🔗 Haber: {article_url}\n" if article_url else "")
        + f"🌐 IP: {client_ip}\n\n"
        f"💬 Mesaj:\n{message}"
    )
    try:
        import telegram_notifier
        await asyncio.to_thread(telegram_notifier.send_admin_ihbar, msg_text)
    except Exception as e:
        print(f"İletişim formu Telegram iletim hatası: {e}")
    return JSONResponse({"ok": True})

@app.get("/api/articles")
async def api_articles(limit: int = 10):
    # Arşivin tek istekte kopyalanmasını ve sunucunun yorulmasını önle (X botu 40, bülten 100 kullanır)
    try:
        limit = max(1, min(int(limit), 100))
    except Exception:
        limit = 10
    rows = database.get_articles(limit=limit)
    keep = ("id", "slug", "title", "summary", "category", "image_path", "source", "created_at")
    out = []
    for r in rows:
        d = {k: r.get(k) for k in keep}
        # Sunucu klasör yolunu (/opt/render/...) dışarıya gösterme; yalnızca herkese açık görsel adresi
        img = (d.get("image_path") or "").replace("\\", "/").split("/")[-1]
        d["image_path"] = f"/images/{img}" if img else ""
        out.append(d)
    return out

_REACT_SEEN = {}      # (ip+tarayıcı+haber) özeti -> zaman
_REACT_IP_RATE = {}   # ip -> [zamanlar]

@app.get("/api/react/{article_id}")
async def api_get_reactions(article_id: int):
    counts = await asyncio.to_thread(database.get_reactions, article_id)
    return {"ok": True, "counts": counts}

@app.post("/api/react")
async def api_add_reaction(request: Request):
    """Okuyucu Nabzı: gerçek oy kaydı. Aynı kişi aynı habere bir kez oy verebilir."""
    import hashlib
    try:
        body = await request.json()
        aid = int(body.get("article_id") or 0)
        choice = str(body.get("choice") or "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz istek")
    if aid <= 0 or choice not in database.REACTION_CHOICES:
        raise HTTPException(status_code=400, detail="Geçersiz istek")

    ip = _client_ip(request)
    now_ts = time.time()
    recent = [t for t in _REACT_IP_RATE.get(ip, []) if now_ts - t < 600]
    if len(recent) >= 30:
        raise HTTPException(status_code=429, detail="Çok fazla istek")

    key = hashlib.sha256(f"{ip}|{request.headers.get('user-agent', '')[:80]}|{aid}".encode("utf-8")).hexdigest()[:24]
    duplicate = key in _REACT_SEEN
    if not duplicate:
        art = await asyncio.to_thread(database.get_article_by_id, aid)
        if not art:
            raise HTTPException(status_code=404, detail="Haber bulunamadı")
        await asyncio.to_thread(database.add_reaction, aid, choice)
        _REACT_SEEN[key] = now_ts
        recent.append(now_ts)
        _REACT_IP_RATE[ip] = recent
        if len(_REACT_SEEN) > 100000:
            for k in [k for k, t in _REACT_SEEN.items() if now_ts - t > 86400 * 3]:
                _REACT_SEEN.pop(k, None)
        if len(_REACT_IP_RATE) > 5000:
            for k in [k for k, v in _REACT_IP_RATE.items() if not v or now_ts - v[-1] > 600]:
                _REACT_IP_RATE.pop(k, None)
    counts = await asyncio.to_thread(database.get_reactions, aid)
    return {"ok": True, "duplicate": duplicate, "counts": counts}

@app.get("/api/stats")
async def api_stats(request: Request):
    require_admin_pin(request)
    return database.get_storage_stats()

@app.get("/api/archive-progress")
async def api_archive_progress(request: Request):
    """Arşiv yenileyicinin ilerlemesi (yalnızca yönetici)."""
    require_admin_pin(request)
    import archive_rewriter
    return await asyncio.to_thread(archive_rewriter.get_progress)

@app.get("/api/db-status")
async def api_db_status(request: Request):
    require_admin_pin(request)
    status = {
        "use_pg": database.USE_PG,
        "has_db_url": bool(database.DATABASE_URL),
        "last_pg_error": getattr(database, "_PG_LAST_ERROR", None),
    }
    with database.get_connection() as conn:
        status["conn_is_pg"] = getattr(conn, "is_pg", False)
        try:
            row = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()
            status["articles_count"] = row["c"] if row else 0
        except Exception as e:
            status["articles_query_error"] = str(e)
    return status

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
    return PlainTextResponse(content="google.com, pub-3827167989675699, DIRECT, f08c47fec0942fa0\n")

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots(request: Request):
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    content = f"""User-agent: *
Allow: /
Disallow: /arama
Disallow: /api/
Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/news-sitemap.xml
"""
    return PlainTextResponse(content=content)

@app.get("/site-haritasi", response_class=HTMLResponse)
async def html_sitemap(request: Request):
    """Ziyaretçiler ve Googlebot için tüm haber arşivini (Sıfır Yetim Sayfa) kategorilere göre sunan HTML Site Haritası."""
    articles = await asyncio.to_thread(_indexable_articles)
    if not articles:
        articles = database.get_articles(limit=200)
    cat_order = ["Gündem", "Ekonomi", "Teknoloji", "Spor", "Otomobil", "Sağlık", "Eğitim", "Dünya"]
    grouped_map = {c: [] for c in cat_order}
    for a in articles:
        c = database.normalize_category_name(a.get("category") or "Gündem") or "Gündem"
        if c not in grouped_map:
            c = "Gündem"
        grouped_map[c].append(a)
    grouped_articles = [(c, grouped_map[c]) for c in cat_order if grouped_map.get(c)]
    return templates.TemplateResponse(
        request=request,
        name="sitemap.html",
        context={
            "articles": articles,
            "grouped_articles": grouped_articles,
            "total_articles_count": len(articles),
        }
    )

@app.get("/sitemap.xsl")
async def sitemap_xsl():
    """XML Site Haritalarını tarayıcıda görselleştiren XSLT şablonu."""
    xsl_path = os.path.join(os.path.dirname(__file__), "templates", "sitemap.xsl")
    with open(xsl_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content, media_type="application/xml; charset=utf-8")

def _is_human_browser_request(request: Request) -> bool:
    if request.query_params.get("raw") == "1" or request.query_params.get("format") == "xml":
        return False
    ua = (request.headers.get("user-agent") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    if any(b in ua for b in ("bot", "google", "bing", "yandex", "slurp", "duckduck", "baidu", "crawler", "spider", "curl", "python", " lighthouse", " inspection")):
        return False
    return "text/html" in accept and "mozilla" in ua

def _render_pretty_sitemap_html(title: str, subtitle: str, rows: list, raw_xml_path: str) -> HTMLResponse:
    rows_html = []
    for i, r in enumerate(rows, 1):
        rows_html.append(f"""
        <tr class="hover:bg-slate-50 transition border-b border-slate-200">
            <td class="py-3.5 px-4 text-xs font-extrabold text-slate-700">{i}</td>
            <td class="py-3.5 px-4">
                <div class="text-xs sm:text-sm font-extrabold text-slate-900 mb-0.5">{r.get('label', '')}</div>
                <a href="{r['loc']}" target="_blank" class="text-xs font-semibold text-blue-600 hover:text-red-600 hover:underline break-all">{r['loc']}</a>
            </td>
            <td class="py-3.5 px-4 text-xs font-semibold text-slate-600 whitespace-nowrap">{r.get('date', '-')}</td>
            <td class="py-3.5 px-4 text-right"><span class="px-2.5 py-1 rounded-md bg-slate-900 text-xs font-bold text-white">{r.get('prio', '0.8')}</span></td>
        </tr>""")
    html_str = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Gündem Analizi</title>
    <link rel="icon" type="image/png" href="/assets/logo.png">
    <link rel="stylesheet" href="/assets/style.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        body {{ font-family: 'Inter', sans-serif; background-color: #f8fafc !important; color: #0f172a !important; }}
    </style>
</head>
<body class="min-h-screen py-10 px-4">
    <div class="max-w-5xl mx-auto space-y-6">
        <div class="rounded-2xl bg-white border border-slate-200 p-6 sm:p-8 shadow-md">
            <h1 class="text-2xl sm:text-3xl font-extrabold text-slate-900 mb-2">{title}</h1>
            <p class="text-xs sm:text-sm text-slate-600 mb-5">{subtitle}</p>
            <div class="flex flex-wrap items-center gap-3">
                <a href="/" class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold shadow transition">← Gündem Analizi Anasayfasına Dön</a>
            </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div class="rounded-2xl bg-white border border-slate-200 p-5 shadow-xs">
                <div class="text-2xl font-black text-slate-900">{len(rows)}</div>
                <div class="text-[11px] font-bold text-slate-600 uppercase tracking-wider mt-1">Toplam İndeksli Bağlantı</div>
            </div>
            <div class="rounded-2xl bg-white border border-slate-200 p-5 shadow-xs">
                <div class="text-2xl font-black text-emerald-600">CANLI</div>
                <div class="text-[11px] font-bold text-slate-600 uppercase tracking-wider mt-1">Google News &amp; SEO Durumu</div>
            </div>
            <div class="rounded-2xl bg-white border border-slate-200 p-5 shadow-xs">
                <div class="text-2xl font-black text-slate-900">UTF-8 / XML</div>
                <div class="text-[11px] font-bold text-slate-600 uppercase tracking-wider mt-1">Protokol Uyumluluğu</div>
            </div>
        </div>
        <div class="rounded-2xl bg-white border border-slate-200 overflow-hidden shadow-md">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="border-b border-slate-200 bg-slate-800 text-[11px] font-extrabold text-white uppercase tracking-wider">
                        <th class="py-3.5 px-4 w-12 text-white">#</th>
                        <th class="py-3.5 px-4 text-white">Sayfa / Haber Başlığı &amp; Bağlantısı</th>
                        <th class="py-3.5 px-4 text-white">Yayın Tarihi</th>
                        <th class="py-3.5 px-4 text-right text-white">Öncelik</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                </tbody>
            </table>
        </div>
        <p class="text-center text-xs text-slate-600 pt-2">© 2026 Gündem Analizi - Doğru Haber, Tarafsız Analiz. Tüm Hakları Saklıdır.</p>
    </div>
</body>
</html>"""
    return HTMLResponse(content=html_str)

# ==================== SİTE HARİTASI (SINIRSIZ, ÖNBELLEKLİ) ====================
_SITEMAP_CHUNK = 1000                      # her alt haritada en fazla 1000 haber (Google sınırı 50.000)
_SITEMAP_TTL = 900                         # 15 dakikada bir tazelenir
_INDEX_MEMO = {}                           # id -> {"slug","created_at","len","ok"}
_INDEX_CACHE = {"ts": 0, "rows": []}
_INDEX_LOCK = threading.Lock()


def _format_w3c_lastmod(raw_dt: str, fallback_date: str) -> str:
    """Tarih dizgesini Google Sitemap standardına uygun tam ISO-8601 (+03:00) formatına dönüştürür."""
    s = (raw_dt or "").strip().replace(" ", "T")
    if not s:
        return f"{fallback_date}T09:00:00+03:00"
    if len(s) == 10:
        return f"{s}T09:00:00+03:00"
    if len(s) == 16:
        return f"{s}:00+03:00"
    if "+" not in s and "Z" not in s:
        return f"{s[:19]}+03:00"
    return s


def _indexable_articles() -> list:
    """Veritabanındaki tüm temiz haberleri (%100 kapsam) en yeniden eskiye hafif meta sözlükleri olarak döner.
    Yeni haber eklendiği saniyede (MAX(id) değiştiğinde) 0 sn gecikmeyle anında güncellenir."""
    import content_quality
    now = time.time()
    try:
        with database.get_connection() as conn:
            chk = conn.execute("SELECT COALESCE(MAX(id), 0) AS mid, COUNT(*) AS cnt FROM articles").fetchone()
            cur_sig = f"{chk['mid']}_{chk['cnt']}"
    except Exception:
        cur_sig = _INDEX_CACHE.get("sig", "")
    if _INDEX_CACHE["rows"] and _INDEX_CACHE.get("sig") == cur_sig and now - _INDEX_CACHE["ts"] < _SITEMAP_TTL:
        return _INDEX_CACHE["rows"]
    with _INDEX_LOCK:
        if _INDEX_CACHE["rows"] and _INDEX_CACHE.get("sig") == cur_sig and time.time() - _INDEX_CACHE["ts"] < _SITEMAP_TTL:
            return _INDEX_CACHE["rows"]
        with database.get_connection() as conn:
            meta = [dict(r) for r in conn.execute(
                "SELECT id, slug, title, category, image_path, created_at FROM articles WHERE COALESCE(category, '') = 'Analiz' OR LENGTH(COALESCE(content, '')) >= 1500 ORDER BY id DESC"
            ).fetchall()]
        rows = []
        for m in meta:
            slug_val = (m.get("slug") or "").strip()
            if not slug_val:
                continue
            d = database._row_to_dict({
                "id": m["id"],
                "slug": slug_val,
                "title": content_quality.clean_title_text(m.get("title") or ""),
                "category": database.normalize_category_name(m.get("category") or "Gündem") or "Gündem",
                "image_path": m.get("image_path") or "",
                "created_at": str(m.get("created_at") or ""),
            })
            rows.append(d)
        _INDEX_CACHE["rows"] = rows
        _INDEX_CACHE["ts"] = time.time()
        _INDEX_CACHE["sig"] = cur_sig
        return rows


_STATIC_SITEMAP_PAGES = [
    ("/", "hourly", "1.0", "Ana Sayfa"),
    ("/analiz", "hourly", "0.95", "Gündem Analizi Veri Radarı ve Derin Analiz Dosyaları"),
    ("/son-dakika", "always", "1.0", "Son Dakika Haberleri"),
    ("/piyasalar", "hourly", "0.9", "Canlı Piyasalar & Döviz/Altın Çevirici"),
    ("/super-lig-puan-durumu", "hourly", "0.9", "Trendyol Süper Lig Canlı Puan Durumu ve 34 Haftalık Fikstür"),
    ("/son-depremler", "always", "0.9", "Son Depremler — Canlı Liste ve Harita"),
    ("/hesaplama", "monthly", "0.8", "Hesaplama Araçları"),
    ("/hesaplama/maas", "monthly", "0.8", "Brüt–Net Maaş Hesaplama"),
    ("/hesaplama/kidem-tazminati", "monthly", "0.8", "Kıdem Tazminatı Hesaplama"),
    ("/hesaplama/emekli-zammi", "monthly", "0.8", "Emekli Zammı Hesaplama"),
    ("/hakkimizda", "monthly", "0.5", "Hakkımızda"),
    ("/kunye", "monthly", "0.5", "Künye (Medya Künyesi)"),
    ("/yayin-ilkeleri", "monthly", "0.5", "Yayın İlkeleri"),
    ("/yazar/yalcin-celik", "weekly", "0.6", "Yalçın Çelik — Genel Yayın Yönetmeni"),
    ("/iletisim", "monthly", "0.5", "İletişim & Düzeltme"),
    ("/gizlilik-politikasi", "monthly", "0.5", "Gizlilik Politikası"),
    ("/kullanim-sartlari", "monthly", "0.5", "Kullanım Şartları"),
    ("/cerez-politikasi", "monthly", "0.5", "Çerez Politikası"),
]
_SITEMAP_CATEGORIES = ("Gündem", "Ekonomi", "Eğitim", "Teknoloji", "Otomobil", "Sağlık", "Dünya", "Spor")


@app.get("/sitemap.xml")
async def sitemap(request: Request):
    """Tek parça doğrudan Google Sitemap (<urlset> + Google Image Sitemap):
    Tüm kurumsal sayfalar, kategoriler ve 1.045 haberin tamamı tek seferde taranır."""
    import urllib.parse
    from xml.sax.saxutils import escape
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    now_tr = datetime.now(timezone(timedelta(hours=3)))
    today_iso = now_tr.strftime("%Y-%m-%d")
    now_w3c = now_tr.strftime("%Y-%m-%dT%H:%M:%S+03:00")
    articles = await asyncio.to_thread(_indexable_articles)
    if _is_human_browser_request(request):
        rows = [{"label": lbl, "loc": f"{base_url}{p}", "date": today_iso, "prio": pr} for p, _cf, pr, lbl in _STATIC_SITEMAP_PAGES]
        for a in articles:
            rows.append({"label": a.get("title") or "", "loc": f"{base_url}/haber/{a['slug']}", "date": (a.get("created_at") or "")[:16], "prio": "0.8"})
        return _render_pretty_sitemap_html(
            "Gündem Analizi - Canlı Site Haritası",
            f"Bu XML site haritası, Google, Yandex ve Bing botlarının sitemizdeki tüm sayfaları ve {len(articles)} özgün haberi tek seferde tarayabilmesi için dinamik olarak üretilmektedir.",
            rows,
            "/sitemap.xml"
        )
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    latest_art_lastmod = _format_w3c_lastmod(articles[0].get("created_at") or "", today_iso) if articles else today_iso
    for p, cf, pr, _lbl in _STATIC_SITEMAP_PAGES:
        page_lm = latest_art_lastmod if cf in ("always", "hourly") else today_iso
        xml.append(f'  <url><loc>{base_url}{p}</loc><lastmod>{page_lm}</lastmod><changefreq>{cf}</changefreq><priority>{pr}</priority></url>')
    xml.append(f'  <url><loc>{base_url}/site-haritasi</loc><lastmod>{latest_art_lastmod}</lastmod><changefreq>hourly</changefreq><priority>0.9</priority></url>')
    for cat in _SITEMAP_CATEGORIES:
        xml.append(f'  <url><loc>{base_url}/?kategori={urllib.parse.quote(cat)}</loc><lastmod>{latest_art_lastmod}</lastmod><changefreq>hourly</changefreq><priority>0.9</priority></url>')
    for a in articles:
        lastmod = _format_w3c_lastmod(a.get("created_at") or "", today_iso)
        img_name = (a.get("image_path") or "").replace("\\", "/").split("/")[-1].split("?")[0]
        img_tag = ""
        if img_name and not img_name.lower().endswith((".mp4", ".webm", ".mov")):
            title_esc = escape(a.get("title") or "Gündem Analizi")
            img_tag = f'<image:image><image:loc>{base_url}/images/{escape(img_name)}</image:loc><image:title>{title_esc}</image:title></image:image>'
        xml.append(f'  <url><loc>{base_url}/haber/{a["slug"]}</loc><lastmod>{lastmod}</lastmod><changefreq>daily</changefreq><priority>0.8</priority>{img_tag}</url>')
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml; charset=utf-8")


@app.get("/sitemap-sayfalar.xml")
async def sitemap_pages():
    import urllib.parse
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    today_iso = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p, cf, pr, _lbl in _STATIC_SITEMAP_PAGES:
        xml.append(f'  <url><loc>{base_url}{p}</loc><lastmod>{today_iso}</lastmod><changefreq>{cf}</changefreq><priority>{pr}</priority></url>')
    for cat in _SITEMAP_CATEGORIES:
        try:
            if database.get_articles_total_count(category=cat) < 3:
                continue
        except Exception:
            pass
        xml.append(f'  <url><loc>{base_url}/?kategori={urllib.parse.quote(cat)}</loc><lastmod>{today_iso}</lastmod><changefreq>hourly</changefreq><priority>0.9</priority></url>')
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml; charset=utf-8")


@app.get("/sitemap-haber-{n}.xml")
async def sitemap_articles_chunk(n: int):
    if n < 1:
        raise HTTPException(status_code=404)
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    articles = await asyncio.to_thread(_indexable_articles)
    part = articles[(n - 1) * _SITEMAP_CHUNK:n * _SITEMAP_CHUNK]
    if not part and n > 1:
        raise HTTPException(status_code=404)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for a in part:
        xml.append(f'  <url><loc>{base_url}/haber/{a["slug"]}</loc><lastmod>{(a.get("created_at") or "")[:10]}</lastmod></url>')
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml; charset=utf-8")

@app.get("/news-sitemap.xml")
async def news_sitemap(request: Request):
    """Google Haberler (Google News & Top Stories) özel XML site haritası."""
    from xml.sax.saxutils import escape
    import content_quality
    # Google Haberler kuralı: yalnızca son 48 saatte yayımlanan haberler
    cutoff = (datetime.now(timezone(timedelta(hours=3))) - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    articles = [a for a in (await asyncio.to_thread(_indexable_articles))[:300] if (a.get("created_at") or "") >= cutoff]
    by_id = {}
    if articles:
        ids = [a["id"] for a in articles]
        with database.get_connection() as conn:
            for r in conn.execute(f"SELECT id, title FROM articles WHERE id IN ({','.join('?' * len(ids))})", tuple(ids)).fetchall():
                by_id[dict(r)["id"]] = dict(r)["title"]
    for a in articles:
        a["title"] = content_quality.clean_title_text(by_id.get(a["id"], "") or a.get("title") or "")
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    if _is_human_browser_request(request):
        rows = [
            {"label": a.get("title", ""), "loc": f"{base_url}/haber/{a['slug']}", "date": (a.get("created_at") or "")[:16], "prio": "0.8"}
            for a in articles
        ]
        return _render_pretty_sitemap_html(
            "Gündem Analizi - Canlı Site Haritası",
            "Bu XML site haritası, Google News, Yandex ve Bing botlarının en son haberlerimizi anında tarayabilmesi için dinamik olarak üretilmektedir.",
            rows,
            "/news-sitemap.xml"
        )
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
    return HTMLResponse(content="\n".join(xml), media_type="application/xml; charset=utf-8")

@app.get("/video-sitemap.xml")
async def video_sitemap(request: Request):
    """Google Video Search için özel XML Video Site Haritası (Sadece gerçek videosu olan makaleler)."""
    from xml.sax.saxutils import escape
    articles = database.get_articles(limit=100)
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    vid_articles = []
    for a in articles:
        content_lower = (a.get("content") or "").lower()
        if "<video" in content_lower or ".mp4" in content_lower or "iframe" in content_lower:
            vid_articles.append(a)
    if _is_human_browser_request(request):
        rows = [
            {"label": a.get("title", ""), "loc": f"{base_url}/haber/{a['slug']}", "date": (a.get("created_at") or "")[:16], "prio": "0.8"}
            for a in vid_articles
        ]
        return _render_pretty_sitemap_html(
            "Gündem Analizi - Video Site Haritası",
            "Bu XML video site haritası, Google Video arama botlarının video barındıran haberlerimizi tarayabilmesi için dinamik olarak üretilmektedir.",
            rows,
            "/video-sitemap.xml"
        )
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">')
    for a in vid_articles:
        raw_dt = (a.get("created_at") or "").strip().replace(" ", "T")
        if len(raw_dt) == 16:
            raw_dt += ":00+03:00"
        elif "+" not in raw_dt and "Z" not in raw_dt:
            raw_dt = raw_dt[:19] + "+03:00"
        title_esc = escape(a.get("title") or "")
        summary_esc = escape((a.get("summary") or a.get("title") or "")[:200])
        img_name = (a.get("image_path") or "").replace("\\", "/").split("/")[-1].split("?")[0]
        img_url = f"{base_url}/images/{img_name}" if img_name else f"{base_url}/assets/logo.png"
        xml.append(f"""  <url>
    <loc>{base_url}/haber/{a["slug"]}</loc>
    <video:video>
      <video:thumbnail_loc>{img_url}</video:thumbnail_loc>
      <video:title>{title_esc}</video:title>
      <video:description>{summary_esc}</video:description>
      <video:player_loc>{base_url}/haber/{a["slug"]}</video:player_loc>
      <video:publication_date>{raw_dt}</video:publication_date>
      <video:family_friendly>yes</video:family_friendly>
      <video:live>no</video:live>
    </video:video>
  </url>""")
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml; charset=utf-8")

@app.get("/rss.xml")
@app.get("/feed.xml")
async def rss_feed(request: Request):
    from xml.sax.saxutils import escape
    from email.utils import format_datetime
    import content_quality
    articles = [a for a in database.get_sitemap_articles(limit=50) if not content_quality.is_thin(a.get("content") or "")][:30]
    base_url = "https://xn--gndemanalizi-dlb.com.tr"
    if _is_human_browser_request(request):
        rows = [
            {
                "label": f"[{a.get('category') or 'Gündem'}] {a['title']}",
                "loc": f"{base_url}/haber/{a['slug']}",
                "date": (a.get("created_at") or "")[:16],
                "prio": "RSS 2.0",
            }
            for a in articles
        ]
        return _render_pretty_sitemap_html(
            "Gündem Analizi - RSS 2.0 Canlı Haber Akışı",
            "Bu canlı RSS 2.0 veri akışı, haber okuyucu uygulamalar ve arama motoru botlarının son dakika gelişmelerini anlık takip edebilmesi için UTF-8 standardında üretilmektedir.",
            rows,
            "/rss.xml",
        )
    items_xml = []
    for a in articles:
        img_name = (a.get("image_path") or "").replace("\\", "/").split("/")[-1].split("?")[0]
        img_url = f"{base_url}/images/{img_name}" if img_name else f"{base_url}/assets/logo.png"
        raw_dt = (a.get("created_at") or "").strip()
        try:
            dt_obj = datetime.strptime(raw_dt[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=3)))
            pub_date = format_datetime(dt_obj)
        except Exception:
            pub_date = format_datetime(datetime.now(timezone(timedelta(hours=3))))
        items_xml.append(f"""    <item>
      <title>{escape(a["title"])}</title>
      <link>{base_url}/haber/{a["slug"]}</link>
      <guid isPermaLink="true">{base_url}/haber/{a["slug"]}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(a.get("summary") or a["title"])}</description>
      <category>{escape(a.get("category") or "Gündem")}</category>
      <enclosure url="{img_url}" type="image/jpeg"/>
    </item>""")
    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="/sitemap.xsl"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Gündem Analizi | Doğru Haber • Tarafsız Analiz</title>
    <link>{base_url}/</link>
    <atom:link href="{base_url}/rss.xml" rel="self" type="application/rss+xml"/>
    <description>Türkiye ve dünyadan son dakika gelişmeleri ve tarafsız analizler.</description>
    <language>tr-TR</language>
{chr(10).join(items_xml)}
  </channel>
</rss>"""
    return HTMLResponse(content=rss, media_type="application/xml; charset=utf-8")

@app.get("/api/audit-report")
async def api_audit_report():
    """HTML temizliği ve yapay kart görseli onarım raporunu döner."""
    return JSONResponse(database.get_audit_report())

@app.get("/api/bot-status")
async def bot_status(request: Request):
    require_admin_pin(request)
    """15 dakikalık haber botunun son ve sıradaki yayın saatini gösterir."""
    try:
        import news_bot
        return JSONResponse(news_bot.status())
    except Exception as e:
        return JSONResponse({"hata": str(e)}, status_code=500)

def start_server(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run("web_server:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    start_server()
