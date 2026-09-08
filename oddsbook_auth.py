"""
Oddsbook login flow — confirmed real structure (2026-09-08):

1. Requires a MOBILE viewport — the login trigger is a bottom-nav
   button (data-testid="bottomnav-profile-login") that's CSS-hidden
   on desktop-width viewports.
2. Click that button -> opens an auth panel with "Continue with
   email" (button.amv2-email-cta).
3. Click that -> reveals the real form:
     <input type="email" name="email">
     <input type="password" name="password">
     <button class="auth-btn" type="submit"> (text: "Sign In")
"""

from playwright.sync_api import sync_playwright

MOBILE_VIEWPORT = {"width": 390, "height": 844}

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)


def oddsbook_login(page, email, password):
    """
    Runs the full login flow on an already-navigated Oddsbook page
    (call page.goto("https://oddsbook.com/") first). Returns True if
    login appears to have succeeded, False otherwise.
    """
    try:
        page.locator('[data-testid="bottomnav-profile-login"]').first.click(timeout=8000)
        print("Step 1 OK: clicked bottomnav-profile-login")
    except Exception as e:
        print(f"Step 1 FAILED: opening login panel: {e}")
        return False

    page.wait_for_timeout(1000)

    try:
        page.locator("button.amv2-email-cta").first.click(timeout=8000)
        print("Step 2 OK: clicked 'Continue with email'")
    except Exception as e:
        print(f"Step 2 FAILED: clicking 'Continue with email': {e}")
        return False

    page.wait_for_timeout(1000)

    try:
        page.locator('input[name="email"]').first.fill(email, timeout=8000)
        page.locator('input[name="password"]').first.fill(password, timeout=8000)
        print("Step 3 OK: filled email + password fields")
    except Exception as e:
        print(f"Step 3 FAILED: filling login form: {e}")
        return False

    # Confirm what's actually in the fields before submitting.
    try:
        filled_email = page.locator('input[name="email"]').first.input_value()
        filled_pw_len = len(page.locator('input[name="password"]').first.input_value())
        print(f"  Verified email field value: {filled_email!r}")
        print(f"  Verified password field length: {filled_pw_len}")
    except Exception as e:
        print(f"  Could not verify field values: {e}")

    try:
        page.locator('button.auth-btn[type="submit"]').first.click(timeout=8000)
        print("Step 4 OK: clicked Sign In submit")
    except Exception as e:
        print(f"Step 4 FAILED: clicking Sign In submit: {e}")
        return False

    page.wait_for_timeout(4000)

    html = page.content()

    # Look for any visible error message on the page.
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    error_candidates = soup.find_all(
        attrs={"class": lambda c: c and any("error" in cl.lower() for cl in c)}
    )
    if error_candidates:
        print(f"\nFound {len(error_candidates)} elements with 'error' in their class:")
        for el in error_candidates[:5]:
            text = el.get_text(" ", strip=True)
            if text:
                print(f"  {el.name}.{el.get('class')}: {text!r}")

    # Check if the auth form is STILL present (would mean submit
    # didn't actually go through, or failed silently).
    still_has_form = bool(soup.find("form", class_="auth-form"))
    print(f"\nAuth form still present after submit: {still_has_form}")

    if still_has_form:
        form_text = soup.find("form", class_="auth-form").get_text(" ", strip=True)
        print(f"Auth form text content: {form_text!r}")

    authenticated = '"authenticated":true' in html

    if authenticated:
        print("\nLogin succeeded — page shows authenticated:true")
    else:
        print("\nLogin may have failed — 'authenticated:true' not found in page")

    return authenticated


def new_authenticated_context(browser, email, password):
    """
    Creates a new browser context, logs in, and returns the
    authenticated context + page for reuse across multiple page
    visits (session/cookies persist within the context).
    """
    context = browser.new_context(user_agent=USER_AGENT, viewport=MOBILE_VIEWPORT)
    page = context.new_page()

    page.goto("https://oddsbook.com/", timeout=45000, wait_until="domcontentloaded")

    try:
        page.wait_for_function(
            "document.title !== 'Just a moment...'", timeout=20000
        )
    except Exception:
        pass

    page.wait_for_timeout(1500)

    success = oddsbook_login(page, email, password)

    return context, page, success


if __name__ == "__main__":
    import os

    email = os.environ["ODDSBOOK_EMAIL"]
    password = os.environ["ODDSBOOK_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context, page, success = new_authenticated_context(browser, email, password)

        print(f"\nLogin success: {success}")
        print(f"Current URL: {page.url}")

        browser.close()
