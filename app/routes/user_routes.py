from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from datetime import date, datetime, timedelta
from sqlalchemy import func
from app.models import db, Member, Reservation, Session, Measurement
from app.decorators import login_required
from collections import defaultdict
# Utils'den takvim yardımcılarını çekiyoruz
from app.utils import week_bounds, make_days, time_range, mark_user_joined

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def user_dashboard():
    name = session['user_name']
    
    # Aktif rezervasyonlar
    my_active = (
        Reservation.query
        .filter_by(user_name=name, status='active')
        .join(Session)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )

    # Haftalık gruplama mantığı (özetlendi)
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
            res_list.append({
                "id": r.id,
                "session_day": r.session.date.strftime('%A'),
                "session_time": r.session.time.strftime('%H:%M'),
                "session_date": r.session.date.strftime('%d.%m.%Y'),
                "session_notes": r.session.notes,
                "cancel_status": r.cancel_status,
                "cancel_reason": getattr(r, 'cancel_reason', None)
            })
        grouped_reservations.append({"week": week, "reservations": res_list, "is_current_week": is_curr})

    # Diğer veriler
    upcoming = Session.query.filter(Session.date >= date.today()).order_by(Session.date.asc(), Session.time.asc()).all()
    member = Member.query.filter(func.lower(Member.full_name) == name.lower()).first()
    credits_left = member.credits if member else 0
    
    # Aylık katılım sayısı
    first_day = date.today().replace(day=1)
    next_month = (first_day.replace(day=28) + timedelta(days=4)).replace(day=1)
    
    monthly_attended = (
        db.session.query(Reservation)
        .join(Session)
        .filter(
            Reservation.user_name == name,
            Reservation.status == 'attended',
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
        my_active=my_active,
        grouped_reservations=grouped_reservations,
        current_week_index=current_week_index,
        upcoming=upcoming,
        credits_left=credits_left,
        monthly_attended=monthly_attended,
        measurements=measurements,
        member=member
    )

@user_bp.route('/reserve/<int:session_id>', methods=['POST'])
@login_required
def reserve(session_id):
    s = Session.query.get_or_404(session_id)
    if s.completed or s.is_past:
        flash('Geçmiş/bitmiş seansa kayıt olunamaz.', 'error')
        return redirect(url_for('user.user_dashboard'))
    
    if s.spots_left <= 0:
        flash('Bu seans dolu.', 'error')
        return redirect(url_for('user.user_dashboard'))

    member = Member.query.filter(func.lower(Member.full_name) == session['user_name'].lower()).first()
    if not member or member.credits <= 0:
        flash('Seans hakkınız kalmamış.', 'error')
        return redirect(url_for('user.user_dashboard'))

    existing = Reservation.query.filter_by(user_name=session['user_name'], session_id=session_id, status='active').first()
    if existing:
        flash('Zaten bu seanstasınız.', 'info')
        return redirect(url_for('user.user_dashboard'))

    r = Reservation(user_name=session['user_name'], session_id=session_id, status='active')
    db.session.add(r)
    s.spots_left -= 1
    db.session.commit()
    flash('Kayıt oluşturuldu ✅', 'success')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)
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
    r = Reservation.query.get_or_404(reservation_id)
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Sebep belirtmelisiniz.', 'error')
        return redirect(url_for('user.user_dashboard'))
        
    r.cancel_reason = reason
    r.cancel_status = 'pending'
    db.session.commit()
    flash('İptal talebi gönderildi.', 'info')
    return redirect(url_for('user.user_dashboard'))

@user_bp.route('/profile')
@login_required
def profile():
    # Profil kodu buraya...
    return render_template('profile.html', member=None, measurements=[])

# --- Listeleme Rotası (Login sayfasındaki 'Keşfet' butonu için) ---

@user_bp.route('/sessions')
def list_sessions():
    # Gelecek seansları getir
    upcoming = Session.query.filter(Session.date >= date.today()).order_by(Session.date.asc(), Session.time.asc()).all()
    return render_template('sessions.html', sessions=upcoming)

