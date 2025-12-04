# GPTHOOK:dashboard-route START
from datetime import date, timedelta
from flask import Blueprint, render_template, g, jsonify, current_app
from sqlalchemy.orm import selectinload
from sqlalchemy import and_
from app.models import db, Session, Reservation
from app.decorators import login_required

dashboard_bp = Blueprint("dashboard_bp", __name__, url_prefix="")

def _week_range(d: date):
    mon = d - timedelta(days=d.weekday())
    return mon, mon + timedelta(days=6)

def _build_weeks(today: date):
    w1s, w1e = _week_range(today)
    w2s, w2e = w1s + timedelta(days=7), w1e + timedelta(days=7)
    w3s, w3e = w2s + timedelta(days=7), w2e + timedelta(days=7)
    fmt = "%d %b"
    return [
        {"key": "week1", "label": f"Bu Hafta ({w1s.strftime(fmt)}–{w1e.strftime(fmt)})", "start": w1s, "end": w1e, "active": True},
        {"key": "week2", "label": f"Gelecek Hafta ({w2s.strftime(fmt)}–{w2e.strftime(fmt)})", "start": w2s, "end": w2e, "active": False},
        {"key": "week3", "label": f"2 Hafta Sonra ({w3s.strftime(fmt)}–{w3e.strftime(fmt)})", "start": w3s, "end": w3e, "active": False},
    ]

def _group_by_day(items):
    out = {}
    for s in items:
        d = getattr(s, "date", None) or (s.datetime.date() if hasattr(s, "datetime") else None)
        out.setdefault(d, []).append(s)
    return out

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    today = date.today()
    weeks = _build_weeks(today)

    week_payload = []
    for i, w in enumerate(weeks):
        q = (db.session.query(Session)
             .options(selectinload(Session.reservations))
             .filter(and_(Session.date >= w["start"], Session.date <= w["end"]))
             .order_by(Session.date.asc(), Session.time.asc()))
        items = q.all()
        week_payload.append({
            "key": w["key"],
            "label": w["label"],
            "days": _group_by_day(items),
            "active": w["active"]
        })

    upcoming_q = (db.session.query(Session)
                  .options(selectinload(Session.reservations))
                  .filter(Session.date >= today)
                  .order_by(Session.date.asc(), Session.time.asc()))
    upcoming = upcoming_q.limit(5).all()

    user_name = getattr(getattr(g, "current_user", None), "name", "Üye")
    return render_template("dashboard.html", user_name=user_name, weeks=week_payload, upcoming=upcoming)

@dashboard_bp.route("/reservations/<int:session_id>/join", methods=["POST"])
@login_required
def join_session(session_id):
    s = Session.query.get_or_404(session_id)
    user_id = getattr(getattr(g, "current_user", None), "id", None)
    if not user_id:
        return jsonify({"ok": False, "message": "Oturum bulunamadı."}), 401
    exists = Reservation.query.filter_by(session_id=s.id, user_id=user_id).first()
    if exists:
        return jsonify({"ok": True, "message": "Zaten kayıtlısın."})
    r = Reservation(session_id=s.id, user_id=user_id, status="active")
    db.session.add(r)
    db.session.commit()
    return jsonify({"ok": True, "message": "Kayıt oluşturuldu."})
# GPTHOOK:dashboard-route END
