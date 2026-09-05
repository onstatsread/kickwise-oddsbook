"""
Oddsbook standings exploration script — run via GitHub Actions.

CONFIRMED so far:
- The real standings data source is a JSON API:
    https://oddsbook.com/bff/league/{league_id}/tab/standings/
        ?sport=football&season={year}&lang=en
  (league_id 39 = Premier League)
- Clicking the Standings tab DOES trigger a request to this URL.
- A SEPARATE manually-fired request to this same URL (via
  page.request.get()) gets Cloudflare-blocked (403, challenge page) —
  it doesn't carry the same fingerprint/headers as the page's own
  in-browser fetch.

This version captures the RESPONSE of the site's own click-triggered
request instead of firing a separate one, to see whether that
request succeeds and what real data it returns.
"""

from playwright.sync_api import sync_playwright

COUNTRY = "england"
LEAGUE = "premier-league"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def main():
    url = f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/"
    print(f"Loading {url} ...")

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        def on_response(response):
            if "bff/league" in response.url:
                try:
                    body = response.text()
                except Exception as e:
                    body = f"<could not read body: {e}>"
                captured.append({
                    "url": response.url,
                    "status": response.status,
                    "body": body,
                })

        page.on("response", on_response)

        page.goto(url, timeout=45000, wait_until="domcontentloaded")

        try:
            page.wait_for_function(
                "document.title !== 'Just a moment...'", timeout=20000
            )
        except Exception:
            pass

        page.wait_for_timeout(2000)
        print(f"Page title after challenge: {page.title()}")

        print(f"\nBFF responses captured BEFORE clicking Standings ({len(captured)}):")
        for c in captured:
            print(f"  [{c['status']}] {c['url']} ({len(c['body'])} chars)")

        before_count = len(captured)

        try:
            page.get_by_role("tab", name="Standings", exact=True).click(timeout=8000)
            print("\nClicked Standings tab successfully.")
        except Exception as e:
            print(f"\nClick failed: {e}")

        page.wait_for_timeout(4000)

        new_responses = captured[before_count:]
        print(f"\nBFF responses captured AFTER clicking Standings ({len(new_responses)} new):")
        for c in new_responses:
            print(f"\n  [{c['status']}] {c['url']}")
            print(f"  Body ({len(c['body'])} chars):")
            print(f"  {c['body'][:6000]}")

        browser.close()

    if not captured:
        print("\nNo bff/league responses were captured at all.")


if __name__ == "__main__":
    main()
