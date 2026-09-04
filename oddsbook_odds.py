"""
Oddsbook fixtures + market-odds scraper.

Equivalent of annabet_odds.py, but for Oddsbook.

CONFIRMED WORKING (verified against real HTML via Playwright on
Render, 2026-09-04): https://oddsbook.com/football/?date=YYYY-MM-DD
returns every match that day, grouped by league, as clean data-*
attributes — no fragile text-scraping needed. Structure:

    <section class="... game-list ..." data-country-slug="england"
              data-league="39" data-league-slug="premier-league">
      ...
      <article class="... game-item ..." data-game-item
                data-fixture-id="1557393" data-home-name="Ipswich"
                data-away-name="Liverpool" data-home-id="57"
                data-away-id="40" data-kickoff="2026-09-04T19:00:00.000Z"
                data-status="scheduled" data-league-id="39">
        ...
        <div class="fx-score ...">
          <em class="fx-sc-ns">-</em><em class="fx-sc-ns">-</em>
        </div>
        ...
        <div aria-label="1X2" class="gi-odds ...">
          <button data-market="1x2" data-outcome="home" data-odd="6.25" .../>
          <button data-market="1x2" data-outcome="draw" data-odd="5.13" .../>
          <button data-market="1x2" data-outcome="away" data-odd="1.57" .../>
        </div>
      </article>
    </section>

Note the "-ns" score class = "not started" — a scheduled match with
no score yet. Finished-match score markup hasn't been directly
confirmed (no live/FT match was in the sampled HTML), so
_extract_score() below falls back gracefully to None/None rather
than guessing a different class name — flag this if a finished
match's score comes back empty and I'll add the right selector.

NOT YET CONFIRMED: Over/Under 2.5 odds — the day-list page only
showed a 1X2 odds block in the sampled match. O/U 2.5 may only exist
on the individual match-detail page (the data-canonical-url each
article carries), similar to how AnnaBet's O/U 2.5 lives on a
separate H2H page. get_oddsbook_ou25() is a placeholder until that's
confirmed — call it with a match's detail URL once verified.
"""

import re
import time
from datetime import date
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


ODDSBOOK_BASE = "https://oddsbook.com"

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ------------------------------------------------------------
# Cache — one entry per calendar day, since /football/?date=
# returns ALL leagues' fixtures for that day in a single request.
# ------------------------------------------------------------

_DAY_CACHE = {}
DAY_CACHE_TTL = 300  # 5 minutes — odds move, same TTL as AnnaBet's


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _norm_team(name):
    return " ".join(str(name or "").lower().split()).strip()


def _float(value):
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f <= 1.0 or f > 1000:
        return None
    return f


def _add_implied_pct(odds_dict, *keys):
    """Same normalization AnnaBet's app.py uses — adds *_pct fields
    (bookmaker overround removed) so daily_predictions.py's existing
    format_match_html()/meets_blog2_standard() code works unchanged."""
    if not odds_dict:
        return odds_dict

    vals = [odds_dict.get(k) for k in keys]
    if any(v is None or v <= 0 for v in vals):
        return odds_dict

    raw = [1 / v for v in vals]
    total = sum(raw)
    if total <= 0:
        return odds_dict

    for k, r in zip(keys, raw):
        pct_key = k.replace("_odds", "_pct")
        odds_dict[pct_key] = round(r / total * 100, 1)

    return odds_dict


# ------------------------------------------------------------
# Fetch a full day's fixtures (all leagues at once) via Playwright
# ------------------------------------------------------------

def _fetch_day_page(date_str):
    """
    date_str: 'YYYY-MM-DD'. Returns raw HTML text, or None on failure.

    Uses a real headless browser (Playwright) because Oddsbook sits
    behind a Cloudflare Turnstile-style JS challenge — confirmed on
    2026-09-04 that plain requests AND cloudscraper both get served a
    "Just a moment..." 403 page. Playwright executes the page's JS so
    Cloudflare treats it as a real browser.

    Slower/heavier than a plain HTTP call — expect several seconds
    per call. The 5-min cache below matters more here than for
    AnnaBet's plain-requests fetcher.
    """
    cache_key = date_str
    cached = _DAY_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < DAY_CACHE_TTL:
        return cached[1]

    url = f"{ODDSBOOK_BASE}/football/?date={date_str}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()

            page.goto(url, timeout=45000, wait_until="domcontentloaded")

            try:
                page.wait_for_function(
                    "document.title !== 'Just a moment...'",
                    timeout=20000,
                )
            except Exception:
                pass

            page.wait_for_timeout(2000)  # let post-challenge JS settle

            html = page.content()
            browser.close()

    except Exception as exc:
        print(f"Oddsbook Playwright fetch failed: {url} -> {exc}")
        return None

    _DAY_CACHE[cache_key] = (time.time(), html)
    return html


# ------------------------------------------------------------
# Parse — using confirmed data-* attribute structure
# ------------------------------------------------------------

def _extract_score(article):
    score_div = article.find("div", class_=re.compile(r"\bfx-score\b"))
    if not score_div:
        return None, None

    ems = score_div.find_all("em")
    if len(ems) != 2:
        return None, None

    def parse(em):
        text = em.get_text(strip=True)
        return int(text) if text.isdigit() else None

    return parse(ems[0]), parse(ems[1])


