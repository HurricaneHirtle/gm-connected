"""
Database initializer and seeder.
Run once: python init_db.py
Seeds 32 NHL teams, a 2026-27 season, draft picks (7 rounds each team), and
an initial prospect cohort for each age group 14-17.
"""
from app import app, db
from models import Season, Team, Player, Prospect, DraftPick, Standing, WeeklyReadiness
from prospect_gen import generate_cohort
from sim_engine import generate_schedule
import json

# ─────────────────────────────────────────────────────────────────────────────
# Team data
# ─────────────────────────────────────────────────────────────────────────────
TEAMS = [
    # Eastern — Atlantic
    ("Boston Bruins",          "Boston",       "BOS", "Eastern", "Atlantic",   "TD Garden",              "#000000", "#FFB81C"),
    ("Buffalo Sabres",         "Buffalo",      "BUF", "Eastern", "Atlantic",   "KeyBank Center",         "#003087", "#00B4D8"),
    ("Detroit Red Wings",      "Detroit",      "DET", "Eastern", "Atlantic",   "Little Caesars Arena",   "#CE1126", "#FFFFFF"),
    ("Florida Panthers",       "Sunrise",      "FLA", "Eastern", "Atlantic",   "Amerant Bank Arena",     "#C8102E", "#041E42"),
    ("Montreal Canadiens",     "Montreal",     "MTL", "Eastern", "Atlantic",   "Bell Centre",            "#AF1E2D", "#192168"),
    ("Ottawa Senators",        "Ottawa",       "OTT", "Eastern", "Atlantic",   "Canadian Tire Centre",   "#C2912C", "#C52032"),
    ("Tampa Bay Lightning",    "Tampa Bay",    "TBL", "Eastern", "Atlantic",   "Amalie Arena",           "#002868", "#FFFFFF"),
    ("Toronto Maple Leafs",    "Toronto",      "TOR", "Eastern", "Atlantic",   "Scotiabank Arena",       "#00205B", "#FFFFFF"),
    # Eastern — Metropolitan
    ("Carolina Hurricanes",    "Raleigh",      "CAR", "Eastern", "Metropolitan","PNC Arena",             "#CC0000", "#000000"),
    ("Columbus Blue Jackets",  "Columbus",     "CBJ", "Eastern", "Metropolitan","Nationwide Arena",      "#002654", "#CE1126"),
    ("New Jersey Devils",      "Newark",       "NJD", "Eastern", "Metropolitan","Prudential Center",     "#CE1126", "#000000"),
    ("New York Islanders",     "Elmont",       "NYI", "Eastern", "Metropolitan","UBS Arena",             "#003087", "#FC4C02"),
    ("New York Rangers",       "New York",     "NYR", "Eastern", "Metropolitan","Madison Square Garden", "#0038A8", "#CE1126"),
    ("Philadelphia Flyers",    "Philadelphia", "PHI", "Eastern", "Metropolitan","Wells Fargo Center",    "#F74902", "#000000"),
    ("Pittsburgh Penguins",    "Pittsburgh",   "PIT", "Eastern", "Metropolitan","PPG Paints Arena",      "#000000", "#FFB81C"),
    ("Washington Capitals",    "Washington",   "WSH", "Eastern", "Metropolitan","Capital One Arena",     "#041E42", "#C8102E"),
    # Western — Central
    ("Arizona Coyotes",        "Salt Lake City","UTA", "Western", "Central",   "Delta Center",           "#6F263D", "#A2AAAD"),
    ("Chicago Blackhawks",     "Chicago",      "CHI", "Western", "Central",   "United Center",           "#CF0A2C", "#000000"),
    ("Colorado Avalanche",     "Denver",       "COL", "Western", "Central",   "Ball Arena",              "#6F263D", "#236192"),
    ("Dallas Stars",           "Dallas",       "DAL", "Western", "Central",   "American Airlines Center","#006847", "#8F8F8C"),
    ("Minnesota Wild",         "Saint Paul",   "MIN", "Western", "Central",   "Xcel Energy Center",      "#154734", "#A6192E"),
    ("Nashville Predators",    "Nashville",    "NSH", "Western", "Central",   "Bridgestone Arena",       "#041E42", "#FFB81C"),
    ("St. Louis Blues",        "St. Louis",    "STL", "Western", "Central",   "Enterprise Center",       "#002F87", "#FCB514"),
    ("Winnipeg Jets",          "Winnipeg",     "WPG", "Western", "Central",   "Canada Life Centre",      "#041E42", "#AC162C"),
    # Western — Pacific
    ("Anaheim Ducks",          "Anaheim",      "ANA", "Western", "Pacific",   "Honda Center",            "#F47A38", "#B9975B"),
    ("Calgary Flames",         "Calgary",      "CGY", "Western", "Pacific",   "Scotiabank Saddledome",   "#C8102E", "#F1BE48"),
    ("Edmonton Oilers",        "Edmonton",     "EDM", "Western", "Pacific",   "Rogers Place",            "#041E42", "#FF4C00"),
    ("Los Angeles Kings",      "Los Angeles",  "LAK", "Western", "Pacific",   "Crypto.com Arena",        "#111111", "#A2AAAD"),
    ("San Jose Sharks",        "San Jose",     "SJS", "Western", "Pacific",   "SAP Center",              "#006D75", "#EA7200"),
    ("Seattle Kraken",         "Seattle",      "SEA", "Western", "Pacific",   "Climate Pledge Arena",    "#001628", "#99D9D9"),
    ("Vancouver Canucks",      "Vancouver",    "VAN", "Western", "Pacific",   "Rogers Arena",            "#00205B", "#00843D"),
    ("Vegas Golden Knights",   "Las Vegas",    "VGK", "Western", "Pacific",   "T-Mobile Arena",          "#B4975A", "#333F42"),
]


