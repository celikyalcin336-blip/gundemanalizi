import os
import sys
import numpy as np
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, 
    concatenate_videoclips, vfx
)

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import config

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_BOLD = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_REGULAR = "C:\\Windows\\Fonts\\segoeui.ttf"

WIDTH = 1080
HEIGHT = 1920

def get_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def wrap_text(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], []
    for w in words:
        cur.append(w)
        bbox = draw.textbbox((0,0), " ".join(cur), font=font)
        if (bbox[2]-bbox[0]) > max_w:
            cur.pop()
            if cur: lines.append(" ".join(cur))
            cur = [w]
    if cur: lines.append(" ".join(cur))
    return lines

# ============================================================
#  SAHNE (SLIDE) ÜRETİCİLERİ
# ============================================================

def make_intro_slide() -> Image.Image:
    """Sahne 1: Logo + SON DAKİKA jenerik açılış."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 16, 24))
    draw = ImageDraw.Draw(img)

    # Kırmızı çizgiler / dekor
    for y in range(0, HEIGHT, 4):
        r = int(20 + 30 * (y / HEIGHT))
        draw.line([(0, y), (WIDTH, y)], fill=(r, 8, 15))

    # Logo (büyük, ortada)
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((320, 320), Image.Resampling.LANCZOS)
        img.paste(logo, ((WIDTH - 320) // 2, 450), mask=logo)

    # SON DAKİKA bandı
    font_big = get_font(FONT_BOLD, 64)
    draw.rounded_rectangle([140, 870, WIDTH - 140, 970], radius=16, fill=(220, 38, 38))
    text_w = draw.textbbox((0, 0), "● SON DAKİKA", font=font_big)
    tx = (WIDTH - (text_w[2] - text_w[0])) // 2
    draw.text((tx, 880), "● SON DAKİKA", fill="white", font=font_big)

    # Marka adı
    font_brand = get_font(FONT_BOLD, 42)
    brand = "GÜNDEM ANALİZİ"
    bw = draw.textbbox((0, 0), brand, font=font_brand)
    bx = (WIDTH - (bw[2] - bw[0])) // 2
    draw.text((bx, 1020), brand, fill=(255, 215, 0), font=font_brand)

    font_sub = get_font(FONT_REGULAR, 28)
    sub = "Doğru Haber • Tarafsız Analiz"
    sw = draw.textbbox((0, 0), sub, font=font_sub)
    sx = (WIDTH - (sw[2] - sw[0])) // 2
    draw.text((sx, 1080), sub, fill=(180, 185, 195), font=font_sub)

    return img

def make_photo_slide(title: str, image_path: str) -> Image.Image:
    """Sahne 2: Haber fotoğrafı üzerinde büyük başlık."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 16, 24))

    if image_path and os.path.exists(image_path):
        try:
            photo = Image.open(image_path).convert("RGB")
            photo = photo.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            img = photo
        except:
            pass

    # Alttan karartma
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(HEIGHT // 2, HEIGHT):
        alpha = int(220 * ((y - HEIGHT // 2) / (HEIGHT // 2)) ** 1.2)
        od.line([(0, y), (WIDTH, y)], fill=(10, 14, 22, min(alpha, 240)))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")

    draw = ImageDraw.Draw(img)

    # Kırmızı etiket
    font_tag = get_font(FONT_BOLD, 30)
    draw.rounded_rectangle([60, HEIGHT - 500, 340, HEIGHT - 450], radius=10, fill=(220, 38, 38))
    draw.text((80, HEIGHT - 495), "● GÜNDEM ANALİZİ", fill="white", font=font_tag)

    # Başlık
    font_title = get_font(FONT_BOLD, 52)
    lines = wrap_text(title, font_title, WIDTH - 140, draw)
    ty = HEIGHT - 420
    for line in lines[:5]:
        draw.text((72, ty + 2), line, fill=(0, 0, 0), font=font_title)  # gölge
        draw.text((70, ty), line, fill="white", font=font_title)
        ty += 64

    return img

def make_summary_slide(title: str, summary: str, source: str) -> Image.Image:
    """Sahne 3: Özet metin ve analiz kutusu."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (14, 18, 28))
    draw = ImageDraw.Draw(img)

    # Logo küçük (sol üst)
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((90, 90), Image.Resampling.LANCZOS)
        mask = Image.new("L", (90, 90), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 90, 90), fill=255)
        img.paste(logo, (60, 80), mask=mask)

    font_brand = get_font(FONT_BOLD, 30)
    draw.text((170, 90), "GÜNDEM ANALİZİ", fill=(255, 215, 0), font=font_brand)
    font_sub = get_font(FONT_REGULAR, 22)
    draw.text((170, 130), "Doğru Haber • Tarafsız Analiz", fill=(160, 165, 175), font=font_sub)

    # Analiz kutusu
    draw.rounded_rectangle([60, 250, WIDTH - 60, HEIGHT - 250], radius=24, fill=(22, 28, 42), outline=(45, 55, 75), width=2)

    # Kırmızı üst çizgi
    draw.rounded_rectangle([60, 250, WIDTH - 60, 260], radius=0, fill=(220, 38, 38))

    # Başlık
    font_title = get_font(FONT_BOLD, 42)
    lines = wrap_text(title, font_title, WIDTH - 200, draw)
    ty = 310
    for line in lines[:4]:
        draw.text((100, ty), line, fill="white", font=font_title)
        ty += 54

    # Ayırıcı çizgi
    draw.line([(100, ty + 20), (WIDTH - 100, ty + 20)], fill=(60, 70, 90), width=2)

    # Özet metin
    font_body = get_font(FONT_REGULAR, 34)
    summary_lines = wrap_text(summary[:300] if summary else title, font_body, WIDTH - 220, draw)
    sy = ty + 60
    for line in summary_lines[:6]:
        draw.text((100, sy), line, fill=(200, 205, 215), font=font_body)
        sy += 46

    # Analiz kutusu
    box_y = sy + 40
    draw.rounded_rectangle([100, box_y, WIDTH - 100, box_y + 120], radius=16, fill=(60, 15, 15), outline=(180, 40, 40), width=2)
    font_az = get_font(FONT_BOLD, 24)
    draw.text((130, box_y + 15), "🔴 GÜNDEM ANALİZİ DEĞERLENDİRMESİ", fill=(255, 120, 120), font=font_az)
    font_azb = get_font(FONT_REGULAR, 22)
    draw.text((130, box_y + 55), "Bu gelişmeyi tarafsız bir bakış açısıyla", fill=(200, 180, 180), font=font_azb)
    draw.text((130, box_y + 82), "takip etmeye devam ediyoruz.", fill=(200, 180, 180), font=font_azb)

    # Alt bilgi
    font_footer = get_font(FONT_REGULAR, 26)
    draw.text((100, HEIGHT - 180), f"Kaynak: {source}", fill=(150, 155, 165), font=font_footer)
    font_url = get_font(FONT_BOLD, 28)
    draw.text((100, HEIGHT - 130), "gündemanalizi.com.tr", fill=(255, 215, 0), font=font_url)

    return img

def make_outro_slide() -> Image.Image:
    """Sahne 4: Kapanış - Kanalı takip et CTA."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 16, 24))
    draw = ImageDraw.Draw(img)

    # Logo (büyük)
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo = logo.resize((260, 260), Image.Resampling.LANCZOS)
        img.paste(logo, ((WIDTH - 260) // 2, 500), mask=logo)

    font_big = get_font(FONT_BOLD, 52)
    cta = "TAKİPTE KALIN!"
    cw = draw.textbbox((0, 0), cta, font=font_big)
    cx = (WIDTH - (cw[2] - cw[0])) // 2
    draw.text((cx, 850), cta, fill="white", font=font_big)

    # Telegram CTA kutusu
    draw.rounded_rectangle([180, 960, WIDTH - 180, 1060], radius=16, fill=(220, 38, 38))
    font_cta = get_font(FONT_BOLD, 36)
    t = "📢 @gundemanalizi"
    tw = draw.textbbox((0, 0), t, font=font_cta)
    ttx = (WIDTH - (tw[2] - tw[0])) // 2
    draw.text((ttx, 978), t, fill="white", font=font_cta)

    # Web sitesi
    font_url = get_font(FONT_BOLD, 32)
    u = "gündemanalizi.com.tr"
    uw = draw.textbbox((0, 0), u, font=font_url)
    ux = (WIDTH - (uw[2] - uw[0])) // 2
    draw.text((ux, 1110), u, fill=(255, 215, 0), font=font_url)

    return img

# ============================================================
#  KEN BURNS ZOOM EFEKTİ (Hareketli Görsel)
# ============================================================

def ken_burns_clip(image_path: str, duration: float, zoom_start=1.0, zoom_end=1.15) -> ImageClip:
    """Görsele yavaşça yakınlaşan sinematik kamera efekti uygular."""
    from PIL import Image as PILImage
    img = PILImage.open(image_path).convert("RGB")
    # Biraz daha büyük yap (zoom payı için)
    big_w = int(WIDTH * zoom_end * 1.1)
    big_h = int(HEIGHT * zoom_end * 1.1)
    img = img.resize((big_w, big_h), PILImage.Resampling.LANCZOS)
    img_array = np.array(img)

    def make_frame(t):
        progress = t / max(duration, 0.01)
        current_zoom = zoom_start + (zoom_end - zoom_start) * progress
        crop_w = int(WIDTH / current_zoom)
        crop_h = int(HEIGHT / current_zoom)
        cx = (big_w - crop_w) // 2
        cy = (big_h - crop_h) // 2
        cropped = img_array[cy:cy + crop_h, cx:cx + crop_w]
        frame = PILImage.fromarray(cropped).resize((WIDTH, HEIGHT), PILImage.Resampling.LANCZOS)
        return np.array(frame)

    from moviepy import VideoClip
    return VideoClip(make_frame, duration=duration)

# ============================================================
#  ANA VİDEO ÜRETİCİ
# ============================================================

def generate_news_video(title: str, summary: str, source: str, image_path: str = None, output_filename: str = "reel.mp4") -> str:
    """
    20-25 saniyelik 4 sahneli, sesli, hareketli dikey haber videosu üretir.
    Sahne 1: Jenerik açılış (Logo + SON DAKİKA)
    Sahne 2: Haber fotoğrafı + başlık (Ken Burns zoom efekti)
    Sahne 3: Özet ve analiz kutusu
    Sahne 4: Kapanış CTA
    """
    print(f"\n🎬 Video üretimi başlatıldı: {title[:50]}...")

    # 1. Seslendirme
    voice_text = f"Son dakika! {title}. {summary[:200]}. Gelişmeleri takip etmek için gündem analizi kanalımıza abone olun."
    audio_path = os.path.join(OUTPUT_DIR, "temp_voice.mp3")

    print("🎙️  Seslendirme üretiliyor...")
    tts = gTTS(text=voice_text, lang="tr", slow=False)
    tts.save(audio_path)

    audio_clip = AudioFileClip(audio_path)
    # Sesi hızlandırmıyoruz - doğal yetişkin tonu korunuyor
    total_dur = audio_clip.duration + 1.5

    # Her sahneye düşen süre
    intro_dur = 3.5
    photo_dur = total_dur * 0.4
    summary_dur = total_dur * 0.35
    outro_dur = max(total_dur - intro_dur - photo_dur - summary_dur, 2.5)

    # 2. Sahneleri üret ve kaydet
    print("🎨 4 ayrı sahne tasarlanıyor...")
    slides = {
        "intro": make_intro_slide(),
        "photo": make_photo_slide(title, image_path),
        "summary": make_summary_slide(title, summary, source),
        "outro": make_outro_slide()
    }

    slide_paths = {}
    for name, img in slides.items():
        p = os.path.join(OUTPUT_DIR, f"temp_slide_{name}.jpg")
        img.save(p, "JPEG", quality=95)
        slide_paths[name] = p

    # 3. Klipleri oluştur (Ken Burns zoom efektli)
    print("⚡ Sahneler birleştiriliyor (Zoom & Geçiş efektleri)...")

    clip_intro = ken_burns_clip(slide_paths["intro"], intro_dur, zoom_start=1.05, zoom_end=1.0)
    clip_photo = ken_burns_clip(slide_paths["photo"], photo_dur, zoom_start=1.0, zoom_end=1.12)
    clip_summary = ken_burns_clip(slide_paths["summary"], summary_dur, zoom_start=1.0, zoom_end=1.05)
    clip_outro = ken_burns_clip(slide_paths["outro"], outro_dur, zoom_start=0.95, zoom_end=1.0)

    # 4. Birleştir
    final_video = concatenate_videoclips([clip_intro, clip_photo, clip_summary, clip_outro], method="compose")
    final_video = final_video.with_audio(audio_clip)

    output_path = os.path.join(OUTPUT_DIR, output_filename)

    print("📼 Video dosyası render ediliyor...")
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )

    # Temizlik
    audio_clip.close()
    final_video.close()
    for p in slide_paths.values():
        if os.path.exists(p): os.remove(p)
    if os.path.exists(audio_path): os.remove(audio_path)

    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Video hazır! ({file_size:.1f} MB): {output_path}")
    return output_path

if __name__ == "__main__":
    test_img = os.path.join(OUTPUT_DIR, "post_1e6d89ad0f.jpg")
    if not os.path.exists(test_img):
        test_img = None
    out = generate_news_video(
        "İletişim Başkanı Duran: Mekke Anlaşması Güvenliği ve Dayanışmayı Önceleyen Önemli Bir Adımdır",
        "Türkiye ve Suudi Arabistan arasında imzalanan tarihi Mekke Anlaşması TBMM onayına sunuldu. Anlaşma bölgesel güvenlik ve uluslararası dayanışmayı güçlendirmeyi hedefliyor.",
        "TRT Haber",
        test_img,
        "test_reel_v2.mp4"
    )
