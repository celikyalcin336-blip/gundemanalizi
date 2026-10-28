"""
X (Twitter) 7/24 Kesintisiz Yerel Arka Plan Servisi
- Bilgisayar açık olduğu sürece arka planda çalışır.
- 5 dakikada bir kontrol eder, 45 dakikalık bekleme süresi dolunca yeni flaş haberi tweetler.
"""
import os
import sys
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import run_x_cycle

def start_daemon():
    print("=" * 60)
    print("🚀 GÜNDEM ANALİZİ X (TWITTER) OTONOM PAYLAŞIM ROBOTU")
    print("📍 Hesap: @gndmanalizi")
    print("⏰ Aralık: 45 dakikada 1 flaş haber")
    print("🌙 Sessiz Saatler: 01:30 - 07:30 (Hesap Güvenlik Kalkanı)")
    print("=" * 60)

    while True:
        try:
            run_x_cycle.run_cycle(force=False)
        except Exception as e:
            print(f"⚠️ Döngü istisnası: {e}")
        time.sleep(300)  # Her 5 dakikada bir yokla

if __name__ == "__main__":
    start_daemon()
