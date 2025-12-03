import os
import uuid
import logging
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func, and_

# Modeller ve Eklentiler
from app.models import db, Session, Reservation, Member, Measurement
from app.decorators import admin_required
from app.utils import auto_reserve  # Utils'e taşıdığımız fonksiyon

# Blueprint Tanımı
# url_prefix='/admin' dediğimiz için rotaların başına otomatik /admin eklenir
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

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
    return redirect(url_for('auth.login')) # auth blueprint'indeki login'e yönlendir

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    total_sessions = Session.query.count()
    upcoming = Session.query.filter(Session.date >= date.today()).count()
    active_res = Reservation.query.filter_by(status='active').count()
    
    today = date.today()
    
    # Bugünün doluluk oranı
    today_fill = (
        db.session.query(func.sum(Session.capacity - Session.spots_left))
        .filter(Session.date == today)
        .scalar() or 0
    )
    today_cap = (
        db.session.query(func.sum(Session.capacity))
        .filter(Session.date == today)
        .scalar() or 0
    )
    
    pending_count = Reservation.query.filter_by(cancel_status='pending').count()
    members = Member.query.order_by(Member.full_name.asc()).all()
    
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

        # Kapasite kontrolü
        try:
            capacity = int(data.get('capacity', 4))
            if capacity < 1: raise ValueError
        except Exception:
            return jsonify(ok=False, error='BAD_CAPACITY'), 400 if is_ajax else redirect(url_for('admin.sessions'))

        # Tekrarlı seans ve diğer ayarlar
        recurring = str(data.get('recurring', data.get('reserved_slot', 'false'))).lower() in ('true', '1', 'on')
        
        repeat_weeks = int(data.get('repeat_weeks', 12))
        repeat_pattern = data.get('repeat_pattern')
        if repeat_pattern == 'weekly': repeat_weeks = 12
        elif repeat_pattern == 'biweekly': repeat_weeks = 24
        elif repeat_pattern == 'monthly': repeat_weeks = 48

        # Üye ID'lerini al
        member_ids = []
        if is_ajax:
            member_ids = data.get('member_ids') or data.get('reserved_member_ids') or []
        else:
            member_ids = request.form.getlist('reserved_member_ids[]') or request.form.getlist('member_ids[]')
            
        if isinstance(member_ids, str):
            member_ids = [int(x) for x in member_ids.split(',') if x.strip().isdigit()]
        elif isinstance(member_ids, list):
            member_ids = [int(x) for x in member_ids if str(x).isdigit()]

        # Tarih formatlama
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
                exists = Session.query.filter_by(date=dt.date(), time=dt.time()).first()
                if exists: continue
                
                s = Session(date=dt.date(), time=dt.time(), capacity=capacity, 
                            spots_left=capacity, notes=notes, is_recurring=True, recur_group_id=group_id)
                db.session.add(s)
                db.session.flush() # ID oluşsun diye flush
                new_sessions.append(s)
                created += 1
            
            db.session.commit()
            
            # Otomatik rezervasyon (Utils'den gelen fonksiyon)
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
            exists = Session.query.filter_by(date=base_dt.date(), time=base_dt.time()).first()
            if exists:
                return jsonify(ok=False, error='DUPLICATE'), 400 if is_ajax else redirect(url_for('admin.sessions'))
                
            s = Session(date=base_dt.date(), time=base_dt.time(), capacity=capacity, spots_left=capacity, notes=notes)
            db.session.add(s)
            db.session.commit()
            
            if member_ids:
                auto_reserve(s, member_ids)
                
            if is_ajax:
                return jsonify(ok=True, mode='single', id=s.id), 201
            else:
                flash('Seans eklendi.', 'success')
                return redirect(url_for('admin.sessions'))

    # GET İsteği: Listeleme
    members = Member.query.order_by(Member.full_name.asc()).all()
    all_sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    
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
    s = Session.query.get_or_404(session_id)
    if s.is_past:
        flash('Geçmiş seans silinemez.', 'error')
        return redirect(url_for('admin.sessions'))

    # Katılımcı kredilerini iade et
    for r in s.reservations:
        m = Member.query.filter(func.lower(Member.full_name) == r.user_name.lower()).first()
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
    s = Session.query.get_or_404(session_id)
    parts = Reservation.query.filter_by(session_id=session_id).order_by(Reservation.created_at.asc()).all()
    return render_template('admin_participants.html', s=s, parts=parts)

