"""
Minimal test app for the Oddsbook fetchers.

Deploy this to Render and visit the endpoints below in your browser:

/
/test-fixtures
/test-fixtures?date=2026-09-05
/test-odds?home=Liverpool&away=Arsenal
/test-slugs

Deep diagnostics:

/debug-html
/debug-html?date=2026-09-05

/debug-standings?country=england&league=premier-league

The standings diagnostic does NOT assume Oddsbook uses an HTML <table>.
It investigates the actual rendered DOM after clicking the Standings tab.
"""

import re
from datetime import date, datetime

from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from playwright.sync_api import sync_playwright

from oddsbook_odds import (
get_fixtures_for_day,
get_oddsbook_market_odds,
)
from oddsbook_leagues import verify_all_slugs

app = FastAPI(
title="Oddsbook Fetcher Test",
version="1.0.0",
)

------------------------------------------------------------

Configuration

------------------------------------------------------------

ODDSBOOK_BASE = "https://oddsbook.com"

USER_AGENT = (
"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
"AppleWebKit/537.36 (KHTML, like Gecko) "
"Chrome/124.0.0.0 Safari/537.36"
)

------------------------------------------------------------

Home

------------------------------------------------------------

@app.get("/")
def home():
return {
"status": "ok",
"message": "Oddsbook Fetcher Test API is running",
"try": [
"/test-fixtures",
"/test-fixtures?date=2026-09-05",
"/test-odds?home=Liverpool&away=Arsenal",
"/test-slugs",
"/debug-html",
"/debug-html?date=2026-09-05",
"/debug-standings?country=england&league=premier-league",
],
}

------------------------------------------------------------

Test fixtures

------------------------------------------------------------

@app.get("/test-fixtures")
def test_fixtures(date_str: str = Query(None, alias="date")):
"""
Visit:

    /test-fixtures

or:

    /test-fixtures?date=2026-09-05
"""

try:
    target = (
        datetime.strptime(
            date_str,
            "%Y-%m-%d",
        ).date()
        if date_str
        else date.today()
    )
except ValueError:
    return {
        "error": "Invalid date format. Use YYYY-MM-DD",
        "received": date_str,
    }

by_league = get_fixtures_for_day(target)

total_matches = sum(
    len(league.get("matches", []))
    for league in by_league.values()
)

return {
    "date": str(target),
    "league_count": len(by_league),
    "total_matches": total_matches,
    "leagues": by_league,
}

------------------------------------------------------------

Test market odds

------------------------------------------------------------

@app.get("/test-odds")
def test_odds(
home: str = Query(...),
away: str = Query(...),
):
"""
Example:

    /test-odds?home=Liverpool&away=Arsenal
"""

result = get_oddsbook_market_odds(
    home,
    away,
)

return {
    "home": home,
    "away": away,
    "result": result,
}

------------------------------------------------------------

Deep standings diagnostic

------------------------------------------------------------

@app.get("/debug-standings")
def debug_standings(
country: str = Query(...),
league: str = Query(...),
):
"""
Deep diagnostic for an Oddsbook league standings page.

Example:

    /debug-standings?country=england&league=premier-league

This endpoint:

1. Opens the league page using Playwright.
2. Waits for JavaScript and possible Cloudflare checks.
3. Finds a visible Standings tab.
4. Clicks it.
5. Waits for the React/Next.js content to render.
6. Searches for normal HTML tables.
7. Searches for standings-related text.
8. Searches for possible standings containers.
9. Extracts useful data-* attributes.

This helps us discover the REAL HTML structure before writing
oddsbook_stats.py.
"""

url = (
    f"{ODDSBOOK_BASE}/football/"
    f"{country}/{league}/"
)

browser = None

