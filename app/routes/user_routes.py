from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from datetime import date, datetime, timedelta, time as dtime
from sqlalchemy import func, and_
from collections import defaultdict

# Modelleri ve Yardımcıları İmport Et
from app.models import db, Member, Reservation, Session, Measurement
from app.decorators import login_required
from app.utils import week_bounds, make_days, time_range, mark_user_joined

user_bp = Blueprint('user', __name__)

# 👇👇👇 BU KISIM EKSİKTİ! BURAYI EKLEMEZSEN /nil ADRESİ ÇALIŞMAZ 👇👇👇
@user_bp.route('/')
def home():
    # Eğer kullanıcı zaten giriş yapmışsa paneline gitsin
    if 'user_name' in session:
        return redirect(url_for('user.user_dashboard'))
    
    # Giriş yapmamışsa, stüdyonun giriş sayfasına yönlensin
    return redirect(url_for('auth.login'))
# 👆👆👆 ---------------------------------------------------------- 👆👆👆

# --- YARDIMCI FONKSİYON: Katılım Verisini Hazırla ---
def build_attendance_weeks(member_id, num_weeks=20):
    """
    Son 'num_weeks' hafta için (Pzt-Paz) katılım sayılarını hazırlar.
    """
    weeks_data = []
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    
    for i in range(num_weeks):
        w_start = current_week_start - timedelta(weeks=i)
        week_days = []
        for d in range(7): 
            day_date = w_start + timedelta(days=d)
            count = (
                db.session.query(Reservation)
                .join(Session)
                .filter(
                    Reservation.user_name == session['user_name'],
                    Reservation.status.in_(['attended', 'active']),
                    Session.date == day_date
                )
                .count()
            )
            week_days.append({'date': day_date, 'count': count})
        weeks_data.append(week_days)
    return weeks_data

# --- 1. Dashboard (Anasayfa) ---
@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    name = session['user_name']
    
    # Sadece BU stüdyonun (tenant) rezervasyonlarını getir
    my_active = (
        Reservation.query
        .filter(
            Reservation.user_name == name,
            Reservation.status == 'active',
            Reservation.tenant_id == g.tenant.id # Çoklu stüdyo güvenliği
        )
        .join(Session)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )

    week_groups = defaultdict(list)
    today = date.today()
    current_week_index = 0
    
    for reservation in my_active:
        sess = reservation.session
        w_start = sess.date - timedelta(days=sess.date.weekday())
        w_end = w_start + timedelta(days=6)
        w_label = f"{w_start.strftime('%d.%m.%Y')} - {w_end.strftime('%d.%m.%Y')}"
        week_groups[w_label].append(reservation)
        
    sorted_weeks = sorted(week_groups.keys(), key=lambda w: datetime.strptime(w.split(' - ')[0], '%d.%m.%Y'))
    grouped_reservations = []
    
    for idx, week in enumerate(sorted_weeks):
        w_start_dt = datetime.strptime(week.split(' - ')[0], '%d.%m.%Y').date()
        w_end_dt = datetime.strptime(week.split(' - ')[1], '%d.%m.%Y').date()
        is_curr = w_start_dt <= today <= w_end_dt
        if is_curr: current_week_index = idx
        
        res_list = []
        for r in week_groups[week]:
            session_dt = datetime.combine(r.session.date, r.session.time)
            is_late = (session_dt - datetime.now()) < timedelta(hours=24)
            
            res_list.append({
                "id": r.id,
                "session_day": r.session.date.strftime('%A'),
                "session_time": r.session.time.strftime('%H:%M'),
                "session_date": r.session.date.strftime('%d.%m.%Y'),
                "session_notes": r.session.notes,
                "cancel_status": r.cancel_status,
                "cancel_reason": getattr(r, 'cancel_reason', None),
                "session_id": r.session.id,
                "is_late": is_late 
            })
        grouped_reservations.append({"week": week, "reservations": res_list, "is_current_week": is_curr})

    upcoming = Session.query.filter(Session.tenant_id == g.tenant.id, Session.date >= date.today()).order_by(Session.date.asc(), Session.time.asc()).all()
    
    member = Member.query.filter(
        Member.tenant_id == g.tenant.id,
        func.lower(Member.full_name) == name.lower()
    ).first()
    
    credits_left = member.credits if member else 0
    
    first_day = date.today().replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year+1, month=1, day=1)
    else:
        next_month = first_day.replace(month=first_day.month+1, day=1)
    
    monthly_attended = (
        db.session.query(Reservation)
        .join(Session)
        .filter(
            Reservation.user_name == name,
            Reservation.status == 'attended',
            Reservation.tenant_id == g.tenant.id,
            Session.date >= first_day,
            Session.date < next_month
        ).count()
    )

    measurements = []
    if member:
        measurements = Measurement.query.filter_by(member_id=member.id).order_by(Measurement.date.desc()).all()

    return render_template(
        'user_dashboard_new.html',
        name=name,
        grouped_reservations=grouped_reservations,
        current_week_index=current_week_index,
        upcoming=upcoming,
        credits_left=credits_left,
        monthly_attended=monthly_attended,
        member=member,
        measurements=measurements
    )

