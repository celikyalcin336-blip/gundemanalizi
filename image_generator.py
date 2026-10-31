import re
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
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.google.com/"
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
    sharp.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
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
    sharp.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
    return output_path

def search_editorial_web_image(title: str, category: str = "") -> str:
    """Haberin konusuyla doğrudan ilgili gerçek, yüksek çözünürlüklü ve yatay basın fotoğrafı arar."""
    try:
        import urllib.parse
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        clean_q = re.sub(r'[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ\s]', ' ', title)
        stop_words = {'haber', 'haberi', 'haberleri', 'son', 'dakika', 'flas', 'flaş', 'iste', 'işte', 'acikladi', 'açıkladı', 'mesaji', 'mesajı', 'dedi', 've', 'ile', 'icin', 'için', 'bir', 'bu'}
        words = [w for w in clean_q.split() if len(w) > 2 and w.lower() not in stop_words]
        
        queries = []
        if len(words) >= 3:
            queries.append(" ".join(words[:4]))
        if len(words) >= 2:
            queries.append(" ".join(words[:2]))
        if words:
            queries.append(words[0])
            
        for q in queries:
            url = f'https://www.bing.com/images/search?q={urllib.parse.quote(q)}&first=1'
            r = requests.get(url, headers=headers, timeout=5)
            murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+?\.(?:jpg|jpeg|png|webp))&quot;', r.text)
            if not murls:
                murls = re.findall(r'"murl":"(https?://[^"]+?\.(?:jpg|jpeg|png|webp))"', r.text)
                
            for candidate in murls:
                if any(b in candidate.lower() for b in ['stock', 'alamy', 'shutterstock', 'dreamstime', 'vector', 'icon']):
                    continue
                return candidate
    except Exception as e:
        print(f"Editoryal görsel arama hatası: {e}")
    return None

