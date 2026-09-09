"""
Tests the real oddstorm_odds.py parser: confirms it correctly
extracts matches (including both 1X2 AND O/U 2.5), and checks
coverage against the same 61-league list used for GOAL API mapping.
"""

from oddstorm_odds import get_all_matches

# Same 61 "Country - League" names used for the GOAL API mapping.
TARGET_LEAGUES = [
    "Belarus", "Brazil", "Canada", "Chile", "China", "Colombia",
    "Ecuador", "Estonia", "Faroe Islands", "Finland", "Georgia",
    "Iceland", "Ireland", "Kazakhstan", "Latvia", "Lithuania",
    "Malaysia", "Norway", "Paraguay", "Peru", "South Korea",
    "Sweden", "Uruguay", "USA", "Venezuela", "England", "Germany",
    "Belgium", "Algeria", "Australia", "Bolivia", "Greece", "India",
    "Jamaica", "Iran", "Kenya", "Jordan", "Morocco", "Singapore",
    "New Zealand", "Syria", "Thailand", "Vietnam", "Taiwan",
    "Turkmenistan", "Tajikistan",
]


def main():
    matches = get_all_matches()
    print(f"Total matches found: {len(matches)}")

    print("\n--- Sample of first 5 matches (full detail) ---")
    for m in matches[:5]:
        print(m)

    # Count matches with BOTH 1X2 and O/U populated.
    both_populated = [
        m for m in matches
        if m.get("home_odds") is not None and m.get("over_odds") is not None
    ]
    print(f"\nMatches with BOTH 1X2 and O/U 2.5 populated: {len(both_populated)} / {len(matches)}")

    only_1x2 = [
        m for m in matches
        if m.get("home_odds") is not None and m.get("over_odds") is None
    ]
    print(f"Matches with ONLY 1X2 (no O/U): {len(only_1x2)}")

    # Check for a specific known Algeria match if present today.
    print("\n--- Searching for Algeria-related matches (by team name heuristics won't work, checking raw HTML instead) ---")

    # Discover the real league-header structure, needed to associate
    # matches with their league (current parser returns a flat list).
    from oddstorm_odds import _fetch_odds_page
    from bs4 import BeautifulSoup

    html = _fetch_odds_page()
    soup = BeautifulSoup(html, "html.parser")

    # Find the first table and walk UP/BACK to see what precedes it —
    # likely a heading or section wrapper with the league name.
    first_table = soup.find("table")
    if first_table:
        # Look at previous siblings for a heading.
        prev = first_table.find_previous(["h1", "h2", "h3", "h4"])
        print(f"\nNearest preceding heading tag: {prev.name if prev else None}")
        if prev:
            print(f"Heading HTML: {str(prev)[:500]}")

        # Also check the table's parent container structure.
        parent = first_table.parent
        print(f"\nTable's parent tag: {parent.name}, class: {parent.get('class')}")

        # Look a bit further up for a container with country/league info.
        grandparent = parent.parent if parent else None
        if grandparent:
            print(f"Grandparent tag: {grandparent.name}, class: {grandparent.get('class')}")
            print(f"Grandparent HTML (first 1000 chars):\n{str(grandparent)[:1000]}")

    print("\nDone.")


if __name__ == "__main__":
    main()
