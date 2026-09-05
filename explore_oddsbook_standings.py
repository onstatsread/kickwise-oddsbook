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
except ImportError:
    HAS_STEALTH = False

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

        # Human-like mouse movement before interacting.
        try:
            page.mouse.move(200, 300)
            human_delay(0.3, 0.7)
            page.mouse.move(400, 450, steps=10)
            human_delay(0.3, 0.7)
        except Exception as e:
            print(f"Mouse movement failed: {e}")

        before_count = len(captured)

        try:
            standings_tab = page.get_by_role("tab", name="Standings", exact=True)
            box = standings_tab.bounding_box()
            if box:
                # Move mouse to the tab first, pause, then click —
                # more human-like than an instant programmatic click.
                page.mouse.move(
                    box["x"] + box["width"] / 2,
                    box["y"] + box["height"] / 2,
                    steps=15,
                )
                human_delay(0.2, 0.5)
            standings_tab.click(timeout=8000)
            print("Clicked Standings tab.")
        except Exception as e:
            print(f"Click failed: {e}")

        human_delay(3, 4)

        new_responses = captured[before_count:]
        print(f"\nBFF responses captured AFTER clicking Standings ({len(new_responses)} new):")
        for c in new_responses:
            print(f"\n  [{c['status']}] {c['url']}")
            print(f"  is_challenge={c['is_challenge']}, body_len={c['body_len']}")
            print(f"  Preview: {c['body_preview']}")

        if not new_responses:
            print("  (none captured)")

        browser.close()

    print(f"\nTotal bff/league responses captured overall: {len(captured)}")
    success = [c for c in captured if c["status"] == 200 and not c["is_challenge"]]
    print(f"Successful (200, non-challenge) responses: {len(success)}")


if __name__ == "__main__":
    main()
