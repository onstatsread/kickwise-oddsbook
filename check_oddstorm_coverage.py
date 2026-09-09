"""
Checks OddStorm's coverage against the 61 "Country - League" targets
used for GOAL API, using strict country-matching + a disqualifying-
word blacklist (same approach that worked well for GOAL API).

Since OddStorm's page only shows TODAY's matches, and not every
league plays daily, this also fetches the full "All leagues" dropdown
list (seen in an earlier manual check) to get a complete, date-
independent inventory — not just what happens to have games today.
"""

import re
import requests
from bs4 import BeautifulSoup

ODDS_URL = "https://www.oddstorm.com/odds/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

TARGET_LEAGUES = [
    "Belarus - Vysshaya Liga", "Brazil - Serie A", "Brazil - Serie B",
    "Canada - Premier League", "Chile - Liga de Primera", "China - Super League",
    "China - League One", "Colombia - Primera A", "Ecuador - Liga Pro",
    "Estonia - Meistriliiga", "Faroe Islands - Premier League",
    "Finland - Veikkausliiga", "Finland - Ykkosliiga", "Georgia - Erovnuli Liga",
    "Iceland - Besta deild", "Iceland - 1. Deild", "Ireland - Premier Division",
    "Ireland - First Division", "Kazakhstan - Premier League", "Latvia - Virsliga",
    "Lithuania - A Lyga", "Malaysia - Super League", "Norway - Eliteserien",
    "Norway - 1st Division", "Paraguay - Primera Div.", "Peru - Liga 1",
    "South Korea - K League 1", "South Korea - K League 2", "Sweden - Allsvenskan",
    "Sweden - Superettan", "Uruguay - Liga AUF", "USA - MLS",
    "USA - USL Championship", "Venezuela - Liga FUTVE",
    "England - Southern Football League", "Germany - Bundesliga",
    "Belgium - First Amateur Division", "Algeria - Ligue 1", "Australia - A-League",
    "Australia - Brisbane Premier League", "Chile - Primera B", "Bolivia - LFPB",
    "Greece - Super League 2", "Estonia - Esiliiga", "Iceland - Division 2",
    "Greece - Football League", "India - I-League", "India - Super League",
    "Jamaica - National Premier League", "Iran - Azadegan League",
    "Kenya - Premier League", "Jordan - League", "Morocco - Botola",
    "Singapore - S.League", "New Zealand - Championship", "Syria - Premier League",
    "Thailand - League 1", "Vietnam - V.League 1", "Taiwan - Premier League",
    "Turkmenistan - Higher League", "Tajikistan - Higher League",
]

DISQUALIFYING_WORDS = [
    "cup", "reserve", "youth", "friendly", "supercup", "super cup",
    "women", "u21", "u20", "u19", "u23", "u22", "academy", "trophy",
    "copa", "coppa", "pokal", "coupe", "beker",  # cup in other languages
]

# Country name aliases — OddStorm may spell these differently than
# Kickwise's LEAGUE_CODES naming.
COUNTRY_ALIASES = {
    "ireland": "republic of ireland",
    "taiwan": "chinese taipei",
    "south korea": "korea republic",
    "iran": "iran, islamic republic of",
}


def normalize(name):
    return " ".join(name.lower().replace(".", "").split())


