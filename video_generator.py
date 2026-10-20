import os
import sys
import wave
import struct
import requests
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import VideoClip, VideoFileClip, AudioFileClip

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(OUTPUT_DIR, exist_ok=True)

FONT_BOLD = os.path.join(ASSETS_DIR, "fonts", "segoeuib.ttf")
FONT_REGULAR = os.path.join(ASSETS_DIR, "fonts", "segoeui.ttf")
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "C:\\Windows\\Fonts\\segoeuib.ttf"
if not os.path.exists(FONT_REGULAR):
    FONT_REGULAR = "C:\\Windows\\Fonts\\segoeui.ttf"

WIDTH = 1080
HEIGHT = 1920


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


def generate_ambient_news_music(duration: float, wav_path: str):
    """
    %100 Telifsiz, kısık sesli, modern BBC / Haber Stüdyosu tarzı
    sinematik derin ambient fon müziği üretir (robot konuşma sesi yoktur).
    """
    sr = 44100
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # 1. Derin sinematik atmosferik pad (A minor: 55Hz, 110Hz, 164.8Hz, 220Hz)
    slow_lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t)
    pad = (
        0.45 * np.sin(2 * np.pi * 55.0 * t) +
        0.30 * np.sin(2 * np.pi * 110.0 * t) +
        0.15 * np.sin(2 * np.pi * 164.81 * t) +
        0.10 * np.sin(2 * np.pi * 220.0 * t)
    ) * slow_lfo

    # 2. Yumuşak kalp atışı / haber ritmi (100 BPM -> her 0.6 saniyede bir derin bas vuruşu)
    beat_period = 0.6
    beat_phase = (t % beat_period) / beat_period
    kick_env = np.exp(-18.0 * beat_phase)
    kick_freq = 50.0 + 60.0 * np.exp(-25.0 * beat_phase)
    pulse = 0.55 * kick_env * np.sin(2 * np.pi * kick_freq * (t % beat_period))

    # 3. Her 2.4 saniyede bir zarif "son dakika" kristal sonar tınısı (A4 + E5)
    chime_period = 2.4
    chime_phase = t % chime_period
    chime_env = np.exp(-3.5 * chime_phase) * (1 - np.exp(-80.0 * chime_phase))
    chime = 0.14 * chime_env * (
        np.sin(2 * np.pi * 440.0 * chime_phase) +
        0.5 * np.sin(2 * np.pi * 659.25 * chime_phase)
    )

    # Birleştir ve başlangıç/bitişe yumuşak fade-in / fade-out uygula
    mix = pad + pulse + chime
    fade_in = np.clip(t / 0.8, 0.0, 1.0)
    fade_out = np.clip((duration - t) / 1.2, 0.0, 1.0)
    # Kısık ve rahatsız etmeyen arka plan ses seviyesi (%22 master volume)
    mix = mix * fade_in * fade_out * 0.22
    mix = np.clip(mix, -0.95, 0.95)

    pcm = (mix * 32767).astype(np.int16)
    with wave.open(wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def _load_clean_photo(image_url: str = None, fallback_path: str = None) -> Image.Image:
    """Ham haber fotoğrafını indirir veya mevcut görselin üst fotoğraf kısmını alır."""
    if image_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(image_url, headers=headers, timeout=10)
            if r.status_code == 200:
                return Image.open(BytesIO(r.content)).convert("RGB")
        except Exception:
            pass

    if fallback_path and os.path.exists(fallback_path):
        try:
            im = Image.open(fallback_path).convert("RGB")
            # Eğer 1080x1080 haber kartıysa, alt yazılı kısmı kırpıp üstteki temiz fotoğraf bölgesini al
            w, h = im.size
            if w == h:
                return im.crop((0, 0, w, int(h * 0.58)))
            return im
        except Exception:
            pass

    # Varsayılan koyu stüdyo arka planı
    bg = Image.new("RGB", (1200, 800), (18, 24, 38))
    return bg


def generate_news_video(
    title: str,
    summary: str,
    source: str,
    image_path: str = None,
    output_filename: str = "reel.mp4",
    image_url: str = None,
    category: str = "GÜNDEM"
) -> str:
    """
    12 saniyelik, konuşmasız (robot ses yok!), ekranda sinematik akan yazılı ve
    arka planda kısık sesli telifsiz haber müziği olan profesyonel 9:16 Reels/TikTok videosu üretir.
    - 0 - 5 sn: Çarpıcı Manşet + Yakınlaşan Haber Fotoğrafı
    - 5 - 12 sn: Haberin Detayları & Analiz Kartı + İlerleme Çubuğu
    """
    duration = 12.0
    phase1_end = 5.0
    print(f"\n🎬 Yeni Nesil Reels Videosu Hazırlanıyor: {title[:55]}...")

    raw_photo = _load_clean_photo(image_url=image_url, fallback_path=image_path)

    # 1. Arka Plan: Bulanıklaştırılmış koyu 9:16 atmosferik tuval
    bg_base = raw_photo.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    dark_layer = Image.new("RGBA", (WIDTH, HEIGHT), (8, 12, 20, 210))
    bg_base = Image.alpha_composite(bg_base.convert("RGBA"), dark_layer).convert("RGB")

    # 2. Sabit Üst Header ve Alt Footer Katmanını Hazırla
    logo_img = None
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        l_raw = Image.open(logo_path).convert("RGBA").resize((84, 84), Image.Resampling.LANCZOS)
        mask = Image.new("L", (84, 84), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 84, 84), fill=255)
        logo_img = (l_raw, mask)

    font_brand = get_font(FONT_BOLD, 34)
    font_sub = get_font(FONT_REGULAR, 21)
    font_badge = get_font(FONT_BOLD, 25)
    font_headline = get_font(FONT_BOLD, 50)
    font_summary_title = get_font(FONT_BOLD, 34)
    font_summary_body = get_font(FONT_REGULAR, 35)
    font_footer = get_font(FONT_BOLD, 26)

    dummy_draw = ImageDraw.Draw(bg_base.copy())
    headline_lines = wrap_text(title, font_headline, WIDTH - 150, dummy_draw)[:6]

    clean_sum = (summary or title).replace("\n", " ").strip()
    if len(clean_sum) > 340:
        clean_sum = clean_sum[:337] + "..."
    summary_lines = wrap_text(clean_sum, font_summary_body, WIDTH - 160, dummy_draw)[:8]

    # Fotoğrafı 16:10 çerçeve için yüksek çözünürlükte hazırla (Ken Burns zoom için)
    box_w, box_h = WIDTH - 96, 620
    photo_big = raw_photo.resize((int(box_w * 1.18), int(box_h * 1.18)), Image.Resampling.LANCZOS)
    photo_arr = np.array(photo_big)
    pb_h, pb_w, _ = photo_arr.shape

    def make_frame(t: float):
        canvas = bg_base.copy()
        draw = ImageDraw.Draw(canvas)

        # --- ÜST HEADER ---
        if logo_img:
            canvas.paste(logo_img[0], (52, 70), mask=logo_img[1])
            draw.ellipse((50, 68, 138, 156), outline=(220, 38, 38), width=3)

        draw.text((154, 78), "GÜNDEM ANALİZİ", fill=(255, 255, 255), font=font_brand)
        draw.text((154, 120), "Doğru Haber • Tarafsız Analiz", fill=(165, 175, 195), font=font_sub)

        # Sağ üst canlı SON DAKİKA rozeti
        pulse_on = int(t * 2.5) % 2 == 0
        badge_bg = (220, 38, 38) if pulse_on else (165, 25, 25)
        draw.rounded_rectangle([WIDTH - 290, 82, WIDTH - 52, 140], radius=14, fill=badge_bg)
        draw.text((WIDTH - 266, 95), "● SON DAKİKA", fill="white", font=font_badge)

        # --- ORTA ÜST: SİNEMATİK ZOOMLU HABER FOTOĞRAFI ÇERÇEVESİ ---
        zoom = 1.0 + 0.14 * (t / duration)
        cw = int(box_w / zoom)
        ch = int(box_h / zoom)
        cx = (pb_w - cw) // 2
        cy = (pb_h - ch) // 2
        cropped = Image.fromarray(photo_arr[cy:cy + ch, cx:cx + cw]).resize((box_w, box_h), Image.Resampling.LANCZOS)

        # Köşeleri yuvarlatılmış fotoğraf kutusu
        frame_y = 195
        draw.rounded_rectangle([44, frame_y - 4, 48 + box_w + 4, frame_y + box_h + 4], radius=26, fill=(220, 38, 38))
        mask_rect = Image.new("L", (box_w, box_h), 0)
        ImageDraw.Draw(mask_rect).rounded_rectangle([0, 0, box_w, box_h], radius=22, fill=255)
        canvas.paste(cropped, (48, frame_y), mask=mask_rect)

        # Fotoğrafın sol üstüne kategori etiketi
        cat_text = f" {category.upper()} "
        cb = draw.textbbox((0, 0), cat_text, font=font_badge)
        draw.rounded_rectangle([72, frame_y + 24, 72 + (cb[2] - cb[0]) + 24, frame_y + 72], radius=10, fill=(15, 20, 32))
        draw.text((84, frame_y + 32), cat_text, fill=(248, 113, 113), font=font_badge)

        # --- ALT BÖLÜM: DİNAMİK YAZI KARTI (MANŞET -> DETAYLAR) ---
        card_top = 855
        card_bottom = 1730
        draw.rounded_rectangle(
            [48, card_top, WIDTH - 48, card_bottom],
            radius=28,
            fill=(16, 22, 35),
            outline=(45, 58, 82),
            width=2
        )
        # Kırmızı üst vurgu şeridi
        draw.rounded_rectangle([48, card_top, WIDTH - 48, card_top + 12], radius=6, fill=(220, 38, 38))

        if t < phase1_end:
            # SAHNE 1 (0 - 5 sn): BÜYÜK MANŞET (Satır satır akıcı giriş)
            draw.rounded_rectangle([84, card_top + 42, 340, card_top + 92], radius=10, fill=(220, 38, 38))
            draw.text((104, card_top + 51), "● MANŞET HABER", fill="white", font=font_badge)

            visible_lines = max(1, int((t / 1.1) * len(headline_lines)) + 1)
            ty = card_top + 130
            for idx, line in enumerate(headline_lines[:visible_lines]):
                # İlk satır sarı/beyaz vurgu, diğerleri parlak beyaz
                color = (255, 255, 255) if idx % 2 == 0 else (254, 240, 138)
                draw.text((86, ty + 2), line, fill=(0, 0, 0), font=font_headline)
                draw.text((84, ty), line, fill=color, font=font_headline)
                ty += 72

            # Alt ipucu
            draw.text((84, card_bottom - 75), "Haberin detayları birazdan ekranda >>", fill=(148, 163, 184), font=font_sub)
        else:
            # SAHNE 2 (5 - 12 sn): HABERİN DETAYLARI & ÖZET
            draw.rounded_rectangle([84, card_top + 40, 400, card_top + 90], radius=10, fill=(30, 41, 59))
            draw.text((104, card_top + 49), "● HABERİN DETAYLARI", fill=(248, 113, 113), font=font_badge)

            # Küçük başlık hatırlatması
            short_title = title if len(title) < 58 else title[:55] + "..."
            draw.text((84, card_top + 115), short_title, fill=(254, 240, 138), font=font_summary_title)
            draw.line([(84, card_top + 170), (WIDTH - 84, card_top + 170)], fill=(45, 58, 82), width=2)

            t_phase2 = t - phase1_end
            visible_sum = max(2, int((t_phase2 / 1.4) * len(summary_lines)) + 2)
            sy = card_top + 198
            for line in summary_lines[:visible_sum]:
                draw.text((84, sy), line, fill=(226, 232, 240), font=font_summary_body)
                sy += 54

            # Kaynak rozeti
            draw.text((84, card_bottom - 75), f"Kaynak: {source}  •  Detaylar web sitemizde", fill=(148, 163, 184), font=font_sub)

        # --- EN ALT BAR & İLERLEME ÇUBUĞU (PROGRESS BAR) ---
        prog_w = int((WIDTH - 96) * (t / duration))
        draw.rounded_rectangle([48, 1755, WIDTH - 48, 1771], radius=8, fill=(30, 41, 59))
        if prog_w > 10:
            draw.rounded_rectangle([48, 1755, 48 + prog_w, 1771], radius=8, fill=(220, 38, 38))

        draw.text((52, 1800), "gündemanalizi.com.tr", fill=(255, 255, 255), font=font_footer)
        draw.text((WIDTH - 290, 1800), "@gundemanalizi", fill=(248, 113, 113), font=font_footer)

        return np.array(canvas)

    # 3. Kısık sesli telifsiz haber müziğini üret
    wav_path = os.path.join(OUTPUT_DIR, "temp_ambient.wav")
    generate_ambient_news_music(duration, wav_path)

    video_clip = VideoClip(make_frame, duration=duration)
    audio_clip = AudioFileClip(wav_path)
    final_clip = video_clip.with_audio(audio_clip)

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )

    audio_clip.close()
    final_clip.close()
    if os.path.exists(wav_path):
        os.remove(wav_path)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"✅ Yeni Nesil Reels Hazır! ({size_mb:.1f} MB): {output_path}")
    return output_path


