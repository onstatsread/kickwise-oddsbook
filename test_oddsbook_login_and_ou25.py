"""
Full end-to-end test: log in with real Oddsbook credentials, then
check a match's detail page to see if the previously-gated Over/Under
2.5 odds are now visible.
"""

import os
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from oddsbook_auth import new_authenticated_context, MOBILE_VIEWPORT, USER_AGENT


def main():
    email = os.environ["ODDSBOOK_EMAIL"]
    password = os.environ["ODDSBOOK_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context, page, success = new_authenticated_context(browser, email, password)
        print(f"Login success: {success}")

        if not success:
            print("Aborting — login did not succeed.")
            browser.close()
            return

        # Find today's fixtures to get a real match URL.
        today = date.today().strftime("%Y-%m-%d")
        day_url = f"https://oddsbook.com/football/?date={today}"

        print(f"\nLoading {day_url} (authenticated session) ...")
        page.goto(day_url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        first_article = soup.find("article", attrs={"data-game-item": True})

        if not first_article:
            print("No fixtures found today.")
            browser.close()
            return

        canonical = first_article.get("data-canonical-url", "")
        match_url = "https://oddsbook.com" + canonical if canonical.startswith("/") else canonical
        home = first_article.get("data-home-name")
        away = first_article.get("data-away-name")

        print(f"Found match: {home} vs {away}")
        print(f"Match URL: {match_url}")

        # Visit the match page WITH the authenticated session (same
        # context/page, cookies carry over).
        print(f"\nLoading match detail page (authenticated) ...")
        page.goto(match_url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        match_html = page.content()

        authenticated_now = '"authenticated":true' in match_html
        print(f"Still authenticated on match page: {authenticated_now}")

        odds_gated = '"odds":"preview"' in match_html
        odds_public = '"odds":"public"' in match_html
        print(f"Odds tab still gated (preview): {odds_gated}")
        print(f"Odds tab now public: {odds_public}")

        match_soup = BeautifulSoup(match_html, "html.parser")
        market_buttons = match_soup.find_all(attrs={"data-market": True})
        distinct_markets = set(b.get("data-market") for b in market_buttons)
        print(f"\nDistinct data-market values found: {distinct_markets}")

        # Try clicking into the Odds/Stats tab area to trigger any
        # lazy-loaded O/U content now that we're authenticated.
        try:
            odds_tab = page.get_by_text("Odds", exact=True).first
            odds_tab.click(timeout=5000)
            page.wait_for_timeout(2000)
            print("\nClicked 'Odds' tab.")

            html_after_click = page.content()
            soup_after = BeautifulSoup(html_after_click, "html.parser")
            markets_after = set(
                b.get("data-market")
                for b in soup_after.find_all(attrs={"data-market": True})
            )
            print(f"Distinct data-market values AFTER clicking Odds tab: {markets_after}")

            ou_present = "Over/Under" in html_after_click or "over_under" in html_after_click.lower()
            print(f"'Over/Under' text present after click: {ou_present}")

        except Exception as e:
            print(f"Could not click Odds tab: {e}")

        browser.close()


if __name__ == "__main__":
    main()
