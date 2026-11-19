# -*- coding: utf-8 -*-
"""
Gündem Analizi - Konu Merkez Sayfaları (topic_hubs.py)

Türkiye'de en çok aranan sürekli gündem konuları için kalıcı, doğrulanabilir bilgi + araç + kronoloji sayfaları:
- /dosya                  -> Tüm özel dosyalar merkezi
- /dosya/asgari-ucret     -> Asgari Ücret (mevcut resmi tutar + komisyon takvimi + net-brüt hesaplayıcı + kronoloji)
- /dosya/emekli-ve-memur-zammi -> Emekli ve Memur Maaş Zammı (yasal formül + hesaplayıcı + kronoloji)
- /dosya/kidem-tazminati  -> Kıdem Tazminatı (tavan, şartlar + hesaplayıcı + kronoloji)
- /dosya/sinav-takvimi    -> ÖSYM ve MEB Sınav Dosyası (KPSS, YKS, LGS resmi süreç + kronoloji)

Tüm rakamlar calc_params.py ve yürürlükteki mevzuattan alınır; uydurma tahmin tablosu yer almaz.
"""
import re
from typing import Dict, List

import calc_params


def _fmt_tl(val: float) -> str:
    s = f"{val:,.2f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def get_hubs() -> Dict[str, Dict]:
    p = calc_params.CALC_PARAMS
    yr = p["year"]
    brut = _fmt_tl(p["asgari_brut"])
    net = _fmt_tl(p["asgari_net"])
    sgk_tavan = _fmt_tl(p["sgk_tavan"])
    kidem_h2 = _fmt_tl(p["kidem_tavanlari"][-1][2])
    kidem_h1 = _fmt_tl(p["kidem_tavanlari"][0][2])

    return {
        "asgari-ucret": {
            "slug": "asgari-ucret",
            "icon": "💼",
            "badge": "Çalışma Hayatı Dosyası",
            "title": f"Asgari Ücret Rehberi: Mevcut Tutar, Kesintiler ve {yr + 1} Belirleme Süreci",
            "meta_desc": f"{yr} yılı net {net} TL / brüt {brut} TL asgari ücret bordro kalemleri, işveren maliyeti, Asgari Ücret Tespit Komisyonu takvimi ve güncel haberler.",
            "lead": f"Yürürlükteki asgari ücret brüt {brut} TL, net {net} TL olarak uygulanmaktadır. Yeni dönem ücreti her yıl Aralık ayında toplanan Asgari Ücret Tespit Komisyonu kararıyla belirlenir ve Resmî Gazete'de yayımlanarak yürürlüğe girer.",
            "calc_href": "/hesaplama/maas",
            "calc_label": "Brüt–Net Maaş Hesaplama Aracını Aç",
            "official_name": "Çalışma ve Sosyal Güvenlik Bakanlığı",
            "official_url": "https://www.csgb.gov.tr/",
            "keywords": [r"asgari ücret", r"tespit komisyonu", r"brüt.*net", r"işveren maliyeti"],
            "facts": [
                ("Yürürlükteki Brüt Asgari Ücret", f"{brut} TL"),
                ("Yürürlükteki Net Asgari Ücret", f"{net} TL"),
                ("SGK İşçi Payı (%14) + İşsizlik (%1)", f"{_fmt_tl(p['asgari_brut'] * 0.15)} TL"),
                ("Gelir ve Damga Vergisi", "0,00 TL (istisna kapsamında)"),
                ("SGK Prime Esas Kazanç Tavanı (9 kat)", f"{sgk_tavan} TL"),
                ("Komisyon Toplantı Dönemi", "Her yıl Aralık ayı"),
            ],
            "sections": [
                {
                    "h": "Asgari Ücret Nasıl Belirlenir?",
                    "p": [
                        "4857 sayılı İş Kanunu'nun 39. maddesi uyarınca asgari ücret; işçi, işveren ve hükümeti temsilen beşer üyeden oluşan 15 kişilik Asgari Ücret Tespit Komisyonu tarafından belirlenir. Komisyon, Çalışma ve Sosyal Güvenlik Bakanlığı'nın çağrısıyla Aralık ayında toplanır ve oy çokluğuyla karar alır.",
                        "Görüşmelerde TÜİK tarafından hesaplanan geçim göstergeleri, gerçekleşen ve hedeflenen enflasyon verileri, istihdam dengeleri ile işveren maliyetleri birlikte değerlendirilir. Nihai karar Resmî Gazete'de yayımlandığı tarihte kesinleşir; bu aşamadan önce basında yer alan oranlar yalnızca senaryo niteliğindedir.",
                    ],
                },
                {
                    "h": "Bordro Kesintileri ve Vergi İstisnası",
                    "p": [
                        f"Brüt {brut} TL üzerinden çalışan payı olarak %14 SGK primi ve %1 işsizlik sigortası primi kesilir. 193 sayılı Gelir Vergisi Kanunu'nda yapılan düzenleme gereği asgari ücret tutarına isabet eden kazançtan gelir vergisi ve damga vergisi alınmaz.",
                        "Asgari ücretin üzerinde maaş alan çalışanlarda da asgari ücrete karşılık gelen gelir ve damga vergisi tutarı her ay bordroda istisna olarak mahsup edilir. Yıl içinde kümülatif vergi matrahı üst dilimlere geçtikçe net maaşın nasıl değiştiğini aşağıdaki hesaplama aracımızdan görebilirsiniz.",
                    ],
                },
            ],
            "faqs": [
                ("Yeni asgari ücret ne zaman belli olur?", "Asgari Ücret Tespit Komisyonu Aralık ayı başında çalışmalarına başlar; karar genellikle Aralık ayının son haftasında açıklanır ve 1 Ocak itibarıyla yürürlüğe girer."),
                ("Ocak zammı hangi maaşa yansır?", "1 Ocak'tan itibaren çalışılan Ocak ayı ücreti zamlı hesaplanır; özel sektörde maaşını çalışılan ayın sonunda alanlar zamlı ilk ödemeyi Ocak sonunda veya Şubat başında alır."),
                ("Asgari ücret artışı başka hangi kalemleri etkiler?", "İşsizlik ödeneği alt ve üst sınırı, genel sağlık sigortası (GSS) primi, doğum ve askerlik borçlanması tutarları, isteğe bağlı sigorta primi ve SGK tavan ücreti doğrudan brüt asgari ücrete endekslidir."),
            ],
        },
        "emekli-ve-memur-zammi": {
            "slug": "emekli-ve-memur-zammi",
            "icon": "📊",
            "badge": "Sosyal Güvenlik Dosyası",
            "title": "Emekli ve Memur Maaş Zammı Rehberi: 6 Aylık Enflasyon Hesabı ve Ödeme Takvimi",
            "meta_desc": "SSK (4A), Bağ-Kur (4B) ve memur / memur emeklisi (4C) maaş artışlarının yasal hesaplama formülü, TÜİK enflasyon takvimi, maaş hesaplama aracı ve son gelişmeler.",
            "lead": "Türkiye'de emekli aylıkları ve kamu görevlilerinin maaşları yılda iki kez, Ocak ve Temmuz aylarında güncellenir. Kesin zam oranı, TÜİK'in 6 aylık dönemin son ayına ilişkin TÜFE verisini açıkladığı gün (Ocak ve Temmuz başı) netleşir.",
            "calc_href": "/hesaplama/emekli-zammi",
            "calc_label": "Emekli ve Memur Zammı Hesaplama Aracını Aç",
            "official_name": "SGK & TÜİK",
            "official_url": "https://www.sgk.gov.tr/",
            "keywords": [r"emekli", r"memur zamm", r"memur maaş", r"enflasyon farkı", r"en düşük emekli", r"\b4a\b|\b4b\b|\b4c\b", r"taban aylık"],
            "facts": [
                ("Zam Dönemleri", "Yılda 2 kez: Ocak ve Temmuz"),
                ("SSK (4A) ve Bağ-Kur (4B) Kuralı", "Son 6 aylık TÜFE değişim oranı kadar artış"),
                ("Memur ve Memur Emeklisi (4C) Kuralı", "Toplu sözleşme zammı + 6 aylık enflasyon farkı"),
                ("Verinin Kesinleşme Günü", "TÜİK Aralık / Haziran TÜFE bülteni (3–4 Ocak / Temmuz)"),
                ("En Düşük Emekli Aylığı Düzenlemesi", "TBMM kanun değişikliği ve Resmî Gazete yayımı ile"),
            ],
            "sections": [
                {
                    "h": "SSK, Bağ-Kur ve Memur Zamları Neden Farklı Çıkar?",
                    "p": [
                        "5510 sayılı Kanun uyarınca SSK (4A) ve Bağ-Kur (4B) emekli aylıkları, bir önceki 6 aylık dönemde (Temmuz–Aralık veya Ocak–Haziran) gerçekleşen kümülatif TÜFE artış oranı kadar doğrudan artırılır.",
                        "Memurlar ve memur emeklileri (4C) ise Kamu Görevlileri Hakem Kurulu / toplu sözleşme hükümlerine tabidir. Önce önceki dönemde alınan toplu sözleşme zammını aşan enflasyon farkı hesaplanır, ardından yeni dönemin toplu sözleşme zammı bu tutara eklenir. Bu nedenle iki grubun yüzdesel artış oranı birbirinden farklı oluşabilir.",
                    ],
                },
                {
                    "h": "Kök Maaş ve En Düşük Emekli Aylığı Uygulaması",
                    "p": [
                        "Yüzdesel enflasyon artışı emeklinin e-Devlet hizmet dökümünde görünen kök aylığına (ve %4/%5 ek ödemesine) uygulanır. Artış sonrası tutar Hazine destekli en düşük emekli aylığının altında kalırsa ödeme taban aylığa tamamlanır.",
                        "En düşük emekli aylığı tutarının değiştirilmesi idari bir karar değil, TBMM'de kabul edilen kanun düzenlemesi gerektirir. Resmi oran açıklandığında kendi maaşınızı kuruşu kuruşuna hesaplamak için hesaplama aracımızı kullanabilirsiniz.",
                    ],
                },
            ],
            "faqs": [
                ("6 aylık enflasyon oranı nasıl toplanır?", "Aylık TÜFE oranları aritmetik olarak toplanmaz; bileşik çarpım yapılır: (1 + r1) × (1 + r2) × ... × (1 + r6) − 1."),
                ("Zamlı emekli maaşları hangi gün yatar?", "SSK emeklileri tahsis numarasının son rakamına göre her ayın 17–26'sı arasında, Bağ-Kur emeklileri ise 25–28'i arasında aylıklarını alır."),
                ("Maaş farkı ne zaman ödenir?", "Memur emeklileri aylıklarını ay başında peşin aldığı için Ocak/Temmuz zam farkları Bakanlık tarafından ilan edilen ek takvimle aynı ay içinde ayrıca yatırılır."),
            ],
        },
        "kidem-tazminati": {
            "slug": "kidem-tazminati",
            "icon": "📑",
            "badge": "İş Hukuku Dosyası",
            "title": f"Kıdem Tazminatı Rehberi: {yr} Tavan Tutarı, Hak Kazanma Şartları ve Hesaplama",
            "meta_desc": f"Kıdem tazminatı tavanı ({kidem_h2} TL), giydirilmiş brüt ücret hesabı, damga vergisi kesintisi, istifa ve emeklilikte kıdem hakkı ile güncel yargı kararları.",
            "lead": f"Aynı işverene bağlı olarak en az 1 tam yıl çalışan işçiler, kanunda sayılan sona erme hallerinde her tam yıl için 30 günlük giydirilmiş brüt ücret tutarında kıdem tazminatı alır. Yürürlükteki kıdem tazminatı tavanı {kidem_h2} TL'dir.",
            "calc_href": "/hesaplama/kidem-tazminati",
            "calc_label": "Kıdem Tazminatı Hesaplama Aracını Aç",
            "official_name": "Hazine ve Maliye Bakanlığı",
            "official_url": "https://www.hmb.gov.tr/",
            "keywords": [r"kıdem tazminat", r"ihbar tazminat", r"iş kanunu", r"yargıtay.*işçi", r"emeklilik.*tazminat"],
            "facts": [
                (f"{yr} Ocak–Haziran Kıdem Tavanı", f"{kidem_h1} TL"),
                (f"{yr} Temmuz–Aralık Kıdem Tavanı", f"{kidem_h2} TL"),
                ("En Az Çalışma Süresi", "Aynı işverende 1 tam yıl"),
                ("Yasal Kesinti", "Yalnızca binde 7,59 damga vergisi (gelir vergisi yok)"),
                ("Tavan Güncelleme Dönemi", "Her yıl Ocak ve Temmuz (memur maaş katsayısına göre)"),
            ],
            "sections": [
                {
                    "h": "Kimler Kıdem Tazminatı Alabilir?",
                    "p": [
                        "1475 sayılı Kanun'un yürürlükteki 14. maddesine göre; işverenin haklı bir neden olmaksızın iş sözleşmesini feshetmesi, işçinin sağlık, iyi niyet ve ahlak kurallarına aykırılık gibi haklı nedenlerle feshi, zorunlu askerlik hizmeti, emeklilik (veya yaş dışındaki prim/sigortalılık şartını tamamlayarak SGK'dan yazı alınması) ve kadın işçinin evlilik tarihinden itibaren 1 yıl içinde ayrılması hallerinde kıdem tazminatı ödenir.",
                        "Hesaplamada çıplak brüt maaşa ek olarak süreklilik arz eden yemek, yol, ikramiye ve yakacak gibi yan haklar da brüt tutarlarıyla 'giydirilmiş ücret'e dahil edilir; ancak yıllık ödeme tutarı Hazine ve Maliye Bakanlığı genelgesiyle ilan edilen kıdem tazminatı tavanını aşamaz.",
                    ],
                },
            ],
            "faqs": [
                ("Kıdem tazminatı tavanı ne zaman yenilenir?", "Memur maaş katsayısının güncellendiği Ocak ve Temmuz aylarında Hazine ve Maliye Bakanlığı Mali ve Sosyal Haklar Genelgesi ile yeniden ilan edilir."),
                ("Kıdem tazminatı taksitle ödenebilir mi?", "Kural olarak iş sözleşmesinin sona erdiği tarihte tek seferde ve peşin ödenmesi gerekir; taksitlendirme yalnızca işçinin açık yazılı onayıyla mümkündür."),
            ],
        },
        "sinav-takvimi": {
            "slug": "sinav-takvimi",
            "icon": "🎓",
            "badge": "Eğitim & Sınav Dosyası",
            "title": "ÖSYM ve MEB Sınav Dosyası: YKS, KPSS, LGS Başvuru ve Sonuç Süreçleri",
            "meta_desc": "ÖSYM (YKS, KPSS, ALES, DGS) ve Millî Eğitim Bakanlığı (LGS, ortak yazılılar, ara tatil) resmi sınav duyuruları, başvuru kılavuzları ve güncel eğitim haberleri.",
            "lead": "YKS, KPSS, ALES, DGS ve LGS başta olmak üzere ulusal sınavların başvuru, geç başvuru, sınav giriş belgesi ve sonuç açıklama tarihleri yalnızca ÖSYM ve Millî Eğitim Bakanlığı'nın resmi takvimleriyle kesinleşir.",
            "calc_href": "",
            "calc_label": "",
            "official_name": "ÖSYM AİS & MEB",
            "official_url": "https://ais.osym.gov.tr/",
            "keywords": [r"\bkpss\b", r"\byks\b", r"\blgs\b", r"\bösym\b", r"\bales\b", r"\bdgs\b", r"ortak sınav", r"ara tatil", r"meb.*takvim"],
            "facts": [
                ("YKS & KPSS Başvuru Kanalı", "ÖSYM Aday İşlemleri Sistemi (ais.osym.gov.tr)"),
                ("Sonuç Sorgulama Adresi", "sonuc.osym.gov.tr ve meb.gov.tr"),
                ("LGS & Okul Takvimi", "Millî Eğitim Bakanlığı (meb.gov.tr)"),
                ("Geç Başvuru Kuralı", "Kılavuzda belirtilen tek günde, artırımlı sınav ücretiyle"),
            ],
            "sections": [
                {
                    "h": "Adayların Resmi Duyurularda Dikkat Etmesi Gerekenler",
                    "p": [
                        "ÖSYM her yıl sınav takvimini toplu olarak ilan eder; ancak bireysel sınavların kesin kuralları, oturum süreleri ve sınav ücreti ilgili sınavın başvuru kılavuzu yayımlandığında yürürlüğe girer. Sosyal medyada dolaşan taslak tarihler yerine yalnızca osym.gov.tr ve meb.gov.tr duyuruları esas alınmalıdır.",
                        "Bu sayfada ÖSYM ve MEB kaynaklı son açıklamalar, kitapçık/cevap anahtarı erişim duyuruları ve tercih süreçlerine ilişkin sitemizde yayımlanan tüm haberler tarih sırasıyla bir arada tutulur.",
                    ],
                },
            ],
            "faqs": [
                ("Sınav giriş belgesi ne zaman yayımlanır?", "ÖSYM sınavlarında sınava gireceğiniz bina ve salon bilgilerini içeren giriş belgesi genellikle sınav haftasından yaklaşık 10 gün önce ais.osym.gov.tr üzerinden erişime açılır."),
                ("Sonuçlara ve sorulara itiraz nasıl yapılır?", "İtiraz süresi ve yöntemi her sınavın başvuru kılavuzunda yazılıdır; başvurular ÖSYM Genel Amaçlı Dilekçe örneği veya ÖSYM elektronik itiraz kanalı üzerinden süresi içinde yapılır."),
            ],
        },
    }


def match_articles_for_hub(hub: Dict, articles: List[Dict], limit: int = 18) -> List[Dict]:
    rx = re.compile("|".join(hub.get("keywords") or []), re.I)
    out = []
    for a in articles or []:
        hay = f"{a.get('title') or ''} {a.get('summary') or ''}".replace("İ", "i").replace("I", "ı")
        if rx.search(hay):
            out.append(a)
            if len(out) >= limit:
                break
    return out
