"""
Oddsbook standings exploration script — run via GitHub Actions
(same pattern as check_annabet_gp.py), prints diagnostics to the
workflow log instead of returning JSON via a FastAPI endpoint.

Goal: find where/how Oddsbook renders standings (GP/W/D/L/GF/GA)
data for a league page. Confirmed so far: the Standings tab click
DOES register (aria-selected=true), but the panel's visible text
just shows a "—" placeholder — data isn't rendering. GF/GA/GD exist
a couple times in raw HTML (likely just column headers/labels), but
no populated row data has shown up yet.
"""

from playwright.sync_api import sync_playwright

COUNTRY = "england"
LEAGUE = "premier-league"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def print_keyword_contexts(html, keywords, window=400):
    for kw in keywords:
        start = 0
        while True:
            idx = html.find(kw, start)
            if idx == -1:
                break
            context = html[max(0, idx - window):idx + window]
            print(f"\n>>> {kw!r} at index {idx}:\n{context}\n")
            start = idx + 1


def main():
    url = f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/"
    print(f"Loading {url} ...")

    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

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

        # Click the Standings tab.
        try:
            page.get_by_role("tab", name="Standings", exact=True).click(timeout=8000)
            print("Clicked Standings tab successfully.")
        except Exception as e:
            print(f"Click failed: {e}")

        page.wait_for_timeout(3000)

        # Try scrolling the tab panel area into view + wait longer,
        # in case it's a lazy/virtualized list.
        try:
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(3000)
            print("Scrolled down and waited an extra 3s.")
        except Exception as e:
            print(f"Scroll attempt failed: {e}")

        print(f"\nAPI-like requests seen so far ({len(api_calls)}):")
        for u in api_calls:
            print(f"  {u}")

        body_text = page.inner_text("body")
        print(f"\n--- Full visible body text ({len(body_text)} chars) ---")
        print(body_text[:8000])

        html = page.content()
        browser.close()

    print(f"\nTotal HTML length: {len(html)}")

    keywords = ["GF", "GA", "GD", "MP", "Pts", "PTS", "Pld"]
    for kw in keywords:
        print(f"Occurrences of {kw!r} in raw HTML: {html.count(kw)}")

    print("\n--- Context around each GF/GA/GD/Pts occurrence ---")
    print_keyword_contexts(html, ["GF", "GA", "GD", "Pts"])


if __name__ == "__main__":
    main()
