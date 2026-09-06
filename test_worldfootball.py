"""
Tests whether worldfootball.net's standings page is scrapable with
PLAIN requests (no headless browser needed) — a much lighter-weight
alternative to Oddsbook's Playwright requirement, if it works.
"""

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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


def try_plain_requests():
    print(f"Fetching {URL} with plain requests (no browser) ...")

    resp = requests.get(URL, headers=HEADERS, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Response length: {len(resp.text)}")

    is_challenge = "Just a moment" in resp.text or "cf-mitigated" in resp.text.lower()
    print(f"Looks like a Cloudflare challenge: {is_challenge}")

    if resp.status_code == 200 and not is_challenge:
        return resp.text

    print(f"First 500 chars: {resp.text[:500]}")
    return None


def try_playwright():
    print(f"\n\nFalling back to Playwright + real Chrome channel ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        resp = page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        print(f"Navigation status: {resp.status if resp else 'unknown'}")

        try:
            page.wait_for_function(
                "document.title !== 'Just a moment...'", timeout=15000
            )
        except Exception:
            pass

        page.wait_for_timeout(2000)
        print(f"Page title: {page.title()}")

        html = page.content()
        browser.close()

    is_challenge = "Just a moment" in html
    print(f"Looks like a Cloudflare challenge: {is_challenge}")

    if is_challenge:
        return None

    return html


def analyze_html(html):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    print(f"\nTotal <table> elements found: {len(tables)}")

    standings_table = None
    for t in tables:
        header_text = t.get_text(" ", strip=True)
        if "Pts" in header_text and "Diff" in header_text:
            standings_table = t
            break

    if not standings_table:
        print("Could not find a table containing 'Pts' and 'Diff' headers.")
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


def main():
    html = try_plain_requests()

    if html is None:
        html = try_playwright()

    if html is None:
        print("\nBoth methods failed — this site is also Cloudflare-locked against automation.")
        return

    analyze_html(html)


if __name__ == "__main__":
    main()