try:
    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={
                "width": 1366,
                "height": 900,
            },
        )

        page = context.new_page()

        # ------------------------------------------------
        # Load page
        # ------------------------------------------------

        response = page.goto(
            url,
            timeout=60000,
            wait_until="domcontentloaded",
        )

        status_code = (
            response.status
            if response is not None
            else None
        )

        # ------------------------------------------------
        # Wait for possible Cloudflare challenge
        # ------------------------------------------------

        try:
            page.wait_for_function(
                """
                () => {
                    const title =
                        (document.title || '').toLowerCase();

                    return !title.includes(
                        'just a moment'
                    );
                }
                """,
                timeout=30000,
            )
        except Exception:
            pass

        # Give Next.js / React time to hydrate
        page.wait_for_timeout(3000)

        title_before = page.title()
        url_before = page.url

        # ------------------------------------------------
        # Find Standings elements
        # ------------------------------------------------

        standings_locator = page.get_by_text(
            "Standings",
            exact=True,
        )

        standings_count = standings_locator.count()

        visible_standings = 0

        for i in range(standings_count):
            try:
                if standings_locator.nth(i).is_visible():
                    visible_standings += 1
            except Exception:
                pass

        # ------------------------------------------------
        # Click visible Standings tab
        # ------------------------------------------------

        clicked = False
        click_error = None

        try:

            for i in range(standings_count):

                element = standings_locator.nth(i)

                try:

                    if not element.is_visible():
                        continue

                    element.scroll_into_view_if_needed()

                    element.click(
                        timeout=10000,
                    )

                    clicked = True
                    break

                except Exception:
                    continue

            if not clicked:
                click_error = (
                    "No visible Standings element "
                    "could be clicked"
                )

        except Exception as exc:
            click_error = str(exc)

        # ------------------------------------------------
        # Wait for standings content to render
        # ------------------------------------------------

        page.wait_for_timeout(4000)

        title_after = page.title()
        url_after = page.url

        # Wait for network activity to settle
        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=10000,
            )
        except Exception:
            pass

        # Final short wait after network requests
        page.wait_for_timeout(1500)

        # ------------------------------------------------
        # Capture final rendered HTML
        # ------------------------------------------------

        html = page.content()

        # Capture visible text from body
        try:
            body_text = page.locator(
                "body"
            ).inner_text(
                timeout=10000
            )
        except Exception as exc:
            body_text = (
                f"Could not extract body text: {exc}"
            )

        # Get some page statistics directly from browser
        try:
            dom_stats = page.evaluate(
                """
                () => ({
                    tables:
                        document.querySelectorAll(
                            'table'
                        ).length,

                    articles:
                        document.querySelectorAll(
                            'article'
                        ).length,

                    sections:
                        document.querySelectorAll(
                            'section'
                        ).length,

                    divs:
                        document.querySelectorAll(
                            'div'
                        ).length,

                    buttons:
                        document.querySelectorAll(
                            'button'
                        ).length,

                    links:
                        document.querySelectorAll(
                            'a'
                        ).length
                })
                """
            )
        except Exception:
            dom_stats = {}

        # Close browser
        browser.close()
        browser = None

except Exception as exc:

    if browser is not None:
        try:
            browser.close()
        except Exception:
            pass

    return {
        "fetch_exception": str(exc),
        "url": url,
    }

# --------------------------------------------------------
# Parse final HTML
# --------------------------------------------------------

soup = BeautifulSoup(
    html,
    "html.parser",
)

tables = soup.find_all("table")

# --------------------------------------------------------
# Base result
# --------------------------------------------------------

result = {
    "url": url,
    "http_status": status_code,
    "page_title_before": title_before,
    "page_title_after": title_after,
    "url_before": url_before,
    "url_after": url_after,
    "standings_elements_found": standings_count,
    "visible_standings_elements": visible_standings,
    "clicked_standings_tab": clicked,
    "click_error": click_error,
    "response_length": len(html),
    "table_count": len(tables),
    "dom_stats": dom_stats,
    "body_text_preview": body_text[:20000],
}

# --------------------------------------------------------
# Cloudflare warning
# --------------------------------------------------------

page_title_lower = (
    title_after.lower()
    if title_after
    else ""
)

if (
    "just a moment" in page_title_lower
    or "attention required" in page_title_lower
):
    result["warning"] = (
        "Possible Cloudflare challenge still active"
    )

# --------------------------------------------------------
# HTML table previews
# --------------------------------------------------------

if tables:

    result["table_previews"] = [
        str(table)[:6000]
        for table in tables[:5]
    ]

else:
    result["table_previews"] = []

# --------------------------------------------------------
# Search for standings keywords
# --------------------------------------------------------

