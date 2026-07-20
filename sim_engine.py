"""
Game simulation engine.
Handles schedule generation, game sim, standings updates, and playoff seeding.
"""
import random
import json
from math import ceil


# ─────────────────────────────────────────────────────────────────────────────
# Schedule generation
# ─────────────────────────────────────────────────────────────────────────────
def generate_schedule(teams, season_id, regular_season_weeks=26, games_per_week=2):
    """
    Build a round-robin schedule across regular_season_weeks weeks.
    Returns list of dicts suitable for bulk-inserting as Game rows.
    """
    team_ids = [t.id for t in teams]
    n = len(team_ids)

    # Build a complete round-robin (each pair plays once)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((team_ids[i], team_ids[j]))

    random.shuffle(pairs)

    # Repeat to fill games_per_week * regular_season_weeks slots
    total_games = regular_season_weeks * games_per_week * (n // 2)
    repeat_factor = ceil(total_games / len(pairs))
    full_list = (pairs * repeat_factor)[:total_games]
    random.shuffle(full_list)

    games = []
    week = 1
    for idx, (home_id, away_id) in enumerate(full_list):
        if idx > 0 and idx % (n // 2 * games_per_week) == 0:
            week += 1
            if week > regular_season_weeks:
                break
        # Randomly flip home/away for variety
        if random.random() < 0.5:
            home_id, away_id = away_id, home_id
        games.append({
            "season_id":    season_id,
            "week":         week,
            "home_team_id": home_id,
            "away_team_id": away_id,
            "status":       "scheduled",
        })

    return games


# ─────────────────────────────────────────────────────────────────────────────
# Team strength calculation
# ─────────────────────────────────────────────────────────────────────────────
def team_strength(team):
    """
    Single offensive + defensive composite used in sim.
    Uses top-12 forwards by OVR for offense, top-6 D for defense, top-2 G.
    Returns (offense, defense, goaltending) floats in ~40–99 range.
    """
    from models import Player  # local import to avoid circular at module load

    roster = [p for p in team.players if p.nhl_roster and not p.injured]

    forwards  = sorted(
        [p for p in roster if p.position in ("C", "LW", "RW")],
        key=lambda p: p.overall, reverse=True
    )[:12]
    defenders = sorted(
        [p for p in roster if p.position == "D"],
        key=lambda p: p.overall, reverse=True
    )[:6]
    goalies   = sorted(
        [p for p in roster if p.position == "G"],
        key=lambda p: p.overall, reverse=True
    )[:2]

    def avg(lst): return sum(p.overall for p in lst) / len(lst) if lst else 60.0

    return avg(forwards), avg(defenders), avg(goalies)


# ─────────────────────────────────────────────────────────────────────────────
# Core game simulation
# ─────────────────────────────────────────────────────────────────────────────
def simulate_game(home_team, away_team, neutral_site=False):
    """
    Simulate one game. Returns a dict with score, shots, OT/SO flags, box_score JSON.
    """
    home_off, home_def, home_g = team_strength(home_team)
    away_off, away_def, away_g = team_strength(away_team)

    # Home-ice advantage (add ~3 pts to home offense unless neutral)
    home_bonus = 0 if neutral_site else 3.0

    # Expected goals model (Poisson-ish)
    home_xg = _expected_goals(home_off + home_bonus, away_def, away_g)
    away_xg = _expected_goals(away_off, home_def, home_g)

    home_goals = _poisson_draw(home_xg)
    away_goals = _poisson_draw(away_xg)

    # Shots based on strength with variance
    home_shots = max(15, int(random.gauss((home_off / 99) * 38, 5)))
    away_shots = max(15, int(random.gauss((away_off / 99) * 38, 5)))

    # Tie → overtime
    overtime = shootout = False
    if home_goals == away_goals:
        overtime = True
        # 50/50 chance home team scores in OT (slightly boosted by offense)
        home_ot_prob = 0.5 + (home_off - away_off) / 400 + 0.04  # ~4% HIA in OT
        home_ot_prob = max(0.2, min(0.8, home_ot_prob))
        if random.random() < 0.75:   # 75% of OT games end before shootout
            if random.random() < home_ot_prob:
                home_goals += 1
            else:
                away_goals += 1
        else:
            shootout = True
            if random.random() < home_ot_prob:
                home_goals += 1
            else:
                away_goals += 1

    # Build a simple box score (per-period scoring)
    box = _build_box_score(home_team, away_team, home_goals, away_goals, overtime)

    return {
        "home_score":  home_goals,
        "away_score":  away_goals,
        "home_shots":  home_shots,
        "away_shots":  away_shots,
        "overtime":    overtime,
        "shootout":    shootout,
        "status":      "completed",
        "box_score":   json.dumps(box),
    }


def _expected_goals(attack, enemy_def, enemy_goalie):
    """Convert team ratings to expected goals per game (target ~2.8)."""
    # Base: attack vs def differential
    base = 2.8
    atk_factor  = (attack      - 70) / 30   # +/- relative to 70 baseline
    def_factor  = (enemy_def   - 70) / 30
    gl_factor   = (enemy_goalie - 70) / 30
    xg = base + atk_factor * 0.8 - def_factor * 0.5 - gl_factor * 0.7
    return max(0.5, min(7.0, xg))


def _poisson_draw(lam):
    """Simple Poisson random draw (Box-Muller approximation for speed)."""
    # For small lambda, use direct method
    if lam < 10:
        L = pow(2.718281828, -lam)
        k, p = 0, 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1
    # For larger lambda, use normal approximation
    return max(0, int(random.gauss(lam, lam ** 0.5) + 0.5))


def _build_box_score(home_team, away_team, home_goals, away_goals, overtime):
    """Distribute goals across 3 periods (+ OT if applicable)."""
    periods = [0, 0, 0]
    total = home_goals + away_goals
    for _ in range(total):
        # Goals more likely in 3rd period if game is tight
        period = random.choices([0, 1, 2], weights=[30, 30, 40])[0]
        periods[period] += 1

    home_per = [0, 0, 0]
    away_per = [0, 0, 0]
    remaining_home = home_goals
    remaining_away = away_goals

    for p in range(3):
        period_total = periods[p]
        for _ in range(period_total):
            # Weight by goals ratio
            if remaining_home + remaining_away == 0:
                break
            ratio = remaining_home / (remaining_home + remaining_away)
            if random.random() < ratio and remaining_home > 0:
                home_per[p] += 1
                remaining_home -= 1
            elif remaining_away > 0:
                away_per[p] += 1
                remaining_away -= 1

    return {
        "home": {"name": home_team.name, "per1": home_per[0], "per2": home_per[1], "per3": home_per[2]},
        "away": {"name": away_team.name, "per1": away_per[0], "per2": away_per[1], "per3": away_per[2]},
        "overtime": overtime,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Standings
# ─────────────────────────────────────────────────────────────────────────────
def update_standings(db, game, home_team, away_team):
    """
    Update Standing rows after a completed game.
    Creates Standing rows if they don't exist.
    """
    from models import Standing

    def get_or_create(team_id):
        s = Standing.query.filter_by(season_id=game.season_id, team_id=team_id).first()
        if not s:
            s = Standing(season_id=game.season_id, team_id=team_id,
                         gp=0, w=0, l=0, otl=0, pts=0, gf=0, ga=0)
            db.session.add(s)
        return s

    hs = get_or_create(home_team.id)
    as_ = get_or_create(away_team.id)

    hs.gp += 1; as_.gp += 1
    hs.gf += game.home_score; hs.ga += game.away_score
    as_.gf += game.away_score; as_.ga += game.home_score

    if game.home_score > game.away_score:
        hs.w += 1; hs.pts += 2
        if game.overtime:
            as_.otl += 1; as_.pts += 1
        else:
            as_.l += 1
    else:
        as_.w += 1; as_.pts += 2
        if game.overtime:
            hs.otl += 1; hs.pts += 1
        else:
            hs.l += 1

    db.session.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Playoff seeding
# ─────────────────────────────────────────────────────────────────────────────
def get_playoff_seeds(db, season_id, conferences=None):
    """
    Return playoff bracket (16 teams: top 3 per division + 2 wildcards per conference).
    Returns dict: {"Eastern": [seed1, seed2, …], "Western": [seed1, …]}
    """
    from models import Standing, Team

    standings = (
        Standing.query
        .filter_by(season_id=season_id)
        .join(Team, Standing.team_id == Team.id)
        .all()
    )

    def sort_key(s): return (-s.pts, -(s.gf - s.ga), -s.gf)

    east = sorted([s for s in standings if s.team.conference == "Eastern"], key=sort_key)
    west = sorted([s for s in standings if s.team.conference == "Western"], key=sort_key)

    def conference_seeds(conf_standings):
        divisions = {}
        for s in conf_standings:
            div = s.team.division
            divisions.setdefault(div, []).append(s)

        div_winners = []
        div_rest    = []
        for div, teams in divisions.items():
            sorted_teams = sorted(teams, key=sort_key)
            div_winners.append(sorted_teams[0])
            div_rest.extend(sorted_teams[1:])

        # Top 3 per division (up to 6 spots)
        seeds = []
        for div, teams in divisions.items():
            sorted_teams = sorted(teams, key=sort_key)
            seeds.extend(sorted_teams[:3])

        # 2 wildcards from remaining
        already_seeded = {s.team_id for s in seeds}
        wildcards = sorted(
            [s for s in conf_standings if s.team_id not in already_seeded],
            key=sort_key
        )[:2]
        seeds.extend(wildcards)
        return seeds[:8]

    return {
        "Eastern": conference_seeds(east),
        "Western": conference_seeds(west),
    }


def build_playoff_bracket(seeds_by_conf, season_id):
    """
    Build first-round matchups from conference seeds.
    Format: 1v8, 2v7, 3v6, 4v5 per conference.
    Returns list of game dicts (scheduled, week=1 of playoffs).
    """
    games = []
    for conf, seeds in seeds_by_conf.items():
        if len(seeds) < 8:
            continue
        matchups = [(0, 7), (1, 6), (2, 5), (3, 4)]
        for high, low in matchups:
            games.append({
                "season_id":    season_id,
                "week":         1,
                "home_team_id": seeds[high].team_id,
                "away_team_id": seeds[low].team_id,
                "status":       "scheduled",
                "playoff":      True,
                "conference":   conf,
            })
    return games


# ─────────────────────────────────────────────────────────────────────────────
# Weekly advance
# ─────────────────────────────────────────────────────────────────────────────
def advance_week(db, season):
    """
    Simulate all games scheduled for the current week, update standings.
    Returns list of completed game result summaries.
    """
    from models import Game, Team

    games = Game.query.filter_by(
        season_id=season.id,
        week=season.week,
        status="scheduled"
    ).all()

    results = []
    for game in games:
        home = Team.query.get(game.home_team_id)
        away = Team.query.get(game.away_team_id)
        if not home or not away:
            continue

        result = simulate_game(home, away)
        game.home_score = result["home_score"]
        game.away_score = result["away_score"]
        game.home_shots = result["home_shots"]
        game.away_shots = result["away_shots"]
        game.overtime   = result["overtime"]
        game.shootout   = result["shootout"]
        game.status     = "completed"
        game.box_score  = result["box_score"]

        update_standings(db, game, home, away)
        results.append({
            "home": home.abbrev,
            "away": away.abbrev,
            "score": f"{result['home_score']}-{result['away_score']}",
            "ot":   result["overtime"],
            "so":   result["shootout"],
        })

    season.week += 1
    db.session.commit()
    return results
