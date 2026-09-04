"""
Minimal test app for the Oddsbook fetchers — deploy this to Render
and hit the URLs below in your phone browser to see real output.
No shell/SSH needed.
"""

from fastapi import FastAPI, Query
from datetime import date, datetime

from oddsbook_odds import get_fixtures_for_day, get_oddsbook_market_odds
from oddsbook_leagues import verify_all_slugs

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