# --- 2. Profil Sayfası ---
@user_bp.route('/profile')
@login_required
def profile():
    name = session['user_name']
    member = Member.query.filter(
        Member.tenant_id == g.tenant.id,
        func.lower(Member.full_name) == name.lower()
    ).first()
    
    measurements = []
    weeks = [] 
    
    if member:
        measurements = Measurement.query.filter_by(member_id=member.id).order_by(Measurement.date.desc()).all()
        weeks = build_attendance_weeks(member.id, num_weeks=20)

    return render_template('profile.html', member=member, measurements=measurements, weeks=weeks)

# --- 3. Rezervasyon İşlemleri ---

@user_bp.route('/reserve/<int:session_id>', methods=['POST'])
@login_required
def reserve(session_id):
    s = Session.query.filter_by(id=session_id, tenant_id=g.tenant.id).first_or_404()
    
    if s.completed or s.is_past:
        flash('Geçmiş/bitmiş seansa kayıt olunamaz.', 'error')
        return redirect(url_for('user.user_dashboard'))
    if s.spots_left <= 0:
        flash('Bu seans dolu.', 'error')
        return redirect(url_for('user.user_dashboard'))

    member = Member.query.filter(
        Member.tenant_id == g.tenant.id,
        func.lower(Member.full_name) == session['user_name'].lower()
    ).first()
    
    if not member or member.credits <= 0:
        flash('Seans hakkınız kalmamış.', 'error')
        return redirect(url_for('user.user_dashboard'))

    existing = Reservation.query.filter_by(user_name=session['user_name'], session_id=session_id, status='active').first()
    if existing:
        flash('Zaten bu seanstasınız.', 'info')
        return redirect(url_for('user.user_dashboard'))

    r = Reservation(tenant_id=g.tenant.id, user_name=session['user_name'], session_id=session_id, status='active')
    db.session.add(r)
    s.spots_left -= 1
    db.session.commit()
    flash('Kayıt oluşturuldu ✅', 'success')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    r = Reservation.query.filter_by(id=reservation_id, tenant_id=g.tenant.id).first_or_404()
    
    if r.user_name != session['user_name']:
        flash('Yetkisiz işlem.', 'error')
        return redirect(url_for('user.user_dashboard'))
        
    session_dt = datetime.combine(r.session.date, r.session.time)
    if session_dt - datetime.now() < timedelta(hours=24):
        flash('24 saatten az kaldığı için iptal edilemez. Hocanızla görüşün.', 'error')
        return redirect(url_for('user.user_dashboard'))

    r.status = 'canceled'
    r.session.spots_left += 1
    db.session.commit()
    flash('Rezervasyon iptal edildi.', 'success')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/cancel_request/<int:reservation_id>', methods=['POST'])
@login_required
def cancel_request(reservation_id):
    r = Reservation.query.filter_by(id=reservation_id, tenant_id=g.tenant.id).first_or_404()
    
    # 24 Saat Kontrolü
    session_dt = datetime.combine(r.session.date, r.session.time)
    time_left = session_dt - datetime.now()
    
    if time_left < timedelta(hours=24):
        flash('Seansa 24 saatten az kaldığı için iptal talebi oluşturulamaz.', 'error')
        return redirect(url_for('user.user_dashboard'))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Sebep belirtmelisiniz.', 'error')
        return redirect(url_for('user.user_dashboard'))
        
    r.cancel_reason = reason
    r.cancel_status = 'pending'
    db.session.commit()
    flash('İptal talebi gönderildi.', 'info')
    return redirect(url_for('user.user_dashboard'))

