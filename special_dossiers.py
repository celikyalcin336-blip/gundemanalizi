# -*- coding: utf-8 -*-
"""
Gündem Analizi — Yalçın Çelik İmzalı Özel Dosya Yayınlayıcısı (special_dossiers.py)

Doğrudan TÜİK, Resmî Gazete, TCMB, ÖSYM ve ilgili bakanlıkların resmi birincil verilerinden
hazırlanan, 'Yalçın Çelik' imzalı (Person schema) özel dosyaları veritabanına tek seferlik kaydeder.
"""
import os
from typing import Dict, List


SPECIAL_DOSSIERS: List[Dict] = [
    {
        "key": "special_dossier_2026_11_19_emekli_4ay",
        "title": "TÜİK 4 aylık enflasyon verisiyle Ocak 2027 emekli ve memur maaş tablosu: Kök aylıklarda kesinleşen hesap",
        "summary": "TÜİK'in Temmuz–Ekim 2026 dönemine ait dört aylık TÜFE verileriyle SSK ve Bağ-Kur emeklileri için yüzde 8,29 artış şimdiden oluştu; memur ve memur emeklilerinde ise toplu sözleşmeye eklenecek enflasyon farkı netleşmeye başladı.",
        "category": "Ekonomi",
        "source": "Gündem Analizi Özel",
        "image_filename": "post_ozel_20261119_tl2.jpg",
        "image_candidates": [
            "https://imgrosetta.mynet.com.tr/file/27130997/27130997-1200x675.jpg",
            "https://imgrosetta.mynet.com.tr/file/2317400/2317400-1200x675.jpg",
        ],
        "content": """<p class="lead font-medium text-lg text-slate-900 mb-6">Türkiye İstatistik Kurumu'nun (TÜİK) açıkladığı Temmuz, Ağustos, Eylül ve Ekim 2026 Tüketici Fiyat Endeksi (TÜFE) bültenleriyle birlikte, milyonlarca emekli ve kamu görevlisinin Ocak 2027 maaş artışını belirleyecek altı aylık hesabın ilk dört basamağı resmen tamamlandı. Dört aylık kümülatif TÜFE artışı yüzde 8,29'a ulaşırken, nihai oran 3 Aralık'ta açıklanacak Kasım ve Ocak başında ilan edilecek Aralık verileriyle kesinleşecek.</p>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Dört Aylık Resmi TÜFE Serisi ve Bileşik Hesap</h3>
<p class="text-slate-800 leading-relaxed mb-4">5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu uyarınca SSK (4A) ve Bağ-Kur (4B) emekli aylıkları, bir önceki altı aylık dönemde gerçekleşen TÜFE değişim oranı kadar doğrudan artırılıyor. Aylık enflasyon oranları aritmetik olarak toplanmıyor; her ayın endeks artışı bir önceki ayın üzerine bileşik çarpımla ekleniyor.</p>
<p class="text-slate-800 leading-relaxed mb-4">TÜİK bültenlerine göre 2026'nın ikinci yarısında aylık TÜFE artışı Temmuz'da yüzde 1,78, Ağustos'ta yüzde 1,84, Eylül'de yüzde 1,84 ve Ekim'de yüzde 2,58 olarak kaydedildi. Bu dört verinin bileşik çarpımı sonucunda SSK ve Bağ-Kur emeklileri için Kasım ve Aralık verileri henüz eklenmeden yüzde 8,29'luk artış tabanı oluşmuş durumda.</p>

<div class="overflow-x-auto my-5"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">
<thead><tr class="bg-slate-100 text-slate-900 font-bold">
<th class="p-2.5 border border-slate-200">Dönem (2026)</th>
<th class="p-2.5 border border-slate-200">Aylık Resmi TÜFE</th>
<th class="p-2.5 border border-slate-200">Bileşik Kümülatif Artış</th>
</tr></thead>
<tbody>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Temmuz 2026</td><td class="p-2.5 border border-slate-200">%1,78</td><td class="p-2.5 border border-slate-200">%1,78</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Ağustos 2026</td><td class="p-2.5 border border-slate-200">%1,84</td><td class="p-2.5 border border-slate-200">%3,65</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Eylül 2026</td><td class="p-2.5 border border-slate-200">%1,84</td><td class="p-2.5 border border-slate-200">%5,56</td></tr>
<tr class="border-b border-slate-200 bg-red-50/60"><td class="p-2.5 border border-slate-200 font-bold text-slate-900">Ekim 2026 (4 Aylık Toplam)</td><td class="p-2.5 border border-slate-200 font-bold">%2,58</td><td class="p-2.5 border border-slate-200 font-extrabold text-red-600">%8,29</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 text-slate-600">Kasım 2026</td><td class="p-2.5 border border-slate-200 text-slate-500" colspan="2">3 Aralık 2026'da TÜİK tarafından açıklanacak</td></tr>
<tr><td class="p-2.5 border border-slate-200 text-slate-600">Aralık 2026 (6 Aylık Kesinleşme)</td><td class="p-2.5 border border-slate-200 text-slate-500" colspan="2">Ocak 2027 başında TÜİK bülteniyle kesinleşecek</td></tr>
</tbody></table></div>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Memur ve Memur Emeklilerinde Enflasyon Farkı Eşiği Aşıldı</h3>
<p class="text-slate-800 leading-relaxed mb-4">Kamu görevlileri ve memur emeklileri (4C) maaş artışlarını 8. Dönem Toplu Sözleşme hükümlerine göre alıyor. 2026 yılının ikinci altı ayı için memurlara Temmuz ayında yüzde 7 toplu sözleşme zammı uygulanmıştı; dört aylık TÜFE'nin yüzde 8,29'a çıkmasıyla yüzde 7'lik eşik aşıldı ve şimdiden yaklaşık yüzde 1,21 oranında enflasyon farkı doğdu.</p>
<p class="text-slate-800 leading-relaxed mb-4">Ocak 2027 döneminde memur maaşlarına, altı aylık kesinleşen enflasyon farkının üzerine yüzde 5 oranındaki yeni dönem toplu sözleşme zammı bileşik olarak eklenecek. Sadece mevcut dört aylık veri baz alındığında dahi memur ve memur emeklileri için oluşan kümülatif artış oranı yüzde 6,27 seviyesine ulaşmış bulunuyor; Kasım ve Aralık enflasyonu bu oranı doğrudan yukarı taşıyacak.</p>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Kök Maaşlara Göre 4 Aylık Kesinleşen Tutar Tablosu ve Taban Aylık Detayı</h3>
<p class="text-slate-800 leading-relaxed mb-4">Emeklilerin en sık karıştırdığı nokta, yüzdesel enflasyon zammının bankaya yatan tamamlanmış tutara değil, e-Devlet hizmet dökümünde yer alan <strong>kök aylığa</strong> (ve yüzde 4–5 ek ödemeye) uygulanmasıdır. 31 Temmuz 2026 tarihli Resmî Gazete'de yayımlanan kanunla en düşük emekli aylığı 23.552 TL olarak uygulanıyor. Kök maaşı düşük olan bir emeklinin zam sonrası aylığı 23.552 TL'nin altında kalırsa Hazine desteğiyle yine taban aylığa tamamlanıyor; taban aylığın artırılması ise Ocak ayında TBMM'den geçecek yeni bir yasal düzenleme gerektiriyor.</p>

<div class="overflow-x-auto my-5"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">
<thead><tr class="bg-slate-100 text-slate-900 font-bold">
<th class="p-2.5 border border-slate-200">Mevcut Kök Aylık (Ek Ödeme Dahil)</th>
<th class="p-2.5 border border-slate-200">4 Aylık Kesinleşen Artış (%8,29)</th>
<th class="p-2.5 border border-slate-200">4 Aylık Hesaba Göre Yeni Tutar</th>
<th class="p-2.5 border border-slate-200">Uygulama Notu</th>
</tr></thead>
<tbody>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">20.000 TL</td><td class="p-2.5 border border-slate-200">+1.658 TL</td><td class="p-2.5 border border-slate-200">21.658 TL</td><td class="p-2.5 border border-slate-200 text-slate-600">Taban aylık (23.552 TL) koruması devrede</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">23.552 TL</td><td class="p-2.5 border border-slate-200">+1.952 TL</td><td class="p-2.5 border border-slate-200 font-bold">25.504 TL</td><td class="p-2.5 border border-slate-200 text-slate-600">Kök maaşı tabana eşit olanlar</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">28.000 TL</td><td class="p-2.5 border border-slate-200">+2.321 TL</td><td class="p-2.5 border border-slate-200 font-bold">30.321 TL</td><td class="p-2.5 border border-slate-200 text-slate-600">Kasım ve Aralık verisi eklenecek</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">35.000 TL</td><td class="p-2.5 border border-slate-200">+2.902 TL</td><td class="p-2.5 border border-slate-200 font-bold">37.902 TL</td><td class="p-2.5 border border-slate-200 text-slate-600">Kasım ve Aralık verisi eklenecek</td></tr>
<tr><td class="p-2.5 border border-slate-200 font-semibold">45.000 TL</td><td class="p-2.5 border border-slate-200">+3.731 TL</td><td class="p-2.5 border border-slate-200 font-bold">48.731 TL</td><td class="p-2.5 border border-slate-200 text-slate-600">Kasım ve Aralık verisi eklenecek</td></tr>
</tbody></table></div>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Aynı Dönemde Netleşen İkinci Kritik Veri: Yüzde 27,83 Yeniden Değerleme Oranı</h3>
<p class="text-slate-800 leading-relaxed mb-4">TÜİK'in Ekim 2026 bülteni yalnızca emekli ve memur hesabını değil, 2027 yılı vergi ve harç takvimini de belirledi. Vergi Usul Kanunu uyarınca Ekim ayı itibarıyla 12 aylık ortalama Yurt İçi Üretici Fiyat Endeksi (Yİ-ÜFE) artışı olan <strong>yüzde 27,83</strong>, 2027 yılı yeniden değerleme oranı olarak kayda geçti. Cumhurbaşkanı'nın indirim veya artırım yetkisini kullanmadığı kalemlerde 1 Ocak 2027'den itibaren pasaport, ehliyet, kimlik harçları, Motorlu Taşıtlar Vergisi (MTV), trafik cezaları ve gelir vergisi dilimleri bu oranda güncellenecek.</p>
<p class="text-slate-800 leading-relaxed mb-4">Önümüzdeki takvimde ilk kritik eşik <strong>3 Aralık 2026</strong>'da açıklanacak Kasım ayı enflasyonu ve Aralık ayı başında toplanacak Asgari Ücret Tespit Komisyonu olacak; altı aylık kesin maaş zam tablosu ise Ocak ayının ilk haftasında TÜİK'in Aralık bülteniyle tamamlanacak.</p>""",
    }
]


