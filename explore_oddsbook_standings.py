"""
KEY FINDING from previous runs: the page's OWN natural preload request
(fired automatically on initial page load, before any of our
interaction) succeeded with 200 real JSON. But ANY request WE trigger
afterward — a UI click, or a manual page.evaluate(fetch(...)) call to
the exact same URL — gets Cloudflare-blocked (403, challenge page).

This suggests Cloudflare's bot-management here is scoring based on
request PATTERN (one natural preload per fresh page load = legit;
anything extra in the same session = suspicious), not just browser
fingerprint.

This script tests whether a dedicated standings sub-URL exists that
would make Standings the page's own naturally-preloaded tab on a
FRESH load — since fresh natural loads are the only thing we've seen
succeed.
"""

import random
import time
from playwright.sync_api import sync_playwright

COUNTRY = "england"
LEAGUE = "premier-league"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


def human_delay(a=0.5, b=1.5):
    time.sleep(random.uniform(a, b))


def try_url(browser, url):
    print(f"\n--- Trying: {url} ---")
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1366, "height": 768},
        locale="en-GB",
        timezone_id="Europe/London",
    )
    page = context.new_page()
    captured = []

    def on_response(response):
        if "bff/league" in response.url:
            try:
                body = response.text()
            except Exception as e:
                body = f"<error: {e}>"
            captured.append({
                "url": response.url,
                "status": response.status,
                "is_challenge": "Just a moment" in body,
                "body_preview": body[:1500],
            })

    page.on("response", on_response)

    try:
        resp = page.goto(url, timeout=30000, wait_until="domcontentloaded")
        print(f"Navigation status: {resp.status if resp else 'unknown'}")
        page.wait_for_timeout(3000)
        print(f"Page title: {page.title()}")
    except Exception as e:
        print(f"Navigation failed: {e}")

    print(f"BFF responses captured on this fresh load: {len(captured)}")
    for c in captured:
        print(f"  [{c['status']}] {c['url']} (challenge={c['is_challenge']})")
        if c["status"] == 200 and not c["is_challenge"]:
            print(f"  *** SUCCESS *** Preview: {c['body_preview']}")

    context.close()
    return captured


def main():
    candidate_urls = [
        f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/",
        f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/standings/",
        f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/table/",
        f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/?tab=standings",
    ]

    all_successes = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)

        for url in candidate_urls:
            results = try_url(browser, url)
            all_successes.extend(
                c for c in results if c["status"] == 200 and not c["is_challenge"]
            )
            human_delay(1.5, 3)

        browser.close()

    print(f"\n\n=== SUMMARY ===")
    print(f"Total successful (200, non-challenge) bff/league responses: {len(all_successes)}")
    for c in all_successes:
        print(f"  {c['url']}")


if __name__ == "__main__":
    main()
