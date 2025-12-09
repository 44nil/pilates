import os
import uuid
import logging
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g
from sqlalchemy import func, and_

# Modeller ve Eklentiler
from app.models import db, Session, Reservation, Member, Measurement, Tenant
from app.decorators import admin_required
from app.utils import auto_reserve

# Blueprint Tanımı
# Not: URL Prefix'i artık __init__.py içinde dinamik veriyoruz, burayı boş bırakıyoruz.
admin_bp = Blueprint('admin', __name__)

# --- 1. Admin Giriş ve Dashboard ---

@admin_bp.route('/', methods=['GET', 'POST'])
def login():
    # Eğer zaten giriş yapmışsa dashboard'a at
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        pwd = request.form.get('password', '')
        # .env dosyasındaki şifre veya varsayılan 'admin'
        if pwd == os.getenv('ADMIN_PASSWORD', 'admin'):
            session['is_admin'] = True
            flash('Admin girişi başarılı.', 'success')
            return redirect(url_for('admin.dashboard'))
        flash('Hatalı şifre.', 'error')
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Admin çıkışı yapıldı.', 'info')
    return redirect(url_for('auth.login'))

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Sadece BU stüdyonun verilerini say
    total_sessions = Session.query.filter_by(tenant_id=g.tenant.id).count()
    
    upcoming = Session.query.filter(
        Session.tenant_id == g.tenant.id,
        Session.date >= date.today()
    ).count()
    
    active_res = Reservation.query.filter(
        Reservation.tenant_id == g.tenant.id,
        Reservation.status == 'active'
    ).count()
    
    today = date.today()
    
    # Bugünün doluluk oranı (Sadece bu stüdyo için)
    today_fill = (
        db.session.query(func.sum(Session.capacity - Session.spots_left))
        .filter(Session.tenant_id == g.tenant.id, Session.date == today)
        .scalar() or 0
    )
    today_cap = (
        db.session.query(func.sum(Session.capacity))
        .filter(Session.tenant_id == g.tenant.id, Session.date == today)
        .scalar() or 0
    )
    
    pending_count = Reservation.query.filter(
        Reservation.tenant_id == g.tenant.id,
        Reservation.cancel_status == 'pending'
    ).count()
    
    members = Member.query.filter_by(tenant_id=g.tenant.id).order_by(Member.full_name.asc()).all()
    
    return render_template('admin_dashboard.html',
                           total_sessions=total_sessions,
                           upcoming=upcoming,
                           active_res=active_res,
                           today_fill=today_fill,
                           today_cap=today_cap,
                           pending_count=pending_count,
                           members=members)


# --- 2. Seans Yönetimi (Ekleme / Listeleme) ---

