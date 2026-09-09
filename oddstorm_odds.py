"""
OddStorm odds fetcher — candidate replacement for Oddsbook's odds
fetching, with a major advantage: plain `requests` works with ZERO
Cloudflare challenge (confirmed 2026-09-09), no Playwright/browser
needed at all. Also includes Over/Under 2.5 directly, which Oddsbook
gated behind a login wall we couldn't crack.

CONFIRMED real HTML structure:
    <tr data-mid="13549562">
      <td class="od-c-time">17:30</td>
      <td class="od-c-event"><a href="/odds/match/...">Home – Away</a></td>
      <td class="od-odd" data-f="b1" data-l="1">1.83</td>   Home
      <td class="od-odd" data-f="bx" data-l="X">3.55</td>   Draw
      <td class="od-odd" data-f="b2" data-l="2">3.60</td>   Away
      <td class="od-odd" data-f="bo" data-l="Over">1.82</td>  Over 2.5
      <td class="od-odd" data-f="bu" data-l="Under">2.05</td> Under 2.5
      <td class="od-c-bs">4</td>                              bookmaker count
    </tr>

Team names are split on the en-dash "–" (U+2013), NOT a hyphen.

League grouping isn't yet confirmed from raw HTML (only seen via
markdown-rendered fetch showing "[Country · League](url) Date"
headers above each table) — this module returns a FLAT match list
for now, sufficient for team-name-based odds lookup. Add league
grouping later if needed for per-league browsing.
"""

import re
import time
import requests
from bs4 import BeautifulSoup

ODDSTORM_BASE = "https://www.oddstorm.com"
ODDSTORM_ODDS_URL = f"{ODDSTORM_BASE}/odds/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

_DAY_CACHE = {}
DAY_CACHE_TTL = 120  # odds refresh ~every minute per OddStorm's own FAQ


def _norm_team(name):
    return " ".join(str(name or "").lower().split()).strip()


def _to_float(value):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f <= 1.0 or f > 1000:
        return None
    return f


def _add_implied_pct(odds_dict, *keys):
    """Same normalization pattern used for AnnaBet/Oddsbook — adds
    *_pct fields (bookmaker overround removed) so existing app.py
    code (format_match_html, meets_blog2_standard) works unchanged."""
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


def _fetch_odds_page():
    """
    Fetches the main odds page — plain requests works fine (confirmed
    no Cloudflare challenge). Returns raw HTML, or None on failure.
    """
    cached = _DAY_CACHE.get("_all")
    if cached and time.time() - cached[0] < DAY_CACHE_TTL:
        return cached[1]

    try:
        resp = SESSION.get(ODDSTORM_ODDS_URL, timeout=20)
        resp.raise_for_status()
        html = resp.text
    except Exception as exc:
        print(f"OddStorm fetch failed: {exc}")
        return None

    _DAY_CACHE["_all"] = (time.time(), html)
    return html


