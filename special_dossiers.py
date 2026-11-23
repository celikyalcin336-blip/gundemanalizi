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
        "tg_bullets": [
            "TÜİK'in Temmuz–Ekim 4 aylık TÜFE verisiyle SSK ve Bağ-Kur emeklilerinde %8,29 artış tabanı oluştu.",
            "Memur ve memur emeklilerinde %7 eşiği aşılarak enflasyon farkı devreye girdi.",
            "Kök maaşlara göre kuruşu kuruşuna 4 aylık hesap tablosu ve 2027 yeniden değerleme (%27,83) takvimi.",
        ],
    },
    {
        "key": "special_dossier_2026_11_23_asgari_sgk",
        "title": "Aralık 2026 Asgari Ücret Tespit Komisyonu öncesi resmi bordro tablosu: İşveren maliyeti, SGK borçlanması ve kıdem hesabı",
        "summary": "Aralık ayında toplanacak Asgari Ücret Tespit Komisyonu öncesinde yürürlükteki 33.030 TL brüt asgari ücretin sektörel işveren maliyeti, 31 Aralık 2026 son tarihli doğum ve askerlik borçlanması tutarları ile kıdem tazminatı geçiş hesabı netleşti.",
        "category": "Ekonomi",
        "source": "Gündem Analizi Özel",
        "image_filename": "post_ozel_20261123_asgari.jpg",
        "image_candidates": [
            "https://trthaberstatic.cdn.wp.trt.com.tr/resimler/1476000/para-odeme-1476750.jpg",
        ],
        "tg_bullets": [
            "33.030 TL brüt / 28.075,50 TL net asgari ücrette imalat (5 puan) ve hizmet sektörü (2 puan) işveren maliyeti farkı.",
            "31 Aralık 2026 mesai bitimine kadar doğum (%32) ve askerlik (%45) borçlanması yapanların mevcut tabandan yararlanma hakkı.",
            "GSS primi (1.981,80 TL), işsizlik ödeneği sınırları ve yıl sonu kıdem tazminatı tavan geçişinde dikkat edilecek kurallar.",
        ],
        "content": """<p class="lead font-medium text-lg text-slate-900 mb-6">Çalışma ve Sosyal Güvenlik Bakanlığı'nın çağrısıyla Aralık 2026'da çalışmalarına başlayacak 15 üyeli Asgari Ücret Tespit Komisyonu yalnızca doğrudan asgari ücretle çalışan milyonlarca işçinin 2027 maaşını değil; işveren SGK maliyetlerinden doğum ve askerlik borçlanmasına, Genel Sağlık Sigortası (GSS) priminden işsizlik ödeneği tavanına kadar tüm sosyal güvenlik parametrelerini yeniden belirleyecek. 1 Ocak 2027 güncellemesi yürürlüğe girmeden önce mevcut yasal tablodaki kuruşu kuruşuna tutarlar ve 31 Aralık son başvuru eşikleri hem çalışanlar hem de işverenler için kritik önem taşıyor.</p>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Yürürlükteki Resmi Bordro Dağılımı ve Sektörel İşveren Maliyeti</h3>
<p class="text-slate-800 leading-relaxed mb-4">4857 sayılı İş Kanunu'nun 39. maddesi kapsamında 2026 yılı boyunca uygulanan aylık brüt asgari ücret <strong>33.030,00 TL</strong> (günlük brüt 1.101,00 TL) düzeyinde bulunuyor. Çalışan bordrosunda bu tutar üzerinden yüzde 14 SGK işçi primi (4.624,20 TL) ve yüzde 1 işsizlik sigortası işçi payı (330,30 TL) olmak üzere toplam 4.954,50 TL yasal kesinti yapılıyor. 193 sayılı Gelir Vergisi Kanunu'nun 23/18. maddesindeki istisna uyarınca gelir ve damga vergisi kesilmediğinden çalışanın eline geçen net asgari ücret <strong>28.075,50 TL</strong> oluyor.</p>
<p class="text-slate-800 leading-relaxed mb-4">İşveren cephesinde ise 7566 sayılı Kanun düzenlemeleri sonrasında SGK prim teşviki sektöre göre ayrışmış durumda. Düzenli prim ödeyen ve borcu bulunmayan imalat sektörü işyerlerinde 5 puanlık Hazine indirimi korunurken, hizmet ve ticaret başta olmak üzere imalat dışı sektörlerde prim indirimi 2 puan olarak uygulanıyor. Ayrıca şartları sağlayan özel sektör işverenlerine sigortalı başına aylık <strong>1.270,00 TL</strong> asgari ücret desteği SGK prim borcundan mahsup ediliyor.</p>

<div class="overflow-x-auto my-5"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">
<thead><tr class="bg-slate-100 text-slate-900 font-bold">
<th class="p-2.5 border border-slate-200">İşyeri Statüsü (2026 Yürürlükteki Tablo)</th>
<th class="p-2.5 border border-slate-200">Brüt Ücret</th>
<th class="p-2.5 border border-slate-200">SGK İşveren Payı</th>
<th class="p-2.5 border border-slate-200">İşsizlik İşveren (%2)</th>
<th class="p-2.5 border border-slate-200">Toplam İşveren Maliyeti</th>
</tr></thead>
<tbody>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">İmalat Sektörü (5 Puan İndirimli • %16,75)</td><td class="p-2.5 border border-slate-200">33.030,00 TL</td><td class="p-2.5 border border-slate-200">5.532,53 TL</td><td class="p-2.5 border border-slate-200">660,60 TL</td><td class="p-2.5 border border-slate-200 font-bold text-slate-900">39.223,13 TL</td></tr>
<tr class="border-b border-slate-200 bg-red-50/60"><td class="p-2.5 border border-slate-200 font-bold text-slate-900">Hizmet ve Diğer Sektörler (2 Puan İndirimli • %19,75)</td><td class="p-2.5 border border-slate-200">33.030,00 TL</td><td class="p-2.5 border border-slate-200">6.523,43 TL</td><td class="p-2.5 border border-slate-200">660,60 TL</td><td class="p-2.5 border border-slate-200 font-extrabold text-red-600">40.214,03 TL</td></tr>
<tr><td class="p-2.5 border border-slate-200 font-semibold">Teşviksiz / İndirimsiz İşyeri (%21,75)</td><td class="p-2.5 border border-slate-200">33.030,00 TL</td><td class="p-2.5 border border-slate-200">7.184,03 TL</td><td class="p-2.5 border border-slate-200">660,60 TL</td><td class="p-2.5 border border-slate-200 font-bold">40.874,63 TL</td></tr>
</tbody></table></div>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">31 Aralık 2026 Son Tarihli Başvurular: Doğum ve Askerlik Borçlanmasında Oran Farkı</h3>
<p class="text-slate-800 leading-relaxed mb-4">Emeklilik için prim günü eksiği bulunan sigortalılar açısından yılın son beş haftası doğrudan maliyet avantajı barındırıyor. 5510 sayılı Kanun'un 41. maddesi uyarınca hizmet borçlanması tutarları, başvuru tarihindeki günlük brüt asgari ücrete (1.101,00 TL) endeksli olarak hesaplanıyor; 1 Ocak 2027 sabahı yeni asgari ücret yürürlüğe girdiğinde borçlanma tarifesi de aynı oranda artacak.</p>
<p class="text-slate-800 leading-relaxed mb-4">Burada en önemli yasal ayrım 7566 sayılı Kanun ile getirilen prim oranlarında görülüyor: <strong>Doğum borçlanmasında</strong> yüzde 32 oranı korunurken, <strong>askerlik ve diğer hizmet borçlanmalarında</strong> hesaplama oranı yüzde 45 olarak uygulanıyor. 31 Aralık 2026 mesai bitimine kadar e-Devlet kapısı veya SGK il müdürlükleri üzerinden başvuru kaydı oluşturan sigortalılar, tebliğ edilen tutarı yasal süresi içinde ödemek şartıyla 2026 taban fiyatını sabitleyebiliyor.</p>

<div class="overflow-x-auto my-5"><table class="w-full text-left border-collapse border border-slate-200 text-xs sm:text-sm">
<thead><tr class="bg-slate-100 text-slate-900 font-bold">
<th class="p-2.5 border border-slate-200">Sosyal Güvenlik Parametresi</th>
<th class="p-2.5 border border-slate-200">Yasal Formül / Oran</th>
<th class="p-2.5 border border-slate-200">31 Aralık 2026'ya Kadar Geçerli Tutar</th>
</tr></thead>
<tbody>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Doğum Borçlanması (En Düşük)</td><td class="p-2.5 border border-slate-200">Günlük brütün %32'si (352,32 TL/gün)</td><td class="p-2.5 border border-slate-200 font-bold">1 çocuk (720 gün): 253.670,40 TL</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Askerlik Borçlanması (En Düşük)</td><td class="p-2.5 border border-slate-200">Günlük brütün %45'i (495,45 TL/gün)</td><td class="p-2.5 border border-slate-200 font-bold">6 ay: 89.181,00 TL • 18 ay: 267.543,00 TL</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">Genel Sağlık Sigortası (60/g GSS Primi)</td><td class="p-2.5 border border-slate-200">Aylık brütün %6'sı</td><td class="p-2.5 border border-slate-200">Aylık 1.981,80 TL</td></tr>
<tr class="border-b border-slate-200"><td class="p-2.5 border border-slate-200 font-semibold">İşsizlik Ödeneği Alt ve Üst Sınırı (Net)</td><td class="p-2.5 border border-slate-200">Brütün %40–%80'i (damga vergisi hariç)</td><td class="p-2.5 border border-slate-200">En düşük 13.111,72 TL • En yüksek 26.223,44 TL</td></tr>
<tr><td class="p-2.5 border border-slate-200 font-semibold">SGK Prime Esas Kazanç Tavanı</td><td class="p-2.5 border border-slate-200">Aylık brüt asgari ücretin 9 katı</td><td class="p-2.5 border border-slate-200 font-bold">297.270,00 TL</td></tr>
</tbody></table></div>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Yıl Sonu İşten Çıkış ve Emeklilikte Kıdem Tazminatı Hesabı</h3>
<p class="text-slate-800 leading-relaxed mb-4">Aralık ve Ocak ayları, emeklilik dilekçesi verecek veya kıdem tazminatına hak kazanarak işten ayrılacak çalışanlar için iki ayrı hesap doğuruyor. Asgari ücretle çalışan bir işçide her tam çalışma yılı için ödenen kıdem tazminatı doğrudan brüt asgari ücret üzerinden hesaplanıyor: 2026 sonuna kadar gerçekleşen çıkışlarda yıllık brüt 33.030,00 TL'den yalnızca binde 7,59 damga vergisi (250,70 TL) düşülerek her yıl için <strong>32.779,30 TL net</strong> ödeme yapılıyor; 1 Ocak 2027 ve sonrasında iş sözleşmesi sona erenlerde ise yeni brüt asgari ücret esas alınacak.</p>
<p class="text-slate-800 leading-relaxed mb-4">Giydirilmiş brüt ücreti yüksek olan çalışanlarda ise belirleyici sınır Hazine ve Maliye Bakanlığı'nın memur maaş katsayısına göre ilan ettiği <strong>kıdem tazminatı tavanı</strong> oluyor. 31 Aralık 2026 tarihine kadar geçerli yıllık kıdem tazminatı tavanı <strong>73.729,87 TL</strong> düzeyinde uygulanırken, Ocak 2027 başında kesinleşecek memur maaş artışıyla birlikte bu tavan da yukarı yönlü yenilenecek.</p>

<h3 class="text-xl font-bold text-slate-900 mt-6 mb-3">Komisyon Takvimi Nasıl İşleyecek?</h3>
<p class="text-slate-800 leading-relaxed mb-4">İşçi, işveren ve hükümeti temsilen beşer üyeden oluşan Asgari Ücret Tespit Komisyonu, Aralık ayının ilk yarısında Çalışma ve Sosyal Güvenlik Bakanlığı ev sahipliğinde ilk toplantısını gerçekleştirecek. Komisyon masasında 3 Aralık'ta açıklanacak Kasım ayı TÜİK enflasyon verisi, Orta Vadeli Program (OVP) enflasyon hedefleri, geçim endeksleri ve kayıtlı istihdam maliyetleri birlikte değerlendirilecek; oy çokluğuyla alınacak nihai karar Aralık ayının son haftasında Resmî Gazete'de yayımlanarak 1 Ocak 2027 itibarıyla yürürlüğe girecek.</p>""",
    },
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
                    import google_indexer
                    google_indexer.notify_google_indexing(site_url)
                except Exception:
                    pass
                try:
                    bullets = item.get("tg_bullets") or []
                    bullet_lines = "\n".join(f"— {b}" for b in bullets) if bullets else item["summary"]
                    tg_caption = f"✍️ ÖZEL DOSYA | {item['title']}\n\n{bullet_lines}"
                    telegram_notifier.send_telegram_news(visual_path, tg_caption, site_url)
                except Exception as _te:
                    print(f"Özel dosya Telegram uyarısı: {_te}")
