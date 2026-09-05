"""
Oddsbook standings exploration script — run via GitHub Actions
(same pattern as check_annabet_gp.py), prints diagnostics to the
workflow log instead of returning JSON via a FastAPI endpoint.

Goal: find where/how Oddsbook renders standings (GP/W/D/L/GF/GA)
data for a league page, since the "Standings" tab is a client-side
React tab (not a separate URL) and its content hasn't shown up in
several targeted searches so far.
"""

import re
import sys
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        # Log every network request that looks like an API call, so we
        # can see if Standings data loads via a separate XHR/fetch —
        # this is the thing our HTML-only inspection couldn't show us.
        api_calls = []

        def on_request(request):
            if any(
                marker in request.url
                for marker in ["/api/", "standings", "table", "_next/data"]
            ):
                api_calls.append(request.url)

        page.on("request", on_request)

        page.goto(url, timeout=45000, wait_until="domcontentloaded")

        try:
            page.wait_for_function(
                "document.title !== 'Just a moment...'", timeout=20000
            )
        except Exception:
            pass

        page.wait_for_timeout(2000)
        print(f"Page title after challenge: {page.title()}")

        print("\n--- API-like requests seen BEFORE clicking Standings ---")
        for u in api_calls:
            print(u)

        # Click the Standings tab.
        try:
            page.get_by_role("tab", name="Standings", exact=True).click(timeout=8000)
            print("\nClicked Standings tab successfully.")
        except Exception as e:
            print(f"\nClick failed: {e}")

        page.wait_for_timeout(4000)

        print("\n--- API-like requests seen AFTER clicking Standings ---")
        for u in api_calls:
            print(u)

        # Check the tab's aria-selected state directly.
        try:
            is_selected = page.get_by_role(
                "tab", name="Standings", exact=True
            ).get_attribute("aria-selected")
            print(f"\nStandings tab aria-selected = {is_selected}")
        except Exception as e:
            print(f"Could not check aria-selected: {e}")

        # Dump visible text of the whole page body — small enough to
        # read directly in the Actions log, and will show us plainly
        # whether standings numbers are present ANYWHERE, in whatever
        # format they use.
        body_text = page.inner_text("body")
        print(f"\n--- Full visible body text ({len(body_text)} chars) ---")
        print(body_text[:8000])
        print("\n--- (truncated at 8000 chars if longer) ---")

        # Also dump the raw HTML of whatever element currently has
        # focus/active state near the tabs, using the same "next
        # sibling after tab bar" approach as before, for comparison.
        html = page.content()
        browser.close()

    print(f"\nTotal HTML length: {len(html)}")

    # Quick keyword scan across the FULL html (not just visible text)
    # for common standings header variants.
    keywords = ["GF", "GA", "GD", "MP", "Pts", "PTS", "Pld", "W D L"]
    for kw in keywords:
        count = html.count(kw)
        print(f"Occurrences of {kw!r} in raw HTML: {count}")


if __name__ == "__main__":
    main()
