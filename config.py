import os
from dotenv import load_dotenv

load_dotenv()

# Meta (Facebook) Ayarları
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# Telegram Bildirim Ayarları
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8882292811:AAHo8qyRE8NgFl3JU3HOgcBkTNOrf0x82B4")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003631115657")  # Gündem Analizi Kanalı
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "1934709259")  # Yalçın Çelik Özel Chat

# Marka ve Web Sitesi Bilgisi
BRAND_NAME = "GÜNDEM ANALİZİ"
SITE_URL = os.getenv("SITE_URL", "https://gundemanalizi.com.tr")

# AI (Google Gemini) Ayarı
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Resim Barındırma
IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")

# RSS Kaynakları (Hepsi yüksek çözünürlüklü haber fotoğraflı kaynaklar)
RSS_FEEDS = [
    {
        "name": "TRT Haber",
        "url": "https://www.trthaber.com/gundem_articles.rss"
    },
    {
        "name": "Habertürk Gündem",
        "url": "https://www.haberturk.com/rss/kategori/gundem.xml"
    },
    {
        "name": "Hürriyet Gündem",
        "url": "https://www.hurriyet.com.tr/rss/gundem"
    },
    {
        "name": "NTV Gündem",
        "url": "https://www.ntv.com.tr/gundem.rss"
    }
]

# Çalışma Modu (True: Simülasyon, False: Canlı Facebook Paylaşımı)
# Not: Telegram her iki durumda da anlık haberleri iletir!
DRY_RUN = os.getenv("DRY_RUN", "True").lower() in ("true", "1", "yes")

# Kontrol Sıklığı (Dakika)
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "20"))
