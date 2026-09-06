"""
Tests worldfootball_stats.py against real leagues — including
Algeria, the exact league that exposed AnnaBet's coverage gap.
"""

import json
from worldfootball_stats import fetch_stats_with_splits

TEST_LEAGUES = {
    "England - Premier League": "co91/england-premier-league",
    "Algeria - Ligue 1": "co1171/algeria-ligue-1",
}


def main():
    for name, slug in TEST_LEAGUES.items():
        print(f"\n{'=' * 60}")
        print(f"Testing: {name} ({slug})")
        print("=" * 60)

        stats = fetch_stats_with_splits(slug)

        print(f"Teams found: {len(stats)}")

        for team, d in stats.items():
            print(
                f"  {team:25s} gp={d['gp']:2d} "
                f"gf={d['gf']:.2f} ga={d['ga']:.2f} "
                f"hgf={d['hgf']:.2f} hga={d['hga']:.2f} "
                f"agf={d['agf']:.2f} aga={d['aga']:.2f}"
            )

        # Diagnostic — check fetch_all_matches directly to see if it's
        # returning anything, and whether names match the standings.
        from worldfootball_stats import fetch_all_matches, _fetch_page, WORLDFOOTBALL_BASE
        matches = fetch_all_matches(slug)
        print(f"\n  [diagnostic] all-matches found: {len(matches)}")
        for m in matches[:5]:
            print(f"    {m}")

        if not matches:
            raw_url = f"{WORLDFOOTBALL_BASE}/competition/{slug.strip('/')}/all-matches/"
            raw_html = _fetch_page(raw_url)
            if raw_html:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(raw_html, "html.parser")
                tables = soup.find_all("table")
                print(f"  [diagnostic] raw all-matches page: {len(raw_html)} chars, {len(tables)} tables")
                if tables:
                    print(f"  [diagnostic] table 0 (likely standings) preview:\n{str(tables[0])[:600]}")
                    if len(tables) > 1:
                        print(f"\n  [diagnostic] table 1 (likely fixtures) preview:\n{str(tables[1])[:3000]}")
                else:
                    print(f"  [diagnostic] no tables at all — page snippet:\n{raw_html[2000:4000]}")
            else:
                print(f"  [diagnostic] raw fetch of all-matches page failed entirely")

    print("\n\nDone.")


if __name__ == "__main__":
    main()
