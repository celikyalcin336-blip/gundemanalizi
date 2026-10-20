import os
import time
import threading
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request, HTTPException
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
async def home(request: Request, kategori: str = None):
    articles = database.get_articles(limit=24, category=kategori)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "articles": articles,
            "active_category": kategori
        }
    )

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

@app.get("/robots.txt", response_class=HTMLResponse)
async def robots():
    content = f"""User-agent: *
Allow: /
Sitemap: {database.config.SITE_URL if hasattr(database, 'config') else 'https://gundemanalizi.com.tr'}/sitemap.xml
"""
    return HTMLResponse(content=content, media_type="text/plain")

@app.get("/sitemap.xml")
async def sitemap():
    articles = database.get_articles(limit=100)
    base_url = "https://gundemanalizi.com.tr"
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    xml.append(f'  <url><loc>{base_url}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>')
    for a in articles:
        xml.append(f'  <url><loc>{base_url}/haber/{a["slug"]}</loc><lastmod>{a["created_at"][:10]}</lastmod><priority>0.8</priority></url>')
    xml.append('</urlset>')
    return HTMLResponse(content="\n".join(xml), media_type="application/xml")

def start_server(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run("web_server:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    start_server()
