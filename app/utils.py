from datetime import datetime, date, timedelta, time as dtime
from app.models import db, Reservation, Session, Member
from sqlalchemy import func, and_

def week_bounds(anchor: datetime):
    start = anchor - timedelta(days=anchor.weekday())
    start = datetime.combine(start.date(), dtime(0, 0))
    end = start + timedelta(days=7)
    return start, end

def make_days(week_start: datetime):
    return [week_start + timedelta(days=i) for i in range(7)]

def time_range(start_h=7, end_h=22, step_min=60):
    cur = datetime.combine(datetime.today(), dtime(start_h, 0))
    end = datetime.combine(datetime.today(), dtime(end_h, 0))
    out = []
    while cur <= end:
        out.append(cur.time().replace(second=0, microsecond=0))
        cur += timedelta(minutes=step_min)
    return out

def mark_user_joined(sessions, member_name: str | None):
    for s in sessions:
        s.user_joined = False
    if not member_name:
        return sessions
    joined = {
        r.session_id
        for r in Reservation.query
            .filter_by(user_name=member_name, status='active')
            .all()
    }
    for s in sessions:
        s.user_joined = (s.id in joined)
    return sessions

def auto_reserve(session, member_ids):
    if not member_ids:
        return
    for member_id in member_ids:
        member = Member.query.get(member_id)
        if not member and isinstance(member_id, int): # ID kontrolü
             pass 
        
        # Eğer member_id bir int ise ve yukarıda bulamadıysa (Member.get logic)
        # Buradaki mantığı senin orijinal koduna sadık kalarak basitleştirdim.
        
        if member:
            reservation = Reservation(
                session_id=session.id,
                user_name=member.full_name,
                status='active'
            )
            db.session.add(reservation)
            if session.spots_left > 0:
                session.spots_left -= 1
    db.session.commit()

# Geçmiş seansları kapatma mantığı
def close_past_sessions_logic():
    now = datetime.now()
    to_close = (
        Session.query
        .filter(
            Session.completed.is_(False),
            (Session.date < now.date()) |
            and_(Session.date == now.date(), Session.time < now.time())
        )
        .all()
    )
    if not to_close:
        return

    for s in to_close:
        s.completed = True
        for r in s.reservations:
            if r.status == 'active':
                r.status = 'attended'
                m = Member.query.filter(
                    func.lower(Member.full_name) == r.user_name.lower()
                ).first()
                if m and (m.credits or 0) > 0:
                    m.credits -= 1
    db.session.commit()