"""
Gündem Analizi - Günlük 58 Saniyelik 6 Kategorili Flaş Bülten Motoru
Kategoriler (Sabit Sıralama):
1. EKONOMİ
2. SAĞLIK
3. SPOR
4. EĞİTİM
5. OTOMOBİL
6. TEKNOLOJİ

Özellikler:
- Sıfır veritabanı yükü (Canlı sitedeki /rss.xml ve açık web sayfalarından çeker).
- Her bültende yepyeni ve taze haberleri seçer (used_bulletin_stories.json hafızası).
- 58 saniyelik 1080x1920 dikey video (Ken Burns zoom, kategori rozetleri, kesintisiz kırmızı ilerleme çubuğu, fon müziği).
"""

import os
import sys
import time
import json
import re
import wave
import requests
import feedparser
import numpy as np
from io import BytesIO
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
HISTORY_FILE = os.path.join(BASE_DIR, "used_bulletin_stories.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

WIDTH = 1080
HEIGHT = 1920
TOTAL_DURATION = 58.0
HOOK_DURATION = 4.5
STORY_DURATION = 8.5
OUTRO_START = 55.5

FONT_BOLD = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_REGULAR = "C:\\Windows\\Fonts\\segoeui.ttf"

CATEGORIES_ORDER = ["EKONOMİ", "SAĞLIK", "SPOR", "EĞİTİM", "OTOMOBİL", "TEKNOLOJİ"]

def get_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def wrap_text(text: str, font: ImageFont.ImageFont, max_w: int, draw: ImageDraw.ImageDraw) -> list:
    words = text.split()
    lines, cur = [], []
    for w in words:
        cur.append(w)
        bbox = draw.textbbox((0, 0), " ".join(cur), font=font)
        if (bbox[2] - bbox[0]) > max_w:
            cur.pop()
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines

def download_image(url: str) -> Image.Image:
    if not url:
        return Image.new("RGB", (1200, 800), (24, 32, 48))
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"⚠️ Görsel indirilemedi ({url}): {e}")
    return Image.new("RGB", (1200, 800), (24, 32, 48))

def load_used_stories() -> set:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("used_slugs", []))
        except Exception:
            return set()
    return set()