keywords = [
    "PTS",
    "Points",
    "GP",
    "Played",
    "Games Played",
    "W",
    "Wins",
    "D",
    "Draws",
    "L",
    "Losses",
    "Team",
    "Position",
    "Goal Difference",
    "GD",
    "Form",
]

keyword_hits = {}

for keyword in keywords:

    matches = soup.find_all(
        string=lambda text: (
            text
            and text.strip().lower()
            == keyword.lower()
        )
    )

    if not matches:
        continue

    previews = []

    for text_node in matches[:5]:

        parent = text_node.parent

        # Walk up through parents to find a useful
        # container containing the standings row/header.
        for _ in range(6):

            if parent is None:
                break

            preview = str(parent)

            if len(preview) >= 200:

                previews.append(
                    preview[:6000]
                )

                break

            parent = parent.parent

    if previews:
        keyword_hits[keyword] = previews

result["keyword_hits"] = keyword_hits

# --------------------------------------------------------
# Search for possible standings containers
# --------------------------------------------------------

interesting_elements = []

search_words = [
    "standing",
    "standings",
    "table",
    "ranking",
    "rank",
    "league",
    "stat",
    "position",
]

seen_html = set()

for tag in soup.find_all(
    ["div", "section", "article", "main"]
):

    classes = " ".join(
        tag.get("class", [])
    )

    tag_id = str(
        tag.get("id", "")
    )

    test_id = str(
        tag.get("data-testid", "")
    )

    role = str(
        tag.get("role", "")
    )

    combined = (
        classes
        + " "
        + tag_id
        + " "
        + test_id
        + " "
        + role
    ).lower()

    if not any(
        word in combined
        for word in search_words
    ):
        continue

    preview = str(tag)[:6000]

    if preview in seen_html:
        continue

    seen_html.add(preview)

    interesting_elements.append({
        "tag": tag.name,
        "classes": tag.get("class", []),
        "id": tag.get("id"),
        "data_testid": tag.get(
            "data-testid"
        ),
        "role": tag.get("role"),
        "html": preview,
    })

    if len(interesting_elements) >= 20:
        break

result["possible_standings_html"] = (
    interesting_elements
)

# --------------------------------------------------------
# Find useful data-* attributes
# --------------------------------------------------------

data_attributes = []

for tag in soup.find_all():

    attrs = {}

    for key, value in tag.attrs.items():

        if str(key).startswith("data-"):

            attrs[key] = value

    if attrs:

        data_attributes.append({
            "tag": tag.name,
            "attributes": attrs,
        })

    if len(data_attributes) >= 200:
        break

result["sample_data_attributes"] = (
    data_attributes
)

# --------------------------------------------------------
# Search for text containing likely standings phrases
# --------------------------------------------------------

standings_text_hits = []

phrase_pattern = re.compile(
    r"\b("
    r"standings?|"
    r"points?|"
    r"played|"
    r"wins?|"
    r"draws?|"
    r"losses?|"
    r"goal difference|"
    r"form"
    r")\b",
    re.IGNORECASE,
)

for text_node in soup.find_all(
    string=phrase_pattern
):

    text = text_node.strip()

    if not text:
        continue

    parent = text_node.parent

    standings_text_hits.append({
        "text": text[:500],
        "parent_tag": (
            parent.name
            if parent
            else None
        ),
        "parent_class": (
            parent.get("class", [])
            if parent
            else []
        ),
    })

    if len(standings_text_hits) >= 100:
        break

result["standings_text_hits"] = (
    standings_text_hits
)

return result

------------------------------------------------------------

Debug raw day-page HTML

------------------------------------------------------------

@app.get("/debug-html")
def debug_html(
date_str: str = Query(
None,
alias="date",
)
):
"""
Shows the rendered HTML structure of Oddsbook's day page.

Examples:

    /debug-html

    /debug-html?date=2026-09-05
"""

try:

    target = (
        datetime.strptime(
            date_str,
            "%Y-%m-%d",
        ).date()
        if date_str
        else date.today()
    )

except ValueError:

    return {
        "error": (
            "Invalid date format. "
            "Use YYYY-MM-DD"
        ),
        "received": date_str,
    }

date_s = target.strftime(
    "%Y-%m-%d"
)

url = (
    f"{ODDSBOOK_BASE}/football/"
    f"?date={date_s}"
)

browser = None

