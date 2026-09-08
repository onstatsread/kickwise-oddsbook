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
    except Exception as e:
        print(f"Failed to open login panel: {e}")
        return False

    page.wait_for_timeout(1000)

    try:
        page.locator("button.amv2-email-cta").first.click(timeout=8000)
    except Exception as e:
        print(f"Failed to click 'Continue with email': {e}")
        return False

    page.wait_for_timeout(1000)

    try:
        page.locator('input[name="email"]').first.fill(email, timeout=8000)
        page.locator('input[name="password"]').first.fill(password, timeout=8000)
    except Exception as e:
        print(f"Failed to fill login form: {e}")
        return False

    try:
        page.locator('button.auth-btn[type="submit"]').first.click(timeout=8000)
    except Exception as e:
        print(f"Failed to click Sign In submit: {e}")
        return False

    page.wait_for_timeout(3000)

    # Verify: the page's embedded JSON config should now show
    # "authenticated":true (confirmed field from earlier investigation
    # into the gated odds tab).
    html = page.content()
    authenticated = '"authenticated":true' in html

    if authenticated:
        print("Login succeeded — page shows authenticated:true")
    else:
        print("Login may have failed — 'authenticated:true' not found in page")

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