def _extract_1x2_odds(article):
    odds = {"home_odds": None, "draw_odds": None, "away_odds": None}

    odds_div = article.find("div", attrs={"aria-label": "1X2"})
    if not odds_div:
        return odds

    for btn in odds_div.find_all("button", attrs={"data-market": "1x2"}):
        outcome = btn.get("data-outcome")
        val = _float(btn.get("data-odd"))

        if outcome == "home":
            odds["home_odds"] = val
        elif outcome == "draw":
            odds["draw_odds"] = val
        elif outcome == "away":
            odds["away_odds"] = val

    return odds


def _parse_day_page(html):
    """
    Returns:
        {
            "england/premier-league": {
                "country_slug": "england",
                "league_slug": "premier-league",
                "league_id": "39",
                "league_name": "Premier League",
                "matches": [
                    {
                        "fixture_id": "1557393",
                        "kickoff": "2026-09-04T19:00:00.000Z",  # ISO, UTC
                        "status": "scheduled",
                        "home": "Ipswich",
                        "away": "Liverpool",
                        "home_score": None,
                        "away_score": None,
                        "match_url": "https://oddsbook.com/football/.../1557393/",
                        "home_odds": 6.25,
                        "draw_odds": 5.13,
                        "away_odds": 1.57,
                    },
                    ...
                ],
            },
            ...
        }

    Keyed by "country_slug/league_slug" (not display name) — reliable
    and matches oddsbook_leagues.py's get_oddsbook_slug() output
    directly, so callers can look up a specific league without any
    text-matching on display names.
    """
    soup = BeautifulSoup(html, "html.parser")
    by_league = {}

    sections = soup.find_all("section", attrs={"data-league-slug": True})

    for section in sections:
        country_slug = section.get("data-country-slug")
        league_slug = section.get("data-league-slug")
        league_id = section.get("data-league")

        name_tag = section.find("a", class_=re.compile(r"\bleague-name\b"))
        league_name = name_tag.get_text(strip=True) if name_tag else league_slug

        key = f"{country_slug}/{league_slug}"

        matches = []

        for article in section.find_all("article", attrs={"data-game-item": True}):
            home_score, away_score = _extract_score(article)
            odds = _extract_1x2_odds(article)

            canonical = article.get("data-canonical-url", "")
            match_url = (
                ODDSBOOK_BASE + canonical if canonical.startswith("/") else canonical
            )

            matches.append({
                "fixture_id": article.get("data-fixture-id"),
                "kickoff": article.get("data-kickoff"),
                "status": article.get("data-status"),
                "home": article.get("data-home-name"),
                "away": article.get("data-away-name"),
                "home_id": article.get("data-home-id"),
                "away_id": article.get("data-away-id"),
                "home_score": home_score,
                "away_score": away_score,
                "match_url": match_url or None,
                **odds,
            })

        by_league[key] = {
            "country_slug": country_slug,
            "league_slug": league_slug,
            "league_id": league_id,
            "league_name": league_name,
            "matches": matches,
        }

    return by_league


# Keywords that mark a competition as a cup/knockout tournament rather
# than a domestic league — matched against the league's slug OR display
# name (case-insensitive substring). Filtered out by default in
# get_fixtures_for_day() since Kickwise's existing scope (LEAGUE_CODES
# in daily_predictions.py) is domestic leagues only, same reasoning as
# annabet_leagues.py's own scope note ("skipping cups/super cups/youth/
# friendlies to keep this comparable and relevant to the prediction
# model").
CUP_KEYWORDS = (
    "cup", "trophy", "shield", "champions league", "confederation",
    "playoff", "play-off", "playoffs", "supercup", "super cup",
    "europa league", "conference league", "libertadores",
    "sudamericana", "afc champions", "caf champions",
)


def _is_cup_competition(league_slug, league_name):
    text = f"{league_slug or ''} {league_name or ''}".lower()
    return any(kw in text for kw in CUP_KEYWORDS)


def get_fixtures_for_day(target_date=None, exclude_cups=True):
    """
    target_date: a datetime.date, or None for today.
    exclude_cups: if True (default), filters out cup/knockout
        competitions (FA Cup, CAF Champions League, etc.) and keeps
        only domestic league competitions — matches Kickwise's
        existing scope. Pass False to get everything, e.g. for
        debugging/inspecting what's on a given day.

    Returns the by_league dict described in _parse_day_page's docstring.
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y-%m-%d")

    html = _fetch_day_page(date_str)
    if not html:
        return {}

    by_league = _parse_day_page(html)

    if exclude_cups:
        by_league = {
            key: data
            for key, data in by_league.items()
            if not _is_cup_competition(data.get("league_slug"), data.get("league_name"))
        }

    return by_league


# ------------------------------------------------------------
# Market odds for a specific fixture (by team names)
# ------------------------------------------------------------

def get_oddsbook_market_odds(home, away, target_date=None):
    """
    Same return shape as annabet_odds.get_annabet_market_odds():

        {
            "market_odds": {"home_odds":..., "draw_odds":..., "away_odds":...},
            "market_ou25": {"over_odds":..., "under_odds":...}
        }

    market_ou25 is currently always None — see module docstring.
    """
    result = {"market_odds": None, "market_ou25": None}

    by_league = get_fixtures_for_day(target_date)

    target_home = _norm_team(home)
    target_away = _norm_team(away)

    for league_data in by_league.values():
        for m in league_data["matches"]:
            if _norm_team(m["home"]) != target_home:
                continue
            if _norm_team(m["away"]) != target_away:
                continue

            if m.get("home_odds") is None:
                return result

            result["market_odds"] = _add_implied_pct(
                {
                    "home_odds": m["home_odds"],
                    "draw_odds": m["draw_odds"],
                    "away_odds": m["away_odds"],
                },
                "home_odds", "draw_odds", "away_odds",
            )

            return result

    return result
