"""
Tests the league-grouped oddstorm_odds.py parser — confirms Algeria
coverage specifically (the league that started this whole
investigation) and overall data quality stats.
"""

from oddstorm_odds import get_all_matches, _iter_all_matches


def main():
    by_league = get_all_matches()
    print(f"Total leagues found: {len(by_league)}")

    all_matches = list(_iter_all_matches(by_league))
    print(f"Total matches found: {len(all_matches)}")

    both_populated = [
        m for m in all_matches
        if m.get("home_odds") is not None and m.get("over_odds") is not None
    ]
    print(f"Matches with BOTH 1X2 and O/U 2.5: {len(both_populated)} / {len(all_matches)}")

    # Find Algeria specifically.
    algeria_leagues = {
        k: v for k, v in by_league.items()
        if "algeria" in k.lower() or "algeria" in v["league_name"].lower()
    }
    print(f"\n--- Algeria leagues found: {len(algeria_leagues)} ---")
    for key, data in algeria_leagues.items():
        print(f"\nLeague: {data['league_name']} ({key})")
        print(f"URL: {data['league_url']}")
        print(f"Matches: {len(data['matches'])}")
        for m in data["matches"]:
            print(f"  {m['time']} {m['home']} vs {m['away']} — "
                  f"1X2: {m['home_odds']}/{m['draw_odds']}/{m['away_odds']} | "
                  f"O/U: {m['over_odds']}/{m['under_odds']}")

    # Show a sample of ALL league names found, to eyeball overall coverage.
    print(f"\n--- All {len(by_league)} league names found today ---")
    for key, data in by_league.items():
        print(f"  {data['league_name']} ({len(data['matches'])} matches)")

    print("\nDone.")


if __name__ == "__main__":
    main()
