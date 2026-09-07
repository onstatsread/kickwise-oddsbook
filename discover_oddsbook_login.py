"""
Discovers Oddsbook's login form structure — clicks "Sign In" and
dumps the resulting form's HTML so the real login function can target
the correct field names/selectors, rather than guessing.

Does NOT use real credentials yet — just inspects the form.
"""

from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        print("Loading homepage...")
        page.goto("https://oddsbook.com/", timeout=45000, wait_until="domcontentloaded")

        try:
            page.wait_for_function(
                "document.title !== 'Just a moment...'", timeout=20000
            )
        except Exception:
            pass

        page.wait_for_timeout(2000)
        print(f"Page title: {page.title()}")

        # Find and click "Sign In".
        try:
            sign_in = page.get_by_text("Sign In", exact=True).first
            sign_in.click(timeout=8000)
            print("Clicked 'Sign In'.")
        except Exception as e:
            print(f"Could not click 'Sign In': {e}")
            # Try alternate text.
            try:
                sign_in = page.get_by_role("button", name="Sign In").first
                sign_in.click(timeout=8000)
                print("Clicked 'Sign In' (via role=button).")
            except Exception as e2:
                print(f"Alternate click also failed: {e2}")

        page.wait_for_timeout(2500)
        print(f"URL after click: {page.url}")
        print(f"Page title after click: {page.title()}")

        # Dump all input fields visible now (login form should have
        # appeared, either as a modal or a new page).
        html = page.content()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        inputs = soup.find_all("input")
        print(f"\nTotal <input> elements found: {len(inputs)}")
        for inp in inputs:
            print(f"  type={inp.get('type')!r} name={inp.get('name')!r} "
                  f"id={inp.get('id')!r} placeholder={inp.get('placeholder')!r}")

        forms = soup.find_all("form")
        print(f"\nTotal <form> elements found: {len(forms)}")
        for i, f in enumerate(forms):
            print(f"\n--- Form {i} (action={f.get('action')!r}) ---")
            print(str(f)[:2000])

        buttons = soup.find_all("button")
        submit_like = [
            b for b in buttons
            if "sign" in b.get_text(" ", strip=True).lower()
            or "log" in b.get_text(" ", strip=True).lower()
        ]
        print(f"\nSign-in/login related buttons found: {len(submit_like)}")
        for b in submit_like[:10]:
            print(f"  text={b.get_text(' ', strip=True)!r} type={b.get('type')!r}")

        browser.close()


if __name__ == "__main__":
    main()
