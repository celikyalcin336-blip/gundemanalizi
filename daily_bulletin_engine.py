"""
Gündem Analizi - Günlük 39.5 Saniyelik 6 Kategorili Viral Reels Bülten Motoru (v2.0)
Kategoriler (Sabit Sıralama):
1. GÜNDEM
2. EKONOMİ
3. DÜNYA
4. SAĞLIK
5. TEKNOLOJİ
6. SPOR

Özellikler:
- Canlı sitedeki /api/articles uç noktasından her kategorinin kendi gerçek haberini çeker.
- Şehit, vefat, cenaze gibi milli/manevi hassasiyet içeren haberleri ve ShiftDelete/YouTuber inceleme kapaklarını filtreler.
- Her bültende taze ve daha önce bültende kullanılmamış haberleri seçer (used_bulletin_stories.json).
- 39.5 saniyelik (3.6 sn 6 fotoğraflı vitrin kanca + 6 x 5.4 sn haber akışı + 3.5 sn kapanış) 1080x1920 dikey HD video.
"""

import json
import os
import re
import sys
import time
import urllib.request
import wave
from datetime import datetime
from io import BytesIO

import numpy as np
import requests
from moviepy import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
HISTORY_FILE = os.path.join(BASE_DIR, "used_bulletin_stories.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

WIDTH = 1080
HEIGHT = 1920
HOOK_DURATION = 3.6
STORY_DURATION = 5.4
OUTRO_START = HOOK_DURATION + 6 * STORY_DURATION  # 36.0s
TOTAL_DURATION = 39.5

FONT_BOLD = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_REGULAR = "C:\\Windows\\Fonts\\segoeui.ttf"

CATEGORIES_ORDER = [
    ("GÜNDEM", "Gündem"),
    ("EKONOMİ", "Ekonomi"),
    ("DÜNYA", "Dünya"),
    ("SAĞLIK", "Sağlık"),
    ("TEKNOLOJİ", "Teknoloji"),
    ("SPOR", "Spor"),
]

CAT_COLORS = {
    "GÜNDEM": (220, 38, 38),      # Kırmızı
    "EKONOMİ": (217, 119, 6),     # Altın Kehribar
    "DÜNYA": (37, 99, 235),       # Kraliyet Mavisi
    "SAĞLIK": (13, 148, 136),     # Turkuaz Yeşil
    "TEKNOLOJİ": (124, 58, 237),  # Mor
    "SPOR": (22, 163, 74),        # Zümrüt Yeşili
}

SENSITIVE_WORDS = [
    "şehit", "sehit", "cenaze", "toprağa verildi", "hayatını kaybetti",
    "ölü", "öldü", "katliam", "intihar", "ceset", "cesed", "facia", "tecavüz", "taciz",
    "incelemesi", "inceleme", "yok satar", "kasım indirim", "macbook", "yaralanan polis"
]


def get_font(path: str, size: int):
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    for fb in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(fb, size)
        except Exception:
            continue
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


def draw_text_with_shadow(draw: ImageDraw.ImageDraw, pos: tuple, text: str, font, fill, shadow_color=(0, 0, 0), offset=3):
    x, y = pos
    draw.text((x + offset, y + offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)


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
        slug_list = list(used_slugs)[-200:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"used_slugs": slug_list, "updated_at": time.time()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Hafıza kaydedilemedi: {e}")


def load_story_image(image_path_str: str) -> Image.Image:
    if image_path_str:
        safe_name = os.path.basename(image_path_str.replace("\\", "/")).split("?")[0]
        local_p = os.path.join(OUTPUT_DIR, safe_name)
        if os.path.exists(local_p) and os.path.getsize(local_p) > 6000:
            try:
                img = Image.open(local_p).convert("RGB")
                img = ImageEnhance.Contrast(img).enhance(1.12)
                img = ImageEnhance.Color(img).enhance(1.14)
                return img
            except Exception:
                pass
        url = f"https://xn--gndemanalizi-dlb.com.tr/images/{safe_name}?v=3"
        try:
            r = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 6000:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                img = ImageEnhance.Contrast(img).enhance(1.12)
                img = ImageEnhance.Color(img).enhance(1.14)
                return img
        except Exception:
            pass
    return Image.new("RGB", (1280, 720), (30, 41, 59))


def fetch_stories_for_bulletin() -> list:
    used_slugs = load_used_stories()
    live_articles = []
    try:
        req = urllib.request.Request(
            "https://xn--gndemanalizi-dlb.com.tr/api/articles?limit=250",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            live_articles = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"⚠️ Canlı API okunamadı ({e}), yerel veritabanı deneniyor...")
        try:
            import database
            live_articles = database.get_articles(limit=200)
        except Exception:
            live_articles = []

    selected = []
    new_used_slugs = set(used_slugs)

    for idx, (cat_upper, cat_db) in enumerate(CATEGORIES_ORDER, 1):
        chosen = None
        for pass_num in (1, 2):
            for a in live_articles:
                if (a.get("category") or "").strip().lower() != cat_db.lower():
                    continue
                slug = a.get("slug", "")
                if pass_num == 1 and slug in new_used_slugs:
                    continue
                if any(s.get("slug") == slug for s in selected):
                    continue
                src_name = (a.get("source") or "").lower()
                if "shiftdelete" in src_name:
                    continue
                title = (a.get("title") or "").strip()
                summary = (a.get("summary") or "").strip()
                combined = f"{title} {summary}".replace("İ", "i").replace("I", "ı").lower()
                if not title or len(title) < 20:
                    continue
                if any(sw in combined for sw in SENSITIVE_WORDS):
                    continue
                img_p = a.get("image_path") or ""
                if not img_p:
                    continue
                chosen = {
                    "num": str(idx),
                    "category": cat_upper,
                    "title": title,
                    "headline": title,
                    "summary": summary,
                    "image_path": img_p,
                    "slug": slug,
                }
                new_used_slugs.add(slug)
                break
            if chosen:
                break

        if not chosen:
            chosen = {
                "num": str(idx),
                "category": cat_upper,
                "title": f"{cat_db} Gündeminde Öne Çıkan Sıcak Gelişmeler",
                "headline": f"{cat_db} Gündeminde Öne Çıkan Sıcak Gelişmeler",
                "summary": f"Günün en önemli {cat_db.lower()} gelişmeleri ve detaylı analizleri www.gundemanalizi.com.tr adresinde.",
                "image_path": "",
                "slug": f"gundem-{cat_db.lower()}-{int(time.time())}",
            }

        selected.append(chosen)

    save_used_stories(new_used_slugs)
    return selected


def generate_broadcast_sfx_and_music(duration: float, transition_times: list, wav_path: str):
    sr = 44100
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)

    pulse_lfo = 0.7 + 0.3 * np.sin(2 * np.pi * 2.0 * t)
    bass = (
        0.35 * np.sin(2 * np.pi * 55.0 * t)
        + 0.25 * np.sin(2 * np.pi * 110.0 * t)
        + 0.15 * np.sin(2 * np.pi * 165.0 * t)
    ) * pulse_lfo

    beat_p = 60.0 / 132.0
    beat_phase = (t % beat_p) / beat_p
    kick_env = np.exp(-18.0 * beat_phase)
    kick = 0.55 * kick_env * np.sin(2 * np.pi * (58.0 + 70.0 * np.exp(-25.0 * beat_phase)) * (t % beat_p))

    sub_p = beat_p / 2.0
    sub_phase = (t % sub_p) / sub_p
    np.random.seed(42)
    noise = np.random.uniform(-1, 1, n)
    ticker = 0.08 * np.exp(-35.0 * sub_phase) * noise

    stinger_p = beat_p * 4.0
    stinger_phase = (t % stinger_p) / stinger_p
    stinger_env = np.exp(-6.0 * stinger_phase)
    stinger = 0.14 * stinger_env * (
        np.sin(2 * np.pi * 880.0 * t) * ((t % 0.24) < 0.12)
        + 0.5 * np.sin(2 * np.pi * 1318.5 * t)
    )

    mix = (bass + kick + ticker + stinger) * 0.24

    for tr_t in transition_times:
        idx_start = int(tr_t * sr)
        effect_len = int(0.42 * sr)
        if 0 <= idx_start < n:
            end_i = min(n, idx_start + effect_len)
            seg_len = end_i - idx_start
            local_t = np.linspace(0, seg_len / sr, seg_len, endpoint=False)
            env = np.sin(np.pi * (local_t / 0.42)) ** 1.5
            sweep_freq = 120.0 + 680.0 * (local_t / 0.42)
            whoosh = 0.42 * env * (0.5 * noise[idx_start:end_i] + 0.5 * np.sin(2 * np.pi * sweep_freq * local_t))
            boom = 0.50 * np.exp(-10.0 * local_t) * np.sin(2 * np.pi * (95.0 * np.exp(-6.0 * local_t) + 38.0) * local_t)
            mix[idx_start:end_i] += (whoosh + boom)

    fade_in = np.clip(t / 0.3, 0.0, 1.0)
    fade_out = np.clip((duration - t) / 1.0, 0.0, 1.0)
    mix = np.clip(mix * fade_in * fade_out, -0.95, 0.95)

    pcm = (mix * 32767).astype(np.int16)
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def render_bulletin_video(output_mp4_path: str = None):
    if not output_mp4_path:
        ts_tag = datetime.now().strftime("%Y%m%d_%H%M")
        output_mp4_path = os.path.join(OUTPUT_DIR, f"bulletin_{ts_tag}.mp4")

    print("📰 Canlı siteden 6 ana kategori (Gündem, Ekonomi, Dünya, Sağlık, Teknoloji, Spor) seçiliyor...")
    stories = fetch_stories_for_bulletin()
    raw_images = [load_story_image(s["image_path"]) for s in stories]

    bg_images = []
    for img in raw_images:
        bg = ImageOps.fit(img, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=28))
        bg = ImageEnhance.Brightness(bg).enhance(0.30)
        bg_images.append(bg)

    tile_w, tile_h = 480, 420
    tile_images = []
    for img in raw_images:
        tile = ImageOps.fit(img, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        grad = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(grad)
        for y in range(tile_h // 3, tile_h):
            alpha = int(240 * ((y - tile_h // 3) / (tile_h - tile_h // 3)) ** 1.25)
            g_draw.line([(0, y), (tile_w, y)], fill=(8, 12, 22, alpha))
        tile_merged = Image.alpha_composite(tile.convert("RGBA"), grad).convert("RGB")
        tile_images.append(tile_merged)

    logo_img = None
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        l_raw = Image.open(logo_path).convert("RGBA").resize((86, 86), Image.Resampling.LANCZOS)
        mask = Image.new("L", (86, 86), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 86, 86), fill=255)
        logo_img = (l_raw, mask)

    f_header = get_font(FONT_BOLD, 36)
    f_sub = get_font(FONT_BOLD, 22)
    f_badge = get_font(FONT_BOLD, 25)
    f_hook_big = get_font(FONT_BOLD, 44)
    f_tile_cat = get_font(FONT_BOLD, 20)
    f_tile_txt = get_font(FONT_BOLD, 24)
    f_tile_num = get_font(FONT_BOLD, 28)
    f_headline = get_font(FONT_BOLD, 46)
    f_body = get_font(FONT_BOLD, 33)
    f_ticker = get_font(FONT_BOLD, 26)

    ticker_full_text = "   •   ".join([f"[{s['category']}] {s['title']}" for s in stories])

    def build_frame(t: float) -> np.ndarray:
        if t < HOOK_DURATION:
            canvas = bg_images[0].copy()
            draw = ImageDraw.Draw(canvas)

            draw.rounded_rectangle([36, 48, WIDTH - 36, 156], radius=22, fill=(12, 16, 28), outline=(220, 38, 38), width=3)
            if logo_img:
                canvas.paste(logo_img[0], (54, 59), mask=logo_img[1])
                draw.ellipse((52, 57, 142, 147), outline=(250, 204, 21), width=3)
            draw_text_with_shadow(draw, (160, 62), "GÜNDEM ANALİZİ", f_header, (255, 255, 255))
            draw.text((160, 108), "TÜRKİYE VE DÜNYA FLAŞ HABER BÜLTENİ", fill=(250, 204, 21), font=f_sub)

            pulse = (int(t * 4.0) % 2 == 0)
            b_col = (220, 38, 38) if pulse else (175, 24, 24)
            draw.rounded_rectangle([WIDTH - 295, 72, WIDTH - 56, 134], radius=14, fill=b_col, outline=(250, 204, 21), width=2)
            draw.ellipse((WIDTH - 274, 93, WIDTH - 254, 113), fill=(250, 204, 21) if pulse else (255, 255, 255))
            draw.text((WIDTH - 242, 87), "CANLI ÖZET", fill="white", font=f_badge)

            draw.rounded_rectangle([36, 174, WIDTH - 36, 326], radius=24, fill=(185, 28, 28), outline=(250, 204, 21), width=4)
            draw.rounded_rectangle([44, 182, WIDTH - 44, 318], radius=20, fill=(24, 12, 16))
            draw.rounded_rectangle([68, 198, 210, 244], radius=10, fill=(220, 38, 38))
            draw.text((84, 206), "DİKKAT!", fill="white", font=get_font(FONT_BOLD, 26))
            draw_text_with_shadow(draw, (226, 194), "GÜNÜN EN ÖNEMLİ", f_hook_big, (250, 204, 21))
            draw_text_with_shadow(draw, (68, 254), "6 KRİTİK SON DAKİKA GELİŞMESİ!", get_font(FONT_BOLD, 40), (255, 255, 255))

            grid_start_y = 350
            col_x = [40, 560]
            row_y = [grid_start_y, grid_start_y + 445, grid_start_y + 890]

            active_spot = int((t / HOOK_DURATION) * 6)

            for idx, s in enumerate(stories[:6]):
                c_idx = idx % 2
                r_idx = idx // 2
                tx = col_x[c_idx]
                ty = row_y[r_idx]

                cat_col = CAT_COLORS.get(s["category"], (220, 38, 38))
                is_spot = (idx == active_spot) or (t < 0.6)

                mask_t = Image.new("L", (tile_w, tile_h), 0)
                ImageDraw.Draw(mask_t).rounded_rectangle([0, 0, tile_w, tile_h], radius=22, fill=255)
                canvas.paste(tile_images[idx], (tx, ty), mask=mask_t)

                border_c = (250, 204, 21) if is_spot else cat_col
                border_w = 5 if is_spot else 3
                draw.rounded_rectangle([tx, ty, tx + tile_w, ty + tile_h], radius=22, outline=border_c, width=border_w)

                draw.rounded_rectangle([tx + 16, ty + 16, tx + 68, ty + 68], radius=14, fill=(220, 38, 38), outline=(255, 255, 255), width=2)
                draw.text((tx + 33, ty + 24), s["num"], fill="white", font=f_tile_num)

                cat_w = draw.textbbox((0, 0), s["category"], font=f_tile_cat)[2] + 28
                draw.rounded_rectangle([tx + 80, ty + 20, tx + 80 + cat_w, ty + 62], radius=10, fill=cat_col, outline=(255, 255, 255), width=1)
                draw.text((tx + 94, ty + 28), s["category"], fill="white", font=f_tile_cat)

                t_lines = wrap_text(s["title"], f_tile_txt, tile_w - 36, draw)[:3]
                ly = ty + tile_h - 32 - len(t_lines) * 32
                for line in t_lines:
                    draw_text_with_shadow(draw, (tx + 18, ly), line, f_tile_txt, (255, 255, 255), offset=2)
                    ly += 31

        elif t < OUTRO_START:
            story_idx = min(int((t - HOOK_DURATION) / STORY_DURATION), 5)
            story_t = (t - HOOK_DURATION) - (story_idx * STORY_DURATION)
            s = stories[story_idx]
            raw_img = raw_images[story_idx]
            cat_col = CAT_COLORS.get(s["category"], (220, 38, 38))

            canvas = bg_images[story_idx].copy()
            draw = ImageDraw.Draw(canvas)

            draw.rounded_rectangle([36, 48, WIDTH - 36, 152], radius=20, fill=(12, 16, 28), outline=cat_col, width=3)
            if logo_img:
                canvas.paste(logo_img[0], (52, 57), mask=logo_img[1])
            draw_text_with_shadow(draw, (156, 60), "GÜNDEM ANALİZİ", f_header, (255, 255, 255))
            draw.text((156, 105), f"{s['category']} GÜNDEMİ  •  HABER {s['num']} / 6", fill=(250, 204, 21), font=f_sub)

            draw.rounded_rectangle([WIDTH - 250, 68, WIDTH - 54, 130], radius=14, fill=cat_col, outline=(255, 255, 255), width=2)
            draw.text((WIDTH - 222, 84), f"{s['num']} / 6 FLAŞ", fill="white", font=f_badge)

            box_w, box_h = WIDTH - 72, 780
            frame_y = 175
            zoom = 1.0 + 0.14 * (story_t / STORY_DURATION)
            big_w, big_h = int(box_w * 1.22), int(box_h * 1.22)
            p_big = ImageOps.fit(raw_img, (big_w, big_h), method=Image.Resampling.LANCZOS)
            cw, ch = int(box_w / zoom), int(box_h / zoom)
            cx, cy = (big_w - cw) // 2, (big_h - ch) // 2
            cropped = p_big.crop((cx, cy, cx + cw, cy + ch)).resize((box_w, box_h), Image.Resampling.LANCZOS)

            if story_t < 0.22:
                flash_factor = 1.0 + 0.65 * (1.0 - story_t / 0.22)
                cropped = ImageEnhance.Brightness(cropped).enhance(flash_factor)

            draw.rounded_rectangle([30, frame_y - 6, 36 + box_w + 6, frame_y + box_h + 6], radius=28, fill=(250, 204, 21) if story_t < 0.4 else cat_col)
            mask_rect = Image.new("L", (box_w, box_h), 0)
            ImageDraw.Draw(mask_rect).rounded_rectangle([0, 0, box_w, box_h], radius=24, fill=255)
            canvas.paste(cropped, (36, frame_y), mask=mask_rect)

            badge_txt = f"{s['category']}  •  SICAK GELİŞME"
            bw = draw.textbbox((0, 0), badge_txt, font=get_font(FONT_BOLD, 23))[2] + 64
            draw.rounded_rectangle([60, frame_y + 24, 60 + bw, frame_y + 82], radius=12, fill=cat_col, outline=(250, 204, 21), width=2)
            draw.ellipse((80, frame_y + 44, 98, frame_y + 62), fill=(250, 204, 21))
            draw.text((108, frame_y + 38), badge_txt, fill="white", font=get_font(FONT_BOLD, 23))

            card_top = 985
            card_bottom = 1665
            draw.rounded_rectangle([36, card_top, WIDTH - 36, card_bottom], radius=28, fill=(14, 19, 32), outline=cat_col, width=3)
            draw.rounded_rectangle([36, card_top, WIDTH - 36, card_top + 16], radius=8, fill=(250, 204, 21))

            hl_lines = wrap_text(s["title"], f_headline, WIDTH - 140, draw)[:3]
            hy = card_top + 42
            for l in hl_lines:
                draw_text_with_shadow(draw, (72, hy), l, f_headline, (250, 204, 21), offset=3)
                hy += 58

            draw.line([(72, hy + 14), (WIDTH - 72, hy + 14)], fill=cat_col, width=3)

            sum_lines = wrap_text(s["summary"], f_body, WIDTH - 140, draw)[:5]
            active_line_idx = int((story_t / STORY_DURATION) * max(1, len(sum_lines)))
            sy = hy + 36
            for l_i, sl in enumerate(sum_lines):
                if l_i == active_line_idx:
                    draw.rounded_rectangle([62, sy - 4, WIDTH - 62, sy + 46], radius=10, fill=(45, 22, 30))
                    draw_text_with_shadow(draw, (72, sy), sl, f_body, (255, 255, 255), offset=2)
                elif l_i < active_line_idx:
                    draw.text((72, sy), sl, fill=(226, 232, 240), font=f_body)
                else:
                    draw.text((72, sy), sl, fill=(148, 163, 184), font=f_body)
                sy += 52

            draw.rounded_rectangle([64, card_bottom - 78, WIDTH - 64, card_bottom - 22], radius=14, fill=(28, 37, 54))
            prompt_txt = ">> Siz bu gelişme hakkında ne düşünüyorsunuz? Yorumlara yazın!" if story_idx % 2 == 1 else ">> Sıradaki flaş gelişme birazdan ekranda!"
            draw.text((88, card_bottom - 64), prompt_txt, fill=(250, 204, 21), font=get_font(FONT_BOLD, 24))

        else:
            canvas = bg_images[0].copy()
            draw = ImageDraw.Draw(canvas)
            box_y = 420
            draw.rounded_rectangle([48, box_y, WIDTH - 48, box_y + 820], radius=36, fill=(14, 19, 32), outline=(250, 204, 21), width=4)
            if logo_img:
                l_big = Image.open(logo_path).convert("RGBA").resize((170, 170), Image.Resampling.LANCZOS)
                m_big = Image.new("L", (170, 170), 0)
                ImageDraw.Draw(m_big).ellipse((0, 0, 170, 170), fill=255)
                canvas.paste(l_big, (WIDTH // 2 - 85, box_y + 60), mask=m_big)
                draw.ellipse((WIDTH // 2 - 88, box_y + 57, WIDTH // 2 + 88, box_y + 233), outline=(220, 38, 38), width=4)

            draw_text_with_shadow(draw, (WIDTH // 2 - 245, box_y + 265), "GÜNDEM ANALİZİ", get_font(FONT_BOLD, 56), (255, 255, 255))
            draw_text_with_shadow(draw, (WIDTH // 2 - 365, box_y + 355), "SİZCE GÜNÜN EN ÖNEMLİ OLAYI HANGİSİ?", get_font(FONT_BOLD, 35), (250, 204, 21))
            draw.text((WIDTH // 2 - 260, box_y + 420), "Fikrinizi Yorumlarda Paylaşın!", fill=(255, 255, 255), font=get_font(FONT_BOLD, 34))

            draw.rounded_rectangle([110, box_y + 510, WIDTH - 110, box_y + 600], radius=22, fill=(220, 38, 38), outline=(250, 204, 21), width=3)
            draw.text((WIDTH // 2 - 255, box_y + 532), "www.gundemanalizi.com.tr", fill="white", font=get_font(FONT_BOLD, 38))
            draw.text((WIDTH // 2 - 190, box_y + 640), "@gndmanalizi  •  Takip Edin", fill=(250, 204, 21), font=get_font(FONT_BOLD, 32))

        ticker_y = 1695
        draw.rectangle([0, ticker_y, WIDTH, ticker_y + 62], fill=(185, 28, 28))
        draw.rectangle([0, ticker_y, 235, ticker_y + 62], fill=(250, 204, 21))
        draw.text((28, ticker_y + 15), "SON DAKİKA", fill=(15, 20, 32), font=get_font(FONT_BOLD, 27))

        scroll_x = 255 - int(t * 210) % 2400
        ticker_crop = Image.new("RGB", (WIDTH - 240, 62), (185, 28, 28))
        t_draw = ImageDraw.Draw(ticker_crop)
        t_draw.text((scroll_x - 240, 15), ticker_full_text + "   •   " + ticker_full_text, fill="white", font=f_ticker)
        canvas.paste(ticker_crop, (240, ticker_y))

        prog_w = int((WIDTH - 72) * (t / TOTAL_DURATION))
        draw.rounded_rectangle([36, 1780, WIDTH - 36, 1798], radius=9, fill=(30, 41, 59))
        if prog_w > 10:
            draw.rounded_rectangle([36, 1780, 36 + prog_w, 1798], radius=9, fill=(250, 204, 21))

        draw.text((42, 1818), "gundemanalizi.com.tr", fill="white", font=get_font(FONT_BOLD, 28))
        draw.text((WIDTH - 235, 1818), "@gndmanalizi", fill=(250, 204, 21), font=get_font(FONT_BOLD, 28))

        return np.array(canvas)

    transition_times = [0.0] + [HOOK_DURATION + i * STORY_DURATION for i in range(6)] + [OUTRO_START]
    wav_path = os.path.join(OUTPUT_DIR, f"temp_music_{int(time.time())}.wav")
    print("🎵 39.5 Saniyelik ses efektli fon müziği üretiliyor...")
    generate_broadcast_sfx_and_music(TOTAL_DURATION, transition_times, wav_path)

    print("🎬 Viral Reels bülteni birleştiriliyor (24 fps)...")
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
        try:
            os.remove(wav_path)
        except Exception:
            pass

    print(f"🎉 BÜLTEN HAZIR: {output_mp4_path} ({os.path.getsize(output_mp4_path) / (1024*1024):.1f} MB)")
    return output_mp4_path, stories


if __name__ == "__main__":
    render_bulletin_video()