# --- 8. Takvim Entegrasyonu (Login gerektirmez veya Üye/Admin herkes görebilir) ---

@user_bp.route('/calendar')
def calendar():
    # ?d=2025-12-04 gibi tarih parametresi alabilir
    qd = request.args.get("d")
    try:
        anchor = datetime.fromisoformat(qd) if qd else datetime.now()
    except Exception:
        anchor = datetime.now()

    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    week_start, _ = week_bounds(anchor)
    
    # Kullanıcı giriş yapmışsa katıldığı dersleri işaretle
    mark_user_joined(sessions, session.get("user_name"))

    by_cell = defaultdict(list)
    for s in sessions:
        day_key = s.date.isoformat()
        time_key = s.time.strftime('%H:%M')
        by_cell[(day_key, time_key)].append(s)

    days = make_days(week_start)
    # Sabah 08:00 - Akşam 22:00 arası slotlar
    slots = time_range(start_h=8, end_h=22, step_min=60)

    prev_week = (week_start - timedelta(days=7)).date().isoformat()
    next_week = (week_start + timedelta(days=7)).date().isoformat()
    week_label = f"{week_start.strftime('%d.%m.%Y')} - {(week_start + timedelta(days=5)).strftime('%d.%m.%Y')}"
    
    # Rol kontrolü (Template'de admin butonlarını göstermek için)
    role = 'admin' if session.get('is_admin') else 'member'

    return render_template(
        "sessions_calendar.html",
        days=days,
        slots=slots,
        by_cell=by_cell,
        week_label=week_label,
        prev_week=prev_week,
        next_week=next_week,
        role=role
    )

@user_bp.route('/calendar/grid')
def calendar_grid():
    # AJAX ile takvimi yenilemek için
    week_start_str = request.args.get('week_start')
    try:
        anchor = datetime.fromisoformat(week_start_str) if week_start_str else datetime.now()
    except:
        anchor = datetime.now()

    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    week_start, _ = week_bounds(anchor)
    mark_user_joined(sessions, session.get("user_name"))
    
    by_cell = defaultdict(list)
    for s in sessions:
        by_cell[(s.date.isoformat(), s.time.strftime('%H:%M'))].append(s)
        
    days = make_days(week_start)
    slots = time_range(start_h=8, end_h=22, step_min=60)
    role = 'admin' if session.get('is_admin') else 'member'
    
    return render_template('_calendar_grid.html', days=days, slots=slots, by_cell=by_cell, role=role)

# --- 9. Saat Değiştirme (Move) ---

@user_bp.route('/move/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def move(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)
    
    # Güvenlik: Başkasının rezervasyonunu değiştiremesin
    if r.user_name != session['user_name'] or r.status != 'active':
        flash('İşlem yapılamadı.', 'error')
        return redirect(url_for('user.user_dashboard'))

    if request.method == 'POST':
        target_id = int(request.form.get('target_id'))
        target = Session.query.get_or_404(target_id)
        
        if target.is_past:
            flash('Geçmiş seansa taşınamaz.', 'error')
            return redirect(url_for('user.move', reservation_id=reservation_id))
        
        if target.spots_left <= 0:
            flash('Hedef seans dolu.', 'error')
            return redirect(url_for('user.move', reservation_id=reservation_id))
            
        # 1. Mevcut rezervasyonu 'moved' yap ve yerini boşalt
        r.status = 'moved'
        r.session.spots_left += 1
        
        # 2. Yeni seansa kayıt yap
        new_r = Reservation(user_name=r.user_name, session_id=target.id, status='active')
        db.session.add(new_r)
        
        target.spots_left -= 1
        db.session.commit()
        
        flash('Saat değiştirildi ✅', 'success')
        return redirect(url_for('user.user_dashboard'))

    # GET: Taşınabilecek uygun seansları listele
    candidates = (
        Session.query
        .filter(Session.date >= date.today())
        .filter(Session.id != r.session_id)
        .filter(Session.spots_left > 0)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )
    return render_template('move.html', reservation=r, candidates=candidates)