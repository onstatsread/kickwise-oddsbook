"""
Combined odds fetcher — tries OddStorm first (no Playwright needed,
includes O/U 2.5), falls back to Oddsbook (Playwright-based) for the
16 leagues confirmed absent from OddStorm's data (see
oddstorm_leagues.py's docstring for the full list and why).

Both underlying fetchers return the same shape:
    {
        "market_odds": {"home_odds":..., "draw_odds":..., "away_odds":...},
        "market_ou25": {"over_odds":..., "under_odds":...}
    }
so this wrapper is a straightforward drop-in for either.
"""

from oddstorm_leagues import has_oddstorm_coverage
from oddstorm_odds import get_market_odds as get_oddstorm_market_odds
from oddsbook_odds import get_oddsbook_market_odds


def get_combined_market_odds(kickwise_league_name, home, away, target_date=None):
    """
    kickwise_league_name: the "Country - League" string used as the
        key in daily_predictions.py's LEAGUE_CODES / GOALAPI_LEAGUE_IDS
        (e.g. "Algeria - Ligue 1") — used ONLY to decide which source
        to try, not passed to either fetcher's own lookup (both match
        by team name across all their own data).
    home, away: team names as they appear in your fixtures data.
    target_date: only used by the Oddsbook fallback (date.today() if
        not given) — OddStorm's page is always "today" only.

    Returns the standard {"market_odds": ..., "market_ou25": ...}
    shape, with a "source" key added so you can see which fetcher
    actually supplied the data (useful for logging/debugging).
    """
    if has_oddstorm_coverage(kickwise_league_name):
        try:
            result = get_oddstorm_market_odds(home, away)
            if result.get("market_odds") or result.get("market_ou25"):
                result["source"] = "oddstorm"
                return result
        except Exception as e:
            print(f"OddStorm odds failed for {kickwise_league_name} "
                  f"({home} vs {away}): {e} — falling back to Oddsbook")

    # Either OddStorm doesn't cover this league, or it returned
    # nothing for this specific match (e.g. not yet priced) — try
    # Oddsbook as the fallback.
    try:
        result = get_oddsbook_market_odds(home, away, target_date)
        result["source"] = "oddsbook"
        return result
    except Exception as e:
        print(f"Oddsbook odds also failed for {kickwise_league_name} "
              f"({home} vs {away}): {e}")
        return {"market_odds": None, "market_ou25": None, "source": None}
