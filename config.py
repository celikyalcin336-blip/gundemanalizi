import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
try:
    if os.path.exists(env_path):
        load_dotenv(env_path)
except Exception:
    pass

# Meta (Facebook & Instagram Reels & Hikayeler) Ayarları (Ortam değişkeninden okunur)
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()

FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "").strip() or "1237983366054395"  # Gündem Analizi Facebook Sayfası (688+ Takipçi)
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip() or "17841437413417808"  # @gundem_analiz Instagram Hesabı

# Otomatik Hikaye (Story) Sıklığı (Saat cinsinden, varsayılan: 4 saatte 1)
STORY_COOLDOWN_HOURS = float(os.getenv("STORY_COOLDOWN_HOURS", "4.0"))

# Resmi Sosyal Medya Kanal Linkleri
TELEGRAM_CHANNEL_URL = "https://t.me/gundemanalizi"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDjlhj8qIzpKkjeWz08"
TIKTOK_URL = "https://www.tiktok.com/@gundemanalizi"
INSTAGRAM_URL = "https://www.instagram.com/gundem_analiz/"
FACEBOOK_URL = "https://www.facebook.com/gundemanalizi"
X_URL = "https://x.com/gndmanalizi"
YOUTUBE_URL = "https://www.youtube.com/@g%C3%BCndemanalizi"
X_COOLDOWN_MINUTES = float(os.getenv("X_COOLDOWN_MINUTES", "45.0"))  # Saatte 1 tweet (Tam saat başı kilit tamponu: 45 dk)

# Telegram Bildirim Ayarları (Ortam değişkeninden okunur)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003631115657").strip() or "-1003631115657"
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "1934709259")  # Yalçın Çelik Özel Chat

# Marka ve Web Sitesi Bilgisi
BRAND_NAME = "GÜNDEM ANALİZİ"
SITE_URL = "https://xn--gndemanalizi-dlb.com.tr"
# Instagram gibi servislerin videoyu indirebilmesi için ASCII (punycode) adres
PUBLIC_MEDIA_BASE = os.getenv("PUBLIC_MEDIA_BASE", "https://xn--gndemanalizi-dlb.com.tr")

# AI (Google Gemini) Ayarı
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Resim Barındırma
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")

