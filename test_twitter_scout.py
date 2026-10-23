import urllib.request
import re
import json

def test_account(screen_name):
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{screen_name}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            print(f"[{screen_name}] HTML length: {len(html)}")
            
            # Find __NEXT_DATA__
            m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
            if m:
                data = json.loads(m.group(1))
                timeline = data.get("props", {}).get("pageProps", {}).get("timeline", {})
                entries = timeline.get("entries", [])
                print(f"[{screen_name}] Entries found in NEXT_DATA: {len(entries)}")
                for e in entries:
                    content = e.get("content", {})
                    tweet = content.get("tweet", {})
                    if tweet:
                        tid = tweet.get("id_str")
                        text = tweet.get("text", "")
                        media = tweet.get("entities", {}).get("media", [])
                        has_video = any(m.get("type") == "video" for m in media) or "video_info" in tweet
                        print(f"  Tweet {tid}: has_video={has_video} | {text[:60]}...")
            else:
                print("No NEXT_DATA found.")
    except Exception as e:
        print(f"Error for {screen_name}: {e}")

if __name__ == "__main__":
    test_account("asayisberkemal")
    test_account("bpthaber")
