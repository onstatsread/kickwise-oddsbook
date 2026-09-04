"""
Oddsbook League Slug Mapping
Maps league names to Oddsbook's (country_slug, league_slug) pair,
used in URLs like:

    oddsbook.com/football/{country_slug}/{league_slug}/

Unlike AnnaBet, Oddsbook doesn't use numeric IDs in its league
URLs — it uses readable slugs. Most slugs are a predictable
lowercase-hyphenated version of the league name, so this module
builds them with a slugify function and only hardcodes the
exceptions we know don't follow that pattern.

Confirmed working slugs (verified against real Oddsbook pages):
    england/premier-league
    spain/la-liga
    italy/serie-a
    germany/bundesliga
    france/ligue-1
    france/ligue-2
    england/national-league
    england/national-league-north
    england/national-league-south
    england/non-league-premier-isthmian
    england/non-league-premier-northern
    world/uefa-champions-league
    argentina/primera-b-metropolitana
    argentina/liga-profesional-argentina
    argentina/primera-nacional
    latvia/virsliga
    paraguay/division-intermedia

Everything else below is a BEST-EFFORT slug generated from the
same naming pattern Kickwise's daily_predictions.py LEAGUE_CODES
already uses (same list of ~61 active leagues) — these have NOT
all been individually verified against live Oddsbook pages yet.
Run verify_all_slugs() against Render (which has open network
access) to find which ones 404 and need a manual override added
to ODDSBOOK_SLUG_OVERRIDES.
"""

import re


def slugify(name):
    """
    Converts a league/country name into Oddsbook's likely URL slug
    format: lowercase, spaces/periods -> hyphens, punctuation
    stripped.

    e.g. "1. Bundesliga" -> "1-bundesliga"
         "K League 1"    -> "k-league-1"
    """
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)   # strip punctuation
    s = re.sub(r"[\s_]+", "-", s)    # spaces -> hyphens
    s = re.sub(r"-+", "-", s)        # collapse repeats
    return s.strip("-")


# Same "Country - League" keys as annabet_leagues.py / daily_predictions.py's
# LEAGUE_CODES, so both fetchers can be driven by the same league list.
# Value is the Kickwise short code (kept identical to LEAGUE_CODES's values)
# purely so results line up 1:1 with the existing AnnaBet-based pipeline
# for comparison during testing.
ODDSBOOK_LEAGUES = {
    "Belarus - Vysshaya Liga": "belarus",
    "Brazil - Serie A": "brazil",
    "Brazil - Serie B": "brazil2",
    "Canada - Premier League": "canada",
    "Chile - Liga de Primera": "chile",
    "China - Super League": "china",
    "China - League One": "china2",
    "Colombia - Primera A": "colombia",
    "Ecuador - Liga Pro": "ecuador",
    "Estonia - Meistriliiga": "estonia",
    "Faroe Islands - Premier League": "faroeislands",
    "Finland - Veikkausliiga": "finland",
    "Finland - Ykkosliiga": "finland2",
    "Georgia - Erovnuli Liga": "georgia",
    "Iceland - Besta deild": "iceland",
    "Iceland - 1. Deild": "iceland2",
    "Ireland - Premier Division": "ireland",
    "Ireland - First Division": "ireland2",
    "Kazakhstan - Premier League": "kazakhstan",
    "Latvia - Virsliga": "latvia",
    "Lithuania - A Lyga": "lithuania",
    "Malaysia - Super League": "malaysia",
    "Norway - Eliteserien": "norway",
    "Norway - 1st Division": "norway2",
    "Paraguay - Primera Div.": "paraguay",
    "Peru - Liga 1": "peru",
    "South Korea - K League 1": "southkorea",
    "South Korea - K League 2": "southkorea2",
    "Sweden - Allsvenskan": "sweden",
    "Sweden - Superettan": "sweden2",
    "Uruguay - Liga AUF": "uruguay",
    "USA - MLS": "usa",
    "USA - USL Championship": "usa2",
    "Venezuela - Liga FUTVE": "venezuela",
    "England - Southern Football League": "englandsouthern",
    "Germany - Bundesliga": "germany",
    "Belgium - First Amateur Division": "belgium",
    "Algeria - Ligue 1": "algeria",
    "Australia - A-League": "australia",
    "Australia - Brisbane Premier League": "australiabrisbane",
    "Chile - Primera B": "chile2",
    "Bolivia - LFPB": "bolivia",
    "Greece - Super League 2": "greece2",
    "Estonia - Esiliiga": "estonia2",
    "Iceland - Division 2": "iceland3",
    "Greece - Football League": "greece3",
    "India - I-League": "indiail",
    "India - Super League": "indiaisl",
    "Jamaica - National Premier League": "jamaica",
    "Iran - Azadegan League": "iranazadegan",
    "Kenya - Premier League": "kenya",
    "Jordan - League": "jordan",
    "Morocco - Botola": "morocco",
    "Singapore - S.League": "singapore",
    "New Zealand - Championship": "newzealand",
    "Syria - Premier League": "syria",
    "Thailand - League 1": "thailand",
    "Vietnam - V.League 1": "vietnam",
    "Taiwan - Premier League": "taiwan",
    "Turkmenistan - Higher League": "turkmenistan",
    "Tajikistan - Higher League": "tajikistan",
}

