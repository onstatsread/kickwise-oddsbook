"""
Tests whether worldfootball.net's standings page is scrapable with
PLAIN requests (no headless browser needed) — a much lighter-weight
alternative to Oddsbook's Playwright requirement, if it works.
"""

import requests
from bs4 import BeautifulSoup

URL = "https://www.worldfootball.net/competition/co91/england-premier-league/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def main():
    print(f"Fetching {URL} with plain requests (no browser) ...")

    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Response length: {len(resp.text)}")

    is_challenge = "Just a moment" in resp.text or "cf-mitigated" in resp.text.lower()
    print(f"Looks like a Cloudflare challenge: {is_challenge}")

    if resp.status_code != 200:
        print(f"First 1000 chars: {resp.text[:1000]}")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    tables = soup.find_all("table")
    print(f"\nTotal <table> elements found: {len(tables)}")

    # Find the standings table — look for one whose header row
    # contains "Pts" (points column).
    standings_table = None
    for t in tables:
        header_text = t.get_text(" ", strip=True)
        if "Pts" in header_text and "Diff" in header_text:
            standings_table = t
            break

    if not standings_table:
        print("Could not find a table containing 'Pts' and 'Diff' headers.")
        print("Table previews:")
        for i, t in enumerate(tables[:5]):
            print(f"\n--- Table {i} ---")
            print(str(t)[:500])
        return

    print("\n--- Found standings table ---")
    rows = standings_table.find_all("tr")
    print(f"Row count: {len(rows)}")

    for row in rows[:5]:
        cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
        print(cells)

    print(f"\nFull first data row HTML:")
    if len(rows) > 1:
        print(str(rows[1])[:2000])


if __name__ == "__main__":
    main()