# --- 4. Saat Değiştirme ---
@user_bp.route('/move/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def move(reservation_id):
    r = Reservation.query.filter_by(id=reservation_id, tenant_id=g.tenant.id).first_or_404()
    
    if r.user_name != session['user_name'] or r.status != 'active':
        flash('İşlem yapılamadı.', 'error')
        return redirect(url_for('user.user_dashboard'))

    if request.method == 'POST':
        target_id = int(request.form.get('target_id'))
        target = Session.query.filter_by(id=target_id, tenant_id=g.tenant.id).first_or_404()
        
        if target.is_past:
            flash('Geçmiş seansa taşınamaz.', 'error')
            return redirect(url_for('user.move', reservation_id=reservation_id))
        if target.spots_left <= 0:
            flash('Hedef seans dolu.', 'error')
            return redirect(url_for('user.move', reservation_id=reservation_id))
            
        r.status = 'moved'
        r.session.spots_left += 1
        
        new_r = Reservation(tenant_id=g.tenant.id, user_name=r.user_name, session_id=target.id, status='active')
        db.session.add(new_r)
        target.spots_left -= 1
        db.session.commit()
        flash('Saat değiştirildi ✅', 'success')
        return redirect(url_for('user.user_dashboard'))

    candidates = Session.query.filter(
        Session.tenant_id == g.tenant.id,
        Session.date >= date.today(),
        Session.id != r.session_id,
        Session.spots_left > 0
    ).order_by(Session.date.asc(), Session.time.asc()).all()
    
    return render_template('move.html', reservation=r, candidates=candidates)

# --- 5. Takvim ve Liste ---
@user_bp.route('/sessions')
def list_sessions():
    upcoming = Session.query.filter(
        Session.tenant_id == g.tenant.id,
        Session.date >= date.today()
    ).order_by(Session.date.asc(), Session.time.asc()).all()
    return render_template('sessions.html', sessions=upcoming)

@user_bp.route('/calendar')
def calendar():
    qd = request.args.get("d")
    try:
        anchor = datetime.fromisoformat(qd) if qd else datetime.now()
    except:
        anchor = datetime.now()
        
    sessions = Session.query.filter_by(tenant_id=g.tenant.id).order_by(Session.date.asc(), Session.time.asc()).all()
    
    week_start, _ = week_bounds(anchor)
    mark_user_joined(sessions, session.get("user_name"))
    by_cell = defaultdict(list)
    for s in sessions:
        by_cell[(s.date.isoformat(), s.time.strftime('%H:%M'))].append(s)
        
    days = make_days(week_start)
    slots = time_range(start_h=8, end_h=22, step_min=60)
    prev_week = (week_start - timedelta(days=7)).date().isoformat()
    next_week = (week_start + timedelta(days=7)).date().isoformat()
    week_label = f"{week_start.strftime('%d.%m.%Y')} - {(week_start + timedelta(days=5)).strftime('%d.%m.%Y')}"
    role = 'admin' if session.get('is_admin') else 'member'
    
    return render_template("sessions_calendar.html", days=days, slots=slots, by_cell=by_cell, week_label=week_label, prev_week=prev_week, next_week=next_week, role=role)

@user_bp.route('/calendar/grid')
def calendar_grid():
    week_start_str = request.args.get('week_start')
    try:
        anchor = datetime.fromisoformat(week_start_str) if week_start_str else datetime.now()
    except:
        anchor = datetime.now()
        
    sessions = Session.query.filter_by(tenant_id=g.tenant.id).order_by(Session.date.asc(), Session.time.asc()).all()
    
    week_start, _ = week_bounds(anchor)
    mark_user_joined(sessions, session.get("user_name"))
    by_cell = defaultdict(list)
    for s in sessions:
        by_cell[(s.date.isoformat(), s.time.strftime('%H:%M'))].append(s)
    days = make_days(week_start)
    slots = time_range(start_h=8, end_h=22, step_min=60)
    role = 'admin' if session.get('is_admin') else 'member'
    
    return render_template('_calendar_grid.html', days=days, slots=slots, by_cell=by_cell, role=role)