# RSS Kaynakları (Otomobil, Teknoloji, Ekonomi, Sağlık ve Sıcak Gündem Odaklı Yüksek Gelirli Medya Havuzu)
RSS_FEEDS = [
    # 🚗 OTOMOBİL & KAMPANYALAR (Yüksek Tık & Gelir Değeri)
    {
        "name": "Motor1",
        "url": "https://tr.motor1.com/rss/news/all/",
        "category": "Otomobil"
    },
    {
        "name": "Otomobil Haber",
        "url": "https://www.otomobilhaber.com.tr/feed/",
        "category": "Otomobil"
    },
    {
        "name": "Ensonhaber",
        "url": "https://www.ensonhaber.com/rss/otomobil.xml",
        "category": "Otomobil"
    },
    {
        "name": "ShiftDelete",
        "url": "https://shiftdelete.net/otomobil/feed",
        "category": "Otomobil"
    },
    {
        "name": "NTV",
        "url": "https://www.ntv.com.tr/otomobil.rss",
        "category": "Otomobil"
    },
    {
        "name": "Otoajanda",
        "url": "https://www.otoajanda.com/feed/",
        "category": "Otomobil"
    },

    # 🚀 TEKNOLOJİ & YAPAY ZEKA (Yüksek Tık & Gelir Değeri)
    {
        "name": "Webtekno",
        "url": "https://www.webtekno.com/rss.xml",
        "category": "Teknoloji"
    },
    {
        "name": "ShiftDelete",
        "url": "https://shiftdelete.net/feed",
        "category": "Teknoloji"
    },
    {
        "name": "Log",
        "url": "https://www.log.com.tr/feed/",
        "category": "Teknoloji"
    },
    {
        "name": "CHIP Online",
        "url": "https://www.chip.com.tr/rss/",
        "category": "Teknoloji"
    },

    # 🤖 ÖZEL YAPAY ZEKA (AI) & İNOVASYON
    {
        "name": "ShiftDelete",
        "url": "https://shiftdelete.net/yapay-zeka/feed",
        "category": "Teknoloji"
    },
    {
        "name": "Webrazzi",
        "url": "https://webrazzi.com/kategori/yapay-zeka/feed/",
        "category": "Teknoloji"
    },
    {
        "name": "E-Girişim",
        "url": "https://egirisim.com/feed/",
        "category": "Teknoloji"
    },

    # 💰 EKONOMİ, FİNANS & TÜKETİCİ (Yüksek Tık & Gelir Değeri)
    {
        "name": "Bloomberg HT",
        "url": "https://www.bloomberght.com/rss",
        "category": "Ekonomi"
    },
    {
        "name": "Ekonomim",
        "url": "https://www.ekonomim.com/rss",
        "category": "Ekonomi"
    },
    {
        "name": "Mynet",
        "url": "https://finans.mynet.com/haber/rss/kategori/ekonomi/",
        "category": "Ekonomi"
    },
    {
        "name": "Ensonhaber",
        "url": "https://www.ensonhaber.com/rss/ekonomi.xml",
        "category": "Ekonomi"
    },
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/ekonomi_articles.rss",
        "category": "Ekonomi"
    },

    # 🩺 SAĞLIK & YAŞAM (Yüksek Tık & Gelir Değeri)
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/saglik_articles.rss",
        "category": "Sağlık"
    },
    {
        "name": "NTV",
        "url": "https://www.ntv.com.tr/saglik.rss",
        "category": "Sağlık"
    },
    {
        "name": "Habertürk",
        "url": "https://www.haberturk.com/rss/kategori/saglik.xml",
        "category": "Sağlık"
    },
    {
        "name": "Cumhuriyet",
        "url": "https://www.cumhuriyet.com.tr/rss/saglik.xml",
        "category": "Sağlık"
    },
    {
        "name": "CNN Türk",
        "url": "https://www.cnnturk.com/feed/rss/saglik/news",
        "category": "Sağlık"
    },

    # 🎓 EĞİTİM, MEB & SINAVLAR (Yüksek Tık & Aile/Öğrenci Trafiği)
    {
        "name": "Anadolu Ajansı",
        "url": "https://www.aa.com.tr/tr/rss/default?cat=egitim",
        "category": "Eğitim"
    },
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/egitim_articles.rss",
        "category": "Eğitim"
    },
    {
        "name": "NTV",
        "url": "https://www.ntv.com.tr/egitim.rss",
        "category": "Eğitim"
    },
    {
        "name": "Sabah",
        "url": "https://www.sabah.com.tr/rss/egitim.xml",
        "category": "Eğitim"
    },
    {
        "name": "Cumhuriyet",
        "url": "https://www.cumhuriyet.com.tr/rss/egitim.xml",
        "category": "Eğitim"
    },

    # 🌍 DÜNYA & DIŞ POLİTİKA (Küresel Sıcak Gelişmeler & Krizler)
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/dunya_articles.rss",
        "category": "Dünya"
    },
    {
        "name": "NTV",
        "url": "https://www.ntv.com.tr/dunya.rss",
        "category": "Dünya"
    },
    {
        "name": "Habertürk",
        "url": "https://www.haberturk.com/rss/kategori/dunya.xml",
        "category": "Dünya"
    },
    {
        "name": "Ensonhaber",
        "url": "https://www.ensonhaber.com/rss/dunya.xml",
        "category": "Dünya"
    },

    # ⚽ SPOR, SÜPER LİG & AVRUPA (Yüksek Anlık Okuyucu Trafiği)
    {
        "name": "A Spor",
        "url": "https://www.aspor.com.tr/rss/anasayfa.xml",
        "category": "Spor"
    },
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/spor_articles.rss",
        "category": "Spor"
    },
    {
        "name": "Fotomaç",
        "url": "https://www.fotomac.com.tr/rss/anasayfa.xml",
        "category": "Spor"
    },
    {
        "name": "Habertürk",
        "url": "https://www.haberturk.com/rss/kategori/spor.xml",
        "category": "Spor"
    },

    # 🚨 SICAK GÜNDEM & SON DAKİKA
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/gundem_articles.rss",
        "category": "Gündem"
    },
    {
        "name": "Habertürk",
        "url": "https://www.haberturk.com/rss/kategori/gundem.xml",
        "category": "Gündem"
    },
    {
        "name": "Ensonhaber",
        "url": "https://www.ensonhaber.com/rss/ensonhaber.xml",
        "category": "Gündem"
    },
    {
        "name": "NTV",
        "url": "https://www.ntv.com.tr/gundem.rss",
        "category": "Gündem"
    }
]

# Çalışma Modu (True: Simülasyon, False: Canlı Facebook Paylaşımı)
# Not: Telegram her iki durumda da anlık haberleri iletir!
DRY_RUN = os.getenv("DRY_RUN", "False").lower() in ("true", "1", "yes")

# Kontrol Sıklığı (Dakika)
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "40"))
