"""
Verifies whether OddStorm's odds page is scrapable for real production
use — tests plain requests first (cheapest, no browser needed), falls
back to Playwright if blocked. Specifically checks Algeria coverage
since that's the league that started this whole investigation.
"""

import re
import requests
from bs4 import BeautifulSoup

URL = "https://www.oddstorm.com/odds/"

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
    print(f"\nFalling back to Playwright ...")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        resp = page.goto(URL, timeout=45000, wait_until="domcontentloaded")
        print(f"Navigation status: {resp.status if resp else 'unknown'}")

        page.wait_for_timeout(3000)
        print(f"Page title: {page.title()}")

        html = page.content()
        browser.close()

    is_challenge = "Just a moment" in html
    print(f"Looks like a Cloudflare challenge: {is_challenge}")

    if is_challenge:
        return None
    return html


def analyze(html):
    soup = BeautifulSoup(html, "html.parser")

    # Confirm real numeric odds are present (not just market labels).
    odds_pattern = re.findall(r"\b\d{1,3}\.\d{2}\b", html)
    print(f"\nDecimal-odds-shaped numbers found: {len(odds_pattern)}")
    print(f"Sample: {odds_pattern[:15]}")

    # Check specifically for Algeria coverage.
    algeria_present = "Algeria" in html
    print(f"\n'Algeria' mentioned: {algeria_present}")

    if algeria_present:
        idx = html.find("Algeria")
        print(f"Context around 'Algeria':\n{html[max(0, idx-100):idx+500]}")

    # Find real match rows (links matching /odds/match/...).
    match_links = soup.find_all("a", href=re.compile(r"/odds/match/"))
    print(f"\nTotal match links found: {len(match_links)}")

    # Show structure of the first match row for parsing reference.
    if match_links:
        first_link = match_links[0]
        row = first_link.find_parent("tr")
        if row:
            print(f"\nFirst match row HTML:\n{str(row)[:1500]}")


def main():
    html = try_plain_requests()

    if html is None:
        html = try_playwright()

    if html is None:
        print("\nBoth methods failed — this site needs stronger anti-detection handling.")
        return

    analyze(html)


if __name__ == "__main__":
    main()
