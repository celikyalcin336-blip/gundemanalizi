"""
Gündem Analizi 7/24 Yerel Otonom Sosyal Medya & Reels Servisi
1. X (Twitter - @gndmanalizi): Her 60 dakikada (saat başı) 1 flaş haber paylaşır.
2. Günlük 6 Kanallı Reels Bülteni: Her gün Öğlen 12:30 ve Akşam 19:30'da otomatik üretip
   Telegram, Instagram Reels, Facebook Reels ve X'te yayınlar.
"""
import json
import os
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_PATH = os.path.join(BASE_DIR, "x_daemon.log")
_log_f = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
sys.stdout = _log_f
sys.stderr = _log_f

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)

import run_x_cycle
import daily_bulletin_publisher

STATE_FILE = os.path.join(BASE_DIR, "reels_schedule_state.json")


def load_reels_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_reels_state(state: dict):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def check_and_run_scheduled_reels():
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    hm = now.hour * 60 + now.minute
    state = load_reels_state()

    if (12 * 60 + 30) <= hm < (18 * 60 + 30):
        slot_key = f"{today_str}_1230"
        if not state.get(slot_key):
            print(f"🎬 [Otonom Reels] {today_str} 12:30 Öğlen Bülteni başlatılıyor...")
            state[slot_key] = {"started_at": now.strftime("%H:%M:%S"), "status": "running"}
            save_reels_state(state)
            try:
                rep = daily_bulletin_publisher.run_bulletin_cycle(video_path=None)
                state[slot_key] = {"completed_at": datetime.now().strftime("%H:%M:%S"), "status": "done", "video": rep.get("video_path")}
                save_reels_state(state)
            except Exception as e:
                print(f"❌ 12:30 Reels bülten hatası: {e}")

    elif (19 * 60 + 30) <= hm <= (23 * 60 + 55):
        slot_key = f"{today_str}_1930"
        if not state.get(slot_key):
            print(f"🎬 [Otonom Reels] {today_str} 19:30 Akşam Bülteni başlatılıyor...")
            state[slot_key] = {"started_at": now.strftime("%H:%M:%S"), "status": "running"}
            save_reels_state(state)
            try:
                rep = daily_bulletin_publisher.run_bulletin_cycle(video_path=None)
                state[slot_key] = {"completed_at": datetime.now().strftime("%H:%M:%S"), "status": "done", "video": rep.get("video_path")}
                save_reels_state(state)
            except Exception as e:
                print(f"❌ 19:30 Reels bülten hatası: {e}")


def start_daemon():
    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 X + REELS DAEMON AKTİF (PID: {os.getpid()})")
    print("=" * 60)

    while True:
        try:
            check_and_run_scheduled_reels()
        except Exception as e:
            print(f"⚠️ Reels zamanlayıcı istisnası: {e}")

        try:
            run_x_cycle.run_cycle(force=False)
        except Exception as e:
            print(f"⚠️ X döngü istisnası: {e}")

        time.sleep(60)


if __name__ == "__main__":
    start_daemon()
