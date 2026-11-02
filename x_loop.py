"""
X (Twitter) 45 Dakikalık Kesintisiz Paylaşım Döngüsü (@gndmanalizi)

GitHub Actions'ın zamanlayıcısı (cron) güvenilmez: "her 10 dakikada bir" yazılsa bile
pratikte ~1 saatte bir, bazen 1.5 saatte bir çalışıyor. Bu yüzden 45 dakikalık ritim
cron'a bırakılmaz; bu script tek bir Actions işi içinde ~5.5 saat ayakta kalır ve
paylaşımları kendisi zamanlar:

  1. Başlar başlamaz: son paylaşımın üzerinden 45 dk geçtiyse HEMEN paylaşır.
  2. Her paylaşımdan sonra x_posted_history.json'u anında repoya push eder
     (bir sonraki çalıştırma kaldığı yeri bilir -> mükerrer paylaşım olmaz).
  3. Bir sonraki paylaşım zamanına kadar uyur (son paylaşım + 45 dk).
  4. Paylaşım başarısız olursa 5 dk sonra tekrar dener.
  5. Süresi dolunca çıkar; workflow kendini yeniden başlatır.

Her turun sonucu x_bot_status.json dosyasına yazılır ve push edilir (uzaktan teşhis için).
"""
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

INTERVAL_MIN = float(os.getenv("X_INTERVAL_MINUTES", "45"))
RETRY_MIN = float(os.getenv("X_RETRY_MINUTES", "5"))
MAX_RUNTIME_MIN = float(os.getenv("X_LOOP_MAX_MINUTES", "335"))
PUSH_ENABLED = os.getenv("X_LOOP_PUSH", "1") == "1"

HISTORY_FILE = os.path.join(BASE_DIR, "x_posted_history.json")
STATUS_FILE = os.path.join(BASE_DIR, "x_bot_status.json")
TR_TZ = timezone(timedelta(hours=3))

START = time.time()


def tr(ts: float) -> str:
    return datetime.fromtimestamp(ts, TR_TZ).strftime("%Y-%m-%d %H:%M:%S")


def last_posted_ts() -> float:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            hist = json.load(f)
        ts = [float(h.get("ts", 0)) for h in hist if isinstance(h, dict) and h.get("status") == "posted"]
        return max(ts) if ts else 0.0
    except Exception:
        return 0.0


def git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True)


def push_state(message: str):
    """Geçmiş ve durum dosyasını repoya kaydeder (çakışmaya karşı 4 deneme)."""
    if not PUSH_ENABLED:
        return
    git("add", "x_posted_history.json", "x_bot_status.json")
    if git("diff", "--staged", "--quiet").returncode == 0:
        return
    git("commit", "-m", f"{message} [skip ci]")
    for attempt in range(1, 5):
        git("pull", "--rebase", "--autostash", "-X", "theirs", "origin", "main")
        r = git("push", "origin", "HEAD:main")
        if r.returncode == 0:
            print(f"💾 Geçmiş repoya kaydedildi ({message}).")
            return
        print(f"⚠️ Push denemesi {attempt} başarısız: {r.stderr.strip()[:200]}")
        time.sleep(5 * attempt)
    print("❌ Geçmiş push edilemedi! (Bir sonraki turda tekrar denenecek)")


def write_status(result: str, log_tail: str, next_ts: float):
    data = {
        "last_check": tr(time.time()),
        "result": result,
        "last_post": tr(last_posted_ts()) if last_posted_ts() else None,
        "next_planned": tr(next_ts) if next_ts else None,
        "runner": "github-actions" if os.getenv("GITHUB_ACTIONS") else "local",
        "log_tail": log_tail[-3000:],
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Tee(io.TextIOBase):
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def run_one_cycle() -> tuple:
    import run_x_cycle
    buf = io.StringIO()
    real = sys.stdout
    sys.stdout = Tee(real, buf)
    ok = False
    try:
        # Zamanlamayı bu döngü yönetiyor -> force=True (cooldown kilidini atla).
        # Kalite filtresi, mükerrer kalkanı ve görsel zorunluluğu run_cycle içinde aynen çalışır.
        ok = bool(run_x_cycle.run_cycle(force=True, max_attempts=3))
    except Exception as e:
        print(f"❌ Döngü istisnası: {e}")
    finally:
        sys.stdout = real
    return ok, buf.getvalue()


def sleep_until(target_ts: float):
    while True:
        remaining = target_ts - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 60))


def main():
    deadline = START + MAX_RUNTIME_MIN * 60
    print(f"🚀 [X 45dk Döngüsü] Başladı: {tr(START)} | Aralık: {INTERVAL_MIN} dk | Bitiş: {tr(deadline)}")

    while True:
        last = last_posted_ts()
        due = last + INTERVAL_MIN * 60 if last else time.time()
        if due > time.time():
            if due > deadline:
                print(f"⏹️ Sonraki paylaşım ({tr(due)}) bu çalıştırmanın süresini aşıyor; devir teslim ediliyor.")
                break
            print(f"😴 Sonraki paylaşım zamanı: {tr(due)} (son paylaşım: {tr(last)})")
            sleep_until(due)

        if time.time() > deadline:
            break

        ok, log = run_one_cycle()
        if ok:
            next_ts = last_posted_ts() + INTERVAL_MIN * 60
            write_status("posted", log, next_ts)
            push_state("chore: x posted (45dk döngüsü)")
            continue

        retry_ts = time.time() + RETRY_MIN * 60
        write_status("no_post", log, retry_ts)
        push_state("chore: x bot status")
        if retry_ts > deadline:
            break
        print(f"🔁 Paylaşım yapılamadı, {RETRY_MIN} dk sonra tekrar denenecek ({tr(retry_ts)}).")
        sleep_until(retry_ts)

    print(f"🏁 [X 45dk Döngüsü] Bitti: {tr(time.time())}")


if __name__ == "__main__":
    main()
