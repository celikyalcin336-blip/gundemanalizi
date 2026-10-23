import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import config

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Evrensel Yazı Tipleri (Windows & Render Linux)
BASE_DIR = os.path.dirname(__file__)
FONT_BOLD_PATH = os.path.join(BASE_DIR, "assets", "fonts", "segoeuib.ttf")
FONT_REGULAR_PATH = os.path.join(BASE_DIR, "assets", "fonts", "segoeui.ttf")

if not os.path.exists(FONT_BOLD_PATH):
    FONT_BOLD_PATH = "C:\\Windows\\Fonts\\segoeuib.ttf"
if not os.path.exists(FONT_REGULAR_PATH):
    FONT_REGULAR_PATH = "C:\\Windows\\Fonts\\segoeui.ttf"

def get_font(path: str, size: int):
    try:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    for fallback in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", "arial.ttf"]:
        try:
            return ImageFont.truetype(fallback, size)
        except Exception:
            continue
    return ImageFont.load_default()

def download_and_prepare(url: str, target_size: tuple) -> Image.Image:
    """
    Görseli orijinal kaynağından indirir, RGB moduna çevirir ve
    en-boy oranını bozmadan merkezden keserek (center crop) hedef boyuta tam oturtur.
    """
    if not url or not url.startswith("http"):
        return None
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200 or len(resp.content) < 1000:
            return None
        
        raw = Image.open(BytesIO(resp.content))
        if raw.mode in ("RGBA", "LA") or (raw.mode == "P" and "transparency" in raw.info):
            bg = Image.new("RGB", raw.size, (255, 255, 255))
            if raw.mode != "RGBA":
                raw = raw.convert("RGBA")
            bg.paste(raw, mask=raw.split()[3])
            img = bg
        else:
            img = raw.convert("RGB")
            
        if img.width < 180 or img.height < 140:
            return None

        fitted = ImageOps.fit(img, target_size, method=Image.Resampling.LANCZOS)
        return fitted
    except Exception as e:
        print(f"Görsel hazırlama hatası ({url[:45]}...): {e}")
        return None

def get_image_signature(url: str) -> str:
    """Aynı görselin farklı boyutlardaki kopyalarını (örn: 1200x675 ve 800x450) tespit etmek için dosya adının kökünü çıkarır."""
    import re, urllib.parse
    path = urllib.parse.urlparse(url).path
    fname = path.split('/')[-1]
    base = re.sub(r'[-_xX]?\d{3,4}x\d{3,4}.*$', '', fname)
    clean = re.sub(r'\.[a-zA-Z0-9]+$', '', base)
    return clean.lower()

def is_valid_secondary_editorial_image(url: str, primary_url: str) -> bool:
    """
    İkinci görselin ana görsel ile aynı olmamasını, bir widget/logo/ikon/reklam olmamasını
    ve aynı haberin editoryal fotoğraf klasöründen gelen gerçek bir ikinci kare olmasını denetler.
    """
    if not url or not url.startswith("http"):
        return False
    if url == primary_url:
        return False

    import urllib.parse
    p_url = urllib.parse.urlparse(primary_url)
    s_url = urllib.parse.urlparse(url)
    
    # 1. Aynı haber CDN veya kaynak alan adı (domain) olmalı
    if p_url.netloc != s_url.netloc:
        return False
        
    p_path = p_url.path
    s_path = s_url.path
    
    # 2. Dosya adını ve kökünü al
    p_fname = p_path.split('/')[-1]
    s_fname = s_path.split('/')[-1]
    
    # Boyut takılarını temizle
    import re
    p_base = re.sub(r'[-_xX]?\d{3,4}x\d{3,4}.*$', '', p_fname).split('.')[0].lower()
    s_base = re.sub(r'[-_xX]?\d{3,4}x\d{3,4}.*$', '', s_fname).split('.')[0].lower()
    
    # Aynı görselin farklı boyutuysa reddet
    if p_base == s_base:
        return False
        
    lower = url.lower()
    # PNG'ler, oto boyutlandırmalar veya ikon/avatar uzantıları elensin
    if lower.endswith(".png") or "auto.jpg" in lower or "-400x400" in lower or "-300x300" in lower or "-200x200" in lower or "avatar" in lower or "icon" in lower:
        return False

    # 3. Aynı haber klasöründe veya galeri yapısında olmalı (Farklı haberlerin veya kenar çubuğunun fotoğraflarını engeller)
    p_dir = '/'.join(p_path.split('/')[:-1])
    s_dir = '/'.join(s_path.split('/')[:-1])
    if p_dir != s_dir:
        return False
        
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, stream=True)
        if resp.status_code != 200:
            return False
        content = resp.raw.read(300000)
        img = Image.open(BytesIO(content))
        w, h = img.size
        # Gerçek haber görseli en az 550px genişliğinde ve yatay formatta olmalıdır
        if w >= 550 and (w / h) >= 1.15:
            return True
        return False
    except Exception:
        return False

