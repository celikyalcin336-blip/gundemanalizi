"""
Hesaplama araçlarının (maaş, kıdem tazminatı, emekli zammı) yasal parametreleri.

⚠️ Bu değerler her yıl (ve kıdem tavanı her 6 ayda bir) değişir.
Güncellerken yalnızca bu dosyayı düzenlemek yeterlidir; sayfalar otomatik güncellenir.

Kaynaklar (2026):
- Asgari ücret 2026: brüt 33.030,00 TL / net 28.075,50 TL
- SGK prime esas kazanç üst sınırı: asgari ücretin 9 katı = 297.270,00 TL
- 2026 ücret gelirleri gelir vergisi tarifesi (GİB): 190.000 / 400.000 / 1.500.000 / 5.300.000 TL
- Kıdem tazminatı tavanı: 01.01-30.06.2026 = 64.948,77 TL; 01.07-31.12.2026 = 73.729,87 TL
"""

CALC_PARAMS = {
    "year": 2026,
    "son_guncelleme": "03.11.2026",
    "asgari_brut": 33030.00,
    "asgari_net": 28075.50,
    "sgk_isci": 0.14,
    "issizlik_isci": 0.01,
    "sgk_tavan": 297270.00,
    "damga": 0.00759,
    # [dilim üst sınırı (yıllık kümülatif matrah), oran] — son dilim için üst sınır None
    "gv_dilimleri": [
        [190000, 0.15],
        [400000, 0.20],
        [1500000, 0.27],
        [5300000, 0.35],
        [None, 0.40],
    ],
    # [başlangıç, bitiş, tavan tutarı] — çıkış tarihine göre seçilir
    "kidem_tavanlari": [
        ["2026-01-01", "2026-06-30", 64948.77],
        ["2026-07-01", "2026-12-31", 73729.87],
    ],
}