try:

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={
                "width": 1366,
                "height": 900,
            },
        )

        page = context.new_page()

        response = page.goto(
            url,
            timeout=60000,
            wait_until="domcontentloaded",
        )

        status_code = (
            response.status
            if response is not None
            else None
        )

        try:

            page.wait_for_function(
                """
                () => {
                    const title =
                        (document.title || '').toLowerCase();

                    return !title.includes(
                        'just a moment'
                    );
                }
                """,
                timeout=30000,
            )

        except Exception:
            pass

        # Wait specifically for real fixture data.
        try:

            page.wait_for_selector(
                "article[data-game-item]",
                timeout=30000,
            )

        except Exception:
            # Continue to collect diagnostics even if
            # fixtures never appeared.
            pass

        page.wait_for_timeout(2000)

        title = page.title()

        html = page.content()

        try:

            body_text = page.locator(
                "body"
            ).inner_text()

        except Exception as exc:

            body_text = (
                f"Could not read body text: {exc}"
            )

        browser.close()
        browser = None

except Exception as exc:

    if browser is not None:

        try:
            browser.close()

        except Exception:
            pass

    return {
        "fetch_exception": str(exc),
        "url": url,
    }

result = {
    "url": url,
    "http_status": status_code,
    "page_title": title,
    "response_length": len(html),
    "body_text_preview": body_text[:15000],
    "first_2000_chars": html[:2000],
}

page_title_lower = (
    title.lower()
    if title
    else ""
)

if (
    "just a moment" in page_title_lower
    or "attention required" in page_title_lower
):

    result["warning"] = (
        "Possible Cloudflare challenge "
        "still active"
    )

soup = BeautifulSoup(
    html,
    "html.parser",
)

# --------------------------------------------------------
# Count confirmed fixture structures
# --------------------------------------------------------

fixture_articles = soup.select(
    "article[data-game-item]"
)

league_sections = soup.select(
    "section[data-league-slug]"
)

result.update({

    "fixture_articles_found":
        len(fixture_articles),

    "league_sections_found":
        len(league_sections),

})

# --------------------------------------------------------
# Find links
# --------------------------------------------------------

all_links = soup.find_all(
    "a",
    href=True,
)

match_link_re = re.compile(
    r"^/football/[^/]+/[^/]+/"
    r"[^/]+/\d+/?$"
)

league_link_re = re.compile(
    r"^/football/[^/]+/[^/]+/?$"
)

match_links = [

    a["href"]

    for a in all_links

    if match_link_re.match(
        a["href"]
    )

]

league_links = [

    a["href"]

    for a in all_links

    if league_link_re.match(
        a["href"]
    )

]

result.update({

    "total_a_tags":
        len(all_links),

    "match_links_found":
        len(match_links),

    "league_links_found":
        len(league_links),

    "sample_match_links":
        match_links[:10],

    "sample_league_links":
        league_links[:20],

})

# --------------------------------------------------------
# Grab one full fixture article
# --------------------------------------------------------

article = soup.select_one(
    "article[data-game-item]"
)

if article:

    result["full_article_html"] = (
        str(article)[:8000]
    )

else:

    result["full_article_html"] = (
        "NOT FOUND"
    )

# --------------------------------------------------------
# Sample league sections
# --------------------------------------------------------

result["sample_league_sections"] = [

    {
        "country_slug": section.get(
            "data-country-slug"
        ),

        "league_slug": section.get(
            "data-league-slug"
        ),

        "league_id": section.get(
            "data-league"
        ),

        "html_preview":
            str(section)[:4000],

    }

    for section in league_sections[:5]

]

return result

------------------------------------------------------------

Test Oddsbook league slugs

------------------------------------------------------------

@app.get("/test-slugs")
def test_slugs():
"""
Verifies league slugs against Oddsbook.

WARNING:
This may take a long time if verify_all_slugs()
checks many leagues.
"""

try:

    result = verify_all_slugs()

    return {

        "ok_count":
            len(result.get("ok", [])),

        "broken_count":
            len(result.get("broken", [])),

        "ok":
            result.get("ok", []),

        "broken": [

            {
                "league": name,
                "url": url,
                "error": str(error),
            }

            for name, url, error
            in result.get(
                "broken",
                []
            )

        ],

    }

except Exception as exc:

    return {
        "error": str(exc),
    }