def create_single_news_photo(img_url: str, output_path: str, width: int = 1280, height: int = 720) -> str:
    """
    Tekil haber fotoğrafını 16:9 HD (1280x720) formatında, pürüzsüz ve jilet gibi keskin üretir.
    Üzerinde yazı veya yapay karartma YOKTUR; salt editoryal basın fotoğrafıdır.
    """
    target_size = (width, height)
    img = download_and_prepare(img_url, target_size)
    if img is None:
        return None
        
    sharp = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=115, threshold=3))
    sharp.save(output_path, "JPEG", quality=95)
    return output_path

def create_dual_news_collage(url1: str, url2: str, output_path: str, width: int = 1280, height: int = 720, border_width: int = 4) -> str:
    """
    Rakiplerin ve önde gelen Telegram kanallarının (ANA HABER, Asayiş Berkemal) kullandığı
    yan yana 2'li kolaj (Side-by-Side Split Grid):
    - Sol: Görsel 1 (Dikey merkez kırpma)
    - Sağ: Görsel 2 (Dikey merkez kırpma)
    - Ortada: 4px temiz beyaz ayırıcı çizgi
    - Kesinlikle üzerinde yazı veya leke yoktur.
    """
    half_width = (width - border_width) // 2
    slot_size = (half_width, height)
    
    img1 = download_and_prepare(url1, slot_size)
    img2 = download_and_prepare(url2, slot_size)
    
    if img1 is None and img2 is None:
        return None
    if img1 is None:
        return create_single_news_photo(url2, output_path, width, height)
    if img2 is None:
        return create_single_news_photo(url1, output_path, width, height)
        
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    canvas.paste(img1, (0, 0))
    canvas.paste(img2, (half_width + border_width, 0))
    
    sharp = canvas.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
    sharp.save(output_path, "JPEG", quality=95)
    return output_path