def seed_teams():
    teams = []
    for row in TEAMS:
        name, city, abbrev, conf, div, arena, primary, secondary = row
        t = Team(
            name=name, city=city, abbrev=abbrev,
            conference=conf, division=div, arena=arena,
            primary_color=primary, secondary_color=secondary,
        )
        db.session.add(t)
        teams.append(t)
    db.session.flush()  # get IDs
    return teams


def seed_season():
    s = Season(
        year=2026,
        week=1,
        phase="preseason",
        cap_ceiling=88_000_000,
    )
    db.session.add(s)
    db.session.flush()
    return s


def seed_draft_picks(teams, season):
    """Seed each team's own picks for seasons 2027, 2028, 2029 (7 rounds each)."""
    picks = []
    for year in [2027, 2028, 2029]:
        for t in teams:
            for rnd in range(1, 8):
                p = DraftPick(
                    year=year,
                    round=rnd,
                    original_team_id=t.id,
                    owner_team_id=t.id,
                    used=False,
                )
                db.session.add(p)
                picks.append(p)
    return picks


def seed_prospects(season):
    """Generate a multi-year prospect pool (14-17-year-olds entering at season start)."""
    cohort = generate_cohort(season.year, count_per_age={14: 30, 15: 28, 16: 26, 17: 24})
    for p_data in cohort:
        p = Prospect(
            first_name    = p_data["first_name"],
            last_name     = p_data["last_name"],
            position      = p_data["position"],
            birth_year    = p_data["birth_year"],
            nationality   = p_data["nationality"],
            shoots        = p_data["shoots"],
            archetype     = p_data["archetype"],
            current_team  = p_data["current_team"],
            current_league= p_data["current_league"],
            potential     = p_data["potential"],
            scout_grade   = p_data["scout_grade"],
            draft_year    = p_data["draft_year"],
            is_drafted    = False,
            skating       = p_data.get("skating", 0),
            shooting      = p_data.get("shooting", 0),
            passing       = p_data.get("passing", 0),
            defense       = p_data.get("defense", 0),
            physical      = p_data.get("physical", 0),
            puck_control  = p_data.get("puck_control", 0),
            awareness     = p_data.get("awareness", 0),
            reflexes      = p_data.get("reflexes", 0),
            positioning   = p_data.get("positioning", 0),
            rebound_ctrl  = p_data.get("rebound_ctrl", 0),
            puck_handling = p_data.get("puck_handling", 0),
        )
        db.session.add(p)


