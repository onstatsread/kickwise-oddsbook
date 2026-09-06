"""
Tests worldfootball_stats.py against real leagues — including
Algeria, the exact league that exposed AnnaBet's coverage gap.
"""

import json
from worldfootball_stats import fetch_stats_with_splits

TEST_LEAGUES = {
    "England - Premier League": "co91/england-premier-league",
    "Algeria - Ligue 1": "alg-ligue-1",
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

    print("\n\nDone.")


if __name__ == "__main__":
    main()