# --- BURAYA EKLENDİ ---
@admin_bp.route('/calendar')
@admin_required
def sessions_calendar():
    return render_template('admin_calendar.html')
# ----------------------



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
        exists = Member.query.filter(func.lower(Member.full_name) == canon.lower()).first()
        if exists:
            flash('Bu isim zaten kayıtlı.', 'error')
            return redirect(url_for('admin.members'))
            
        m = Member(full_name=canon, credits=max(0, credits))
        db.session.add(m)
        db.session.commit()
        flash('Üye eklendi.', 'success')
        return redirect(url_for('admin.members'))

    members_list = Member.query.order_by(Member.full_name.asc()).all()
    return render_template('admin_members.html', members=members_list)


@admin_bp.route('/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def delete_member(member_id):
    m = Member.query.get_or_404(member_id)
    # Önce üyeye ait ölçümleri sil
    Measurement.query.filter_by(member_id=member_id).delete()
    db.session.delete(m)
    db.session.commit()
    flash('Üye silindi.', 'success')
    return redirect(url_for('admin.members'))


@admin_bp.route('/members/<int:member_id>/credits', methods=['POST'])
@admin_required
def adjust_credits(member_id):
    m = Member.query.get_or_404(member_id)
    delta = int(request.form.get('delta', 0))
    m.credits = max(0, m.credits + delta)
    db.session.commit()
    flash('Seans hakkı güncellendi.', 'success')
    return redirect(url_for('admin.members'))


# --- 4. Rezervasyon Yönetimi (Admin Müdahalesi) ---

@admin_bp.route('/reservations/<int:reservation_id>/cancel_refund', methods=['POST'])
@admin_required
def cancel_reservation_refund(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)

    if r.status == 'canceled':
        flash('Rezervasyon zaten iptal.', 'info')
        return redirect(url_for('admin.session_participants', session_id=r.session_id))

    m = Member.query.filter(func.lower(Member.full_name) == r.user_name.lower()).first()

    # İade Mantığı
    if r.status == 'attended' and m:
        m.credits += 1

    if r.status == 'active' and not r.session.completed:
        r.session.spots_left += 1

    r.status = 'canceled'
    db.session.commit()
    flash('Rezervasyon iptal edildi (Varsa iade yapıldı).', 'success')
    return redirect(url_for('admin.session_participants', session_id=r.session_id))


# --- 5. API Endpointleri (AJAX için) ---

# Not: JavaScript tarafında URL artık /admin/api/session/... oldu.
# Eğer JS bozulursa JS dosyasındaki url'i güncellemek gerekir.
@admin_bp.route('/api/session/<int:session_id>/details', methods=['GET'])
@admin_required
def get_session_details_api(session_id):
    session_obj = Session.query.get_or_404(session_id)
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
    # Bekleyen iptal taleplerini getir
    pending_requests = Reservation.query.filter_by(cancel_status='pending').all()
    # admin_cancel_requests.html dosyasının templates klasöründe olduğundan emin ol
    return render_template('admin_cancel_requests.html', requests=pending_requests)

# --- 7. Geçmiş (Tamamlanan) Seanslar ---

# --- 7. Geçmiş (Tamamlanan) Seanslar ---

@admin_bp.route('/sessions/completed')
@admin_required
def completed_sessions():
    # Tamamlanmış seansları tarihe göre (yeniden eskiye) getir
    sessions = Session.query.filter_by(completed=True).order_by(Session.date.desc(), Session.time.desc()).all()
    # Template dosyası app/templates klasöründe olmalı
    return render_template('admin_completed_sessions.html', sessions=sessions)