def _parse_matches(html):
    """
    Returns a dict keyed by league:
        {
            "andorra-super-cup": {
                "league_name": "Andorra · Super Cup",
                "league_url": "https://www.oddstorm.com/odds/league/1869352-andorra-super-cup",
                "matches": [
                    {
                        "match_id": "13549810", "time": "17:30",
                        "home": "Inter Club d'Escaldes",
                        "away": "Atletic Club d'Escaldes",
                        "match_url": "...",
                        "home_odds": 1.83, "draw_odds": 3.65, "away_odds": 3.75,
                        "over_odds": 1.82, "under_odds": 2.05,
                        "bookmaker_count": 7,
                    },
                    ...
                ],
            },
            ...
        }

    CONFIRMED real structure (2026-09-09):
        <div class="od-container">
          <div class="od-group">
            <div class="od-group-head">
              <a class="od-group-league" href="/odds/league/{id}-{slug}">
                {Country} · {League}
              </a>
              <span class="od-group-date">...</span>
            </div>
            <table class="od-table">
              <tbody><tr data-mid="...">...</tr>...</tbody>
            </table>
          </div>
          ...
        </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    by_league = {}

    for group in soup.find_all("div", class_="od-group"):
        league_link = group.find("a", class_="od-group-league")
        if not league_link:
            continue

        league_name = league_link.get_text(strip=True)
        league_href = league_link.get("href", "")
        league_url = ODDSTORM_BASE + league_href if league_href.startswith("/") else league_href

        # Extract a stable key from the URL slug, e.g.
        # "/odds/league/1869352-andorra-super-cup" -> "1869352-andorra-super-cup"
        slug_match = re.search(r"/odds/league/([^/]+)", league_href)
        league_key = slug_match.group(1) if slug_match else league_name

        matches = []

        for row in group.find_all("tr", attrs={"data-mid": True}):
            match_id = row.get("data-mid")

            time_cell = row.find("td", class_="od-c-time")
            time_str = time_cell.get_text(strip=True) if time_cell else None

            event_cell = row.find("td", class_="od-c-event")
            if not event_cell:
                continue

            link = event_cell.find("a", href=True)
            if not link:
                continue

            match_url = ODDSTORM_BASE + link["href"] if link["href"].startswith("/") else link["href"]
            event_text = link.get_text(strip=True)

            # Teams are split on an EN-DASH (–, U+2013), not a hyphen.
            if "–" in event_text:
                home, away = event_text.split("–", 1)
            elif " - " in event_text:
                home, away = event_text.split(" - ", 1)
            else:
                continue

            home = home.strip()
            away = away.strip()

            odds = {}
            for cell in row.find_all("td", attrs={"data-f": True}):
                field = cell.get("data-f")
                value = _to_float(cell.get_text(strip=True))

                if field == "b1":
                    odds["home_odds"] = value
                elif field == "bx":
                    odds["draw_odds"] = value
                elif field == "b2":
                    odds["away_odds"] = value
                elif field == "bo":
                    odds["over_odds"] = value
                elif field == "bu":
                    odds["under_odds"] = value

            bs_cell = row.find("td", class_="od-c-bs")
            bookmaker_count = None
            if bs_cell:
                try:
                    bookmaker_count = int(bs_cell.get_text(strip=True))
                except ValueError:
                    pass

            matches.append({
                "match_id": match_id,
                "time": time_str,
                "home": home,
                "away": away,
                "match_url": match_url,
                "home_odds": odds.get("home_odds"),
                "draw_odds": odds.get("draw_odds"),
                "away_odds": odds.get("away_odds"),
                "over_odds": odds.get("over_odds"),
                "under_odds": odds.get("under_odds"),
                "bookmaker_count": bookmaker_count,
            })

        by_league[league_key] = {
            "league_name": league_name,
            "league_url": league_url,
            "matches": matches,
        }

    return by_league


def get_all_matches():
    """
    Returns the by_league dict described in _parse_matches' docstring.
    """
    html = _fetch_odds_page()
    if not html:
        return {}
    return _parse_matches(html)


def _iter_all_matches(by_league):
    """Flattens the by_league dict into a simple list of matches."""
    for league_data in by_league.values():
        for m in league_data["matches"]:
            yield m


def get_market_odds(home, away):
    """
    Same return shape as annabet_odds.get_annabet_market_odds() /
    oddsbook_odds.get_oddsbook_market_odds():

        {
            "market_odds": {"home_odds":..., "draw_odds":..., "away_odds":...},
            "market_ou25": {"over_odds":..., "under_odds":...}
        }
    """
    result = {"market_odds": None, "market_ou25": None}

    by_league = get_all_matches()

    target_home = _norm_team(home)
    target_away = _norm_team(away)

    for m in _iter_all_matches(by_league):
        if _norm_team(m["home"]) != target_home:
            continue
        if _norm_team(m["away"]) != target_away:
            continue

        if m.get("home_odds") is not None:
            result["market_odds"] = _add_implied_pct(
                {
                    "home_odds": m["home_odds"],
                    "draw_odds": m["draw_odds"],
                    "away_odds": m["away_odds"],
                },
                "home_odds", "draw_odds", "away_odds",
            )

        if m.get("over_odds") is not None:
            result["market_ou25"] = _add_implied_pct(
                {
                    "over_odds": m["over_odds"],
                    "under_odds": m["under_odds"],
                },
                "over_odds", "under_odds",
            )

        return result

    return result
