import requests
from curl_cffi import requests as cr
print("Testing F1 livetiming standard requests...")
try:
    r1 = requests.get("https://livetiming.formula1.com/static/StreamingStatus.json", timeout=5)
    print(f"Status: {r1.status_code}")
except Exception as e:
    print(f"requests failed: {e}")

print("\nTesting F1 livetiming curl_cffi...")
try:
    r2 = cr.get("https://livetiming.formula1.com/static/StreamingStatus.json", impersonate="chrome124", timeout=5)
    print(f"Status: {r2.status_code}")
except Exception as e:
    print(f"curl_cffi failed: {e}")