@admin_bp.route('/sessions', methods=['GET', 'POST'])
@admin_required
def sessions():
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        data = request.get_json(silent=True) if is_ajax else request.form

        date_str = data.get('date')
        time_str = data.get('time')
        notes = data.get('notes', '')

        try:
            capacity = int(data.get('capacity', 4))
            if capacity < 1: raise ValueError
        except Exception:
            return jsonify(ok=False, error='BAD_CAPACITY'), 400 if is_ajax else redirect(url_for('admin.sessions'))

        recurring = str(data.get('recurring', data.get('reserved_slot', 'false'))).lower() in ('true', '1', 'on')
        
        repeat_weeks = int(data.get('repeat_weeks', 12))
        repeat_pattern = data.get('repeat_pattern')
        if repeat_pattern == 'weekly': repeat_weeks = 12
        elif repeat_pattern == 'biweekly': repeat_weeks = 24
        elif repeat_pattern == 'monthly': repeat_weeks = 48

        member_ids = []
        if is_ajax:
            member_ids = data.get('member_ids') or data.get('reserved_member_ids') or []
        else:
            member_ids = request.form.getlist('reserved_member_ids[]') or request.form.getlist('member_ids[]')
            
        if isinstance(member_ids, str):
            member_ids = [int(x) for x in member_ids.split(',') if x.strip().isdigit()]
        elif isinstance(member_ids, list):
            member_ids = [int(x) for x in member_ids if str(x).isdigit()]

        if date_str and '.' in date_str:
            parts = date_str.split('.')
            if len(parts) == 3:
                date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
        
        if not date_str or not time_str:
            return jsonify(ok=False, error='BAD_PAYLOAD'), 400 if is_ajax else redirect(url_for('admin.sessions'))
            
        try:
            base_dt = datetime.fromisoformat(f"{date_str}T{time_str}")
        except Exception:
            return jsonify(ok=False, error='BAD_DATETIME'), 400 if is_ajax else redirect(url_for('admin.sessions'))

        created = 0
        group_id = None
        
        # --- Kayıt İşlemi ---
        if recurring:
            group_id = str(uuid.uuid4())
            new_sessions = []
            for i in range(repeat_weeks):
                dt = base_dt + timedelta(weeks=i)
                # Çakışma kontrolü (Sadece bu stüdyo için)
                exists = Session.query.filter_by(tenant_id=g.tenant.id, date=dt.date(), time=dt.time()).first()
                if exists: continue
                
                # YENİ: tenant_id=g.tenant.id EKLENDİ 👇
                s = Session(tenant_id=g.tenant.id, date=dt.date(), time=dt.time(), capacity=capacity, 
                            spots_left=capacity, notes=notes, is_recurring=True, recur_group_id=group_id)
                db.session.add(s)
                db.session.flush()
                new_sessions.append(s)
                created += 1
            
            db.session.commit()
            
            for s in new_sessions:
                if member_ids:
                    auto_reserve(s, member_ids)
                    
            if is_ajax:
                return jsonify(ok=True, mode='recurring', count=created, group_id=group_id), 201
            else:
                flash(f'{created} haftalık seans eklendi.', 'success')
                return redirect(url_for('admin.sessions'))
        else:
            # Tekil Seans
            exists = Session.query.filter_by(tenant_id=g.tenant.id, date=base_dt.date(), time=base_dt.time()).first()
            if exists:
                return jsonify(ok=False, error='DUPLICATE'), 400 if is_ajax else redirect(url_for('admin.sessions'))
            
            # YENİ: tenant_id=g.tenant.id EKLENDİ 👇
            s = Session(tenant_id=g.tenant.id, date=base_dt.date(), time=base_dt.time(), capacity=capacity, spots_left=capacity, notes=notes)
            db.session.add(s)
            db.session.commit()
            
            if member_ids:
                auto_reserve(s, member_ids)
                
            if is_ajax:
                return jsonify(ok=True, mode='single', id=s.id), 201
            else:
                flash('Seans eklendi.', 'success')
                return redirect(url_for('admin.sessions'))

    # GET İsteği: Listeleme (Sadece bu stüdyonun verileri)
    members = Member.query.filter_by(tenant_id=g.tenant.id).order_by(Member.full_name.asc()).all()
    all_sessions = Session.query.filter_by(tenant_id=g.tenant.id).order_by(Session.date.asc(), Session.time.asc()).all()
    
    categories = [
        {
            'name': 'Planlandı',
            'icon': '📅',
            'bg': 'yellow-100',
            'color': 'yellow-800',
            'items': [s for s in all_sessions if not s.completed and not s.is_recurring]
        },
        {
            'name': 'Haftalık Seri',
            'icon': '🔄',
            'bg': 'blue-100',
            'color': 'blue-800',
            'items': [s for s in all_sessions if not s.completed and s.is_recurring]
        }
    ]
    
    return render_template('admin_sessions_simplified.html', sessions=all_sessions, members=members, categories=categories)


@admin_bp.route('/sessions/<int:session_id>/delete', methods=['POST'])
@admin_required
def delete_session(session_id):
    # Başkasının seansını silmesin diye filter_by(tenant_id...) kullanıyoruz
    s = Session.query.filter_by(id=session_id, tenant_id=g.tenant.id).first_or_404()
    
    if s.is_past:
        flash('Geçmiş seans silinemez.', 'error')
        return redirect(url_for('admin.sessions'))

    for r in s.reservations:
        # Üyeyi bu stüdyoda ara
        m = Member.query.filter(Member.tenant_id == g.tenant.id, func.lower(Member.full_name) == r.user_name.lower()).first()
        if m and r.status == 'attended':
            m.credits += 1
        db.session.delete(r)
    
    db.session.delete(s)
    db.session.commit()
    flash('Seans silindi.', 'success')
    return redirect(url_for('admin.sessions'))


