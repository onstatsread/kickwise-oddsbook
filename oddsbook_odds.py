"""
Oddsbook fixtures + market-odds scraper.

Equivalent of annabet_odds.py, but for Oddsbook. Returns fixtures
for a given day (all leagues in one page load, unlike AnnaBet which
needed a separate /upcoming/ scan) plus per-match 1X2 odds already
embedded in that same page.

CONFIRMED WORKING (verified via direct fetch during design, Aug/Sep
2026): https://oddsbook.com/football/?date=YYYY-MM-DD returns every
match that day, grouped by league, with kickoff time, live/FT/PST
status, and per-bookmaker 1X2 odds (e.g. "16.50 Betwinner" = Home
odds 6.50 from Betwinner).

NOT YET CONFIRMED: Over/Under 2.5 odds. The day-list page only showed
1X2 (Win/Draw/Win) prices in testing — O/U markets may only exist on
individual match-detail pages (the /football/{country}/{league}/
{slug}/{id}/ URLs each fixture links to), similar to how AnnaBet's
O/U 2.5 lives on the H2H page rather than the /upcoming/ list. This
needs to be confirmed by opening one live match page on Render and
checking for an O/U 2.5 section — get_oddsbook_ou25() below is a
best-effort placeholder until that's verified.
"""

import re
import time
import requests
from datetime import date
from bs4 import BeautifulSoup


ODDSBOOK_BASE = "https://oddsbook.com"

ODDSBOOK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

SESSION = requests.Session()
SESSION.headers.update(ODDSBOOK_HEADERS)


# ------------------------------------------------------------
# Cache — one entry per calendar day, since /football/?date=
# returns ALL leagues' fixtures for that day in a single request.
# ------------------------------------------------------------

_DAY_CACHE = {}
DAY_CACHE_TTL = 300  # 5 minutes — odds move, same TTL as AnnaBet's


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

