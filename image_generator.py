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