@admin_bp.route('/sessions/<int:session_id>/participants')
@admin_required
def session_participants(session_id):
    s = Session.query.filter_by(id=session_id, tenant_id=g.tenant.id).first_or_404()
    parts = Reservation.query.filter_by(session_id=session_id).order_by(Reservation.created_at.asc()).all()
    return render_template('admin_participants.html', s=s, parts=parts)


@admin_bp.route('/calendar')
@admin_required
def sessions_calendar():
    return render_template('admin_calendar.html')


# --- 3. Üye Yönetimi ---

@admin_bp.route('/members', methods=['GET', 'POST'])
@admin_required
def members():
    if request.method == 'POST':
        name = request.form.get('full_name', '').strip()
        credits = int(request.form.get('credits', 0))
        if not name:
            flash('İsim boş olamaz.', 'error')
            return redirect(url_for('admin.members'))
            
        canon = Member.canonical(name)
        
        # Sadece BU stüdyoda bu isim var mı diye bakıyoruz
        exists = Member.query.filter(
            Member.tenant_id == g.tenant.id,
            func.lower(Member.full_name) == canon.lower()
        ).first()
        
        if exists:
            flash('Bu isim bu stüdyoda zaten kayıtlı.', 'error')
            return redirect(url_for('admin.members'))
            
        # YENİ: tenant_id=g.tenant.id EKLENDİ 👇
        m = Member(tenant_id=g.tenant.id, full_name=canon, credits=max(0, credits))
        db.session.add(m)
        db.session.commit()
        flash('Üye eklendi.', 'success')
        return redirect(url_for('admin.members'))

    # Listelerken sadece bu stüdyonun üyeleri
    members_list = Member.query.filter_by(tenant_id=g.tenant.id).order_by(Member.full_name.asc()).all()
    return render_template('admin_members.html', members=members_list)


