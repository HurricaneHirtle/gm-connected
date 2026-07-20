"""
GM Connected — Flask application.
"""
import os
import json
from datetime import datetime, timezone

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_sqlalchemy import SQLAlchemy

# ─────────────────────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"]             = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///gm_connected.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import db, User, Team, Player, Prospect, DraftPick, Game, Standing
from models import Trade, TradeAsset, WeeklyReadiness, Season

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def current_season():
    return Season.query.order_by(Season.id.desc()).first()


def require_commissioner(f):
    """Decorator: 403 unless user is commissioner."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_commissioner:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        team_id  = request.form.get("team_id", type=int)
        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
            return redirect(url_for("register"))
        is_first = User.query.count() == 0  # first user becomes commissioner
        user = User(username=username, team_id=team_id, is_commissioner=is_first)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("dashboard"))
    available_teams = Team.query.filter(
        ~Team.id.in_(db.session.query(User.team_id).filter(User.team_id.isnot(None)))
    ).order_by(Team.name).all()
    return render_template("register.html", teams=available_teams)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def dashboard():
    season = current_season()
    team   = Team.query.get(current_user.team_id) if current_user.team_id else None

    # Readiness status
    readiness = None
    if season and team:
        readiness = WeeklyReadiness.query.filter_by(
            season_id=season.id, week=season.week, team_id=team.id
        ).first()

    # Recent games
    recent_games = []
    if team and season:
        recent_games = (
            Game.query
            .filter(
                Game.season_id == season.id,
                Game.status == "completed",
                db.or_(Game.home_team_id == team.id, Game.away_team_id == team.id)
            )
            .order_by(Game.week.desc())
            .limit(5)
            .all()
        )

    # Pending trades
    pending_trades = []
    if team:
        pending_trades = Trade.query.filter_by(
            receiving_team_id=team.id, status="pending"
        ).all()

    return render_template("dashboard.html",
        season=season, team=team, readiness=readiness,
        recent_games=recent_games, pending_trades=pending_trades)


# ─────────────────────────────────────────────────────────────────────────────
# Roster
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/roster")
@app.route("/roster/<int:team_id>")
@login_required
def roster(team_id=None):
    if team_id is None:
        team_id = current_user.team_id
    team = Team.query.get_or_404(team_id)
    players = (
        Player.query
        .filter_by(team_id=team.id)
        .order_by(Player.nhl_roster.desc(), Player.position, Player.cap_hit.desc())
        .all()
    )
    return render_template("roster.html", team=team, players=players,
                           is_own=team_id == current_user.team_id)


# ─────────────────────────────────────────────────────────────────────────────
# Free Agency
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/free-agency")
@login_required
def free_agency():
    pos_filter = request.args.get("pos", "")
    query = Player.query.filter_by(team_id=None)
    if pos_filter:
        query = query.filter_by(position=pos_filter)
    free_agents = query.order_by(Player.cap_hit.desc()).all()
    return render_template("free_agency.html", players=free_agents, pos_filter=pos_filter)


@app.route("/sign/<int:player_id>", methods=["POST"])
@login_required
def sign_player(player_id):
    player = Player.query.get_or_404(player_id)
    team   = Team.query.get_or_404(current_user.team_id)
    season = current_season()

    if player.team_id is not None:
        flash("Player is no longer available.", "error")
        return redirect(url_for("free_agency"))

    cap_hit   = request.form.get("cap_hit",   type=int)
    years_left = request.form.get("years_left", type=int, default=1)

    if cap_hit is None or cap_hit < 750_000:
        flash("Invalid contract value.", "error")
        return redirect(url_for("free_agency"))

    if team.cap_space < cap_hit:
        flash(f"Not enough cap space. You have ${team.cap_space:,.0f} available.", "error")
        return redirect(url_for("free_agency"))

    player.team_id    = team.id
    player.cap_hit    = cap_hit
    player.years_left = years_left
    player.nhl_roster = True
    db.session.commit()
    flash(f"Signed {player.first_name} {player.last_name}!", "success")
    return redirect(url_for("roster"))


@app.route("/release/<int:player_id>", methods=["POST"])
@login_required
def release_player(player_id):
    player = Player.query.get_or_404(player_id)
    if player.team_id != current_user.team_id:
        abort(403)
    player.team_id    = None
    player.nhl_roster = False
    db.session.commit()
    flash(f"Released {player.first_name} {player.last_name}.", "info")
    return redirect(url_for("roster"))


# ─────────────────────────────────────────────────────────────────────────────
# Trades
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/trades")
@login_required
def trades():
    season = current_season()
    team   = Team.query.get(current_user.team_id)
    incoming = Trade.query.filter_by(receiving_team_id=team.id).order_by(Trade.created_at.desc()).all()
    outgoing = Trade.query.filter_by(proposing_team_id=team.id).order_by(Trade.created_at.desc()).all()
    teams    = Team.query.order_by(Team.name).all()
    return render_template("trades.html", incoming=incoming, outgoing=outgoing,
                           teams=teams, team=team, season=season)


@app.route("/trades/propose", methods=["POST"])
@login_required
def propose_trade():
    season      = current_season()
    my_team_id  = current_user.team_id
    other_id    = request.form.get("receiving_team_id", type=int)
    message     = request.form.get("message", "")

    my_player_ids   = request.form.getlist("my_players",   type=int)
    my_pick_ids     = request.form.getlist("my_picks",     type=int)
    their_player_ids= request.form.getlist("their_players",type=int)
    their_pick_ids  = request.form.getlist("their_picks",  type=int)

    if not other_id or other_id == my_team_id:
        flash("Invalid trade partner.", "error")
        return redirect(url_for("trades"))

    if not (my_player_ids or my_pick_ids or their_player_ids or their_pick_ids):
        flash("A trade must include at least one asset.", "error")
        return redirect(url_for("trades"))

    trade = Trade(
        season_id=season.id,
        proposing_team_id=my_team_id,
        receiving_team_id=other_id,
        status="pending",
        message=message,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(trade)
    db.session.flush()

    for pid in my_player_ids:
        db.session.add(TradeAsset(trade_id=trade.id, from_team_id=my_team_id,
                                   to_team_id=other_id, asset_type="player", player_id=pid))
    for pkid in my_pick_ids:
        db.session.add(TradeAsset(trade_id=trade.id, from_team_id=my_team_id,
                                   to_team_id=other_id, asset_type="pick", pick_id=pkid))
    for pid in their_player_ids:
        db.session.add(TradeAsset(trade_id=trade.id, from_team_id=other_id,
                                   to_team_id=my_team_id, asset_type="player", player_id=pid))
    for pkid in their_pick_ids:
        db.session.add(TradeAsset(trade_id=trade.id, from_team_id=other_id,
                                   to_team_id=my_team_id, asset_type="pick", pick_id=pkid))

    db.session.commit()
    flash("Trade proposal sent!", "success")
    return redirect(url_for("trades"))


@app.route("/trades/<int:trade_id>/respond", methods=["POST"])
@login_required
def respond_trade(trade_id):
    trade  = Trade.query.get_or_404(trade_id)
    action = request.form.get("action")

    if trade.receiving_team_id != current_user.team_id:
        abort(403)
    if trade.status != "pending":
        flash("This trade is no longer pending.", "error")
        return redirect(url_for("trades"))

    if action == "accept":
        _execute_trade(trade)
        trade.status = "accepted"
        flash("Trade accepted!", "success")
    elif action == "reject":
        trade.status = "rejected"
        flash("Trade rejected.", "info")
    else:
        flash("Unknown action.", "error")

    trade.resolved_at = datetime.now(timezone.utc)
    db.session.commit()
    return redirect(url_for("trades"))


def _execute_trade(trade):
    """Move players and picks between teams."""
    for asset in trade.assets:
        if asset.asset_type == "player":
            p = Player.query.get(asset.player_id)
            if p:
                p.team_id = asset.to_team_id
        elif asset.asset_type == "pick":
            pk = DraftPick.query.get(asset.pick_id)
            if pk:
                pk.owner_team_id = asset.to_team_id


# ─────────────────────────────────────────────────────────────────────────────
# Standings
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/standings")
@login_required
def standings():
    season = current_season()
    rows = (
        Standing.query
        .filter_by(season_id=season.id)
        .join(Team, Standing.team_id == Team.id)
        .order_by(Team.conference, Team.division, Standing.pts.desc())
        .all()
    )
    # Group by conference and division
    grouped = {}
    for s in rows:
        key = (s.team.conference, s.team.division)
        grouped.setdefault(key, []).append(s)
    return render_template("standings.html", grouped=grouped, season=season)


# ─────────────────────────────────────────────────────────────────────────────
# Schedule
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/schedule")
@login_required
def schedule():
    season  = current_season()
    team_id = current_user.team_id
    week    = request.args.get("week", season.week if season else 1, type=int)
    games   = (
        Game.query
        .filter_by(season_id=season.id, week=week)
        .order_by(Game.id)
        .all()
    )
    return render_template("schedule.html", games=games, week=week,
                           season=season, team_id=team_id)


# ─────────────────────────────────────────────────────────────────────────────
# Prospects
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/prospects")
@login_required
def prospects():
    season   = current_season()
    year     = request.args.get("year", season.year + 1 if season else 2027, type=int)
    eligible = Prospect.query.filter_by(draft_year=year, is_drafted=False).order_by(
        Prospect.scout_grade, Prospect.last_name
    ).all()
    future   = (
        Prospect.query
        .filter(Prospect.draft_year > year, Prospect.is_drafted == False)
        .order_by(Prospect.draft_year, Prospect.last_name)
        .limit(50).all()
    )
    return render_template("prospects.html", eligible=eligible, future=future,
                           year=year, season=season)


# ─────────────────────────────────────────────────────────────────────────────
# Draft
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/draft")
@login_required
def draft():
    season = current_season()
    if season and season.phase != "draft":
        flash("The draft is not currently open.", "info")
    draft_year = (season.year + 1) if season else 2027
    available  = Prospect.query.filter_by(draft_year=draft_year, is_drafted=False).all()
    my_picks   = (
        DraftPick.query
        .filter_by(owner_team_id=current_user.team_id, year=draft_year, used=False)
        .order_by(DraftPick.round, DraftPick.pick_number)
        .all()
    )
    return render_template("draft.html", available=available, my_picks=my_picks,
                           season=season, draft_year=draft_year)


@app.route("/draft/pick", methods=["POST"])
@login_required
def make_pick():
    prospect_id = request.form.get("prospect_id", type=int)
    pick_id     = request.form.get("pick_id",     type=int)
    season      = current_season()

    if season and season.phase != "draft":
        flash("Draft is not open.", "error")
        return redirect(url_for("draft"))

    pick    = DraftPick.query.get_or_404(pick_id)
    prospect= Prospect.query.get_or_404(prospect_id)

    if pick.owner_team_id != current_user.team_id:
        abort(403)
    if pick.used or prospect.is_drafted:
        flash("That pick or prospect is no longer available.", "error")
        return redirect(url_for("draft"))

    pick.used               = True
    pick.pick_number        = pick.pick_number or 0
    prospect.is_drafted     = True
    prospect.nhl_team_id    = current_user.team_id
    prospect.draft_round    = pick.round
    prospect.draft_pick_num = pick.pick_number

    db.session.commit()
    flash(f"Drafted {prospect.first_name} {prospect.last_name}!", "success")
    return redirect(url_for("draft"))


# ─────────────────────────────────────────────────────────────────────────────
# Readiness
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/ready-up", methods=["POST"])
@login_required
def ready_up():
    season = current_season()
    team   = Team.query.get(current_user.team_id)
    if not season or not team:
        flash("No active season.", "error")
        return redirect(url_for("dashboard"))

    existing = WeeklyReadiness.query.filter_by(
        season_id=season.id, week=season.week, team_id=team.id
    ).first()
    if existing:
        flash("Already readied up this week.", "info")
        return redirect(url_for("dashboard"))

    wr = WeeklyReadiness(season_id=season.id, week=season.week,
                          team_id=team.id, is_ready=True,
                          readied_at=datetime.now(timezone.utc))
    db.session.add(wr)
    db.session.commit()

    # Check if all active GMs are ready
    active_team_ids = {u.team_id for u in User.query.filter(User.team_id.isnot(None)).all()}
    ready_ids = {
        r.team_id for r in
        WeeklyReadiness.query.filter_by(season_id=season.id, week=season.week, is_ready=True).all()
    }
    if active_team_ids <= ready_ids:
        _advance_week_auto(season)
        flash("All GMs ready! Week advanced automatically.", "success")
    else:
        remaining = len(active_team_ids - ready_ids)
        flash(f"Readied up! Waiting on {remaining} more GM(s).", "success")

    return redirect(url_for("dashboard"))


def _advance_week_auto(season):
    from sim_engine import advance_week
    from prospect_gen import generate_cohort, develop_prospect

    advance_week(db, season)

    # End of regular season → switch to playoffs/draft
    if season.week > 26 and season.phase == "regular":
        season.phase = "playoffs"
    elif season.week > 30 and season.phase == "playoffs":
        season.phase = "draft"
    elif season.week > 32 and season.phase == "draft":
        season.phase = "offseason"
        _run_offseason(season)

    db.session.commit()


def _run_offseason(season):
    """Age all prospects, generate new 14-year-old cohort for next year."""
    from prospect_gen import develop_prospect, generate_cohort
    from models import Prospect

    # Age existing prospects
    for p in Prospect.query.filter_by(is_drafted=False).all():
        data = {c.name: getattr(p, c.name) for c in p.__table__.columns}
        updated = develop_prospect(data, seasons=1)
        for attr, val in updated.items():
            if hasattr(p, attr) and attr not in ("id",):
                try:
                    setattr(p, attr, val)
                except Exception:
                    pass

    # New 14-year-old class for next season
    new_cohort = generate_cohort(season.year + 1, count_per_age={14: 30})
    for p_data in new_cohort:
        p = Prospect(
            first_name=p_data["first_name"], last_name=p_data["last_name"],
            position=p_data["position"], birth_year=p_data["birth_year"],
            nationality=p_data["nationality"], shoots=p_data["shoots"],
            archetype=p_data["archetype"], current_team=p_data["current_team"],
            current_league=p_data["current_league"], potential=p_data["potential"],
            scout_grade=p_data["scout_grade"], draft_year=p_data["draft_year"],
            is_drafted=False, **{k: p_data.get(k, 0) for k in [
                "skating","shooting","passing","defense","physical",
                "puck_control","awareness","reflexes","positioning",
                "rebound_ctrl","puck_handling"
            ]},
        )
        db.session.add(p)

    # Roll season year forward
    new_season = Season(year=season.year + 1, week=1, phase="preseason",
                        cap_ceiling=season.cap_ceiling + 1_000_000)
    db.session.add(new_season)


# ─────────────────────────────────────────────────────────────────────────────
# Admin / Commissioner
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/admin")
@login_required
@require_commissioner
def admin():
    season = current_season()
    teams  = Team.query.order_by(Team.name).all()
    users  = User.query.all()
    readiness = (
        WeeklyReadiness.query
        .filter_by(season_id=season.id, week=season.week)
        .all()
    ) if season else []
    return render_template("admin.html", season=season, teams=teams,
                           users=users, readiness=readiness)


@app.route("/admin/force-advance", methods=["POST"])
@login_required
@require_commissioner
def force_advance():
    season = current_season()
    if not season:
        flash("No active season.", "error")
        return redirect(url_for("admin"))
    _advance_week_auto(season)
    flash(f"Week advanced to {season.week}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/set-phase", methods=["POST"])
@login_required
@require_commissioner
def set_phase():
    season = current_season()
    phase  = request.form.get("phase")
    if phase in ("preseason", "regular", "playoffs", "draft", "offseason"):
        season.phase = phase
        db.session.commit()
        flash(f"Phase set to {phase}.", "success")
    return redirect(url_for("admin"))


# ─────────────────────────────────────────────────────────────────────────────
# API endpoints (JSON) used by JS
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/team/<int:team_id>/players")
@login_required
def api_team_players(team_id):
    players = Player.query.filter_by(team_id=team_id).all()
    return jsonify([{
        "id": p.id, "name": f"{p.first_name} {p.last_name}",
        "pos": p.position, "ovr": p.overall,
        "cap_hit": p.cap_hit, "years_left": p.years_left,
    } for p in players])


@app.route("/api/team/<int:team_id>/picks")
@login_required
def api_team_picks(team_id):
    season = current_season()
    picks  = DraftPick.query.filter_by(owner_team_id=team_id, used=False).all()
    return jsonify([{
        "id": pk.id, "label": pk.label,
        "year": pk.year, "round": pk.round,
    } for pk in picks])


@app.route("/api/standings")
@login_required
def api_standings():
    season = current_season()
    rows   = Standing.query.filter_by(season_id=season.id).join(Team).all()
    return jsonify([{
        "team": r.team.name, "abbrev": r.team.abbrev,
        "conference": r.team.conference, "division": r.team.division,
        "gp": r.gp, "w": r.w, "l": r.l, "otl": r.otl, "pts": r.pts,
        "gf": r.gf, "ga": r.ga,
    } for r in rows])


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