def save_used_stories(used_slugs: set):
    try:
        # Son 200 haberi sakla
        slug_list = list(used_slugs)[-200:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"used_slugs": slug_list, "updated_at": time.time()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Hafıza kaydedilemedi: {e}")

def fetch_stories_for_bulletin() -> list:
    """Canlı siteden 6 kategori için en taze ve kullanılmamış haberleri derler."""
    used_slugs = load_used_stories()
    rss_url = "https://xn--gndemanalizi-dlb.com.tr/rss.xml"
    feed = feedparser.parse(rss_url)

    pool = {}
    for c in CATEGORIES_ORDER:
        pool[c] = []

    for entry in feed.entries:
        cat = getattr(entry, "category", "") or "Gündem"
        cat_upper = cat.upper().strip()
        
        # Kategori eşleştirme
        target_cat = None
        for c in CATEGORIES_ORDER:
            if c in cat_upper or (c == "OTOMOBİL" and "OTO" in cat_upper) or (c == "EKONOMİ" and "EKON" in cat_upper):
                target_cat = c
                break
        
        img_url = ""
        if hasattr(entry, "enclosures") and entry.enclosures:
            img_url = entry.enclosures[0].href

        slug = entry.link.rstrip("/").split("/")[-1]
        
        clean_title = entry.title.strip()
        clean_desc = entry.description.strip() if hasattr(entry, "description") else ""
        
        item = {
            "title": clean_title,
            "summary": clean_desc,
            "category": target_cat or cat,
            "image_url": img_url,
            "link": entry.link,
            "slug": slug
        }
        if target_cat:
            pool[target_cat].append(item)

    selected_stories = []
    new_used_slugs = set(used_slugs)

    for idx, cat_name in enumerate(CATEGORIES_ORDER, 1):
        candidates = pool.get(cat_name, [])
        # Önce kullanılmamış haber ara
        chosen = None
        for cand in candidates:
            if cand["slug"] not in used_slugs:
                chosen = cand
                break
        if not chosen and candidates:
            chosen = candidates[0]  # Hepsi kullanılmışsa en yenisini al
        
        # Eğer RSS'te o kategori yoksa kategori sayfasından çek
        if not chosen:
            cat_slug = cat_name.lower().replace("ö", "o").replace("ü", "u").replace("ı", "i").replace("ğ", "g").replace("ş", "s").replace("ç", "c")
            try:
                from bs4 import BeautifulSoup
                cat_url = f"https://xn--gndemanalizi-dlb.com.tr/kategori/{cat_slug}"
                r = requests.get(cat_url, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'html.parser')
                    art = soup.find('article')
                    if art:
                        t_tag = art.find('h2') or art.find('h3')
                        img_tag = art.find('img')
                        a_tag = art.find('a')
                        if t_tag and a_tag:
                            link = a_tag.get('href', '')
                            if not link.startswith('http'):
                                link = f"https://xn--gndemanalizi-dlb.com.tr{link}"
                            img_src = img_tag.get('src', '') if img_tag else ''
                            if img_src and not img_src.startswith('http'):
                                img_src = f"https://xn--gndemanalizi-dlb.com.tr{img_src}"
                            chosen = {
                                "title": t_tag.get_text(strip=True),
                                "summary": f"{cat_name} alanında günün en çok konuşulan gelişmesi ve detayları sitemizde.",
                                "category": cat_name,
                                "image_url": img_src,
                                "link": link,
                                "slug": link.rstrip("/").split("/")[-1]
                            }
            except Exception as e:
                print(f"⚠️ Kategori sayfası çekilemedi ({cat_name}): {e}")

        # Son çare varsayılan güvenli haber
        if not chosen:
            chosen = {
                "title": f"{cat_name.title()} Gündeminde Sıcak Gelişmeler",
                "summary": f"Günün en kritik {cat_name.lower()} haberleri ve analizleri için www.gundemanalizi.com.tr adresini ziyaret edin.",
                "category": cat_name,
                "image_url": "https://xn--gndemanalizi-dlb.com.tr/images/post_0b3436d57c.jpg",
                "link": f"https://xn--gndemanalizi-dlb.com.tr/kategori/{cat_name.lower()}",
                "slug": f"varsayilan-{cat_name.lower()}"
            }

        # Teaser cümlesi (kısa ve merak uyandıran)
        teaser_text = chosen["title"]
        if len(teaser_text) > 42:
            teaser_text = teaser_text[:40] + "…"

        chosen["num"] = str(idx)
        chosen["teaser"] = teaser_text
        selected_stories.append(chosen)
        new_used_slugs.add(chosen["slug"])

    save_used_stories(new_used_slugs)
    return selected_stories

def generate_ambient_music(duration: float, wav_path: str):
    sr = 44100
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    slow_lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.22 * t)
    pad = (
        0.40 * np.sin(2 * np.pi * 55.0 * t) +
        0.28 * np.sin(2 * np.pi * 110.0 * t) +
        0.18 * np.sin(2 * np.pi * 164.81 * t) +
        0.12 * np.sin(2 * np.pi * 220.0 * t)
    ) * slow_lfo

    beat_p = 0.5357
    beat_phase = (t % beat_p) / beat_p
    kick_env = np.exp(-16.0 * beat_phase)
    kick = 0.52 * kick_env * np.sin(2 * np.pi * (54.0 + 52.0 * np.exp(-22.0 * beat_phase)) * (t % beat_p))

    chime_p = 2.14
    chime_phase = (t % chime_p) / chime_p
    chime_env = np.exp(-4.0 * chime_phase) * (1 - np.exp(-70.0 * chime_phase))
    chime = 0.16 * chime_env * (np.sin(2 * np.pi * 440.0 * chime_phase) + 0.5 * np.sin(2 * np.pi * 659.25 * chime_phase))

    mix = (pad + kick + chime)
    fade_in = np.clip(t / 0.8, 0.0, 1.0)
    fade_out = np.clip((duration - t) / 1.5, 0.0, 1.0)
    mix = mix * fade_in * fade_out * 0.25
    mix = np.clip(mix, -0.95, 0.95)

    pcm = (mix * 32767).astype(np.int16)
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

