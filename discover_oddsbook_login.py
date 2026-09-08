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
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 390, "height": 844},  # mobile viewport — the login button is data-testid="bottomnav-profile-login", CSS-hidden on desktop widths
        )
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

        # Dump ALL buttons and links with any text, to find the real
        # sign-in trigger — exact-text "Sign In" search found nothing.
        html_before = page.content()
        from bs4 import BeautifulSoup
        soup_before = BeautifulSoup(html_before, "html.parser")

        print("\n--- All buttons with text ---")
        for b in soup_before.find_all("button"):
            text = b.get_text(" ", strip=True)
            if text:
                print(f"  button: {text!r} class={b.get('class')} aria-label={b.get('aria-label')!r}")

        print("\n--- All links with text mentioning sign/log/account/user ---")
        for a in soup_before.find_all("a"):
            text = a.get_text(" ", strip=True).lower()
            if any(kw in text for kw in ["sign", "log", "account", "register"]):
                print(f"  a: text={a.get_text(' ', strip=True)!r} href={a.get('href')!r}")

        print("\n--- All elements with aria-label mentioning sign/log/account ---")
        for el in soup_before.find_all(attrs={"aria-label": True}):
            label = el.get("aria-label", "").lower()
            if any(kw in label for kw in ["sign", "log", "account", "user", "menu"]):
                print(f"  {el.name}: aria-label={el.get('aria-label')!r}")

        # Try clicking "Profile" — a more typical account-icon trigger
        # for logged-out users. The earlier "Retry"/mz-login attempt
        # registered a click but nothing opened, suggesting that
        # button is a stalled session-check, not the login CTA itself.
        try:
            profile_btn = page.locator('[data-testid="bottomnav-profile-login"]').first
            profile_btn.click(timeout=8000)
            print("\nClicked bottomnav-profile-login.")
        except Exception as e:
            print(f"\nCould not click bottomnav-profile-login: {e}")

        page.wait_for_timeout(2500)
        print(f"URL after Profile click: {page.url}")

        html_after_profile = page.content()
        from bs4 import BeautifulSoup
        soup_after_profile = BeautifulSoup(html_after_profile, "html.parser")

        inputs_after_profile = soup_after_profile.find_all("input")
        print(f"Inputs after Profile click: {len(inputs_after_profile)}")
        for inp in inputs_after_profile:
            print(f"  type={inp.get('type')!r} name={inp.get('name')!r} placeholder={inp.get('placeholder')!r}")

        # Dump any NEW buttons that appeared after the Profile click.
        buttons_after = soup_after_profile.find_all("button")
        print(f"\nAll buttons after Profile click ({len(buttons_after)}):")
        for b in buttons_after:
            text = b.get_text(" ", strip=True)
            if text and any(kw in text.lower() for kw in ["sign", "log", "email", "password", "register", "continue"]):
                print(f"  button: {text!r} class={b.get('class')}")

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
