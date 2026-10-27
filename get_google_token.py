import json
import urllib.parse
import http.server
import socketserver
import webbrowser
import requests
import os
import sys
import threading

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

auth_code = None

def run_server(port, ready_event):
    global auth_code
    class OAuthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            global auth_code
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html_resp = """
                <html>
                <body style="font-family:sans-serif; text-align:center; padding-top:60px;">
                    <h1 style="color:#10b981;">[BASARILI] Google Yetkisi Alindi!</h1>
                    <p>Gundem Analizi Indexer yetkilendirmesi tamamlandi.</p>
                    <p>Bu sekmeyi kapatip konsola donebilirsiniz.</p>
                </body>
                </html>
                """
                self.wfile.write(html_resp.encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Code not found")

        def log_message(self, format, *args):
            return

    try:
        with socketserver.TCPServer(("localhost", port), OAuthHandler) as httpd:
            ready_event.set()
            while not auth_code:
                httpd.handle_request()
    except Exception as e:
        ready_event.set()

def main():
    global auth_code
    secret_path = os.path.join(os.path.dirname(__file__), "client_secret.json")
    if not os.path.exists(secret_path):
        print(f"HATA: client_secret.json bulunamadi.")
        return

    with open(secret_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data.get("installed") or data.get("web")
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    port = 8085
    redirect_uri = f"http://localhost:{port}"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/indexing",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(auth_params)

    print("\n" + "="*70)
    print("GOOGLE INDEXING API YETKILENDIRME BASLATILIYOR")
    print("="*70)
    print("\nTarayicinizda asagidaki link otomatik acilacak.\nAcilmazsa linki kopyalayip tarayiciniza yapistirin:\n")
    print(auth_url)
    print("\n" + "="*70 + "\n")

    ready_event = threading.Event()
    t = threading.Thread(target=run_server, args=(port, ready_event), daemon=True)
    t.start()
    ready_event.wait()

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("Google hesabinizla giris yapip 'Devam Et / Allow' butonuna basin...")
    print("(Eger tarayici yonlendirmeyi yakalayamazsa, yonlendirilen URL'yi buraya yapistirabilirsiniz)")

    import time
    while not auth_code:
        time.sleep(1)

    print("\n[OK] Onay kodu alindi, kalici Refresh Token uretiliyor...")
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    resp = requests.post(token_url, data=token_data, timeout=15)
    if resp.status_code == 200:
        token_res = resp.json()
        refresh_token = token_res.get("refresh_token")
        if refresh_token:
            save_payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token
            }
            save_path = os.path.join(os.path.dirname(__file__), "google_indexing_token.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(save_payload, f, indent=2)
            print("="*70)
            print("[TEBRIKLER] Google Indexing API icin kalici yetki basariyla alindi!")
            print(f"Anahtar kaydedildi: {save_path}")
            print("="*70)
        else:
            print("Uyari: Refresh token donmedi:")
            print(resp.text)
    else:
        print(f"Token alinamadi ({resp.status_code}): {resp.text}")

if __name__ == "__main__":
    main()
