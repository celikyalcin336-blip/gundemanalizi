import os
import sys
import wave
import struct
import requests
from io import BytesIO
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

    from moviepy import VideoClip, AudioFileClip
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
    ham videoyu indirir. Subprocess ve hafif API kullanarak ana sunucu RAM'ini (512MB) hiç şişirmez.
    """
    import re
    import subprocess
    clean_url = url.strip()

    def _stream_download(mp4_url: str, dest: str):
        with requests.get(mp4_url, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        return dest

    if clean_url.lower().split("?")[0].endswith(".mp4"):
        return _stream_download(clean_url, output_path)

    # 1. X (Twitter) linkleri için 0-RAM hızlı doğrudan CDN çözücü (fxtwitter API)
    m_tw = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)/status/(\d+)", clean_url)
    if m_tw:
        try:
            fx_url = f"https://api.fxtwitter.com/{m_tw.group(1)}/status/{m_tw.group(2)}"
            r_fx = requests.get(fx_url, headers={"User-Agent": "TelegramBot (like TwitterBot)"}, timeout=12)
            if r_fx.status_code == 200:
                data = r_fx.json()
                videos = ((data.get("tweet") or {}).get("media") or {}).get("videos") or []
                if videos:
                    v0 = videos[0]
                    best_mp4 = v0.get("url")
                    # Render 0.1 CPU'da çok hızlı işlenmesi için varsa orta (480p-720p) mp4 formatını seç
                    for fmt in (v0.get("formats") or []):
                        if fmt.get("container") == "mp4" and 400000 <= (fmt.get("bitrate") or 0) <= 1500000:
                            best_mp4 = fmt.get("url")
                            break
                    if best_mp4:
                        return _stream_download(best_mp4, output_path)
        except Exception:
            pass

    if os.path.exists(output_path):
        os.remove(output_path)

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--no-warnings",
        "--no-check-certificates",
        "--max-filesize", "35M",
        "-f", "best[height<=720][ext=mp4]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", output_path,
        clean_url
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
    if proc.returncode != 0 or not os.path.exists(output_path):
        err_msg = (proc.stderr or proc.stdout or "Video indirilemedi").strip().splitlines()[-1]
        raise RuntimeError(f"Linkten video indirilemedi ({err_msg}). Lütfen videoyu cihazınıza indirip 'MP4 Dosyası Seç' kısmından yükleyin.")
    return output_path


def brand_raw_video(
    raw_video_path: str,
    title: str,
    category: str = "SON DAKİKA",
    output_filename: str = "viral_branded.mp4",
    start_sec: float = 0.0,
    max_dur_sec: float = 45.0,
    wm_pos: str = "center",
    audio_mode: str = "original",
    ticker_text: str = "",
    source: str = ""
) -> dict:
    """
    Ultra-Hafif (~25MB RAM) Doğrudan FFmpeg Tabanlı Tam Ekran Video Logolama & Kurgu Motoru:
    - start_sec / max_dur_sec ile başlangıç ve bitiş süresini kırpar (trim).
    - wm_pos ('center', 'right', 'left') ile çalınmaz filigran konumunu ayarlar.
    - audio_mode ('original', 'ambient', 'mute') ile ses modunu kontrol eder.
    - ticker_text ile ekranın altında TV tarzı canlı kayan SON DAKİKA bandı oluşturur.
    """
    import gc
    import subprocess
    import imageio_ffmpeg
    print(f"\n🔥 Ultra-Hızlı FFmpeg ile Tam Ekran Logolanıyor: {title[:55]}...")

    VW_OUT, VH_OUT = 720, 1280

    # Reels / Shorts / TikTok için İdeal Viral Tipografi
    font_brand = get_font(FONT_BOLD, 26)
    font_sub = get_font(FONT_REGULAR, 15)
    font_badge = get_font(FONT_BOLD, 18)
    
    # Başlık uzunluğuna göre dinamik font ölçekleme (Göz alıcı dev kanca başlık)
    raw_title = title.strip()
    if len(raw_title) > 85:
        title_font_size = 32
        line_step = 42
    else:
        title_font_size = 38
        line_step = 48
    font_title = get_font(FONT_BOLD, title_font_size)

    font_footer = get_font(FONT_BOLD, 17)
    font_ticker = get_font(FONT_BOLD, 20)

    use_ticker = (ticker_text or "").strip().lower() != "off"
    raw_ticker = (ticker_text or "").strip() or raw_title
    clean_src = source.strip() if source else ""
    has_custom_src = bool(clean_src and clean_src.lower() not in ("gündem analizi", "özel"))
    if has_custom_src:
        ticker_unit = f"   •   {raw_ticker.upper()}   •   KAYNAK: {clean_src.upper()}   •   DOĞRU HABER & TARAFSIZ ANALİZ: GÜNDEMANALİZİ.COM.TR (@gundemanalizi)"
    else:
        ticker_unit = f"   •   {raw_ticker.upper()}   •   DOĞRU HABER & TARAFSIZ ANALİZ: GÜNDEMANALİZİ.COM.TR (@gundemanalizi)"

    # 1. Şeffaf (RGBA) Overlay PNG katmanını hazırla (HD 720x1280 Kalite)
    overlay = Image.new("RGBA", (VW_OUT, VH_OUT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    lines = wrap_text(raw_title, font_title, VW_OUT - 60, odraw)[:3]
    top_grad_h = 120 + len(lines) * line_step + 35

    # Üst Derin Sinematik Karartma (Videodaki ışık parlamalarını engeller, yazıyı patlatır)
    for y in range(top_grad_h):
        ratio = 1.0 - (y / top_grad_h)
        alpha = int(240 * (ratio ** 1.3))
        odraw.line([(0, y), (VW_OUT, y)], fill=(8, 12, 20, alpha))

    for y in range(VH_OUT - 120, VH_OUT):
        ratio = (y - (VH_OUT - 120)) / 120.0
        alpha = int(230 * (ratio ** 1.1))
        odraw.line([(0, y), (VW_OUT, y)], fill=(8, 12, 20, alpha))

    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    if os.path.exists(logo_path):
        l_raw = Image.open(logo_path).convert("RGBA")
        ls = l_raw.resize((54, 54), Image.Resampling.LANCZOS)
        m1 = Image.new("L", (54, 54), 0)
        ImageDraw.Draw(m1).ellipse((0, 0, 54, 54), fill=255)
        overlay.paste(ls, (24, 24), mask=m1)
        odraw.ellipse((22, 22, 80, 80), outline=(220, 38, 38, 255), width=2)

    odraw.text((90, 26), "GÜNDEM ANALİZİ", fill=(255, 255, 255, 255), font=font_brand)
    odraw.text((90, 56), "Doğru Haber • Tarafsız Analiz", fill=(200, 210, 225, 230), font=font_sub)

    cat_label = f"● {category.upper()}"
    cb = odraw.textbbox((0, 0), cat_label, font=font_badge)
    bw = (cb[2] - cb[0]) + 28
    odraw.rounded_rectangle([VW_OUT - bw - 24, 26, VW_OUT - 24, 66], radius=8, fill=(220, 38, 38, 255))
    odraw.text((VW_OUT - bw - 10, 35), cat_label, fill=(255, 255, 255, 255), font=font_badge)

    # Kaynak Rozeti (Mynet, İHA, Habertürk vb. belirtilmişse şık TV rozeti ekle)
    if has_custom_src:
        src_label = f"Kaynak: {clean_src}"
        font_src = get_font(FONT_BOLD, 14)
        sb = odraw.textbbox((0, 0), src_label, font=font_src)
        sw = (sb[2] - sb[0]) + 20
        odraw.rounded_rectangle([VW_OUT - sw - 24, 72, VW_OUT - 24, 98], radius=6, fill=(15, 23, 42, 220), outline=(203, 213, 225, 140), width=1)
        odraw.text((VW_OUT - sw - 14, 76), src_label, fill=(241, 245, 249, 240), font=font_src)

    # Dev Vurucu Başlık (1.5 Saniye Kuralı - 3D Siyah Çerçeve ile Maksimum Kontrast)
    ty = 96
    for idx, line in enumerate(lines):
        col = (255, 255, 255, 255) if idx == 0 else (255, 235, 10, 255)
        odraw.text(
            (28, ty),
            line,
            fill=col,
            font=font_title,
            stroke_width=3,
            stroke_fill=(0, 0, 0, 255)
        )
        ty += line_step

    # --- ÇALINMAYA KARŞI VİDEO İÇİ FİLİGRAN (WATERMARK) KATMANI ---
    wm_y = 920
    wm_box_w = 236
    if wm_pos == "right":
        wm_x = VW_OUT - wm_box_w - 28
    elif wm_pos == "left":
        wm_x = 28
    else:
        wm_x = (VW_OUT - wm_box_w) // 2

    odraw.rounded_rectangle(
        [wm_x, wm_y, wm_x + wm_box_w, wm_y + 54],
        radius=27,
        fill=(10, 14, 22, 160),
        outline=(220, 38, 38, 185),
        width=2
    )
    if os.path.exists(logo_path):
        l_wm = Image.open(logo_path).convert("RGBA").resize((38, 38), Image.Resampling.LANCZOS)
        m_wm = Image.new("L", (38, 38), 0)
        ImageDraw.Draw(m_wm).ellipse((0, 0, 38, 38), fill=225)
        overlay.paste(l_wm, (wm_x + 10, wm_y + 8), mask=m_wm)

    font_wm_bold = get_font(FONT_BOLD, 16)
    font_wm_sub = get_font(FONT_REGULAR, 12)
    odraw.text((wm_x + 56, wm_y + 8), "@gundemanalizi", fill=(255, 255, 255, 235), font=font_wm_bold)
    odraw.text((wm_x + 56, wm_y + 28), "gündemanalizi.com.tr", fill=(254, 240, 138, 220), font=font_wm_sub)

    # 2. Videonun orta-sağ iç kısmına hafif hayalet (ghost) filigran (kırpılsa bile videonun içinde kalır)
    font_ghost = get_font(FONT_BOLD, 24)
    odraw.text((VW_OUT - 240, 620), "@gundemanalizi", fill=(255, 255, 255, 75), font=font_ghost)

    # 3. ALTTAN KAYAN SON DAKİKA BANDI SOL SABİT ROZETİ (TV Stili)
    ticker_y = 1160
    ticker_h = 46
    ticker_path = None
    loop_w = 800
    if use_ticker:
        # Sol taraftaki sabit kırmızı "● SON DAKİKA" kutusu
        ticker_badge_w = 170
        odraw.rectangle([0, ticker_y, ticker_badge_w, ticker_y + ticker_h], fill=(220, 38, 38, 255))
        odraw.line([(0, ticker_y), (VW_OUT, ticker_y)], fill=(220, 38, 38, 255), width=2)
        odraw.line([(0, ticker_y + ticker_h), (VW_OUT, ticker_y + ticker_h)], fill=(30, 41, 59, 255), width=1)
        odraw.text((16, ticker_y + 11), "● SON DAKİKA", fill=(255, 255, 255, 255), font=font_badge)

        # Kayan şerit PNG'sini hazırla
        tb = odraw.textbbox((0, 0), ticker_unit, font=font_ticker)
        loop_w = max(600, (tb[2] - tb[0]))
        strip_w = loop_w * 2 + VW_OUT
        strip_img = Image.new("RGBA", (strip_w, ticker_h), (14, 20, 34, 240))
        sdraw = ImageDraw.Draw(strip_img)
        cx = 0
        while cx < strip_w:
            sdraw.text((cx, 11), ticker_unit, fill=(248, 250, 252, 245), font=font_ticker)
            cx += loop_w

        ticker_path = os.path.join(OUTPUT_DIR, f"tk_{output_filename}.png")
        strip_img.save(ticker_path, "PNG")
        del strip_img

    # 4. En alt bar imzası
    odraw.text((20, VH_OUT - 34), "gündemanalizi.com.tr", fill=(255, 255, 255, 235), font=font_footer)
    odraw.text((VW_OUT - 135, VH_OUT - 34), "@gundemanalizi", fill=(248, 113, 113, 245), font=font_footer)

    overlay_path = os.path.join(OUTPUT_DIR, f"ov_{output_filename}.png")
    overlay.save(overlay_path, "PNG")
    del overlay
    gc.collect()

    output_path = os.path.join(OUTPUT_DIR, output_filename)
    thumb_name = output_filename.replace(".mp4", ".jpg")
    thumb_path = os.path.join(OUTPUT_DIR, thumb_name)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    # 2. Doğrudan FFmpeg ile HD 720p Video Kurgulama (Net, Canlı ve Keskin)
    if use_ticker and ticker_path:
        filter_complex = (
            f"[0:v]fps=30,scale={VW_OUT}:{VH_OUT}:force_original_aspect_ratio=decrease:flags=bicubic,"
            f"pad={VW_OUT}:{VH_OUT}:(ow-iw)/2:(oh-ih)/2:color=#0a0e16,setsar=1[bg];"
            f"[bg][2:v]overlay=x='170-mod(t*130\\,{loop_w})':y={ticker_y}[bg_tk];"
            f"[bg_tk][1:v]overlay=0:0,format=yuv420p[v]"
        )
    else:
        filter_complex = (
            f"[0:v]fps=30,scale={VW_OUT}:{VH_OUT}:force_original_aspect_ratio=decrease:flags=bicubic,"
            f"pad={VW_OUT}:{VH_OUT}:(ow-iw)/2:(oh-ih)/2:color=#0a0e16,setsar=1[bg];"
            f"[bg][1:v]overlay=0:0,format=yuv420p[v]"
        )

    safe_start = max(0.0, float(start_sec or 0.0))
    safe_dur = max(3.0, min(60.0, float(max_dur_sec or 45.0)))

    amb_wav = None
    ff_cmd = [ffmpeg_exe, "-y"]
    if safe_start > 0:
        ff_cmd += ["-ss", f"{safe_start:.1f}"]
    ff_cmd += [
        "-t", f"{safe_dur:.1f}",
        "-i", raw_video_path,
        "-i", overlay_path,
    ]
    if use_ticker and ticker_path:
        ff_cmd += ["-i", ticker_path]

    amb_input_idx = 3 if (use_ticker and ticker_path) else 2
    if audio_mode == "ambient":
        amb_wav = os.path.join(OUTPUT_DIR, f"amb_{output_filename}.wav")
        generate_ambient_news_music(min(safe_dur, 30.0), amb_wav)
        ff_cmd += ["-i", amb_wav]

    ff_cmd += [
        "-filter_complex", filter_complex,
        "-map", "[v]",
    ]
    if audio_mode == "mute":
        ff_cmd += ["-an"]
    elif audio_mode == "ambient" and amb_wav:
        ff_cmd += ["-map", f"{amb_input_idx}:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        # Twitter veya internet videolarındaki Opus/farklı sesleri standart AAC formatına dönüştür (MP4 uyumsuzluğunu önler)
        ff_cmd += ["-map", "0:a?", "-c:a", "aac", "-b:a", "128k"]

    ff_cmd += [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-crf", "23",
        "-threads", "2",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]
    res_ff = subprocess.run(ff_cmd, capture_output=True, text=True, timeout=300)
    if os.path.exists(overlay_path):
        os.remove(overlay_path)
    if ticker_path and os.path.exists(ticker_path):
        os.remove(ticker_path)
    if amb_wav and os.path.exists(amb_wav):
        os.remove(amb_wav)

    if res_ff.returncode != 0 or not os.path.exists(output_path):
        err_tail = (res_ff.stderr or "")[-300:]
        raise RuntimeError(f"FFmpeg video işleme hatası: {err_tail}")

    # 3. Kapak fotoğrafını (thumbnail) FFmpeg ile 0.1 saniyede çıkar
    thumb_cmd = [
        ffmpeg_exe, "-y",
        "-ss", "00:00:01",
        "-i", output_path,
        "-frames:v", "1",
        "-vf", f"crop={VW_OUT}:{VW_OUT}:0:0",
        "-q:v", "4",
        thumb_path
    ]
    subprocess.run(thumb_cmd, capture_output=True, timeout=15)
    if not os.path.exists(thumb_path):
        # Video 1 saniyeden kısaysa 0. saniyeden al
        thumb_cmd[3] = "00:00:00"
        subprocess.run(thumb_cmd, capture_output=True, timeout=15)

    gc.collect()
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
