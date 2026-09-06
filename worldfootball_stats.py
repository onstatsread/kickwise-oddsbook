"""
WorldFootball.net team-stats scraper — candidate replacement for
AnnaBet's fetch_stats_annabet() in the main Kickwise app.

CONFIRMED (2026-09-05, via GitHub Actions):
- worldfootball.net is Cloudflare-protected against plain requests,
  but Playwright + a real Chrome channel (channel="chrome") passes
  on a simple page.goto() — no clicking, no hidden API, no stealth
  tricks needed (much simpler than Oddsbook's standings wall).
- The competition page's standings table has real semantic <table>
  markup: columns #, Team, Team(short), M, W, D, L, Score ("GF:GA"),
  Diff, Pts.
- Algeria - Ligue 1 coverage confirmed to include all 16 real teams
  (AnnaBet only had 8), so this may be a genuine full replacement for
  AnnaBet, not just a supplement.

NOT YET CONFIRMED: home/away split accuracy at scale — derived here
from the "all matches" page's individual results (each tagged with
a home and away team), not from a pre-built split table (none found).
Early-season sample sizes will be small per team, same limitation
AnnaBet has.

URL shape:
    https://www.worldfootball.net/competition/{comp_slug}/
    https://www.worldfootball.net/competition/{comp_slug}/all-matches/

comp_slug can be either the numeric form (e.g. "co91/england-premier-
league") or worldfootball's short alias form (e.g. "alg-ligue-1") —
both resolve to the same page per testing.
"""

import re
import time
from playwright.sync_api import sync_playwright

WORLDFOOTBALL_BASE = "https://www.worldfootball.net"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

_PAGE_CACHE = {}
PAGE_CACHE_TTL = 1800  # 30 minutes — standings don't change every minute


def _fetch_page(url):
    """
    Fetches a worldfootball.net page via Playwright + real Chrome
    channel (required — plain requests gets Cloudflare-blocked).
    Returns raw HTML, or None on failure.
    """
    cached = _PAGE_CACHE.get(url)
    if cached and time.time() - cached[0] < PAGE_CACHE_TTL:
        return cached[1]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True)
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()

            page.goto(url, timeout=30000, wait_until="domcontentloaded")

            try:
                page.wait_for_function(
                    "document.title !== 'Just a moment...'", timeout=15000
                )
            except Exception:
                pass

            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()

    except Exception as exc:
        print(f"worldfootball.net fetch failed: {url} -> {exc}")
        return None

    if "Just a moment" in html:
        print(f"worldfootball.net still Cloudflare-challenged: {url}")
        return None

    _PAGE_CACHE[url] = (time.time(), html)
    return html


def _parse_score(score_text):
    """'6:2' -> (6, 2). Returns (None, None) if unparseable."""
    m = re.match(r"^(\d+)\s*:\s*(\d+)$", score_text.strip())
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def fetch_combined_stats(comp_slug):
    """
    Returns { team_name: {"gp": int, "gf": int, "ga": int}, ... }
    from the competition's main standings table.

    comp_slug example: "co91/england-premier-league" or "alg-ligue-1"
    """
    from bs4 import BeautifulSoup

    url = f"{WORLDFOOTBALL_BASE}/competition/{comp_slug.strip('/')}/"
    html = _fetch_page(url)

    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")

    standings_table = None
    for t in soup.find_all("table"):
        header_text = t.get_text(" ", strip=True)
        if "Pts" in header_text and "Diff" in header_text:
            standings_table = t
            break

    if not standings_table:
        print(f"No standings table found for {comp_slug}")
        return {}

    result = {}
    rows = standings_table.find_all("tr")

    for row in rows[1:]:  # skip header
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        # Team name is in a link — prefer the first non-empty team
        # link text (the full name, not the short abbreviation).
        team_link = row.find("a", href=re.compile(r"/teams/"))
        if not team_link:
            continue
        team_name = team_link.get_text(strip=True)

        cell_texts = [c.get_text(strip=True) for c in cells]

        # Find M, Score columns positionally is fragile across layout
        # quirks (rank/logo cells sometimes merge) — instead, locate
        # the Score cell by its "N:N" pattern, and M as the first
        # plain integer cell before it.
        score_idx = None
        for i, t in enumerate(cell_texts):
            if re.match(r"^\d+\s*:\s*\d+$", t):
                score_idx = i
                break

        if score_idx is None:
            continue

        gf, ga = _parse_score(cell_texts[score_idx])
        if gf is None:
            continue

        # M (matches played) is the integer cell 4 positions before
        # Score in the standard layout (M, W, D, L, Score).
        try:
            gp = int(cell_texts[score_idx - 4])
        except (ValueError, IndexError):
            continue

        result[team_name] = {"gp": gp, "gf": gf, "ga": ga}

    return result


