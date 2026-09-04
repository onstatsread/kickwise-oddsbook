"""
Minimal test app for the Oddsbook fetchers — deploy this to Render
and hit the URLs below in your phone browser to see real output.
No shell/SSH needed.
"""

from fastapi import FastAPI, Query
from datetime import date, datetime
import re

from oddsbook_odds import get_fixtures_for_day, get_oddsbook_market_odds, _fetch_day_page
from oddsbook_leagues import verify_all_slugs
from bs4 import BeautifulSoup

app = FastAPI(title="Oddsbook Fetcher Test")


@app.get("/")
def home():
    return {
        "status": "ok",
        "try": [
            "/test-fixtures",
            "/test-fixtures?date=2026-09-05",
            "/test-odds?home=Liverpool&away=Arsenal",
            "/test-slugs",
        ],
    }


@app.get("/test-fixtures")
def test_fixtures(date_str: str = Query(None, alias="date")):
    """
    Visit: /test-fixtures  (today)
    or:    /test-fixtures?date=2026-09-05
    """
    target = (
        datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_str else date.today()
    )

    by_league = get_fixtures_for_day(target)

    return {
        "date": str(target),
        "league_count": len(by_league),
        "leagues": by_league,
    }


@app.get("/test-odds")
def test_odds(home: str = Query(...), away: str = Query(...)):
    """
    Visit: /test-odds?home=Liverpool&away=Arsenal
    """
    return get_oddsbook_market_odds(home, away)


@app.get("/debug-html")
def debug_html(date_str: str = Query(None, alias="date")):
    """
    Diagnostic — shows the REAL raw HTML structure of Oddsbook's day
    page, so the parser in oddsbook_odds.py can be fixed against
    what's actually there instead of a guess. Does its own fetch
    (not via the silently-failing helper) so real errors/status
    codes/response bodies are visible instead of swallowed.
    """
    from playwright.sync_api import sync_playwright

    target = (
        datetime.strptime(date_str, "%Y-%m-%d").date()
        if date_str else date.today()
    )
    date_s = target.strftime("%Y-%m-%d")
    url = f"https://oddsbook.com/football/?date={date_s}"

    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(url, timeout=45000, wait_until="domcontentloaded")

            try:
                page.wait_for_function(
                    "document.title !== 'Just a moment...'",
                    timeout=20000,
                )
            except Exception:
                pass

            page.wait_for_timeout(2000)

            title = page.title()
            html = page.content()
            browser.close()
    except Exception as e:
        return {"fetch_exception": str(e), "url": url}

    result = {
        "url": url,
        "page_title": title,
        "response_length": len(html),
        "first_1000_chars": html[:1000],
    }

    if title == "Just a moment...":
        result["warning"] = "Still hitting the Cloudflare challenge page"
        return result
    soup = BeautifulSoup(html, "html.parser")

    all_links = soup.find_all("a", href=True)

    match_link_re = re.compile(r"^/football/[^/]+/[^/]+/[^/]+/\d+/?$")
    league_link_re = re.compile(r"^/football/[^/]+/[^/]+/?$")

    match_links = [a["href"] for a in all_links if match_link_re.match(a["href"])]
    league_links = [a["href"] for a in all_links if league_link_re.match(a["href"])]

    sample_html = ""
    if match_links:
        first_link_tag = soup.find("a", href=match_links[0])
        if first_link_tag:
            container = first_link_tag
            for _ in range(3):
                if container.parent:
                    container = container.parent
            sample_html = str(container)[:3000]

    result.update({
        "total_a_tags": len(all_links),
        "match_links_found": len(match_links),
        "league_links_found": len(league_links),
        "sample_match_links": match_links[:5],
        "sample_league_links": league_links[:10],
        "sample_row_html": sample_html,
    })

    return result


@app.get("/test-slugs")
def test_slugs():
    """
    Verifies all 61 league slugs against live Oddsbook. Takes ~90s
    (61 leagues x 1.5s delay) — Render free tier may time out on
    this one; if it does, reduce the league list temporarily or
    run in smaller batches by editing verify_all_slugs() to accept
    a start/end slice like app.py's /check_leagues_gp does.
    """
    result = verify_all_slugs()
    return {
        "ok_count": len(result["ok"]),
        "broken_count": len(result["broken"]),
        "broken": [
            {"league": name, "url": url, "error": str(err)}
            for name, url, err in result["broken"]
        ],
    }