def create_default_brand_backdrop(output_path: str, title: str = "", category: str = "GÜNDEM", width: int = 1280, height: int = 720) -> str:
    """Haberde hiç görsel bulunamazsa profesyonel antrasit/lacivert stüdyo arka planı oluşturur."""
    canvas = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(canvas)
    
    for y in range(height):
        r = int(15 + (35 - 15) * (y / height))
        g = int(23 + (25 - 23) * (y / height))
        b = int(42 + (55 - 42) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            wm = Image.open(logo_path).convert("RGBA")
            wm_size = 240
            wm = wm.resize((wm_size, wm_size), Image.Resampling.LANCZOS)
            canvas.paste(wm, ((width - wm_size) // 2, (height - wm_size) // 2), mask=wm)
        except Exception:
            pass
            
    canvas.save(output_path, "JPEG", quality=95)
    return output_path

def create_news_visual(candidate_urls: list, output_filename: str, title: str = "", category: str = "Gündem") -> str:
    """
    Sitenin ana sayfası ve Telegram kanalı için nihai haber görselini üretir:
    - 2 veya daha fazla gerçek editoryal haber fotoğrafı varsa -> Yan yana 2'li Split Kolaj
    - 1 görsel varsa -> 16:9 HD kristal netliğinde tekil fotoğraf
    - Hiç görsel yoksa -> Şık editoryal marka tuvali
    """
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    cleaned_urls = []
    for u in candidate_urls:
        if u and u.startswith("http") and u not in cleaned_urls:
            cleaned_urls.append(u)
            
    if not cleaned_urls:
        return create_default_brand_backdrop(output_path, title, category)
        
    primary_url = cleaned_urls[0]
    
    # Gerçek ikincil editoryal görsel ara
    secondary_url = None
    if len(cleaned_urls) >= 2:
        for u in cleaned_urls[1:]:
            if is_valid_secondary_editorial_image(u, primary_url):
                secondary_url = u
                break
                
    if secondary_url:
        res = create_dual_news_collage(primary_url, secondary_url, output_path)
        if res and os.path.exists(res):
            return res
            
    # Tekil net haber fotoğrafı
    res = create_single_news_photo(primary_url, output_path)
    if res and os.path.exists(res):
        return res
        
    return create_default_brand_backdrop(output_path, title, category)

def wrap_text(text: str, font, max_width: int) -> list:
    """Metni verilen piksel genişliğini aşmayacak şekilde satırlara böler."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = ' '.join(current + [word])
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(' '.join(current))
            current = [word]
    if current:
        lines.append(' '.join(current))
    return lines

def create_story_card(candidate_urls: list, output_filename: str, title: str = "", category: str = "Gündem") -> str:
    """
    Instagram ve Facebook Hikayeleri (Story - 9:16 dikey format 1080x1920) için
    haber başlığı, kategori rozeti, Gündem Analizi logosu ve web sitesi yönlendirmesi
    içeren, televizyon bülteni kalitesinde özel dikey hikaye kartı üretir.
    Çıplak veya yazısız görsel paylaşımını kesin olarak engeller.
    """
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    width, height = 1080, 1920
    canvas = Image.new("RGB", (width, height), (10, 13, 20))
    draw = ImageDraw.Draw(canvas)

    cleaned_urls = [u for u in candidate_urls if u and u.startswith("http")]
    primary_url = cleaned_urls[0] if cleaned_urls else None

    # 1. Sinematik Arka Plan (Görsel varsa bulanık derinlik, yoksa premium koyu degrade)
    photo_raw = None
    if primary_url:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(primary_url, headers=headers, timeout=8)
            if resp.status_code == 200 and len(resp.content) > 1000:
                raw_img = Image.open(BytesIO(resp.content)).convert("RGB")
                photo_raw = raw_img
                # Arka plan için bulanık versiyon
                bg_blur = ImageOps.fit(raw_img, (width, height), method=Image.Resampling.LANCZOS)
                bg_blur = bg_blur.filter(ImageFilter.GaussianBlur(radius=45))
                # Koyu renk filtre katmanı ekle
                dark_overlay = Image.new("RGBA", (width, height), (10, 13, 20, 205))
                bg_blur.paste(dark_overlay, (0, 0), mask=dark_overlay)
                canvas.paste(bg_blur, (0, 0))
        except Exception as e:
            print(f"Hikaye arka plan hazırlama hatası: {e}")

    if photo_raw is None:
        for y in range(height):
            ratio = y / height
            r = int(10 + (22 - 10) * ratio)
            g = int(13 + (28 - 13) * ratio)
            b = int(20 + (42 - 20) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Üst Header (Logo + Marka + Kategori Rozeti)
    logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo = logo.resize((90, 90), Image.Resampling.LANCZOS)
            canvas.paste(logo, (70, 95), mask=logo)
        except Exception:
            pass

    f_brand = get_font(FONT_BOLD_PATH, 38)
    draw.text((180, 98), "GÜNDEM ANALİZİ", font=f_brand, fill=(255, 255, 255))
    f_sub = get_font(FONT_REGULAR_PATH, 18)
    draw.text((182, 148), "DOĞRU HABER • TARAFSIZ ANALİZ", font=f_sub, fill=(148, 163, 184))

    # Kategori Rozeti (Sağ üst)
    cat_text = category.upper() if category else "GÜNDEM"
    f_cat = get_font(FONT_BOLD_PATH, 22)
    cat_bbox = f_cat.getbbox(cat_text)
    cat_w = cat_bbox[2] - cat_bbox[0] + 36
    cat_h = 44
    cat_x = width - 70 - cat_w
    cat_y = 118
    draw.rounded_rectangle([cat_x, cat_y, cat_x + cat_w, cat_y + cat_h], radius=12, fill=(220, 38, 38))
    draw.text((cat_x + 18, cat_y + 10), cat_text, font=f_cat, fill=(255, 255, 255))

    # 3. Ana Haber Görseli (Ortalanmış 940x680 HD Çerçeve)
    slot_w, slot_h = 940, 680
    frame_x, frame_y = 70, 230
    if photo_raw is not None:
        try:
            cropped_photo = ImageOps.fit(photo_raw, (slot_w, slot_h), method=Image.Resampling.LANCZOS)
            cropped_photo = cropped_photo.filter(ImageFilter.UnsharpMask(radius=1.0, percent=110, threshold=3))
            canvas.paste(cropped_photo, (frame_x, frame_y))
            # Çerçeve kenarlık çizgisi
            draw.rectangle([frame_x, frame_y, frame_x + slot_w, frame_y + slot_h], outline=(51, 65, 85), width=2)
        except Exception as e:
            print(f"Hikaye fotoğraf yerleştirme hatası: {e}")
    else:
        draw.rounded_rectangle([frame_x, frame_y, frame_x + slot_w, frame_y + slot_h], radius=16, fill=(18, 23, 34), outline=(51, 65, 85), width=2)

    # 4. Haber Başlığı Kartı (940x670 Özel Okuma Alanı)
    card_x1, card_y1 = 70, 955
    card_x2, card_y2 = 1010, 1640
    draw.rounded_rectangle([card_x1, card_y1, card_x2, card_y2], radius=24, fill=(15, 20, 30), outline=(31, 41, 61), width=2)

    # Kırmızı vurgu etiketi
    draw.rounded_rectangle([100, 990, 270, 1032], radius=8, fill=(220, 38, 38))
    f_badge = get_font(FONT_BOLD_PATH, 20)
    draw.text((112, 998), "⚡ SON GELİŞME", font=f_badge, fill=(255, 255, 255))

    # Başlık Metni (Büyük, yüksek kontrastlı ve okunaklı)
    clean_title = title.strip()
    f_title = get_font(FONT_BOLD_PATH, 44)
    lines = wrap_text(clean_title, f_title, 850)
    
    # Çok uzun başlıklarda taşmayı önlemek için fontu küçült
    if len(lines) > 5:
        f_title = get_font(FONT_BOLD_PATH, 38)
        lines = wrap_text(clean_title, f_title, 850)

    y_text = 1065
    for line in lines[:5]:
        draw.text((100, y_text), line, font=f_title, fill=(255, 255, 255))
        y_text += 58

    # 5. Alt Aksiyon / Web Yönlendirme Butonu (CTA)
    cta_box = [100, 1705, 980, 1805]
    draw.rounded_rectangle(cta_box, radius=50, fill=(220, 38, 38))
    f_cta = get_font(FONT_BOLD_PATH, 30)
    cta_text = "🌐 Haberin Detayları: www.gündemanalizi.com.tr"
    c_bbox = f_cta.getbbox(cta_text)
    c_w = c_bbox[2] - c_bbox[0]
    draw.text((cta_box[0] + (880 - c_w) // 2, cta_box[1] + 32), cta_text, font=f_cta, fill=(255, 255, 255))

    # Alt yönlendirme fısıltısı
    f_hint = get_font(FONT_REGULAR_PATH, 20)
    hint_text = "👆 Yukarı kaydırın veya profildeki linke tıklayın"
    h_bbox = f_hint.getbbox(hint_text)
    h_w = h_bbox[2] - h_bbox[0]
    draw.text(((width - h_w) // 2, 1835), hint_text, font=f_hint, fill=(148, 163, 184))

    canvas.save(output_path, "JPEG", quality=95)
    return output_path

def generate_news_card(title: str, source: str, image_url: str = None, tag: str = "TÜRKİYE GÜNDEMİ", output_filename: str = "post.jpg") -> str:
    """Geriye uyumluluk fonksiyonu."""
    urls = [image_url] if image_url else []
    return create_news_visual(urls, output_filename, title=title, category=tag)

if __name__ == "__main__":
    test_urls = [
        "https://images.ntv.com.tr/images/iStock-148421596-889339.jpg?width=1200",
        "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2496000/berlin-sonbahar-aa-2497786_2.jpg"
    ]
    res = create_news_visual(test_urls, "test_dual.jpg")
    print(f"Oluşturulan görsel: {res}")