def download_social_video(url: str, output_path: str) -> str:
    """
    X (Twitter), TikTok, Instagram, Reddit veya doğrudan .mp4 linkinden
    ham videoyu indirir.
    """
    if url.lower().split("?")[0].endswith(".mp4"):
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        return output_path

    import yt_dlp
    if os.path.exists(output_path):
        os.remove(output_path)
    ydl_opts = {
        "outtmpl": output_path,
        "format": "best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return output_path


def brand_raw_video(
    raw_video_path: str,
    title: str,
    category: str = "SON DAKİKA",
    output_filename: str = "viral_branded.mp4"
) -> dict:
    """
    Tam Ekran (Küçültmesiz) Viral Video Logolama Motoru:
    - Videoyu ASLA küçük bir kutuya hapsetmez, tam genişlik / tam ekran kullanır.
    - Dikey (9:16) videoları %100 TAM EKRAN (1080x1920) oynatır; üst kısma yarı saydam
      şık bir bantla Gündem Analizi logosu ve başlığı yazar, videonun ortasını asla kapatmaz.
    - Yatay (16:9) veya kare (1:1) videoları %100 TAM GENİŞLİK (1080px, sıfır kenar boşluğu)
      olarak ortalar, arka planı videonun kendi bulanık görüntüsüyle doldurur, başlığı üst boşluğa yazar.
    - Videonun KENDİ ORİJİNAL SESİNİ korur.
    """
    from PIL import ImageFilter
    print(f"\n🔥 Ham Video Tam Ekran Logolanıyor: {title[:55]}...")
    src_clip = VideoFileClip(raw_video_path)
    max_dur = min(src_clip.duration or 15.0, 58.0)
    if src_clip.duration and src_clip.duration > max_dur:
        src_clip = src_clip.subclipped(0, max_dur)

    vw, vh = src_clip.size
    is_vertical = (vh / max(vw, 1)) >= 1.25

    font_brand = get_font(FONT_BOLD, 30)
    font_sub = get_font(FONT_REGULAR, 19)
    font_badge = get_font(FONT_BOLD, 22)
    font_title = get_font(FONT_BOLD, 38)
    font_footer = get_font(FONT_BOLD, 24)

    # Şeffaf (RGBA) Overlay katmanı hazırla (videonun üstüne/boşluğuna binecek)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    # Üst yarı saydam karartma geçişi (yazıların her videoda net okunması için, sadece en üstte)
    lines = wrap_text(title, font_title, WIDTH - 80, odraw)[:3]
    top_grad_h = 165 + len(lines) * 48 + 35

    for y in range(top_grad_h):
        # En üstte %78 koyu, aşağı indikçe tamamen şeffaf (0)
        ratio = 1.0 - (y / top_grad_h)
        alpha = int(205 * (ratio ** 1.3))
        odraw.line([(0, y), (WIDTH, y)], fill=(8, 12, 20, alpha))

    # Alt ince şeffaf imza bandı
    for y in range(HEIGHT - 110, HEIGHT):
        ratio = (y - (HEIGHT - 110)) / 110.0
        alpha = int(185 * (ratio ** 1.2))
        odraw.line([(0, y), (WIDTH, y)], fill=(8, 12, 20, alpha))

    # Logo hazırla
    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        l_raw = Image.open(logo_path).convert("RGBA")
        ls = l_raw.resize((68, 68), Image.Resampling.LANCZOS)
        m1 = Image.new("L", (68, 68), 0)
        ImageDraw.Draw(m1).ellipse((0, 0, 68, 68), fill=255)
        overlay.paste(ls, (36, 38), mask=m1)
        odraw.ellipse((34, 36, 106, 108), outline=(220, 38, 38, 255), width=3)

    odraw.text((120, 42), "GÜNDEM ANALİZİ", fill=(255, 255, 255, 255), font=font_brand)
    odraw.text((120, 78), "Doğru Haber • Tarafsız Analiz", fill=(200, 210, 225, 230), font=font_sub)

    cat_label = f"● {category.upper()}"
    cb = odraw.textbbox((0, 0), cat_label, font=font_badge)
    bw = (cb[2] - cb[0]) + 34
    odraw.rounded_rectangle([WIDTH - bw - 36, 46, WIDTH - 36, 96], radius=10, fill=(220, 38, 38, 240))
    odraw.text((WIDTH - bw - 19, 57), cat_label, fill=(255, 255, 255, 255), font=font_badge)

    # Başlık (kompakt, en üstte, videonun ortasını asla kapatmaz)
    ty = 126
    for idx, line in enumerate(lines):
        col = (255, 255, 255, 255) if idx == 0 else (254, 240, 138, 255)
        odraw.text((40, ty + 2), line, fill=(0, 0, 0, 220), font=font_title)
        odraw.text((38, ty), line, fill=col, font=font_title)
        ty += 48

    # En alt köşe filigran / imza (kompakt, videoyu kapatmaz)
    odraw.text((38, HEIGHT - 58), "gündemanalizi.com.tr", fill=(255, 255, 255, 235), font=font_footer)
    odraw.text((WIDTH - 255, HEIGHT - 58), "@gundemanalizi", fill=(248, 113, 113, 245), font=font_footer)

    # Hızlı alfa birleştirme için numpy dizileri
    ov_arr = np.array(overlay)
    ov_rgb = ov_arr[:, :, :3].astype(np.float32)
    ov_alpha = (ov_arr[:, :, 3:4].astype(np.float32)) / 255.0

    # Video tam genişlik boyutu (küçültme yok, %100 1080px genişlik!)
    scale_w = WIDTH / max(vw, 1)
    fg_w = WIDTH
    fg_h = int(vh * scale_w)

    def make_branded_frame(t: float):
        try:
            raw_f = src_clip.get_frame(min(t, max_dur - 0.04))
            pil_raw = Image.fromarray(raw_f)

            if is_vertical and fg_h >= HEIGHT:
                # Dikey video: %100 TAM EKRAN (1080x1920)
                scaled = pil_raw.resize((fg_w, fg_h), Image.Resampling.BILINEAR)
                top_crop = (fg_h - HEIGHT) // 2
                canvas_pil = scaled.crop((0, top_crop, WIDTH, top_crop + HEIGHT))
            elif is_vertical:
                # Dikey ama 1920'den biraz kısa: Tam ekran doldur
                canvas_pil = pil_raw.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
            else:
                # Yatay veya Kare video: Arka plan bulanık tam ekran, ortada %100 tam genişlik (1080px) net video!
                bg_small = pil_raw.resize((180, 320), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(radius=8))
                canvas_pil = bg_small.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
                # Arka planı hafif koyulaştır ki ortadaki ana video patlasın
                bg_np = (np.array(canvas_pil, dtype=np.float32) * 0.45).astype(np.uint8)
                canvas_pil = Image.fromarray(bg_np)

                fg_pil = pil_raw.resize((WIDTH, fg_h), Image.Resampling.BILINEAR)
                vy = max(top_grad_h - 20, (HEIGHT - fg_h) // 2)
                if vy + fg_h > HEIGHT - 70:
                    vy = max(0, (HEIGHT - fg_h) // 2)
                canvas_pil.paste(fg_pil, (0, vy))

            base_np = np.array(canvas_pil, dtype=np.float32)
            blended = base_np * (1.0 - ov_alpha) + ov_rgb * ov_alpha
            return blended.astype(np.uint8)
        except Exception:
            return np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)

    out_clip = VideoClip(make_branded_frame, duration=max_dur)
    if src_clip.audio is not None:
        out_clip = out_clip.with_audio(src_clip.audio)

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    out_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )

    # Web sitesi için kapak görseli (thumbnail) kaydet
    thumb_name = output_filename.replace(".mp4", ".jpg")
    thumb_path = os.path.join(OUTPUT_DIR, thumb_name)
    mid_frame = make_branded_frame(min(1.5, max_dur / 2))
    thumb_img = Image.fromarray(mid_frame).crop((0, 0, WIDTH, WIDTH))
    thumb_img.save(thumb_path, "JPEG", quality=88)

    out_clip.close()
    src_clip.close()

    return {
        "video_path": output_path,
        "thumb_path": thumb_path,
        "video_filename": output_filename
    }


if __name__ == "__main__":
    sample_img = os.path.join(OUTPUT_DIR, "post_8bb629541d.jpg")
    out = generate_news_video(
        title="Cemalettin Kani Torun, AK Parti'ye katıldı: Rozetini Cumhurbaşkanı Erdoğan taktı",
        summary="Gelecek Partisi'nden istifa eden Bursa Milletvekili Cemalettin Kani Torun, AK Parti grup toplantısında düzenlenen törenle AK Parti'ye katıldı. Torun'un rozetini Cumhurbaşkanı Recep Tayyip Erdoğan taktı.",
        source="TRT Haber",
        image_path=sample_img,
        output_filename="yeni_nesil_reel.mp4",
        category="SİYASET"
    )
