import os
import time
import threading
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, Response, PlainTextResponse
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

app = FastAPI(title="Gündem Analizi Web Portalı", lifespan=lifespan)

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

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, kategori: str = None, q: str = None):
    database.record_visit("home_visits")
    if q and q.strip():
        q_low = q.strip().lower()
        all_arts = database.get_articles(limit=150)
        articles = [
            a for a in all_arts
            if q_low in (a.get("title") or "").lower() or q_low in (a.get("summary") or "").lower()
        ]
    else:
        articles = database.get_articles(limit=24, category=kategori)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "articles": articles,
            "active_category": kategori,
            "search_query": q.strip() if q else ""
        }
    )

ADMIN_PIN = os.getenv("ADMIN_PIN", "1453")

@app.get("/panel", response_class=HTMLResponse)
async def admin_panel(request: Request):
    stats = database.get_dashboard_summary()
    stats["gemini_active"] = bool(config.GEMINI_API_KEY)
    stats["telegram_active"] = bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)
    stats["check_interval"] = config.CHECK_INTERVAL_MINUTES
    return templates.TemplateResponse(
        request=request,
        name="panel.html",
        context={"stats": stats}
    )

@app.post("/api/panel/fetch-now")
async def panel_fetch_now(request: Request):
    pin = request.headers.get("X-Admin-Pin", "")
    if pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Hatalı yönetici şifresi (PIN)")
    threading.Thread(target=main.run_bot, kwargs={"max_items": 1}, daemon=True).start()
    return {"ok": True, "message": "Yeni haber taraması başlatıldı! 15-20 saniye içinde siteye ve Telegram'a düşecek."}

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
    pub_x: bool = False
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
            ticker_text=auto_ticker
        )

        # ADIM 3: Yapay Zeka Haber & Sosyal Medya Metni
        job.update({
            "step": 3,
            "percent": 68,
            "eta_sec": 9,
            "step_text": "🤖 3/5: Gemini AI ile haber makalesi ve Reels/TikTok açıklaması hazırlanıyor..."
        })
        base_summary = summary or title
        ai_cap = ai_writer.generate_social_caption(title, base_summary, "Gündem Analizi Özel")
        article_data = ai_writer.generate_full_article(title, base_summary, "Gündem Analizi Özel")

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
            <div class="my-6 rounded-2xl overflow-hidden border border-red-600/40 bg-black shadow-2xl">
                <video controls playsinline class="w-full max-h-[640px] mx-auto" poster="/images/{os.path.basename(res['thumb_path'])}">
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
                source="Gündem Analizi",
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
                ok = telegram_notifier.send_telegram_video(res["video_path"], ai_cap["caption"], site_url)
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

        social_pack = f"{ai_cap['caption']}\n\n🌐 Detaylar: {site_url}\n#gündem #sondakika #haber #gündemanalizi"
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
            pub_x.lower() == "true"
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

@app.get("/haber/{slug}", response_class=HTMLResponse)
async def article_detail(request: Request, slug: str):
    article = database.get_article_by_slug(slug)
    if not article:
        raise HTTPException(status_code=404, detail="Haber bulunamadı")
    
    other_articles = [a for a in database.get_articles(limit=6) if a["slug"] != slug][:5]
    return templates.TemplateResponse(
        request=request,
        name="article.html",
        context={
            "article": article,
            "other_articles": other_articles
        }
    )

@app.get("/hakkimizda", response_class=HTMLResponse)
async def about_page(request: Request):
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
    content = os.getenv("ADS_TXT", "# Google AdSense ads.txt - Gündem Analizi\n")
    return PlainTextResponse(content=content)

@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots(request: Request):
    host = request.headers.get("host", "xn--gndemanalizi-dlb.com.tr")
    base_url = f"https://{host}"
    content = f"""User-agent: *
Allow: /
Disallow: /panel
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
    for cat in ("Gündem", "Ekonomi", "Dünya", "Spor", "Asayiş", "Son Dakika"):
        xml.append(f'  <url><loc>{base_url}/?kategori={cat}</loc><changefreq>hourly</changefreq><priority>0.9</priority></url>')
    xml.append(f'  <url><loc>{base_url}/hakkimizda</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>')
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
