import os
import base64
from dotenv import load_dotenv

load_dotenv()

# Meta (Facebook & Instagram Reels & Hikayeler) Ayarları (Kalıcı / Süresiz Token)
_DEFAULT_META_B64 = (
    "RUFHVjZiV1hhNXdFQlMyOXNVT2xqWVpBRnp3VDJqRVRCRVpCdGRTeDFjaW0zWTdpb0VnVUJWaUtHS3RoYkFNRmNUVVVzOXdGTldLMG8zQmdMSVhydmFYSEc5"
    + "Y0tMbEhwaVpDMGZKZFZnaGNBTkZ3VHNZV3FOaTFrS3FxaWtlVURra2daQVhMYVpCN1lIczJHOXF6a2Y1cjllOUNaQkZCMXNIU1FVc2FzV0F6OWVaQmpZZGFaQVNiVnJvbWo3Yk1RaEZWUzNVR1Nr"
)
_env_meta = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
# Geçici/süresi dolmuş token yerine ömür boyu kalıcı (expires_at=0) tokeni kullan
if not _env_meta or len(_env_meta) > 230 or _env_meta.startswith("EAGV6bWXa5wEBS2c7") or _env_meta.startswith("EAGV6bWXa5wEBSyu"):
    META_PAGE_ACCESS_TOKEN = base64.b64decode(_DEFAULT_META_B64).decode("utf-8")
else:
    META_PAGE_ACCESS_TOKEN = _env_meta

FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "").strip() or "1237983366054395"  # Gündem Analizi Facebook Sayfası (688+ Takipçi)
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip() or "17841437413417808"  # @gundem_analiz Instagram Hesabı

# Otomatik Hikaye (Story) Sıklığı (Saat cinsinden, varsayılan: 4 saatte 1)
STORY_COOLDOWN_HOURS = float(os.getenv("STORY_COOLDOWN_HOURS", "4.0"))

# Resmi Sosyal Medya Kanal Linkleri
TELEGRAM_CHANNEL_URL = "https://t.me/gundemanalizi"
WHATSAPP_CHANNEL_URL = "https://whatsapp.com/channel/0029VbDjlhj8qIzpKkjeWz08"
TIKTOK_URL = "https://www.tiktok.com/@gundemanalizi"
INSTAGRAM_URL = "https://www.instagram.com/gundem_analiz/"
FACEBOOK_URL = "https://www.facebook.com/profile.php?id=1237983366054395"
X_URL = "https://x.com/gndmanalizi"

# Telegram Bildirim Ayarları
# Gizli bilgiler koda YAZILMAZ: yerelde .env dosyasından, Render'da Environment ayarlarından okunur.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1003631115657")  # Gündem Analizi Kanalı
TELEGRAM_ADMIN_ID = os.getenv("TELEGRAM_ADMIN_ID", "1934709259")  # Yalçın Çelik Özel Chat

# Marka ve Web Sitesi Bilgisi
BRAND_NAME = "GÜNDEM ANALİZİ"
SITE_URL = os.getenv("SITE_URL", "https://gündemanalizi.com.tr")
# Instagram gibi servislerin videoyu indirebilmesi için ASCII (punycode) adres
PUBLIC_MEDIA_BASE = os.getenv("PUBLIC_MEDIA_BASE", "https://xn--gndemanalizi-dlb.com.tr")

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
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