@admin_bp.route('/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def delete_member(member_id):
    m = Member.query.filter_by(id=member_id, tenant_id=g.tenant.id).first_or_404()
    
    Measurement.query.filter_by(member_id=member_id).delete()
    db.session.delete(m)
    db.session.commit()
    flash('Üye silindi.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/<int:member_id>/credits', methods=['POST'])
@admin_required
def adjust_credits(member_id):
    m = Member.query.filter_by(id=member_id, tenant_id=g.tenant.id).first_or_404()
    delta = int(request.form.get('delta', 0))
    m.credits = max(0, m.credits + delta)
    db.session.commit()
    flash('Seans hakkı güncellendi.', 'success')
    return redirect(url_for('admin.members'))


# --- 4. Rezervasyon Yönetimi (Admin Müdahalesi) ---

@admin_bp.route('/reservations/<int:reservation_id>/cancel_refund', methods=['POST'])
@admin_required
def cancel_reservation_refund(reservation_id):
    # Güvenlik için tenant kontrolü de yapılmalı ama reservation->session->tenant ilişkisinden gelir
    r = Reservation.query.get_or_404(reservation_id)
    if r.session.tenant_id != g.tenant.id:
        return "Yetkisiz işlem", 403

    if r.status == 'canceled':
        flash('Rezervasyon zaten iptal.', 'info')
        return redirect(url_for('admin.session_participants', session_id=r.session_id))

    m = Member.query.filter(Member.tenant_id == g.tenant.id, func.lower(Member.full_name) == r.user_name.lower()).first()

    if r.status == 'attended' and m:
        m.credits += 1

    if r.status == 'active' and not r.session.completed:
        r.session.spots_left += 1

    r.status = 'canceled'
    db.session.commit()
    flash('Rezervasyon iptal edildi (Varsa iade yapıldı).', 'success')
    return redirect(url_for('admin.session_participants', session_id=r.session_id))


# --- 5. API Endpointleri (AJAX için) ---

@admin_bp.route('/api/session/<int:session_id>/details', methods=['GET'])
@admin_required
def get_session_details_api(session_id):
    session_obj = Session.query.filter_by(id=session_id, tenant_id=g.tenant.id).first_or_404()
    reservations = Reservation.query.filter(Reservation.session_id == session_id).all()

    participants = []
    for res in reservations:
        status_text = {
            'active': 'Aktif',
            'canceled': 'İptal',
            'moved': 'Taşındı',
            'attended': 'Katıldı',
            'no_show': 'Gelmedi'
        }.get(res.status, res.status)
        participants.append(f"{res.user_name} ({status_text})")

    remaining = session_obj.capacity - len(reservations)
    start_at = datetime.combine(session_obj.date, session_obj.time).isoformat()

    return jsonify({
        'start_at': start_at,
        'capacity': session_obj.capacity,
        'remaining': remaining,
        'participants': participants,
        'notes': session_obj.notes or ''
    })

# --- 6. İptal İstekleri ve Diğerleri ---

@admin_bp.route('/cancel_requests')
@admin_required
def list_cancel_requests():
    pending_requests = Reservation.query.filter(
        Reservation.tenant_id == g.tenant.id,
        Reservation.cancel_status == 'pending'
    ).all()
    return render_template('admin_cancel_requests.html', requests=pending_requests)


@admin_bp.route('/sessions/completed')
@admin_required
def completed_sessions():
    sessions = Session.query.filter(
        Session.tenant_id == g.tenant.id,
        Session.completed == True
    ).order_by(Session.date.desc(), Session.time.desc()).all()
    return render_template('admin_completed_sessions.html', sessions=sessions)

# --- 8. Ölçüm (Measurement) İşlemleri ---

@admin_bp.route('/measurements/<int:member_id>', methods=['GET'])
@admin_required
def member_measurements(member_id):
    member = Member.query.filter_by(id=member_id, tenant_id=g.tenant.id).first_or_404()
    measurements = Measurement.query.filter_by(member_id=member_id).order_by(Measurement.date.desc()).all()
    return render_template('admin_measurement_list.html', member=member, measurements=measurements)

@admin_bp.route('/measurements/<int:member_id>/add', methods=['GET', 'POST'])
@admin_required
def add_measurement(member_id):
    member = Member.query.filter_by(id=member_id, tenant_id=g.tenant.id).first_or_404()
    
    if request.method == 'POST':
        try:
            def get_float(key):
                val = request.form.get(key)
                if not val or val.strip() == '': return 0.0
                return float(val)

            weight = get_float('weight')
            waist = get_float('waist')
            hip = get_float('hip')
            chest = get_float('chest')
            
            date_str = request.form.get('date')
            m_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

            new_m = Measurement(
                tenant_id=g.tenant.id, # YENİ: tenant_id EKLENDİ
                member_id=member.id,
                date=m_date,
                weight=weight,
                waist=waist,
                hip=hip,
                chest=chest
            )
            db.session.add(new_m)
            db.session.commit()
            
            flash('Ölçüm başarıyla eklendi. ✅', 'success')
            return redirect(url_for('admin.member_measurements', member_id=member.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Hata: {str(e)}', 'error')
            return render_template('admin_add_measurement.html', member=member), 400

    return render_template('admin_add_measurement.html', member=member)

@admin_bp.route('/measurements/delete/<int:measurement_id>', methods=['POST'])
@admin_required
def delete_measurement(measurement_id):
    # Sadece bu stüdyoya ait ölçümü sil (Güvenlik)
    measurement = Measurement.query.filter_by(id=measurement_id, tenant_id=g.tenant.id).first_or_404()
    member_id = measurement.member_id
    
    try:
        db.session.delete(measurement)
        db.session.commit()
        flash('Ölçüm silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Silme hatası: {str(e)}', 'error')
        
    return redirect(url_for('admin.member_measurements', member_id=member_id))

# --- 9. İptal Taleplerini Yönetme ---

@admin_bp.route('/cancel_requests/handle/<int:req_id>/<action>', methods=['POST'])
@admin_required
def handle_cancel_request(req_id, action):
    r = Reservation.query.filter_by(id=req_id, tenant_id=g.tenant.id).first_or_404()
    
    if action == 'approve':
        r.status = 'canceled'
        r.cancel_status = 'approved'
        r.session.spots_left += 1
        
        member = Member.query.filter(Member.tenant_id == g.tenant.id, func.lower(Member.full_name) == r.user_name.lower()).first()
        if member:
            member.credits += 1
            
        flash('İptal talebi onaylandı. Kredi iade edildi.', 'success')
        
    elif action == 'reject':
        r.cancel_status = 'rejected'
        flash('İptal talebi reddedildi.', 'warning')
        
    db.session.commit()
    return redirect(url_for('admin.list_cancel_requests'))