def seed_special_dossiers():
    """Tanımlı özel dosyaları (henüz kaydedilmemişse) gerçek görseliyle veritabanına ve Telegram'a kaydeder."""
    import config
    import database
    import image_generator
    import telegram_notifier

    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    for item in SPECIAL_DOSSIERS:
        key = item["key"]
        if database.get_setting(key, "") == "1":
            continue
        fname = item["image_filename"]
        asset_copy = os.path.join(assets_dir, fname)
        out_copy = os.path.join(output_dir, fname)
        visual_path = ""
        if os.path.exists(asset_copy) and os.path.getsize(asset_copy) >= 8000:
            import shutil
            shutil.copyfile(asset_copy, out_copy)
            visual_path = out_copy
        else:
            visual_path = image_generator.create_news_visual(
                candidate_urls=item.get("image_candidates") or [],
                output_filename=fname,
                title=item["title"],
                category=item["category"],
            ) or ""
        if not visual_path or not os.path.exists(visual_path):
            print(f"⚠️ [Özel Dosya] Görsel hazırlanamadı: {key}")
            continue

        slug, created = database.save_article(
            title=item["title"],
            summary=item["summary"],
            content=item["content"],
            image_path=visual_path,
            source=item["source"],
            category=item["category"],
            return_status=True,
        )
        if slug:
            database.set_setting(key, "1")
            if created:
                site_url = f"{config.SITE_URL}/haber/{slug}"
                print(f"✅ [Özel Dosya Yayında - Yalçın Çelik] {site_url}")
                try:
                    tg_caption = (
                        f"✍️ ÖZEL DOSYA | {item['title']}\n\n"
                        "— TÜİK'in Temmuz–Ekim 4 aylık TÜFE verisiyle SSK ve Bağ-Kur emeklilerinde %8,29 artış tabanı oluştu.\n"
                        "— Memur ve memur emeklilerinde %7 eşiği aşılarak enflasyon farkı devreye girdi.\n"
                        "— Kök maaşlara göre kuruşu kuruşuna 4 aylık hesap tablosu ve 2027 yeniden değerleme (%27,83) takvimi."
                    )
                    telegram_notifier.send_telegram_news(visual_path, tg_caption, site_url)
                except Exception as _te:
                    print(f"Özel dosya Telegram uyarısı: {_te}")
