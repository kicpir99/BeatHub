import urllib.request
import urllib.parse
try:
    url = 'http://127.0.0.1:8000/albums/?q=dts'
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        with open('debug_search.html', 'w', encoding='utf-8') as f:
            f.write(html)
    print("Saved to debug_search.html")
except Exception as e:
    print(f"Error: {e}")
