"""
OddStorm league mapping for the 61 leagues in daily_predictions.py's
LEAGUE_CODES — manually verified against complete per-country
candidate dumps (2026-09-10), not just algorithmic best-guess.

CONFIRMED ABSENT (16 leagues) — OddStorm has NO usable data for these,
either because the entire country is missing (10 countries) or because
the specific league doesn't exist even though the country does (6 more):

    Country entirely absent:
        Jamaica, Kenya, Morocco, Singapore, New Zealand, Syria,
        Thailand, Taiwan, Turkmenistan, Tajikistan

    Country exists, but this specific league doesn't:
        China - League One       (only Chinese Super League exists)
        Malaysia - Super League  (only Cup + Liga A1 Semi Pro exist)
        Venezuela - Liga FUTVE   (only Copa Venezuela exists)
        Belgium - First Amateur Division (only Pro League + Challenger Pro League)
        India - I-League         (only 3 obscure state leagues: Mizoram/Shillong/Sikkim)
        India - Super League     (same as above)
        Australia - A-League     (only regional NPL competitions)
        Australia - Brisbane Premier League (same — no Brisbane-specific league)
        Iceland - Division 2     (only 1/2-Women/4 Deild exist, no plain tier-3)
        Greece - Football League (only Super League/Super League 2/cups exist)

For these leagues, callers MUST fall back to Oddsbook (or accept no
O/U 2.5 via AnnaBet-only) — do not silently skip odds entirely.

CORRECTIONS made to the naive best-guess matches (verified by eye
against full candidate lists, not trusted from string-similarity
scoring alone):
    Georgia          -> "Erovnuli" (plain), NOT "Erovnuli Liga 3" (tier 3)
    Iceland top flight -> "Urvalsdeild (Premier League)", NOT "1 Deild" (tier 2)
    Ireland - First Division -> "Division 1", NOT "Premier Division" (tier 1, wrongly reused)
    South Korea - K League 1 -> "K-League Classic 1" (their naming for tier 1),
                                 NOT "K League 2"
    USA - MLS        -> "MLS (Major League Soccer)", NOT "MLS Next Pro" (the reserve league)
    Jordan           -> "Premier League", NOT "Division 1" (a separate, lower competition)

SUBSTITUTIONS (not a perfect match, but the closest real equivalent —
flagged so callers can decide whether the tier difference matters):
    Iran - Azadegan League -> substituted with "Pro League" (Iran's
        actual TOP flight — Azadegan League is tier 2, but no tier-2
        entry exists in OddStorm's data)
    Paraguay - Primera Div. -> best-guess "Division de Honor, Apertura"
        (closest available name to a top-flight competition; not
        independently confirmed against the season this data covers)
    England - Southern Football League -> UNRESOLVED. Two candidates
        exist ("Southern League Premier Division South" and "Southern
        Premier League Central") and it's unclear which (if either)
        corresponds to what AnnaBet's original naming meant. Left as
        None (unmatched) rather than guessing wrong.
"""

