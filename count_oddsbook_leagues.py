"""
Counts Oddsbook's real football league coverage by reading their own
sitemap.xml (referenced in robots.txt: Sitemap: https://oddsbook.com/
sitemap.xml). This gives an authoritative number instead of guessing
from sidebar counts or single-day fixture samples.

League pages have the URL shape:
    /football/{country-slug}/{league-slug}/
(exactly 2 path segments after /football/, no trailing match ID)

Match detail pages, team pages, and everything else are excluded.
"""

import re
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Matches exactly /football/{country}/{league}/ — 2 segments, no
# trailing numeric ID (which would indicate a match detail page).
LEAGUE_URL_RE = re.compile(r"^https://oddsbook\.com/football/([^/]+)/([^/]+)/?$")


def fetch_via_playwright(url, page):
    resp = page.goto(url, timeout=45000, wait_until="domcontentloaded")
    try:
        page.wait_for_function(
            "document.title !== 'Just a moment...'", timeout=15000
        )
    except Exception:
        pass
    page.wait_for_timeout(1000)
    return page.content(), resp.status if resp else None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        # Sitemap index first — large sites usually split into
        # multiple sub-sitemaps (e.g. sitemap-football.xml).
        print("Fetching sitemap.xml ...")
        html, status = fetch_via_playwright("https://oddsbook.com/sitemap.xml", page)
        print(f"Status: {status}, length: {len(html)}")
        print(html[:2000])

        # Collect every <loc> URL from the main sitemap (or its
        # sub-sitemaps, if this is a sitemap index).
        all_urls = set(re.findall(r"<loc>(.*?)</loc>", html))
        print(f"\nURLs found in top-level sitemap: {len(all_urls)}")

        sub_sitemaps = [u for u in all_urls if u.endswith(".xml")]
        print(f"Sub-sitemaps found: {len(sub_sitemaps)}")
        for s in sub_sitemaps[:20]:
            print(f"  {s}")

        # If this was a sitemap INDEX (all entries are .xml files),
        # fetch each sub-sitemap and merge their URLs in.
        if sub_sitemaps and len(sub_sitemaps) == len(all_urls):
            print("\nThis was a sitemap index — fetching sub-sitemaps...")
            all_urls = set()
            for sub_url in sub_sitemaps:
                sub_html, sub_status = fetch_via_playwright(sub_url, page)
                found = re.findall(r"<loc>(.*?)</loc>", sub_html)
                print(f"  {sub_url} [{sub_status}] -> {len(found)} URLs")
                all_urls.update(found)

        browser.close()

    print(f"\nTotal URLs across all sitemaps: {len(all_urls)}")

    league_urls = [u for u in all_urls if LEAGUE_URL_RE.match(u)]
    print(f"\nURLs matching league pattern (/football/{{country}}/{{league}}/): {len(league_urls)}")

    # Group by country for a readable breakdown.
    by_country = {}
    for u in league_urls:
        m = LEAGUE_URL_RE.match(u)
        country, league = m.group(1), m.group(2)
        by_country.setdefault(country, []).append(league)

    print(f"\nCountries with at least one league: {len(by_country)}")
    print("\nBreakdown (country: league count):")
    for country in sorted(by_country, key=lambda c: -len(by_country[c])):
        print(f"  {country}: {len(by_country[country])}")

    print("\nSample league URLs (first 30):")
    for u in league_urls[:30]:
        print(f"  {u}")


if __name__ == "__main__":
    main()