def create_thematic_editorial_card(output_path: str, title: str = "", category: str = "Gündem", width: int = 1280, height: int = 720) -> str:
    """Haber görseli bulunamadığında boş gri kutu yerine TV bülteni tarzında şık, tipografik son dakika haber kartı üretir."""
    import textwrap
    cat_lower = category.lower()
    
    if "spor" in cat_lower:
        c1, c2 = (180, 25, 25), (15, 23, 42)
        badge_bg, badge_txt = (220, 38, 38), (255, 255, 255)
    elif "eko" in cat_lower:
        c1, c2 = (16, 120, 75), (15, 23, 42)
        badge_bg, badge_txt = (16, 185, 129), (255, 255, 255)
    elif "tekno" in cat_lower:
        c1, c2 = (67, 56, 202), (15, 23, 42)
        badge_bg, badge_txt = (99, 102, 241), (255, 255, 255)
    elif "sağlık" in cat_lower or "saglik" in cat_lower:
        c1, c2 = (14, 116, 144), (15, 23, 42)
        badge_bg, badge_txt = (6, 182, 212), (255, 255, 255)
    elif "oto" in cat_lower:
        c1, c2 = (190, 24, 93), (15, 23, 42)
        badge_bg, badge_txt = (244, 63, 94), (255, 255, 255)
    else:
        c1, c2 = (220, 38, 38), (15, 23, 42)
        badge_bg, badge_txt = (239, 68, 68), (255, 255, 255)
        
    canvas = Image.new("RGB", (width, height), c2)
    draw = ImageDraw.Draw(canvas)
    
    for y in range(height):
        factor = (y / height) ** 1.3
        r = int(c1[0] * (1 - factor) + c2[0] * factor)
        g = int(c1[1] * (1 - factor) + c2[1] * factor)
        b = int(c1[2] * (1 - factor) + c2[2] * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    card_margin = 60
    card_box = [(card_margin, card_margin), (width - card_margin, height - card_margin)]
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle(card_box, radius=24, fill=(15, 23, 42, 190), outline=(255, 255, 255, 30), width=2)
    canvas.paste(overlay, (0, 0), mask=overlay)
    
    draw = ImageDraw.Draw(canvas)
    badge_font = get_font(FONT_BOLD_PATH, 26)
    badge_text = f"● {category.upper()}"
    b_left = card_margin + 50
    b_top = card_margin + 50
    b_padding_x = 24
    
    draw.rounded_rectangle([(b_left, b_top), (b_left + 220, b_top + 46)], radius=23, fill=badge_bg)
    draw.text((b_left + b_padding_x, b_top + 8), badge_text, font=badge_font, fill=badge_txt)
    
    logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            wm = Image.open(logo_path).convert("RGBA")
            wm_size = 90
            wm = wm.resize((wm_size, wm_size), Image.Resampling.LANCZOS)
            canvas.paste(wm, (width - card_margin - wm_size - 40, card_margin + 35), mask=wm)
        except Exception:
            pass

    clean_title = (title or "").strip()
    clean_title = re.sub(r'^(?:SON DAKİKA|FLAŞ|GALATASARAY HABERİ|BEŞİKTAŞ HABERİ|FENERBAHÇE HABERİ):\s*', '', clean_title, flags=re.I).strip()
    
    title_font = get_font(FONT_BOLD_PATH, 44)
    wrapped_lines = textwrap.wrap(clean_title, width=38)
    
    text_y = b_top + 85
    for line in wrapped_lines[:4]:
        draw.text((b_left, text_y), line, font=title_font, fill=(255, 255, 255))
        text_y += 62
        
    sub_font = get_font(FONT_REGULAR_PATH, 22)
    draw.text((b_left, height - card_margin - 55), "gündemanalizi.com.tr | Doğru Haber • Tarafsız Analiz", font=sub_font, fill=(148, 163, 184))
    
    canvas.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
    return output_path

def create_default_brand_backdrop(output_path: str, title: str = "", category: str = "GÜNDEM", width: int = 1280, height: int = 720) -> str:
    """Geriye uyumluluk için şık tipografik editoryal kart fonksiyonunu çağırır."""
    return create_thematic_editorial_card(output_path, title, category, width, height)

def create_news_visual(candidate_urls: list, output_filename: str, title: str = "", category: str = "Gündem") -> str:
    """
    Sitenin ana sayfası ve Telegram kanalı için nihai haber görselini üretir:
    1. 2 veya daha fazla gerçek editoryal haber fotoğrafı varsa -> Yan yana 2'li Split Kolaj
    2. 1 görsel varsa -> 16:9 HD kristal netliğinde tekil fotoğraf
    3. Hiç görsel yoksa -> Otomatik olarak konunun gerçek editoryal basın fotoğrafını arar ve indirir
    4. Ağ engeli varsa -> TV bülteni kalitesinde tipografik özel haber kartı üretir (Asla boş kutu bırakmaz)
    """
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    cleaned_urls = []
    for u in candidate_urls:
        if u and u.startswith("http") and u not in cleaned_urls:
            cleaned_urls.append(u)
            
    # 1. Aday görseller varsa: Konunun tekil, orijinal ve kristal netliğindeki 16:9 HD basın görselini üret
    # (Asla farklı konuları birbirine karıştıran yapay kolaj yapılmaz!)
    if cleaned_urls:
        for u in cleaned_urls:
            res = create_single_news_photo(u, output_path)
            if res and os.path.exists(res):
                return res

    # 2. Görsel yoksa veya indirilemediyse: Haberin konusuna özel gerçek basın fotoğrafı ara
    if title:
        print(f"🔍 Habere özel görsel aranıyor: {title[:40]}...")
        web_img = search_editorial_web_image(title, category)
        if web_img:
            print(f"📸 Gerçek haber görseli bulundu: {web_img[:60]}...")
            res = create_single_news_photo(web_img, output_path)
            if res and os.path.exists(res):
                return res

    # 3. Son çare: TV bülteni tarzında şık, tipografik son dakika haber kartı üret (Asla boş logo kutusu olmaz!)
    return create_thematic_editorial_card(output_path, title, category)


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

    canvas.save(output_path, "JPEG", quality=82, optimize=True, progressive=True)
    return output_path

def generate_news_card(title: str, source: str, image_url: str = None, tag: str = "TÜRKİYE GÜNDEMİ", output_filename: str = "post.jpg") -> str:
    """Geriye uyumluluk fonksiyonu."""
    urls = [image_url] if image_url else []
    return create_news_visual(urls, output_filename, title=title, category=tag)



def create_x_editorial_card(image_input: str, title: str, category: str = "Gündem", output_path: str = None) -> str:
    """
    X (Twitter) için BPT/Pusholder kalitesinde 16:9 HD (1200x675) editoryal haber kartı üretir:
    1. Haberin orijinal görselini kullanır (merkez crop ile HD 1200x675).
    2. Alt yarıya sinematik koyu degrade çeker (yazı cam gibi parlar).
    3. Sol üste şık kategori rozeti basar (🔴 EKONOMİ, 🚀 TEKNOLOJİ vb.).
    4. Cevabı doğrudan veren manşet başlığını büyük beyaz puntolarla yazar.
    5. Alt banda 'GÜNDEM ANALİZİ' ve sağ köşeye 'Takip Et: @gndmanalizi' çağrısını ekler.
    """
    width, height = 1200, 675
    canvas = Image.new("RGB", (width, height), (15, 20, 26))

    raw_img = None
    if image_input:
        if os.path.exists(image_input):
            try:
                raw_img = Image.open(image_input).convert("RGB")
            except Exception as e:
                print(f"Görsel açılamadı: {e}")
        elif str(image_input).startswith("http"):
            try:
                resp = requests.get(image_input, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200 and len(resp.content) > 1000:
                    raw_img = Image.open(BytesIO(resp.content)).convert("RGB")
            except Exception as e:
                print(f"Görsel indirilemedi: {e}")

    if raw_img is not None:
        photo = ImageOps.fit(raw_img, (width, height), method=Image.Resampling.LANCZOS)
        photo = photo.filter(ImageFilter.UnsharpMask(radius=1.0, percent=105, threshold=3))
        canvas.paste(photo, (0, 0))
    else:
        # Fotoğraf bulunamazsa koyu şık lacivert degrade arka plan
        for y in range(height):
            ratio = y / float(height)
            r = int(14 + (24 - 14) * ratio)
            g = int(20 + (36 - 20) * ratio)
            b = int(32 + (55 - 32) * ratio)
            draw_bg = ImageDraw.Draw(canvas)
            draw_bg.line([(0, y), (width, y)], fill=(r, g, b))

    # 1. Sinematik Koyu Gradyan Katmanı (Yazının arkasında cam gibi netlik)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    start_grad = int(height * 0.28)
    grad_h = height - start_grad

    for y in range(start_grad, height):
        ratio = max(0.0, min(1.0, (y - start_grad) / float(grad_h)))
        alpha = int(246 * (ratio ** 1.25))
        draw_ov.line([(0, y), (width, y)], fill=(8, 12, 18, alpha))

    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB"), (0, 0))
    draw = ImageDraw.Draw(canvas)

    # 2. Sol Üst: Kategori Rozeti
    category_emojis = {
        "Ekonomi": "📊", "Gündem": "🚨", "Teknoloji": "🚀", "Otomobil": "🚗",
        "Dünya": "🌍", "Sağlık": "🩺", "Spor": "⚽", "Eğitim": "🎓"
    }
    cat_clean = category.strip().capitalize() if category else "Gündem"
    cat_emoji = category_emojis.get(cat_clean, "🔴")
    cat_text = f"{cat_emoji} {cat_clean.upper()}"

    cat_font = get_font(FONT_BOLD_PATH, 22)
    cat_bbox = cat_font.getbbox(cat_text)
    cat_w = cat_bbox[2] - cat_bbox[0] + 32
    cat_h = 44
    draw.rounded_rectangle([50, 45, 50 + cat_w, 45 + cat_h], radius=10, fill=(220, 38, 38))
    draw.text((66, 54), cat_text, font=cat_font, fill=(255, 255, 255))

    # 3. Manşet Başlığı (Cevabı veren net başlık)
    clean_title = title.strip()
    clean_title = re.sub(r'\s*-\s*[A-Za-z0-9ğüşıöçĞÜŞİÖÇ\s\.]+$', '', clean_title)

    # Dinamik font boyutu seçimi (Başlığın uzunluğuna göre 46, 42 veya 38 px)
    if len(clean_title) > 95:
        font_size = 38
        line_height = 48
    elif len(clean_title) > 65:
        font_size = 42
        line_height = 54
    else:
        font_size = 46
        line_height = 58

    title_font = get_font(FONT_BOLD_PATH, font_size)

    words = clean_title.split()
    lines = []
    curr = []
    for w in words:
        test_line = " ".join(curr + [w])
        bbox = title_font.getbbox(test_line)
        if (bbox[2] - bbox[0]) <= (width - 120):
            curr.append(w)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    # En fazla 3 satır izin ver (taşmayı önlemek için)
    if len(lines) > 3:
        lines = lines[:2] + [lines[2] + "..."]

    total_text_h = len(lines) * line_height
    start_y = height - 90 - total_text_h

    for line in lines:
        # İnce siyah gölge (Her türlü arka planda okunabilirlik)
        draw.text((52, start_y + 2), line, font=title_font, fill=(0, 0, 0))
        # Beyaz Manşet Metni
        draw.text((50, start_y), line, font=title_font, fill=(255, 255, 255))
        start_y += line_height

    # 4. Alt Bilgi & Takip Şeridi
    bar_y = height - 55
    bar_font = get_font(FONT_BOLD_PATH, 22)

    # Kırmızı marka noktası + GÜNDEM ANALİZİ
    draw.ellipse([50, bar_y + 4, 64, bar_y + 18], fill=(239, 68, 68))
    draw.text((75, bar_y), "GÜNDEM ANALİZİ", font=bar_font, fill=(255, 255, 255))

    # Takip Et Çağrısı (Sağ alt modern hap rozet)
    cta_text = "Takip Et: @gndmanalizi"
    cta_bbox = bar_font.getbbox(cta_text)
    cta_w = cta_bbox[2] - cta_bbox[0] + 32
    cta_h = 40
    draw.rounded_rectangle([width - 50 - cta_w, bar_y - 6, width - 50, bar_y - 6 + cta_h], radius=10, fill=(30, 41, 59))
    draw.text((width - 50 - cta_w + 16, bar_y), cta_text, font=bar_font, fill=(56, 189, 248))

    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, f"x_card_{int(time.time())}.jpg")

    canvas.save(output_path, "JPEG", quality=92, optimize=True)
    return output_path

if __name__ == "__main__":
    test_urls = [
        "https://images.ntv.com.tr/images/iStock-148421596-889339.jpg?width=1200",
        "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/2496000/berlin-sonbahar-aa-2497786_2.jpg"
    ]
    res = create_news_visual(test_urls, "test_dual.jpg")
    print(f"Oluşturulan görsel: {res}")