def fetch_all_leagues_dropdown():
    """
    Fetches the full "All leagues" <select> dropdown — this lists
    every league OddStorm covers, regardless of whether they have a
    match today (confirmed structure from an earlier manual check:
    <optgroup label="Country"><option value="/odds/league/{id}-{slug}">
    {League} ({match_count})</option></optgroup>).
    """
    resp = requests.get(ODDS_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    select = soup.find("select")

    if not select:
        print("Could not find the leagues <select> dropdown.")
        return []

    leagues = []
    for optgroup in select.find_all("optgroup"):
        country = optgroup.get("label", "")
        for option in optgroup.find_all("option"):
            league_text = option.get_text(strip=True)
            href = option.get("value", "")
            leagues.append({
                "country": country,
                "league_text": league_text,  # e.g. "Division 1  (3)"
                "href": href,
            })

    return leagues


def main():
    print("Fetching OddStorm's full leagues dropdown...")
    all_leagues = fetch_all_leagues_dropdown()
    print(f"Total league entries found: {len(all_leagues)}\n")

    mapping = {}
    unmatched = []
    flagged = []

    for target in TARGET_LEAGUES:
        if " - " not in target:
            unmatched.append(target)
            continue

        country_part, league_part = target.split(" - ", 1)
        country_norm = normalize(country_part)
        country_alias = COUNTRY_ALIASES.get(country_norm, country_norm)

        country_candidates = [
            l for l in all_leagues
            if normalize(l["country"]) == country_norm
            or normalize(l["country"]) == country_alias
        ]

        if not country_candidates:
            unmatched.append(f"{target}  (NO COUNTRY MATCH for {country_part!r})")
            continue

        # Strip the trailing "(N)" match count for comparison.
        def clean_league_text(t):
            return re.sub(r"\s*\(\d+\)\s*$", "", t).strip()

        clean_candidates = [
            l for l in country_candidates
            if not any(
                w in normalize(clean_league_text(l["league_text"]))
                and w not in normalize(league_part)
                for w in DISQUALIFYING_WORDS
            )
        ]

        if not clean_candidates:
            unmatched.append(f"{target}  (only cup/reserve/youth matches in {country_part})")
            continue

        # Find best match by simple containment/similarity on league name.
        import difflib
        league_norm = normalize(league_part)

        best = None
        best_ratio = 0
        for l in clean_candidates:
            cand_norm = normalize(clean_league_text(l["league_text"]))
            ratio = difflib.SequenceMatcher(None, league_norm, cand_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = l

        mapping[target] = {
            "league_text": best["league_text"],
            "href": best["href"],
            "confidence": round(best_ratio, 2),
        }

        if best_ratio < 0.5:
            flagged.append(target)

    print(f"{'=' * 60}")
    print(f"MATCHED: {len(mapping)} / {len(TARGET_LEAGUES)}")
    print("=" * 60)
    for target, info in mapping.items():
        flag = "  ⚠️ LOW CONFIDENCE" if info["confidence"] < 0.5 else ""
        print(f"  {target!r:45s} -> {info['league_text']!r} [{info['confidence']}]{flag}")
        print(f"      {info['href']}")

    print(f"\n{'=' * 60}")
    print(f"UNMATCHED: {len(unmatched)}")
    print("=" * 60)
    for t in unmatched:
        print(f"  {t}")

    # Dump every distinct country name OddStorm actually has, so we
    # can resolve the remaining unmatched ones by eye rather than
    # guessing aliases blindly.
    all_countries = sorted(set(l["country"] for l in all_leagues))
    print(f"\n{'=' * 60}")
    print(f"ALL {len(all_countries)} DISTINCT COUNTRY NAMES IN ODDSTORM")
    print("=" * 60)
    for c in all_countries:
        print(f"  {c!r}")

    # Dump FULL candidate lists for every country in the target list —
    # several "matched" entries above are actually wrong (e.g. Georgia
    # matched to tier-3 instead of tier-1, USA MLS matched to the
    # reserve league) because only 1-2 candidates existed and the
    # algorithm force-picked one rather than admitting no good option.
    print(f"\n{'=' * 60}")
    print("FULL CANDIDATE LIST PER TARGET COUNTRY (verify by eye)")
    print("=" * 60)

    seen_countries = set()
    for target in TARGET_LEAGUES:
        if " - " not in target:
            continue
        country_part = target.split(" - ", 1)[0]
        if country_part in seen_countries:
            continue
        seen_countries.add(country_part)

        country_norm = normalize(country_part)
        country_alias = COUNTRY_ALIASES.get(country_norm, country_norm)

        candidates = [
            l for l in all_leagues
            if normalize(l["country"]) == country_norm
            or normalize(l["country"]) == country_alias
        ]

        print(f"\n{country_part} ({len(candidates)} leagues found):")
        for l in candidates:
            print(f"    {l['league_text']!r} -> {l['href']}")


if __name__ == "__main__":
    main()