def render_bulletin_video(output_mp4_path: str = None) -> str:
    """Tüm bülten videosunu baştan sona otomatik üretir."""
    if not output_mp4_path:
        ts_tag = datetime.now().strftime("%Y%m%d_%H%M")
        output_mp4_path = os.path.join(OUTPUT_DIR, f"bulletin_{ts_tag}.mp4")

    print("📰 Canlı siteden 6 kategori haberi seçiliyor...")
    stories = fetch_stories_for_bulletin()

    print("🖼️ Haber fotoğrafları indiriliyor...")
    preloaded_images = []
    for s in stories:
        img = download_image(s["image_url"])
        preloaded_images.append(img)

    # Logo
    logo_img = None
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        l_raw = Image.open(logo_path).convert("RGBA").resize((84, 84), Image.Resampling.LANCZOS)
        mask = Image.new("L", (84, 84), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 84, 84), fill=255)
        logo_img = (l_raw, mask)

    f_sub = get_font(FONT_REGULAR, 22)
    f_badge = get_font(FONT_BOLD, 26)
    f_headline = get_font(FONT_BOLD, 46)
    f_body = get_font(FONT_REGULAR, 34)
    f_teaser_num = get_font(FONT_BOLD, 30)
    f_teaser_cat = get_font(FONT_BOLD, 22)
    f_teaser_txt = get_font(FONT_BOLD, 28)
    f_footer = get_font(FONT_BOLD, 26)

    def build_frame(t: float) -> np.ndarray:
        canvas = Image.new("RGB", (WIDTH, HEIGHT), (12, 16, 26))
        draw = ImageDraw.Draw(canvas)

        # Header
        if logo_img:
            canvas.paste(logo_img[0], (52, 60), mask=logo_img[1])
            draw.ellipse((50, 58, 138, 146), outline=(220, 38, 38), width=3)
        draw.text((154, 68), "GÜNDEM ANALİZİ", fill="white", font=get_font(FONT_BOLD, 34))
        draw.text((154, 110), "Günün Özeti • 1 Dakikada 6 Önemli Gelişme", fill=(165, 175, 195), font=f_sub)

        # Flaş rozeti
        pulse = (int(t * 3.5) % 2 == 0)
        badge_col = (220, 38, 38) if pulse else (160, 24, 24)
        draw.rounded_rectangle([WIDTH - 290, 72, WIDTH - 52, 132], radius=14, fill=badge_col)
        draw.text((WIDTH - 268, 86), "● GÜNÜN ÖZETİ", fill="white", font=f_badge)

        # 1. Faz: Kanca (0 - 4.5 sn)
        if t < HOOK_DURATION:
            draw.rounded_rectangle([48, 170, WIDTH - 48, 395], radius=22, fill=(18, 24, 38), outline=(220, 38, 38), width=2)
            draw.text((80, 200), "BUGÜN NELER OLDU?", fill=(254, 240, 138), font=get_font(FONT_BOLD, 52))
            draw.text((80, 270), "1 Dakikada 6 Kritik Gelişme!", fill="white", font=get_font(FONT_BOLD, 36))
            draw.text((80, 330), "Ekonomi, Sağlık, Spor, Eğitim, Otomobil ve Teknoloji", fill=(148, 163, 184), font=get_font(FONT_REGULAR, 26))

            teaser_top = 425
            card_h = 195
            gap = 18
            for idx, s in enumerate(stories):
                appear_time = 0.4 + idx * 0.65
                box_y = teaser_top + idx * (card_h + gap)
                is_active = (t >= appear_time)

                box_bg = (24, 34, 52) if is_active else (15, 20, 30)
                border_col = (220, 38, 38) if is_active else (30, 42, 60)
                text_col = (255, 255, 255) if is_active else (90, 105, 125)

                draw.rounded_rectangle([48, box_y, WIDTH - 48, box_y + card_h], radius=18, fill=box_bg, outline=border_col, width=2)
                
                num_bg = (220, 38, 38) if is_active else (35, 48, 68)
                draw.ellipse((76, box_y + 45, 156, box_y + 125), fill=num_bg)
                draw.text((105, box_y + 64), s["num"], fill="white", font=f_teaser_num)

                cat_tag_bg = (38, 24, 24) if is_active else (25, 25, 35)
                draw.rounded_rectangle([180, box_y + 35, 345, box_y + 75], radius=8, fill=cat_tag_bg)
                draw.text((195, box_y + 42), s["category"], fill=(248, 113, 113) if is_active else (140, 140, 140), font=f_teaser_cat)

                draw.text((180, box_y + 95), s["teaser"], fill=text_col, font=f_teaser_txt)

        # 2. Faz: 6 Haber (4.5 - 55.5 sn)
        elif t < OUTRO_START:
            story_idx = int((t - HOOK_DURATION) / STORY_DURATION)
            story_idx = min(story_idx, 5)
            story_t = (t - HOOK_DURATION) - (story_idx * STORY_DURATION)
            s = stories[story_idx]
            raw_img = preloaded_images[story_idx]

            box_w, box_h = WIDTH - 96, 680
            frame_y = 185
            zoom = 1.0 + 0.12 * (story_t / STORY_DURATION)
            big_w = int(box_w * 1.2)
            big_h = int(box_h * 1.2)
            p_big = raw_img.resize((big_w, big_h), Image.Resampling.LANCZOS)
            p_arr = np.array(p_big)
            cw = int(box_w / zoom)
            ch = int(box_h / zoom)
            cx = (big_w - cw) // 2
            cy = (big_h - ch) // 2
            cropped = Image.fromarray(p_arr[cy:cy + ch, cx:cx + cw]).resize((box_w, box_h), Image.Resampling.LANCZOS)

            draw.rounded_rectangle([44, frame_y - 4, 48 + box_w + 4, frame_y + box_h + 4], radius=26, fill=(220, 38, 38))
            mask_rect = Image.new("L", (box_w, box_h), 0)
            ImageDraw.Draw(mask_rect).rounded_rectangle([0, 0, box_w, box_h], radius=22, fill=255)
            canvas.paste(cropped, (48, frame_y), mask=mask_rect)

            slot_text = f" {s['num']} / 6 • {s['category']} "
            draw.rounded_rectangle([72, frame_y + 24, 380, frame_y + 76], radius=12, fill=(15, 20, 32))
            draw.text((86, frame_y + 34), slot_text, fill=(248, 113, 113), font=f_badge)

            card_top = 910
            card_bottom = 1730
            draw.rounded_rectangle([48, card_top, WIDTH - 48, card_bottom], radius=26, fill=(18, 24, 38), outline=(45, 58, 82), width=2)
            draw.rounded_rectangle([48, card_top, WIDTH - 48, card_top + 12], radius=6, fill=(220, 38, 38))

            hl_lines = wrap_text(s["title"], f_headline, WIDTH - 160, draw)[:3]
            hy = card_top + 45
            for l in hl_lines:
                draw.text((84, hy), l, fill=(254, 240, 138), font=f_headline)
                hy += 62

            draw.line([(84, hy + 15), (WIDTH - 84, hy + 15)], fill=(45, 58, 82), width=2)

            sum_lines = wrap_text(s["summary"], f_body, WIDTH - 160, draw)[:5]
            sy = hy + 45
            for sl in sum_lines:
                draw.text((84, sy), sl, fill=(226, 232, 240), font=f_body)
                sy += 52

            next_hint = "Sıradaki haber geliyor >>" if story_idx < 5 else "Tüm detaylar web sitemizde >>"
            draw.text((84, card_bottom - 70), next_hint, fill=(148, 163, 184), font=f_sub)

        # 3. Faz: Kapanış (55.5 - 58.0 sn)
        else:
            box_y = 480
            draw.rounded_rectangle([48, box_y, WIDTH - 48, box_y + 700], radius=32, fill=(18, 24, 38), outline=(220, 38, 38), width=3)
            if logo_img:
                l_big = Image.open(logo_path).convert("RGBA").resize((160, 160), Image.Resampling.LANCZOS)
                m_big = Image.new("L", (160, 160), 0)
                ImageDraw.Draw(m_big).ellipse((0, 0, 160, 160), fill=255)
                canvas.paste(l_big, (WIDTH // 2 - 80, box_y + 70), mask=m_big)

            draw.text((WIDTH // 2 - 240, box_y + 270), "GÜNDEM ANALİZİ", fill="white", font=get_font(FONT_BOLD, 54))
            draw.text((WIDTH // 2 - 310, box_y + 350), "Tüm Gelişmeler İçin Takipte Kalın!", fill=(254, 240, 138), font=get_font(FONT_BOLD, 36))
            draw.text((WIDTH // 2 - 270, box_y + 440), "🔗  gundemanalizi.com.tr", fill="white", font=get_font(FONT_BOLD, 38))
            draw.text((WIDTH // 2 - 180, box_y + 510), "📱  @gndmanalizi", fill=(248, 113, 113), font=get_font(FONT_BOLD, 34))

        # Kırmızı İlerleme Çubuğu
        prog_w = int((WIDTH - 96) * (t / TOTAL_DURATION))
        draw.rounded_rectangle([48, 1755, WIDTH - 48, 1771], radius=8, fill=(30, 41, 59))
        if prog_w > 10:
            draw.rounded_rectangle([48, 1755, 48 + prog_w, 1771], radius=8, fill=(220, 38, 38))

        draw.text((52, 1800), "gundemanalizi.com.tr", fill="white", font=f_footer)
        draw.text((WIDTH - 290, 1800), "@gndmanalizi", fill=(248, 113, 113), font=f_footer)

        return np.array(canvas)

    wav_path = os.path.join(OUTPUT_DIR, f"temp_music_{int(time.time())}.wav")
    print("🎵 58 Saniyelik fon müziği üretiliyor...")
    generate_ambient_music(TOTAL_DURATION, wav_path)

    print("🎬 Video renderlanıyor (24 fps)...")
    video_clip = VideoClip(build_frame, duration=TOTAL_DURATION)
    audio_clip = AudioFileClip(wav_path)
    final_clip = video_clip.with_audio(audio_clip)

    final_clip.write_videofile(
        output_mp4_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="veryfast",
        logger=None
    )

    audio_clip.close()
    final_clip.close()
    if os.path.exists(wav_path):
        os.remove(wav_path)

    print(f"🎉 BÜLTEN HAZIR: {output_mp4_path} ({os.path.getsize(output_mp4_path) / (1024*1024):.1f} MB)")
    return output_mp4_path

if __name__ == "__main__":
    render_bulletin_video()
