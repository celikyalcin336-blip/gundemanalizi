import os
import requests
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Windows Yazı Tipleri (Türkçe karakter desteği tam olan sistem fontları)
FONT_BOLD_PATH = "C:\\Windows\\Fonts\\segoeuib.ttf"
FONT_REGULAR_PATH = "C:\\Windows\\Fonts\\segoeui.ttf"

def get_font(path: str, size: int):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """Metni belirtilen piksel genişliğine sığacak şekilde satırlara böler."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]

        if line_width > max_width:
            current_line.pop()
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    return lines

def create_gradient(width: int, height: int, start_alpha: int = 40, end_alpha: int = 240) -> Image.Image:
    """Aşağı doğru koyulaşan şık bir karartma katmanı oluşturur."""
    gradient = Image.new("RGBA", (width, height), color=0)
    draw = ImageDraw.Draw(gradient)
    for y in range(height):
        # Üstten alta doğru artan opaklık
        ratio = y / height
        alpha = int(start_alpha + (end_alpha - start_alpha) * (ratio ** 1.5))
        draw.line([(0, y), (width, y)], fill=(15, 20, 28, alpha))
    return gradient

def generate_news_card(title: str, source: str, image_url: str = None, tag: str = "TÜRKİYE GÜNDEMİ", output_filename: str = "post.jpg") -> str:
    """
    Instagram ve Facebook için 1080x1350 (4:5 dikey) veya 1080x1080 boyutunda profesyonel haber görseli üretir.
    """
    width = 1080
    height = 1080  # Kare format (Facebook ve Instagram için ideal uyumluluk)

    # 1. Taban Görseli (Varsa haber resmi, yoksa koyu şık arkaplan)
    base_image = None
    if image_url:
        try:
            resp = requests.get(image_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                raw_img = Image.open(BytesIO(resp.content)).convert("RGBA")
                # Görseli en-boy oranını koruyarak kırpıp ortala
                img_ratio = raw_img.width / raw_img.height
                target_ratio = width / height
                if img_ratio > target_ratio:
                    new_width = int(height * img_ratio)
                    raw_img = raw_img.resize((new_width, height), Image.Resampling.LANCZOS)
                    crop_x = (new_width - width) // 2
                    base_image = raw_img.crop((crop_x, 0, crop_x + width, height))
                else:
                    new_height = int(width / img_ratio)
                    raw_img = raw_img.resize((width, new_height), Image.Resampling.LANCZOS)
                    crop_y = (new_height - height) // 2
                    base_image = raw_img.crop((0, crop_y, width, crop_y + height))
        except Exception as e:
            print(f"Haber görseli indirilemedi, varsayılan arka plan kullanılıyor: {e}")

    if base_image is None:
        # Görsel yoksa kırmızı-antrasit şık stüdyo arka planı ve ortada büyük logo filigranı
        base_image = Image.new("RGBA", (width, height), (15, 20, 30, 255))
        bg_draw = ImageDraw.Draw(base_image)
        # Kırmızı ve lacivert degrade dokusu
        for y in range(height):
            r = int(25 + (60 - 25) * (y / height))
            g = int(10 + (15 - 10) * (y / height))
            b = int(20 + (35 - 20) * (y / height))
            bg_draw.line([(0, y), (width, y)], fill=(r, g, b, 255))
        
        # Ortada büyük logo filigranı
        logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
        if os.path.exists(logo_path):
            try:
                watermark = Image.open(logo_path).convert("RGBA")
                wm_size = 380
                watermark = watermark.resize((wm_size, wm_size), Image.Resampling.LANCZOS)
                # Dairesel maske
                circle_m = Image.new("L", (wm_size, wm_size), 0)
                m_draw = ImageDraw.Draw(circle_m)
                m_draw.ellipse((0, 0, wm_size, wm_size), fill=120)  # Yarı saydam
                pos_x = (width - wm_size) // 2
                pos_y = (height - wm_size) // 3
                base_image.paste(watermark, (pos_x, pos_y), mask=circle_m)
            except Exception as e:
                print(f"Filigran ekleme hatası: {e}")

    # 2. Karartma Katmanı Ekle (Metinlerin rahat okunması için)
    gradient = create_gradient(width, height, start_alpha=80, end_alpha=245)
    composed = Image.alpha_composite(base_image, gradient)

    draw = ImageDraw.Draw(composed)

    # 3. Üst Etiket (Badge: Örn: 🔴 TÜRKİYE GÜNDEMİ)
    font_badge = get_font(FONT_BOLD_PATH, 28)
    badge_text = f"●  {tag.upper()}"
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_w = badge_bbox[2] - badge_bbox[0]
    badge_h = badge_bbox[3] - badge_bbox[1]

    badge_x = 60
    badge_y = 60
    padding_x = 24
    padding_y = 12

    # Kırmızı/Bordo arka plan kutucuğu
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w + padding_x * 2, badge_y + badge_h + padding_y * 2],
        radius=8,
        fill=(220, 38, 38, 240)  # Canlı Kırmızı
    )
    draw.text((badge_x + padding_x, badge_y + padding_y - 2), badge_text, fill=(255, 255, 255), font=font_badge)

    # 4. Ana Başlık Metni
    font_title = get_font(FONT_BOLD_PATH, 52)
    max_text_width = width - 120  # Sağdan soldan 60px boşluk
    lines = wrap_text(title, font_title, max_text_width, draw)

    # Başlığın yüksekliğini hesapla
    line_height = 68
    total_text_h = len(lines) * line_height

    # Başlığı alt kısma konumlandır (Instagram haber kartı estetiği)
    text_start_y = height - total_text_h - 160

    for i, line in enumerate(lines):
        y = text_start_y + (i * line_height)
        # Metin gölgesi
        draw.text((62, y + 2), line, fill=(0, 0, 0, 180), font=font_title)
        # Asıl metin (Beyaz)
        draw.text((60, y), line, fill=(255, 255, 255), font=font_title)

    # 5. Alt Bilgi Çubuğu (Kaynak ve Tarih)
    font_meta = get_font(FONT_REGULAR_PATH, 24)
    current_date = datetime.now().strftime("%d.%m.%Y • %H:%M")
    footer_text = f"Kaynak: {source}   |   {current_date}"
    draw.text((60, height - 80), footer_text, fill=(200, 205, 215), font=font_meta)

    # Sağ alt köşe marka etiketi (GÜNDEM ANALİZİ)
    font_brand = get_font(FONT_BOLD_PATH, 26)
    brand_text = f"@{config.BRAND_NAME.replace(' ', '').lower()}"
    draw.text((width - 270, height - 80), brand_text, fill=(255, 215, 0), font=font_brand)

    # Logo varsa (assets/logo.png), sağ üste şık dairesel rozet olarak ekle
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
    if os.path.exists(logo_path):
        try:
            logo_size = 130
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            # Dairesel maske oluştur (köşeler şeffaf olsun)
            circle_mask = Image.new("L", (logo_size, logo_size), 0)
            mask_draw = ImageDraw.Draw(circle_mask)
            mask_draw.ellipse((0, 0, logo_size, logo_size), fill=255)
            
            composed.paste(logo_img, (width - logo_size - 60, 50), mask=circle_mask)
        except Exception as e:
            print(f"Logo eklenirken hata: {e}")

    # 6. Kaydet (JPEG olarak RGB modunda)
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    final_rgb = composed.convert("RGB")
    final_rgb.save(output_path, "JPEG", quality=95)

    return output_path

if __name__ == "__main__":
    test_title = "Hazine ve Maliye Bakanlığı Yeni Ekonomik Tedbirleri ve Enflasyon Hedeflerini Açıkladı"
    test_img = "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/1666000/meclis-aa-1667780.jpg"
    out = generate_news_card(test_title, "TRT Haber", image_url=test_img, tag="SON DAKİKA", output_filename="test_card.jpg")
    print(f"Görsel başarıyla oluşturuldu: {out}")