def seed_placeholder_players(teams):
    """
    Seed each team with 23 placeholder players (12F, 8D, 3G) so the sim runs
    without real roster data. Ratings are randomized around team 'tier'.
    In a real deploy, you'd replace this with scraped PuckPedia data.
    """
    import random
    from models import Player

    positions_config = (
        [("C",3),("LW",3),("RW",3),("C",1),("LW",1),("RW",1)],  # 12 F
        [("D",6),("D",2)],                                          # 8 D
        [("G",3)],                                                   # 3 G
    )

    first_names = ["Alex","Ryan","Tyler","Dylan","Connor","Nathan","Marcus","Erik",
                   "Mikko","Jari","Pavel","Nikita","Viktor","Lucas","Cole","Brady"]
    last_names  = ["Smith","Johnson","Williams","Brown","Jones","Wilson","Taylor",
                   "Anderson","Martin","Thompson","Karlsson","Pettersson","Barkov",
                   "Draisaitl","Aho","MacKinnon","McDavid","Crosby","Ovechkin"]

    for t in teams:
        # Rough tier based on name hash (just for variety)
        tier_bonus = (hash(t.name) % 20) - 10  # -10 to +10

        for pos_group in positions_config:
            for pos, count in pos_group:
                for _ in range(count):
                    is_g = (pos == "G")
                    base = 72 + tier_bonus
                    def r(lo, hi): return random.randint(lo, hi)
                    def stat(): return r(max(40, base-15), min(99, base+10))

                    p = Player(
                        first_name   = random.choice(first_names),
                        last_name    = random.choice(last_names),
                        position     = pos,
                        age          = r(19, 35),
                        nationality  = random.choice(["Canadian","American","Swedish","Finnish","Russian"]),
                        shoots       = random.choice(["L","R"]),
                        team_id      = t.id,
                        cap_hit      = r(750_000, 12_000_000),
                        years_left   = r(1, 7),
                        contract_type= random.choice(["Standard","Standard","Standard","ELC","UFA"]),
                        nhl_roster   = True,
                        injured      = False,
                        waiver_exempt= False,
                        skating      = stat() if not is_g else 0,
                        shooting     = stat() if not is_g else 0,
                        passing      = stat() if not is_g else 0,
                        defense      = stat() if not is_g else 0,
                        physical     = stat() if not is_g else 0,
                        puck_control = stat() if not is_g else 0,
                        awareness    = stat() if not is_g else 0,
                        reflexes     = stat() if is_g else 0,
                        positioning  = stat() if is_g else 0,
                        rebound_ctrl = stat() if is_g else 0,
                        puck_handling= stat() if is_g else 0,
                        gp=0, goals=0, assists=0, pim=0, plus_minus=0,
                        wins=0, losses=0, gaa=0.0, sv_pct=0.0,
                    )
                    db.session.add(p)


def seed_standings(teams, season):
    for t in teams:
        s = Standing(season_id=season.id, team_id=t.id,
                     gp=0, w=0, l=0, otl=0, pts=0, gf=0, ga=0)
        db.session.add(s)


def main():
    with app.app_context():
        print("Dropping and recreating all tables…")
        db.drop_all()
        db.create_all()

        print("Seeding teams…")
        teams = seed_teams()

        print("Seeding season…")
        season = seed_season()

        print("Seeding draft picks…")
        seed_draft_picks(teams, season)

        print("Seeding prospects…")
        seed_prospects(season)

        print("Seeding placeholder players…")
        seed_placeholder_players(teams)

        print("Seeding standings…")
        seed_standings(teams, season)

        db.session.commit()
        print(f"\n✓ Done — {len(teams)} teams, 1 season (2026-27), prospects generated.")
        print("  Run `python app.py` to start the server.")


if __name__ == "__main__":
    main()
