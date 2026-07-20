"""
Database models for GM Connected.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


# ─────────────────────────────────────────────────────────────────────────────
# Season / League state
# ─────────────────────────────────────────────────────────────────────────────
class Season(db.Model):
    __tablename__ = "seasons"
    id        = db.Column(db.Integer, primary_key=True)
    year      = db.Column(db.Integer, nullable=False)   # e.g. 2027
    week      = db.Column(db.Integer, default=0)        # 0 = preseason
    phase     = db.Column(db.String(20), default="preseason")
    # phases: preseason | regular | playoffs | offseason | draft
    cap_ceiling = db.Column(db.Integer, default=104_000_000)

    def __repr__(self):
        return f"<Season {self.year} W{self.week} [{self.phase}]>"


# ─────────────────────────────────────────────────────────────────────────────
# Teams
# ─────────────────────────────────────────────────────────────────────────────
class Team(db.Model):
    __tablename__ = "teams"
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(60), nullable=False)   # "Toronto Maple Leafs"
    city        = db.Column(db.String(40), nullable=False)
    abbrev      = db.Column(db.String(5),  nullable=False, unique=True)  # "TOR"
    conference  = db.Column(db.String(10))  # "Eastern" / "Western"
    division    = db.Column(db.String(20))  # "Atlantic" etc.
    arena       = db.Column(db.String(60))
    primary_color  = db.Column(db.String(7), default="#001B33")
    secondary_color = db.Column(db.String(7), default="#FFFFFF")

    # Relationships
    players     = db.relationship("Player", backref="team", lazy=True,
                                  foreign_keys="Player.team_id")
    prospects   = db.relationship("Prospect", backref="drafted_by", lazy=True,
                                  foreign_keys="Prospect.nhl_team_id")
    gm          = db.relationship("User", backref="managed_team", uselist=False,
                                  foreign_keys="User.team_id")

    @property
    def cap_hit(self):
        active = [p for p in self.players if p.nhl_roster]
        return sum(p.cap_hit for p in active)

    @property
    def cap_space(self, ceiling=104_000_000):
        return ceiling - self.cap_hit

    @property
    def overall(self):
        """Average OVR of top 20 NHL-roster players."""
        rostered = sorted(
            [p for p in self.players if p.nhl_roster],
            key=lambda p: p.overall, reverse=True
        )[:20]
        if not rostered:
            return 70
        return int(sum(p.overall for p in rostered) / len(rostered))

    def __repr__(self):
        return f"<Team {self.abbrev}>"


# ─────────────────────────────────────────────────────────────────────────────
# Players (signed, under contract)
# ─────────────────────────────────────────────────────────────────────────────
class Player(db.Model):
    __tablename__ = "players"
    id           = db.Column(db.Integer, primary_key=True)
    first_name   = db.Column(db.String(40), nullable=False)
    last_name    = db.Column(db.String(40), nullable=False)
    position     = db.Column(db.String(5), nullable=False)   # C LW RW D G
    age          = db.Column(db.Integer, default=22)
    nationality  = db.Column(db.String(30), default="Canadian")
    shoots       = db.Column(db.String(1), default="R")  # L or R

    # Contract
    team_id      = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    cap_hit      = db.Column(db.Integer, default=775_000)   # in dollars
    years_left   = db.Column(db.Integer, default=1)
    contract_type = db.Column(db.String(10), default="Standard")  # ELC Standard UFA RFA
    nmc          = db.Column(db.Boolean, default=False)
    ntc          = db.Column(db.Boolean, default=False)

    # Roster status
    nhl_roster   = db.Column(db.Boolean, default=True)   # on NHL roster vs AHL
    injured      = db.Column(db.Boolean, default=False)
    waiver_exempt = db.Column(db.Boolean, default=False)

    # ── Skater ratings (1-99) ─────────────────────────────────────────────
    skating      = db.Column(db.Integer, default=70)
    shooting     = db.Column(db.Integer, default=70)
    passing      = db.Column(db.Integer, default=70)
    defense      = db.Column(db.Integer, default=70)
    physical     = db.Column(db.Integer, default=70)
    puck_control = db.Column(db.Integer, default=70)
    awareness    = db.Column(db.Integer, default=70)

    # ── Goalie ratings ────────────────────────────────────────────────────
    reflexes     = db.Column(db.Integer, default=70)
    positioning  = db.Column(db.Integer, default=70)
    rebound_ctrl = db.Column(db.Integer, default=70)
    puck_handling = db.Column(db.Integer, default=70)

    # Season stats (reset each season)
    gp  = db.Column(db.Integer, default=0)
    goals = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    pim   = db.Column(db.Integer, default=0)
    plus_minus = db.Column(db.Integer, default=0)
    # Goalie
    wins   = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    gaa    = db.Column(db.Float, default=0.0)
    sv_pct = db.Column(db.Float, default=0.0)

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def overall(self):
        if self.position == "G":
            return int((self.reflexes + self.positioning +
                        self.rebound_ctrl + self.puck_handling) / 4)
        weights = {
            "C":  [0.85, 0.90, 1.00, 0.80, 0.70, 0.95, 0.90],
            "LW": [0.90, 1.00, 0.80, 0.75, 0.90, 0.90, 0.80],
            "RW": [0.90, 1.00, 0.80, 0.75, 0.85, 0.90, 0.80],
            "D":  [0.85, 0.70, 0.85, 1.00, 1.00, 0.80, 0.95],
        }
        w = weights.get(self.position, [1]*7)
        attrs = [self.skating, self.shooting, self.passing,
                 self.defense, self.physical, self.puck_control, self.awareness]
        return int(sum(a*wt for a, wt in zip(attrs, w)) / sum(w))

    @property
    def cap_hit_str(self):
        h = self.cap_hit
        if h >= 1_000_000:
            return f"${h/1_000_000:.2f}M"
        return f"${h//1000}K"

    @property
    def points(self):
        return self.goals + self.assists

    def __repr__(self):
        return f"<Player {self.name} [{self.position}] OVR:{self.overall}>"


# ─────────────────────────────────────────────────────────────────────────────
# Prospects (undrafted, aging into the draft)
# ─────────────────────────────────────────────────────────────────────────────
class Prospect(db.Model):
    __tablename__ = "prospects"
    id            = db.Column(db.Integer, primary_key=True)
    first_name    = db.Column(db.String(40), nullable=False)
    last_name     = db.Column(db.String(40), nullable=False)
    position      = db.Column(db.String(5),  nullable=False)
    birth_year    = db.Column(db.Integer,    nullable=False)  # determines age
    nationality   = db.Column(db.String(30), default="Canadian")
    shoots        = db.Column(db.String(1),  default="R")
    archetype     = db.Column(db.String(20))  # Sniper, Playmaker, Two-Way, etc.

    # Current junior/college team
    current_team  = db.Column(db.String(60))   # e.g. "Brantford Bulldogs"
    current_league = db.Column(db.String(20))  # OHL / WHL / QMJHL / NCAA / SHL / etc.

    # Ratings (partially hidden from GMs — shown after scouting)
    skating       = db.Column(db.Integer, default=55)
    shooting      = db.Column(db.Integer, default=55)
    passing       = db.Column(db.Integer, default=55)
    defense       = db.Column(db.Integer, default=55)
    physical      = db.Column(db.Integer, default=55)
    puck_control  = db.Column(db.Integer, default=55)
    awareness     = db.Column(db.Integer, default=55)
    # Goalie
    reflexes      = db.Column(db.Integer, default=55)
    positioning   = db.Column(db.Integer, default=55)
    rebound_ctrl  = db.Column(db.Integer, default=55)
    puck_handling = db.Column(db.Integer, default=55)

    potential     = db.Column(db.Integer, default=75)   # hidden ceiling OVR

    # Draft status
    draft_year    = db.Column(db.Integer, nullable=True)   # which year they'll be draft-eligible
    nhl_team_id   = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    draft_round   = db.Column(db.Integer, nullable=True)
    draft_pick_num = db.Column(db.Integer, nullable=True)
    is_drafted    = db.Column(db.Boolean, default=False)

    # Scout rating (visible to all GMs — rougher than actual)
    scout_grade   = db.Column(db.String(5))  # "A+", "A", "B+", "B", "C+", "C", "D"

    @property
    def age(self):
        """Age as of current sim season — stored as birth year."""
        from flask import current_app
        try:
            season = Season.query.order_by(Season.id.desc()).first()
            return (season.year if season else 2027) - self.birth_year
        except Exception:
            return 2027 - self.birth_year

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def overall(self):
        if self.position == "G":
            return int((self.reflexes + self.positioning +
                        self.rebound_ctrl + self.puck_handling) / 4)
        w = [0.85, 0.90, 0.85, 0.80, 0.75, 0.90, 0.85]
        attrs = [self.skating, self.shooting, self.passing,
                 self.defense, self.physical, self.puck_control, self.awareness]
        return int(sum(a*wt for a, wt in zip(attrs, w)) / sum(w))

    def __repr__(self):
        return f"<Prospect {self.name} [{self.position}] Age:{self.age} POT:{self.potential}>"


# ─────────────────────────────────────────────────────────────────────────────
# Draft picks (tradeable assets)
# ─────────────────────────────────────────────────────────────────────────────
class DraftPick(db.Model):
    __tablename__ = "draft_picks"
    id              = db.Column(db.Integer, primary_key=True)
    year            = db.Column(db.Integer, nullable=False)
    round           = db.Column(db.Integer, nullable=False)   # 1-7
    original_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    owner_team_id   = db.Column(db.Integer, db.ForeignKey("teams.id"))
    used            = db.Column(db.Boolean, default=False)
    pick_number     = db.Column(db.Integer, nullable=True)  # assigned after lottery

    original_team = db.relationship("Team", foreign_keys=[original_team_id])
    owner_team    = db.relationship("Team", foreign_keys=[owner_team_id])

    @property
    def label(self):
        suffix = {1:"st",2:"nd",3:"rd"}.get(self.round, "th")
        if self.pick_number:
            return f"{self.year} #{self.pick_number} ({self.original_team.abbrev})"
        return f"{self.year} {self.round}{suffix} Rd ({self.original_team.abbrev})"

    def __repr__(self):
        return f"<Pick {self.label}>"


# ─────────────────────────────────────────────────────────────────────────────
# Schedule / Games
# ─────────────────────────────────────────────────────────────────────────────
class Game(db.Model):
    __tablename__ = "games"
    id           = db.Column(db.Integer, primary_key=True)
    season_id    = db.Column(db.Integer, db.ForeignKey("seasons.id"))
    week         = db.Column(db.Integer, nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    status       = db.Column(db.String(15), default="scheduled")  # scheduled / completed
    home_score   = db.Column(db.Integer, nullable=True)
    away_score   = db.Column(db.Integer, nullable=True)
    home_shots   = db.Column(db.Integer, nullable=True)
    away_shots   = db.Column(db.Integer, nullable=True)
    overtime     = db.Column(db.Boolean, default=False)
    shootout     = db.Column(db.Boolean, default=False)
    # Box score stored as JSON string
    box_score    = db.Column(db.Text, nullable=True)

    home_team = db.relationship("Team", foreign_keys=[home_team_id])
    away_team = db.relationship("Team", foreign_keys=[away_team_id])

    @property
    def result_str(self):
        if self.status != "completed":
            return "vs"
        ot = " (OT)" if self.overtime else (" (SO)" if self.shootout else "")
        return f"{self.home_score}-{self.away_score}{ot}"

    def __repr__(self):
        return f"<Game {self.away_team_id}@{self.home_team_id} W{self.week}>"


# ─────────────────────────────────────────────────────────────────────────────
# Standings
# ─────────────────────────────────────────────────────────────────────────────
class Standing(db.Model):
    __tablename__ = "standings"
    id        = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"))
    team_id   = db.Column(db.Integer, db.ForeignKey("teams.id"))
    gp  = db.Column(db.Integer, default=0)
    w   = db.Column(db.Integer, default=0)
    l   = db.Column(db.Integer, default=0)
    otl = db.Column(db.Integer, default=0)
    pts = db.Column(db.Integer, default=0)
    gf  = db.Column(db.Integer, default=0)
    ga  = db.Column(db.Integer, default=0)

    team = db.relationship("Team")

    @property
    def gd(self):
        return self.gf - self.ga

    def __repr__(self):
        return f"<Standing {self.team_id}: {self.pts}pts>"


# ─────────────────────────────────────────────────────────────────────────────
# Trades
# ─────────────────────────────────────────────────────────────────────────────
class Trade(db.Model):
    __tablename__ = "trades"
    id              = db.Column(db.Integer, primary_key=True)
    season_id       = db.Column(db.Integer, db.ForeignKey("seasons.id"))
    proposing_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    receiving_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"))
    status          = db.Column(db.String(15), default="pending")
    # pending | accepted | rejected | countered | expired
    message         = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at     = db.Column(db.DateTime, nullable=True)

    proposing_team  = db.relationship("Team", foreign_keys=[proposing_team_id])
    receiving_team  = db.relationship("Team", foreign_keys=[receiving_team_id])
    assets          = db.relationship("TradeAsset", backref="trade", lazy=True)

    def __repr__(self):
        return f"<Trade {self.proposing_team_id}→{self.receiving_team_id} [{self.status}]>"


class TradeAsset(db.Model):
    __tablename__ = "trade_assets"
    id            = db.Column(db.Integer, primary_key=True)
    trade_id      = db.Column(db.Integer, db.ForeignKey("trades.id"))
    from_team_id  = db.Column(db.Integer, db.ForeignKey("teams.id"))
    to_team_id    = db.Column(db.Integer, db.ForeignKey("teams.id"))
    asset_type    = db.Column(db.String(10))  # "player" or "pick"
    player_id     = db.Column(db.Integer, db.ForeignKey("players.id"), nullable=True)
    pick_id       = db.Column(db.Integer, db.ForeignKey("draft_picks.id"), nullable=True)

    player = db.relationship("Player")
    pick   = db.relationship("DraftPick")
    from_team = db.relationship("Team", foreign_keys=[from_team_id])
    to_team   = db.relationship("Team", foreign_keys=[to_team_id])


# ─────────────────────────────────────────────────────────────────────────────
# Weekly Readiness
# ─────────────────────────────────────────────────────────────────────────────
class WeeklyReadiness(db.Model):
    __tablename__ = "weekly_readiness"
    id        = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"))
    week      = db.Column(db.Integer, nullable=False)
    team_id   = db.Column(db.Integer, db.ForeignKey("teams.id"))
    is_ready  = db.Column(db.Boolean, default=False)
    readied_at = db.Column(db.DateTime, nullable=True)

    team = db.relationship("Team")


# ─────────────────────────────────────────────────────────────────────────────
# Users (GMs)
# ─────────────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(40), unique=True, nullable=False)
    password_hash   = db.Column(db.String(128), nullable=False)
    team_id         = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    is_commissioner = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def __repr__(self):
        return f"<User {self.username}>"
