# 🤖 Otonom Sosyal Medya Haber Botu (Facebook & Instagram)

Türkiye gündemindeki en son haberleri güvenilir RSS kaynaklarından (Google News TR, TRT Haber, BBC Türkçe, NTV) toplayan, yapay zekâ destekli açıklama ve etiketler hazırlayan, Instagram & Facebook için profesyonel haber kartları üreten ve Meta Graph API üzerinden otomatik paylaşım yapan otonom bot.

---

## 📁 Proje Dosya Yapısı

* **[`main.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/main.py):** Sistemin ana orkestratörü. Haberleri çeker, işler, görseli üretir ve paylaşımı tetikler.
* **[`news_fetcher.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/news_fetcher.py):** Güncel Türkiye haberlerini RSS beslemelerinden çeker ve filtreler.
* **[`image_generator.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/image_generator.py):** Instagram (1:1 / 1080x1080) formatında yüksek kaliteli haber kartı görseli oluşturur.
* **[`ai_writer.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/ai_writer.py):** Sosyal medyaya uygun dikkat çekici metinler, özetler ve hashtag'ler yazar (Gemini AI destekli + fallback şablonlu).
* **[`meta_poster.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/meta_poster.py):** Meta Graph API üzerinden Facebook Sayfasına ve Instagram Profesyonel hesabına gönderi yayınlar.
* **[`database.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/database.py):** Paylaşılan haberleri SQLite veritabanında tutar (aynı haberin tekrar paylaşılmasını engeller).
* **[`config.py`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/config.py):** Ayarlar, kaynak listesi ve ortam değişkenleri.
* **[`.env`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/.env):** API anahtarları ve gizli bilgiler (şablon için [`.env.example`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/.env.example)).

---

## 🚀 Hızlı Başlangıç

### 1. Test / Simülasyon Çalıştırması (Dry Run)
Varsayılan olarak `DRY_RUN=True` ayarlanmıştır. Bu modda sistem hiçbir API anahtarı gerektirmeden çalışır; gerçek haberleri çeker, görselleri üretir (`output/` klasörüne kaydeder) ve paylaşım simülasyonunu ekrana basar:

```bash
# Tek bir haber paylaşımını test etmek için:
python main.py --count 1

# Sürekli döngüde (her 15 dakikada bir) test etmek için:
python main.py --loop
```

---

## 🔑 Canlı Moda Geçiş (Meta API Kurulumu)

Canlı paylaşıma geçmek için [`.env.example`](file:///C:/Users/celik/.gemini/antigravity/scratch/social-news-bot/.env.example) dosyasını `.env` olarak kopyalayın ve aşağıdaki bilgileri girin:

### 1. Facebook Sayfası & Instagram Hesabı Bağlantısı
1. Bir **Facebook Sayfası** oluşturun.
2. Instagram hesabınızı **İşletme (Business) veya İçerik Üretici (Creator)** hesabına çevirin.
3. Instagram hesabınızı Facebook Sayfanıza bağlayın (*Facebook Sayfa Ayarları > Bağlı Hesaplar > Instagram*).

### 2. Meta for Developers Token Alma
1. [Meta for Developers](https://developers.facebook.com/) adresine gidin ve bir Uygulama (App) oluşturun (*Tür: "Diğer / Other"*).
2. **Graph API Explorer** aracını açın.
3. Uygulamanızı ve Facebook Sayfanızı seçin.
4. Gerekli izinleri ekleyin:
   * `pages_show_list`
   * `pages_read_engagement`
   * `pages_manage_posts`
   * `instagram_basic`
   * `instagram_content_publish`
5. Üretilen **Page Access Token**'ı ve **Sayfa ID / Instagram Hesap ID** değerlerini `.env` dosyasına yazın:

```env
META_PAGE_ACCESS_TOKEN=EAA...
FACEBOOK_PAGE_ID=123456789...
INSTAGRAM_ACCOUNT_ID=987654321...
DRY_RUN=False
```