def fetch_all_matches(comp_slug):
    """
    Returns a list of finished matches:
        [{"home": ..., "away": ..., "home_score": int, "away_score": int}, ...]

    Used to derive home-only/away-only splits, since no pre-built
    split table was found on worldfootball.net.
    """
    from bs4 import BeautifulSoup

    url = f"{WORLDFOOTBALL_BASE}/competition/{comp_slug.strip('/')}/all-matches/"
    html = _fetch_page(url)

    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    matches = []

    # Match rows on the all-matches page are typically simple tables
    # with team links and a score link (format "N:N"). We scan all
    # tables and pick rows containing exactly 2 team links + 1 score.
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            team_links = row.find_all("a", href=re.compile(r"/teams/"))
            if len(team_links) < 2:
                continue

            row_text = row.get_text(" ", strip=True)
            score_match = re.search(r"\b(\d+):(\d+)\b", row_text)
            if not score_match:
                continue

            home = team_links[0].get_text(strip=True)
            away = team_links[1].get_text(strip=True)
            home_score = int(score_match.group(1))
            away_score = int(score_match.group(2))

            matches.append({
                "home": home,
                "away": away,
                "home_score": home_score,
                "away_score": away_score,
            })

    return matches


def fetch_stats_with_splits(comp_slug):
    """
    Returns the SAME shape as AnnaBet's fetch_stats_annabet():

        {
            team_name: {
                "gp": ..., "gf": ..., "ga": ..., "tot": ...,
                "hgf": ..., "hga": ..., "htot": ...,
                "agf": ..., "aga": ..., "atot": ...,
            },
            ...
        }

    Combined gp/gf/ga come from the standings table (reliable, full
    season). Home/away splits are derived by aggregating individual
    match results from the all-matches page — sample size grows as
    the season progresses, same limitation AnnaBet's own home/away
    tables have early in a season.
    """
    combined = fetch_combined_stats(comp_slug)
    if not combined:
        return {}

    matches = fetch_all_matches(comp_slug)

    home_stats = {}  # team -> {"gf": int, "ga": int, "gp": int}
    away_stats = {}

    for m in matches:
        h, a = m["home"], m["away"]
        hs, as_ = m["home_score"], m["away_score"]

        home_stats.setdefault(h, {"gf": 0, "ga": 0, "gp": 0})
        home_stats[h]["gf"] += hs
        home_stats[h]["ga"] += as_
        home_stats[h]["gp"] += 1

        away_stats.setdefault(a, {"gf": 0, "ga": 0, "gp": 0})
        away_stats[a]["gf"] += as_
        away_stats[a]["ga"] += hs
        away_stats[a]["gp"] += 1

    result = {}

    for team, c in combined.items():
        gp = c["gp"]
        gf = c["gf"]
        ga = c["ga"]

        h = home_stats.get(team, {"gf": 0, "ga": 0, "gp": 0})
        a = away_stats.get(team, {"gf": 0, "ga": 0, "gp": 0})

        result[team] = {
            "gp": gp,
            "gf": gf / gp if gp else 0,
            "ga": ga / gp if gp else 0,
            "tot": (gf + ga) / gp if gp else 0,
            "hgf": h["gf"] / h["gp"] if h["gp"] else 0,
            "hga": h["ga"] / h["gp"] if h["gp"] else 0,
            "htot": (h["gf"] + h["ga"]) / h["gp"] if h["gp"] else 0,
            "agf": a["gf"] / a["gp"] if a["gp"] else 0,
            "aga": a["ga"] / a["gp"] if a["gp"] else 0,
            "atot": (a["gf"] + a["ga"]) / a["gp"] if a["gp"] else 0,
        }

    return result
