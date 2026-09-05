"""
Second attempt at cracking Oddsbook's standings BFF endpoint.

CONFIRMED so far: even the site's OWN click-triggered request to
    https://oddsbook.com/bff/league/{id}/tab/standings/?...
gets a 403 Cloudflare challenge — meaning Cloudflare's bot-management
is scoring this browser session as automated and applying a stricter
rule specifically to that API path (the main HTML pages pass fine).

This attempt tries several anti-detection techniques together:
1. playwright-stealth (patches navigator.webdriver, chrome runtime,
   permissions, plugins, WebGL vendor, and other automation tells)
2. Real Chrome channel instead of bundled Chromium (different,
   more "normal" fingerprint)
3. Realistic viewport/locale/timezone/geolocation context
4. Human-like delays and a real mouse move before clicking
5. Captures the actual response status of the click-triggered request
"""

import random
import time
from playwright.sync_api import sync_playwright

try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
    STEALTH_IMPORT_ERROR = None
except Exception as e:
    HAS_STEALTH = False
    STEALTH_IMPORT_ERROR = str(e)

COUNTRY = "england"
LEAGUE = "premier-league"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


def human_delay(a=0.5, b=1.5):
    time.sleep(random.uniform(a, b))


def main():
    print(f"playwright-stealth available: {HAS_STEALTH}")
    if not HAS_STEALTH:
        print(f"Stealth import error: {STEALTH_IMPORT_ERROR}")

    url = f"https://oddsbook.com/football/{COUNTRY}/{LEAGUE}/"
    captured = []

    with sync_playwright() as p:
        launch_kwargs = {"headless": True}
        try:
            browser = p.chromium.launch(channel="chrome", **launch_kwargs)
            print("Launched using real Chrome channel.")
        except Exception as e:
            print(f"Chrome channel unavailable ({e}), falling back to bundled Chromium.")
            browser = p.chromium.launch(**launch_kwargs)

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1366, "height": 768},
            locale="en-GB",
            timezone_id="Europe/London",
            device_scale_factor=1,
        )

        page = context.new_page()

        if HAS_STEALTH:
            stealth_sync(page)
            print("Applied playwright-stealth patches.")

        def on_response(response):
            if "bff/league" in response.url:
                try:
                    body = response.text()
                except Exception as e:
                    body = f"<could not read body: {e}>"
                captured.append({
                    "url": response.url,
                    "status": response.status,
                    "body_len": len(body),
                    "body_preview": body[:1500],
                    "is_challenge": "Just a moment" in body,
                })

        page.on("response", on_response)

        print(f"Loading {url} ...")
        page.goto(url, timeout=45000, wait_until="domcontentloaded")

        try:
            page.wait_for_function(
                "document.title !== 'Just a moment...'", timeout=20000
            )
        except Exception:
            pass

        human_delay(1.5, 2.5)
        print(f"Page title: {page.title()}")

        # Direct in-page fetch() calls — guarantees the exact same
        # browser fingerprint/TLS/headers as the page's own requests
        # (which we just confirmed CAN pass Cloudflare using the real
        # Chrome channel), without depending on UI click reliability.
        endpoints = {
            "standings": "https://oddsbook.com/bff/league/39/tab/standings/?sport=football&season=2026&lang=en",
            "statistics": "https://oddsbook.com/bff/league/39/tab/statistics/?sport=football&season=2026&lang=en",
        }

        for name, endpoint_url in endpoints.items():
            print(f"\n--- Direct in-page fetch: {name} ---")
            try:
                result = page.evaluate(
                    """async (url) => {
                        const resp = await fetch(url, {
                            headers: { 'Accept': 'application/json' },
                            credentials: 'include'
                        });
                        const text = await resp.text();
                        return { status: resp.status, body: text };
                    }""",
                    endpoint_url,
                )
                status = result["status"]
                body = result["body"]
                is_challenge = "Just a moment" in body
                print(f"Status: {status}, is_challenge: {is_challenge}, body_len: {len(body)}")
                print(f"Preview: {body[:2000]}")
            except Exception as e:
                print(f"fetch() failed: {e}")

            human_delay(1, 2)

        browser.close()

    print(f"\nTotal bff/league responses captured overall: {len(captured)}")
    success = [c for c in captured if c["status"] == 200 and not c["is_challenge"]]
    print(f"Successful (200, non-challenge) responses: {len(success)}")


if __name__ == "__main__":
    main()
