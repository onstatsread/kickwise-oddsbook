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

    all_xhr_requests = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        def on_request(request):
            if request.resource_type in ("xhr", "fetch"):
                all_xhr_requests.append(f"{request.method} {request.url}")

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

        print(f"\nXHR/fetch requests BEFORE clicking Standings ({len(all_xhr_requests)}):")
        for u in all_xhr_requests:
            print(f"  {u}")

        before_count = len(all_xhr_requests)

        # Click the Standings tab.
        try:
            page.get_by_role("tab", name="Standings", exact=True).click(timeout=8000)
            print("\nClicked Standings tab successfully.")
        except Exception as e:
            print(f"\nClick failed: {e}")

        page.wait_for_timeout(3000)

        try:
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(3000)
            print("Scrolled down and waited an extra 3s.")
        except Exception as e:
            print(f"Scroll attempt failed: {e}")

        new_requests = all_xhr_requests[before_count:]
        print(f"\nXHR/fetch requests AFTER clicking Standings ({len(new_requests)} new):")
        for u in new_requests:
            print(f"  {u}")

        # FOUND IT — the real standings data source is a JSON API:
        #   https://oddsbook.com/bff/league/{league_id}/tab/standings/
        #       ?sport=football&season={year}&lang=en
        # Fetch it directly via the same browser context (so it carries
        # the Cloudflare-clearance cookie/session already established)
        # and print the raw JSON response.
        print("\n--- Fetching BFF standings endpoint directly ---")
        try:
            bff_url = (
                "https://oddsbook.com/bff/league/39/tab/standings/"
                "?sport=football&season=2026&lang=en"
            )
            resp = page.request.get(bff_url)
            print(f"Status: {resp.status}")
            body = resp.text()
            print(f"Response length: {len(body)}")
            print(body[:6000])
        except Exception as e:
            print(f"BFF fetch failed: {e}")

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
