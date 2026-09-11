"""
Diagnostic: dumps the REAL team names OddStorm and Oddsbook have for
Brazil - Serie B today, since Vila Nova vs Goiás returned null odds
from both even with fuzzy matching applied.
"""

from oddstorm_odds import get_all_matches as get_oddstorm_matches, _iter_all_matches
from oddsbook_odds import get_fixtures_for_day


def main():
    print("=== OddStorm — Brazil Serie B matches today ===")
    by_league = get_oddstorm_matches()

    brazil_serie_b_key = None
    for key, data in by_league.items():
        if "brazil" in key.lower() and "serie-b" in key.lower():
            brazil_serie_b_key = key
            break

    if brazil_serie_b_key:
        data = by_league[brazil_serie_b_key]
        print(f"Found league: {data['league_name']} ({brazil_serie_b_key})")
        print(f"Matches: {len(data['matches'])}")
        for m in data["matches"]:
            print(f"  {m['time']} {m['home']!r} vs {m['away']!r} — "
                  f"1X2: {m['home_odds']}/{m['draw_odds']}/{m['away_odds']} | "
                  f"O/U: {m['over_odds']}/{m['under_odds']}")
    else:
        print("Brazil Serie B league key not found in OddStorm's data today.")
        print(f"All league keys containing 'brazil':")
        for key in by_league:
            if "brazil" in key.lower():
                print(f"  {key}")

    print("\n\n=== Oddsbook — today's fixtures, searching for Brazil ===")
    by_league_ob = get_fixtures_for_day()

    for key, data in by_league_ob.items():
        if "brazil" in key.lower():
            print(f"\nLeague: {data.get('league_name')} ({key})")
            for m in data["matches"]:
                print(f"  {m.get('home')!r} vs {m.get('away')!r} — "
                      f"odds: {m.get('home_odds')}/{m.get('draw_odds')}/{m.get('away_odds')}")

    if not any("brazil" in k.lower() for k in by_league_ob):
        print("No Brazil leagues found in Oddsbook's fixtures today at all.")
        print(f"All Oddsbook league keys today: {list(by_league_ob.keys())}")


if __name__ == "__main__":
    main()