# Country name -> Oddsbook country slug, only where it's NOT simply
# slugify(country). Oddsbook's flags/URLs mostly match ISO-ish country
# names but a few differ from how Kickwise's league names spell them.
COUNTRY_SLUG_OVERRIDES = {
    "usa": "usa",
    "south korea": "south-korea",
    "new zealand": "new-zealand",
    "faroe islands": "faroe-islands",
}

# "Country - League" key -> exact (country_slug, league_slug) override,
# for cases where the mechanical slugify() guess is wrong. Add entries
# here as verify_all_slugs() finds 404s.
ODDSBOOK_SLUG_OVERRIDES = {
    "USA - MLS": ("usa", "mls"),
    "USA - USL Championship": ("usa", "usl-championship"),
    "South Korea - K League 1": ("south-korea", "k-league-1"),
    "South Korea - K League 2": ("south-korea", "k-league-2"),
    "Ireland - Premier Division": ("republic-of-ireland", "premier-division"),
    "Ireland - First Division": ("republic-of-ireland", "first-division"),
}


def get_oddsbook_slug(league_name):
    """
    Returns (country_slug, league_slug) for a "Country - League" name
    from ODDSBOOK_LEAGUES, e.g. "Brazil - Serie A" -> ("brazil", "serie-a").

    Checks the manual override table first, then falls back to a
    mechanical slugify() guess from the "Country - League" string.
    """
    if league_name in ODDSBOOK_SLUG_OVERRIDES:
        return ODDSBOOK_SLUG_OVERRIDES[league_name]

    if " - " not in league_name:
        raise ValueError(f"Unexpected league name format: {league_name}")

    country, league = league_name.split(" - ", 1)
    country_key = country.strip().lower()

    country_slug = COUNTRY_SLUG_OVERRIDES.get(
        country_key, slugify(country)
    )
    league_slug = slugify(league)

    return country_slug, league_slug


def oddsbook_league_url(league_name):
    country_slug, league_slug = get_oddsbook_slug(league_name)
    return f"https://oddsbook.com/football/{country_slug}/{league_slug}/"


def verify_all_slugs(delay=1.5, timeout=15):
    """
    Run this ONCE from Render (or anywhere with open network access to
    oddsbook.com — NOT available in the sandbox this file was written
    in) to check every league in ODDSBOOK_LEAGUES actually resolves.

    Prints a report of which slugs 404'd so you can add the correct
    (country_slug, league_slug) to ODDSBOOK_SLUG_OVERRIDES above.

    Usage (one-off, e.g. in a Python shell on Render):
        from oddsbook_leagues import verify_all_slugs
        verify_all_slugs()
    """
    import time
    import requests

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    }

    broken = []
    ok = []

    for name in ODDSBOOK_LEAGUES:
        url = oddsbook_league_url(name)

        try:
            resp = requests.get(url, headers=headers, timeout=timeout)

            if resp.status_code == 200:
                ok.append((name, url))
            else:
                broken.append((name, url, resp.status_code))

        except Exception as e:
            broken.append((name, url, str(e)))

        time.sleep(delay)

    print(f"\n✅ {len(ok)} slugs OK")
    print(f"❌ {len(broken)} slugs need fixing:\n")

    for name, url, status in broken:
        print(f"  {name!r}: {url}  -> {status}")

    return {"ok": ok, "broken": broken}