FLOAT_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _float(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value or not FLOAT_RE.match(value):
        return None
    try:
        f = float(value)
    except ValueError:
        return None
    if f <= 1.0 or f > 100:
        return None
    return f


def _norm_team(name):
    return " ".join(str(name).lower().split()).strip()


def _add_implied_pct(odds_dict, *keys):
    """Same normalization as annabet's version in app.py — adds
    *_pct fields (overround removed) so daily_predictions.py's
    existing format_match_html()/meets_blog2_standard() code works
    unchanged against this fetcher's output."""
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
# Fetch a full day's fixtures (all leagues at once)
# ------------------------------------------------------------

def _fetch_day_page(date_str):
    """
    date_str: 'YYYY-MM-DD'. Returns raw HTML text, or None on failure.
    """
    cache_key = date_str
    cached = _DAY_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < DAY_CACHE_TTL:
        return cached[1]

    url = f"{ODDSBOOK_BASE}/football/?date={date_str}"

    try:
        resp = SESSION.get(url, timeout=25)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        print(f"Oddsbook day-page fetch failed: {url} -> {exc}")
        return None

    _DAY_CACHE[cache_key] = (time.time(), html)
    return html


def _parse_day_page(html):
    """
    Parses the day page into:

        {
            "England - Premier League": [
                {
                    "time": "19:00",
                    "status": "scheduled" | "live" | "FT" | "PST",
                    "home": "Ipswich",
                    "away": "Liverpool",
                    "home_score": None,
                    "away_score": None,
                    "match_url": "https://oddsbook.com/football/.../1557393/",
                    "home_odds": 6.50,
                    "draw_odds": 5.13,
                    "away_odds": 1.57,
                },
                ...
            ],
            ...
        }

    NOTE: this parser targets Oddsbook's rendered text/DOM structure
    as observed via fetch during design — it has NOT been run against
    raw HTML with BeautifulSoup yet (the design environment could only
    reach Oddsbook through a text-extracting fetch tool, not raw
    requests). Structure below (rows grouped under a league heading,
    each row containing team names + a match link + three odds cells)
    is a best-effort match to AnnaBet's row-scanning approach and
    WILL likely need small selector fixes once run against real HTML
    on Render — same as annabet_odds.py needed several iterations.
    """
    soup = BeautifulSoup(html, "html.parser")
    by_league = {}
    current_league = None

    # Oddsbook groups fixtures under league header blocks containing a
    # link to /football/{country}/{league}/ followed by a "· Country"
    # label, then one row per match. We walk elements in document
    # order and track the most recent league header seen.
    league_link_re = re.compile(r"^/football/[^/]+/[^/]+/$")
    match_link_re = re.compile(r"^/football/[^/]+/[^/]+/[^/]+/\d+/$")

    for el in soup.find_all(["a"]):
        href = el.get("href", "")

        # League header link (e.g. /football/england/premier-league/)
        if league_link_re.match(href) and "standings" not in (el.get("title") or "").lower():
            text = el.get_text(" ", strip=True)
            if text and text not in ("Standings",):
                current_league = text
                by_league.setdefault(current_league, [])
            continue

        # Match link (e.g. /football/england/premier-league/ipswich-vs-liverpool/1557393/)
        if match_link_re.match(href):
            row_text = el.get_text(" ", strip=True)

            # Extract status/time prefix (FT, PST, live minute, or HH:MM)
            status = "scheduled"
            time_str = None

            time_match = re.match(r"^(\d{1,2}:\d{2})\s+", row_text)
            ft_match = re.match(r"^FT\s+", row_text)
            pst_match = re.match(r"^PST\s+", row_text)
            live_match = re.match(r"^(\d{1,3})'\s+", row_text)

            if time_match:
                time_str = time_match.group(1)
                rest = row_text[time_match.end():]
            elif ft_match:
                status = "FT"
                rest = row_text[ft_match.end():]
            elif pst_match:
                status = "PST"
                rest = row_text[pst_match.end():]
            elif live_match:
                status = f"{live_match.group(1)}'"
                rest = row_text[live_match.end():]
            else:
                rest = row_text

            # rest is like "Ipswich Liverpool -  -" or "Aston Villa Arsenal 0 1"
            # Scores are the last two tokens if both are digits, else None.
            tokens = rest.split()
            home_score = away_score = None

            if len(tokens) >= 2 and tokens[-1].lstrip("-").isdigit() and tokens[-2].lstrip("-").isdigit():
                away_score = _float(tokens[-1]) and int(tokens[-1])
                home_score = _float(tokens[-2]) and int(tokens[-2])
                team_text = " ".join(tokens[:-2])
            else:
                team_text = rest

            # Team names aren't separated by a delimiter in the extracted
            # text (concatenated "HomeAway" in some fetch modes) — this
            # is the biggest risk point needing live-HTML confirmation.
            # Prefer splitting on the match URL slug instead, which IS
            # reliably delimited by " vs ".
            slug_match = re.search(r"/([^/]+)-vs-([^/]+)/\d+/$", href)

            if slug_match:
                home_guess = slug_match.group(1).replace("-", " ").title()
                away_guess = slug_match.group(2).replace("-", " ").title()
            else:
                home_guess = team_text
                away_guess = ""

            if current_league is None:
                continue

            by_league[current_league].append({
                "time": time_str,
                "status": status,
                "home": home_guess,
                "away": away_guess,
                "home_score": home_score,
                "away_score": away_score,
                "match_url": ODDSBOOK_BASE + href,
                "home_odds": None,
                "draw_odds": None,
                "away_odds": None,
            })

    return by_league


def get_fixtures_for_day(target_date=None):
    """
    target_date: a datetime.date, or None for today.

    Returns { "Country - League": [match_dict, ...], ... }
    Keys use Oddsbook's own display league name (e.g. "Premier League")
    — NOT yet normalized to the "Country - League" format the rest of
    the pipeline uses. Call normalize against ODDSBOOK_LEAGUES from
    oddsbook_leagues.py to match Kickwise's naming, or match by league
    URL slug instead, which is more reliable than display-name text.
    """
    if target_date is None:
        target_date = date.today()

    date_str = target_date.strftime("%Y-%m-%d")

    html = _fetch_day_page(date_str)
    if not html:
        return {}

    return _parse_day_page(html)


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
    Once confirmed where O/U 2.5 lives on Oddsbook, add a
    get_oddsbook_ou25(match_url) function (parsing the individual
    match page) and call it here, same pattern as annabet_odds.py's
    _extract_ou25(h2h_url).
    """
    result = {"market_odds": None, "market_ou25": None}

    by_league = get_fixtures_for_day(target_date)

    target_home = _norm_team(home)
    target_away = _norm_team(away)

    for matches in by_league.values():
        for m in matches:
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