# Value is the full URL slug after /odds/league/, or None if OddStorm
# has no usable coverage for this league (see docstring above for why).
ODDSTORM_LEAGUE_SLUGS = {
    "Belarus - Vysshaya Liga": "160-belarus-premier-league",
    "Brazil - Serie A": "145-brazil-serie-a",
    "Brazil - Serie B": "146-brazil-serie-b",
    "Canada - Premier League": "2182876-canada-canadian-premier-league",
    "Chile - Liga de Primera": "178-chile-primera-division",
    "China - Super League": "2182861-china-chinese-super-league",
    "China - League One": None,  # confirmed absent
    "Colombia - Primera A": "1740202-colombia-primera-a",
    "Ecuador - Liga Pro": "1024568-ecuador-ligapro-primera-a",
    "Estonia - Meistriliiga": "341-estonia-meistriliiga",
    "Faroe Islands - Premier League": "1997082-faroe-islands-premier-league",
    "Finland - Veikkausliiga": "1617355-finland-veikkausliiga",
    "Finland - Ykkosliiga": "2180158-finland-ykkosliiga",
    "Georgia - Erovnuli Liga": "1940888-georgia-erovnuli",
    "Iceland - Besta deild": "437-iceland-urvalsdeild-premier-league",
    "Iceland - 1. Deild": "427-iceland-1-deild",
    "Ireland - Premier Division": "564-ireland-premier-division",
    "Ireland - First Division": "563-ireland-division-1",
    "Kazakhstan - Premier League": "2176661-kazakhstan-premier-league",
    "Latvia - Virsliga": "2179260-latvia-virsliga",
    "Lithuania - A Lyga": "648-lithuania-a-lyga",
    "Malaysia - Super League": None,  # confirmed absent
    "Norway - Eliteserien": "747-norway-eliteserien",
    "Norway - 1st Division": "1765053-norway-division-1",
    "Paraguay - Primera Div.": "2181526-paraguay-division-de-honor-apertura",  # best-guess substitution, see docstring
    "Peru - Liga 1": "771-peru-liga-1",
    "South Korea - K League 1": "1614422-south-korea-k-league-classic-1",
    "South Korea - K League 2": "2176658-south-korea-k-league-2",
    "Sweden - Allsvenskan": "923-sweden-allsvenskan",
    "Sweden - Superettan": "2181081-sweden-superettan",
    "Uruguay - Liga AUF": "2102325-uruguay-primera-division",
    "USA - MLS": "90-usa-mls-major-league-soccer",
    "USA - USL Championship": "2181288-usa-usl-championship",
    "Venezuela - Liga FUTVE": None,  # confirmed absent (only Copa Venezuela exists)
    "England - Southern Football League": None,  # unresolved, see docstring
    "Germany - Bundesliga": "380-germany-bundesliga",
    "Belgium - First Amateur Division": None,  # confirmed absent
    "Algeria - Ligue 1": "623041-algeria-division-1",
    "Australia - A-League": None,  # confirmed absent
    "Australia - Brisbane Premier League": None,  # confirmed absent
    "Chile - Primera B": "2189234-chile-primera-b-tier-2",
    "Bolivia - LFPB": "2180370-bolivia-division-profesional",
    "Greece - Super League 2": "1961452-greece-super-league-2",
    "Estonia - Esiliiga": "2167256-estonia-esiliiga",
    "Iceland - Division 2": None,  # confirmed absent
    "Greece - Football League": None,  # confirmed absent
    "India - I-League": None,  # confirmed absent
    "India - Super League": None,  # confirmed absent
    "Jamaica - National Premier League": None,  # country absent
    "Iran - Azadegan League": "1771723-iran-pro-league",  # substitution, different tier, see docstring
    "Kenya - Premier League": None,  # country absent
    "Jordan - League": "610-jordan-premier-league",
    "Morocco - Botola": None,  # country absent
    "Singapore - S.League": None,  # country absent
    "New Zealand - Championship": None,  # country absent
    "Syria - Premier League": None,  # country absent
    "Thailand - League 1": None,  # country absent
    "Vietnam - V.League 1": "2178704-vietnam-v-league-1",
    "Taiwan - Premier League": None,  # country absent
    "Turkmenistan - Higher League": None,  # country absent
    "Tajikistan - Higher League": None,  # country absent
}


def has_oddstorm_coverage(kickwise_league_name):
    """Returns True if OddStorm has usable odds data for this league."""
    return ODDSTORM_LEAGUE_SLUGS.get(kickwise_league_name) is not None


def get_oddstorm_league_url(kickwise_league_name):
    """
    Returns the full OddStorm league URL, or None if not covered.
    """
    slug = ODDSTORM_LEAGUE_SLUGS.get(kickwise_league_name)
    if not slug:
        return None
    return f"https://www.oddstorm.com/odds/league/{slug}"

