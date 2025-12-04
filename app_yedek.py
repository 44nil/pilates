import os
import traceback

from datetime import date, datetime, time as dtime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session as flask_session, flash, g, abort, jsonify
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import and_, func
from dotenv import load_dotenv
from collections import defaultdict
from flask_migrate import Migrate

load_dotenv()

# =========================
# 2) UYGULAMA OLUŞTURMA ve AYARLAR
# =========================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///pilates.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = True

# CSRF korumasını başlat
csrf = CSRFProtect(app)

# Veritabanı modellerini ve bağlantısını ayarla
from app.models import db, Session, Reservation, Member, Attendance, Measurement, ALLOWED_STATUSES, ALLOWED_CANCEL
db.init_app(app)
migrate = Migrate(app, db)

# Blueprint'leri kaydet
from routes.completed_sessions import completed_sessions_bp
app.register_blueprint(completed_sessions_bp)

from routes.calendar_member import calendar_member_bp
app.register_blueprint(calendar_member_bp)

from services.activity import build_attendance_weeks
from app.decorators import login_required, admin_required

from routes.admin_cancel_requests import admin_cancel_requests_bp
app.register_blueprint(admin_cancel_requests_bp)

from routes.admin_measurements import admin_measurements_bp
app.register_blueprint(admin_measurements_bp)



# =========================
# 5) ROUTE'LAR
# =========================

# --- 5.1 Admin Ölçüm (Measurement) Rotaları ---




# --- 5.2 Yardımcı Fonksiyonlar (Takvim / Otomatik Rezervasyon) ---
 
def auto_reserve(session, member_ids):
    """Belirtilen üyeleri otomatik olarak seansa kaydet"""
    if not member_ids:
        return
    
    for member_id in member_ids:
        member = Member.query.get(member_id)
        if not member:
            continue
            
        # Üye için rezervasyon oluştur
        reservation = Reservation(
            session_id=session.id,
            user_name=member.full_name,
            status='active'
        )
        db.session.add(reservation)
        
        # Kalan yeri azalt
        if session.spots_left > 0:
            session.spots_left -= 1
    
    db.session.commit()


def week_bounds(anchor: datetime):
    """Anchor (bugün ya da ?d=) tarihine göre haftanın Pazartesi 00:00'ı ve bir hafta sonrası."""
    start = anchor - timedelta(days=anchor.weekday())
    start = datetime.combine(start.date(), dtime(0, 0))
    end = start + timedelta(days=7)
    return start, end


def make_days(week_start: datetime):
    """Pazartesi'den itibaren 7 gün listesi (datetime)."""
    return [week_start + timedelta(days=i) for i in range(7)]


def time_range(start_h=7, end_h=22, step_min=60):
    """Takvimde görünecek saat slotları (Time objeleri)."""
    cur = datetime.combine(datetime.today(), dtime(start_h, 0))
    end = datetime.combine(datetime.today(), dtime(end_h, 0))
    out = []
    while cur <= end:
        out.append(cur.time().replace(second=0, microsecond=0))
        cur += timedelta(minutes=step_min)
    return out

def mark_user_joined(sessions, member_name: str | None):
    """Kullanıcı bu derse katılmış mı işaretle (Reservation.user_name ile)."""
    for s in sessions:
        s.user_joined = False
    if not member_name:
        return sessions
    # Aktif rezervasyonları çek (status='active')
    joined = {
        r.session_id
        for r in Reservation.query
            .filter_by(user_name=member_name, status='active')
            .all()
    }
    for s in sessions:
        s.user_joined = (s.id in joined)
    return sessions
  

# --- 5.3 before_request Hook'ları ---


@app.before_request
def inject_member_name():
    # Üye adını bir yerde set ediyorsan (login, form vb.) session'a kaydet:
    # flask_session['member_name'] = "Eray"
    g.member_name = flask_session.get('member_name')  # yoksa None


# --- Otomatik Tamamlandı + kredi düşürme ---
@app.before_request
def close_past_sessions_and_apply_attendance():
    now = datetime.now()

    # Tamamlanmamış ve zamanı geçmiş seanslar
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
        return  # yapılacak iş yok

    for s in to_close:
        s.completed = True
        for r in s.reservations:
            if r.status == 'active':
                r.status = 'attended'
                # Üye kredisini 1 düş
                m = Member.query.filter(
                    func.lower(Member.full_name) == r.user_name.lower()
                ).first()
                if m and (m.credits or 0) > 0:
                    m.credits -= 1

    db.session.commit()



# --- 5.4 Auth (Giriş / Çıkış) Rotaları ---

# ——— Routes: Auth ———
@app.route('/')
def home():
    if flask_session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    if 'user_name' in flask_session:
        return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('user_name', '').strip()
        if not name:
            flash('Lütfen ad–soyad girin.', 'error')
            return redirect(url_for('login'))

        canon = Member.canonical(name)
        member = Member.query.filter(func.lower(Member.full_name) == canon.lower()).first()
        if not member:
            flash('Üyeler listesinde bulunmuyorsunuz. Lütfen hocayla iletişime geçin.', 'error')
            return redirect(url_for('login'))

        flask_session['user_name'] = member.full_name  # üyedeki standardize isim
        flask_session['member_name'] = member.full_name  # takvim için gerekli
        flash(f'Hoş geldin, {member.full_name}!', 'success')
        return redirect(url_for('user_dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    flask_session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('login'))


# --- 5.5 Kullanıcı (User) Rotaları ---


@app.route('/dashboard')
@login_required
def user_dashboard():
    name = flask_session['user_name']

    # aktif (gelecek) rezervasyonlar
    my_active = (
        Reservation.query
        .filter_by(user_name=name, status='active')
        .join(Session)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )
    
    # Rezervasyonları haftalara göre grupla
    from collections import defaultdict
    import calendar
    week_groups = defaultdict(list)
    today = date.today()
    current_week_index = 0
    for reservation in my_active:
        session = reservation.session
        week_start = session.date - timedelta(days=session.date.weekday())
        week_end = week_start + timedelta(days=6)
        week_label = f"{week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')}"
        week_groups[week_label].append(reservation)
    sorted_weeks = sorted(week_groups.keys(), key=lambda w: datetime.strptime(w.split(' - ')[0], '%d.%m.%Y'))
    grouped_reservations = []
    for idx, week in enumerate(sorted_weeks):
        week_start_dt = datetime.strptime(week.split(' - ')[0], '%d.%m.%Y').date()
        week_end_dt = datetime.strptime(week.split(' - ')[1], '%d.%m.%Y').date()
        is_current_week = week_start_dt <= today <= week_end_dt
        if is_current_week:
            current_week_index = idx
        # Reservation nesnelerini dict'e çevir
        reservations_dict = []
        for r in week_groups[week]:
            reservations_dict.append({
                "id": r.id,
                "session_day": r.session.date.strftime('%A'),
                "session_time": r.session.time.strftime('%H:%M'),
                "session_date": r.session.date.strftime('%d.%m.%Y'),
                "session_notes": r.session.notes,
                "cancel_status": r.cancel_status,
                "cancel_reason": getattr(r, 'cancel_reason', None)
            })
        grouped_reservations.append({"week": week, "reservations": reservations_dict, "is_current_week": is_current_week})

    # yaklaşan seanslar
    upcoming = (
        Session.query
        .filter(Session.date >= date.today())
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )

    # üye + kalan kredi
    member = Member.query.filter(func.lower(Member.full_name) == name.lower()).first()
    credits_left = member.credits if member else 0

    # bu ay attended sayısı
    first_day = date.today().replace(day=1)
    if first_day.month == 12:
        next_month = first_day.replace(year=first_day.year+1, month=1, day=1)
    else:
        next_month = first_day.replace(month=first_day.month+1, day=1)

    monthly_attended = (
        db.session.query(Reservation)
        .join(Session, Reservation.session_id == Session.id)
        .filter(
            Reservation.user_name == name,
            Reservation.status == 'attended',
            Session.date >= first_day,
            Session.date < next_month
        )
        .count()
    )


    # Kullanıcıya ait ölçümler
    measurements = []
    if member:
        measurements = (Measurement.query
            .filter_by(member_id=member.id)
            .order_by(Measurement.date.desc()).all())

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




@app.route('/sessions')
@login_required
def list_sessions():
    upcoming = (
        Session.query
        .filter(Session.date >= date.today())
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )
    return render_template('sessions.html', sessions=upcoming)

    
@app.route('/reserve/<int:session_id>', methods=['POST'])
@login_required
def reserve(session_id):
    s = Session.query.get_or_404(session_id)
    if s.completed or s.is_past:
        flash('Geçmiş/bitmiş seansa kayıt olunamaz.', 'error')
        return redirect(url_for('user_dashboard'))
    if s.spots_left <= 0:
        flash('Bu seans dolu.', 'error')
        return redirect(url_for('user_dashboard'))

    # Üye kredi kontrolü
    # Üye kredi kontrolü — import YOK
    member = Member.query.filter(
        func.lower(Member.full_name) == flask_session['user_name'].lower()
    ).first()
    if not member or member.credits <= 0:
        flash('Seans hakkınız kalmamış. Lütfen hocanızla iletişime geçin.', 'error')
        return redirect(url_for('user_dashboard'))


    existing = Reservation.query.filter_by(
        user_name=flask_session['user_name'], session_id=session_id, status='active'
    ).first()
    if existing:
        flash('Zaten bu seanstasınız.', 'info')
        return redirect(url_for('user_dashboard'))

    r = Reservation(user_name=flask_session['user_name'], session_id=session_id, status='active')
    db.session.add(r)
    s.spots_left -= 1
    db.session.commit()
    flash('Kayıt oluşturuldu ✅', 'success')
    return redirect(url_for('user_dashboard'))


@app.route('/cancel/<int:reservation_id>', methods=['POST'])
@login_required
def cancel(reservation_id):
    flash('İptal için sebep girerek talep göndermelisiniz.', 'warning')
    r = Reservation.query.get_or_404(reservation_id)
    if r.user_name != flask_session['user_name']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('user_dashboard'))
    if r.status != 'active':
        flash('Bu rezervasyon zaten aktif değil.', 'info')
        return redirect(url_for('user_dashboard'))
    # 24 saat kala kullanıcı iptali yasak
    session_dt = datetime.combine(r.session.date, r.session.time)
    if session_dt - datetime.now() < timedelta(hours=24):
        flash('Seans başlamaya 24 saatten az kaldığı için iptal kullanıcılara kapalı. Lütfen hocayla iletişime geçin.', 'error')
        return redirect(url_for('user_dashboard'))

    if r.session.is_past:
        flash('Geçmiş seans iptal edilemez.', 'error')
        return redirect(url_for('user_dashboard'))
    r.status = 'canceled'
    r.session.spots_left += 1
    db.session.commit()
    flash('Rezervasyon iptal edildi.', 'success')
    return redirect(url_for('user_dashboard'))

@app.route('/move/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def move(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)
    if r.user_name != flask_session['user_name'] or r.status != 'active':
        flash('İşlem yapılamadı.', 'error')
        return redirect(url_for('user_dashboard'))
    if request.method == 'POST':
        target_id = int(request.form.get('target_id'))
        target = Session.query.get_or_404(target_id)
        if target.is_past:
            flash('Geçmiş seansa taşınamaz.', 'error')
            return redirect(url_for('move', reservation_id=reservation_id))
        if target.spots_left <= 0:
            flash('Hedef seans dolu.', 'error')
            return redirect(url_for('move', reservation_id=reservation_id))
        # taşımayı yap
        r.status = 'moved'
        r.session.spots_left += 1
        new_r = Reservation(user_name=r.user_name, session_id=target.id, status='active')
        db.session.add(new_r)
        target.spots_left -= 1
        db.session.commit()
        flash('Saat değiştirildi ✅', 'success')
        return redirect(url_for('user_dashboard'))

    # GET -> uygun seansları listele (aynı gün veya hocanın belirlediği aralık kriteri istenirse genişletilebilir)
    candidates = (
        Session.query
        .filter(Session.date >= date.today())
        .filter(Session.id != r.session_id)
        .filter(Session.spots_left > 0)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )
    return render_template('move.html', reservation=r, candidates=candidates)

# --- 5.6 Admin Rezervasyon / İptal Rotaları ---


@app.route('/admin/reservations/<int:reservation_id>/cancel_refund', methods=['POST'])
@admin_required
def admin_cancel_reservation_refund(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)

    if r.status == 'canceled':
        flash('Rezervasyon zaten iptal.', 'info')
        return redirect(url_for('admin_participants', session_id=r.session_id))

    # iade mantığı
    m = Member.query.filter(func.lower(Member.full_name) == r.user_name.lower()).first()

    # seans tamamlanmış ve kullanıcı attended ise kredi zaten düşmüştür -> geri ver
    if r.status == 'attended' and m:
        m.credits += 1

    # seans tamamlanmadıysa ve rezervasyon aktifse boş yer iade et
    if r.status == 'active' and not r.session.completed:
        r.session.spots_left += 1

    r.status = 'canceled'
    db.session.commit()
    flash('Rezervasyon iptal edildi. (İade uygulandı)', 'success')
    return redirect(url_for('admin_participants', session_id=r.session_id))

# app.py
@app.route('/cancel_request/<int:reservation_id>', methods=['POST'])
@login_required
def cancel_request(reservation_id):
    r = Reservation.query.get_or_404(reservation_id)
    if r.user_name != flask_session['user_name']:
        flash('Bu işlem için yetkiniz yok.', 'error')
        return redirect(url_for('user_dashboard'))
    if r.status != 'active':
        flash('Bu rezervasyon aktif değil.', 'error')
        return redirect(url_for('user_dashboard'))
    start_dt = datetime.combine(r.session.date, r.session.time)
    if start_dt - datetime.now() < timedelta(hours=24):
        # 24 saatten az ise istek kabul edilmez
        flash('Seans saatine 24 saatten az kaldığı için uygulamadan iptal talebi oluşturamazsınız. Lütfen hocanızla iletişime geçin.', 'warning')
        return redirect(url_for('user_dashboard'))

    reason = (request.form.get('reason') or '').strip()
    if not reason:
        flash('Lütfen iptal sebebini yazın.', 'error')
        return redirect(url_for('user_dashboard'))

    r.cancel_reason = reason
    r.cancel_status = 'pending'
    db.session.commit()
    flash('İptal talebiniz alındı. Eğitmen onayı sonrası sonuçlanacak.', 'info')
    return redirect(url_for('user_dashboard'))




# --- 5.7 Admin Giriş ve Dashboard ---

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        pwd = request.form.get('password', '')
        if pwd == os.getenv('ADMIN_PASSWORD', 'admin'):
            flask_session['is_admin'] = True
            flash('Admin girişi başarılı.', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Hatalı şifre.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_sessions = Session.query.count()
    upcoming = Session.query.filter(Session.date >= date.today()).count()
    active_res = Reservation.query.filter_by(status='active').count()
    today = date.today()
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


# --- 5.9 Admin Seans Yönetimi ---


@app.route('/admin/sessions', methods=['GET', 'POST'])
@admin_required
def admin_sessions():
    from datetime import datetime, timedelta
    import uuid
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json
        data = request.get_json(silent=True) if is_ajax else request.form


        # Alanları oku ve logla
        import logging
        date_str = data.get('date')
        time_str = data.get('time')
        notes = data.get('notes', '')
        
        # Debug için form verilerini yazdır
        if not is_ajax and hasattr(request, 'form'):
            logging.warning(f"FORM DATA: {dict(request.form)}")
            if hasattr(request.form, 'getlist'):
                logging.warning(f"MEMBERS (getlist): {request.form.getlist('reserved_member_ids[]')}")
        try:
            capacity = int(data.get('capacity', 4))
            if capacity < 1:
                raise ValueError
        except Exception:
            return jsonify(ok=False, error='BAD_CAPACITY'), 400 if is_ajax else redirect(url_for('admin_sessions'))
        # Checkbox backend eşleşmesi: reserved_slot
        recurring = str(data.get('recurring', data.get('reserved_slot', 'false'))).lower() in ('true', '1', 'on')
        
        # Tekrarlama deseni için hem repeat_weeks hem de repeat_pattern'i kontrol et
        repeat_weeks = int(data.get('repeat_weeks', 12))  # Varsayılan 12 hafta
        repeat_pattern = data.get('repeat_pattern')
        if repeat_pattern:
            if repeat_pattern == 'weekly':
                repeat_weeks = 12  # Her hafta için 12 hafta
            elif repeat_pattern == 'biweekly':
                repeat_weeks = 24  # 2 haftada bir için 24 hafta (12 event)
            elif repeat_pattern == 'monthly':
                repeat_weeks = 48  # Aylık için ~48 hafta (12 ay)
        
        # Otomatik rezervasyon için member_ids
        # Form verisi için request.form.getlist kullan
        member_ids = []
        if is_ajax:
            # AJAX için JSON verilerinden al
            member_ids = data.get('member_ids') or data.get('reserved_member_ids') or []
        else:
            # Normal form submit için request.form.getlist kullan
            member_ids = request.form.getlist('reserved_member_ids[]')
            if not member_ids:
                member_ids = request.form.getlist('member_ids[]')
                
        # String veya liste dönüşümü
        if isinstance(member_ids, str):
            member_ids = [int(x) for x in member_ids.split(',') if x.strip().isdigit()]
        elif isinstance(member_ids, list):
            member_ids = [int(x) for x in member_ids if str(x).isdigit()]
            
        logging.warning(f"PROCESSED MEMBER IDS: {member_ids}")

        logging.warning(f"ADMIN SESSION POST: date={date_str}, time={time_str}, capacity={capacity}, notes={notes}, recurring={recurring}, repeat_weeks={repeat_weeks}, member_ids={member_ids}")

        # Tarih formatını ISO'ya çevir
        if date_str and '.' in date_str:
            # gg.mm.yyyy formatı ise
            parts = date_str.split('.')
            if len(parts) == 3:
                date_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
        if not date_str or not time_str:
            return jsonify(ok=False, error='BAD_PAYLOAD'), 400 if is_ajax else redirect(url_for('admin_sessions'))
        try:
            base_dt = datetime.fromisoformat(f"{date_str}T{time_str}")
        except Exception:
            return jsonify(ok=False, error='BAD_DATETIME'), 400 if is_ajax else redirect(url_for('admin_sessions'))

        created = 0
        group_id = None
        if recurring:
            group_id = str(uuid.uuid4())
            new_sessions = []
            for i in range(repeat_weeks):
                dt = base_dt + timedelta(weeks=i)
                exists = Session.query.filter_by(date=dt.date(), time=dt.time()).first()
                if exists:
                    continue
                s = Session(date=dt.date(), time=dt.time(), capacity=capacity, spots_left=capacity, notes=notes, is_recurring=True, recur_group_id=group_id)
                db.session.add(s)
                db.session.flush()
                new_sessions.append(s)
                created += 1
            db.session.commit()
            # Otomatik rezervasyon
            for s in new_sessions:
                if member_ids:
                    auto_reserve(s, member_ids)
            if is_ajax:
                return jsonify(ok=True, mode='recurring', count=created, group_id=group_id), 201
            else:
                flash(f'{created} haftalık seans eklendi.', 'success')
                return redirect(url_for('admin_sessions'))
        else:
            exists = Session.query.filter_by(date=base_dt.date(), time=base_dt.time()).first()
            if exists:
                return jsonify(ok=False, error='DUPLICATE'), 400 if is_ajax else redirect(url_for('admin_sessions'))
            s = Session(date=base_dt.date(), time=base_dt.time(), capacity=capacity, spots_left=capacity, notes=notes)
            db.session.add(s)
            db.session.commit()
            # Otomatik rezervasyon
            if member_ids:
                auto_reserve(s, member_ids)
            if is_ajax:
                return jsonify(ok=True, mode='single', id=s.id), 201
            else:
                flash('Seans eklendi.', 'success')
                return redirect(url_for('admin_sessions'))
    # GET: sadece listeleri ver
    members = Member.query.order_by(Member.full_name.asc()).all()
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    
    # Hata ayıklama için konsola bilgi yazdır
    print(f"[DEBUG] admin_sessions route: Toplam {len(sessions)} seans bulundu")
    
    # Seans niteliklerini kontrol et
    if sessions:
        print(f"[DEBUG] İlk seans: ID={sessions[0].id}")
        print(f"[DEBUG] completed: {sessions[0].completed}")
        print(f"[DEBUG] is_recurring: {sessions[0].is_recurring}")
    
    # Seansları kategorilere ayır - Tamamlanan seanslar ayrı sayfaya taşındı
    categories = [
        {
            'name': 'Planlandı',
            'icon': '📅',
            'bg': 'yellow-100',
            'color': 'yellow-800',
            'items': [s for s in sessions if not s.completed and not s.is_recurring]
        },
        {
            'name': 'Haftalık Seri',
            'icon': '🔄',
            'bg': 'blue-100',
            'color': 'blue-800',
            'items': [s for s in sessions if not s.completed and s.is_recurring]
        }
    ]
    
    # Kategorilerin içeriklerini kontrol et
    for cat in categories:
        print(f"[DEBUG] {cat['name']}: {len(cat['items'])} seans")
    
    # Template context'ini yazdır
    print(f"[DEBUG] Template context: sessions={len(sessions)}, members={len(members)}, categories={len(categories)}")
    
    return render_template('admin_sessions_simplified.html', sessions=sessions, members=members, categories=categories)



@app.route('/admin/sessions/<int:session_id>/delete', methods=['POST'])
@admin_required
def admin_delete_session(session_id):
    s = Session.query.get_or_404(session_id)
    if s.is_past:
        flash('Geçmiş seans silinemez.', 'error')
        return redirect(url_for('admin_sessions'))

    # --- Katılımcı kredilerini iade et ---
    for r in s.reservations:
        m = Member.query.filter(func.lower(Member.full_name) == r.user_name.lower()).first()
        if m:
            # Eğer attended olmuşsa kredi geri ver
            if r.status == 'attended':
                m.credits += 1
        # Önce rezervasyonları sil (NOT NULL constraint hatası almamak için)
        db.session.delete(r)
    
    db.session.commit()
    # --- buraya kadar ---

    # Sonra seans silinebilir
    db.session.delete(s)
    db.session.commit()
    flash('Seans silindi.', 'success')
    return redirect(url_for('admin_sessions'))


@app.route('/admin/sessions/<int:session_id>/participants')
@admin_required
def admin_participants(session_id):
    s = Session.query.get_or_404(session_id)
    parts = Reservation.query.filter_by(session_id=session_id).order_by(Reservation.created_at.asc()).all()
    return render_template('admin_participants.html', s=s, parts=parts)


# --- 5.10 Admin Üye Yönetimi ---


@app.route('/admin/members', methods=['GET', 'POST'])
@admin_required
def admin_members():
    if request.method == 'POST':
        name = request.form.get('full_name', '').strip()
        credits = int(request.form.get('credits', 0))
        if not name:
            flash('İsim boş olamaz.', 'error')
            return redirect(url_for('admin_members'))
        canon = Member.canonical(name)
        exists = Member.query.filter(func.lower(Member.full_name) == canon.lower()).first()
        if exists:
            flash('Bu isim zaten kayıtlı.', 'error')
            return redirect(url_for('admin_members'))
        m = Member(full_name=canon, credits=max(0, credits))
        db.session.add(m)
        db.session.commit()
        flash('Üye eklendi.', 'success')
        return redirect(url_for('admin_members'))

    members = Member.query.order_by(Member.full_name.asc()).all()
    return render_template('admin_members.html', members=members)

@app.route('/admin/members/<int:member_id>/delete', methods=['POST'])
@admin_required
def admin_members_delete(member_id):
    m = Member.query.get_or_404(member_id)

    # Önce üyeye ait tüm ölçümleri sil (foreign key constraint hatası önlemek için)
    Measurement.query.filter_by(member_id=member_id).delete()

    # Sonra üyeyi sil
    db.session.delete(m)
    db.session.commit()
    flash('Üye silindi.', 'success')
    return redirect(url_for('admin_members'))

@app.route('/admin/members/<int:member_id>/credits', methods=['POST'])
@admin_required
def admin_members_adjust_credits(member_id):
    m = Member.query.get_or_404(member_id)
    delta = int(request.form.get('delta', 0))
    m.credits = max(0, m.credits + delta)
    db.session.commit()
    flash('Seans hakkı güncellendi.', 'success')
    return redirect(url_for('admin_members'))

# =====================[ CALENDAR INTEGRATION - START ]=====================

# --- 5.11 Takvim (Calendar) Rotaları ---


# AJAX takvim grid endpoint
@app.route('/calendar/grid')
@login_required  # admin_required -> login_required değiştirildi (AJAX ile kullanılması için)
def calendar_grid():
    # CSRF koruması ekle
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not is_ajax and not flask_session.get('is_admin'):
        abort(403)  # Doğrudan URL erişiminde yine admin kontrolü
        
    week_start_str = request.args.get('week_start')
    try:
        anchor = datetime.fromisoformat(week_start_str) if week_start_str else datetime.now()
    except Exception:
        anchor = datetime.now()

    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    week_start, _ = week_bounds(anchor)
    _mark_user_joined(sessions, getattr(g, "member_name", None))
    by_cell = defaultdict(list)
    for s in sessions:
        day_key = s.date.isoformat()
        time_key = s.time.strftime('%H:%M')
        by_cell[(day_key, time_key)].append(s)
    days  = _make_days(week_start)
    slots = _time_range(start_h=8, end_h=21, step_min=60)
    
    # Kullanıcı rolünü belirle
    role = 'admin' if flask_session.get('is_admin') else 'member'
    
    return render_template('_calendar_grid.html', days=days, slots=slots, by_cell=by_cell, role=role)
def _make_days(week_start: datetime):
    """Pazartesi'den Cumartesi'ye kadar 6 günlük liste (datetime). Pazar hariç."""
    return [week_start + timedelta(days=i) for i in range(6)]

def _time_range(start_h=7, end_h=22, step_min=60):
    """Takvimde gösterilecek saat slotları (datetime.time)."""
    cur = datetime.combine(datetime.today(), dtime(start_h, 0))
    end = datetime.combine(datetime.today(), dtime(end_h, 0))
    out = []
    while cur <= end:
        out.append(cur.time().replace(second=0, microsecond=0))
        cur += timedelta(minutes=step_min)
    return out

def _mark_user_joined(sessions, member_name: str | None):
    """Aktif rezervasyonlara göre s.user_joined işaretle."""
    for s in sessions:
        s.user_joined = False
    if not member_name:
        return sessions
    joined_ids = {
        r.session_id
        for r in Reservation.query.filter_by(user_name=member_name, status='active').all()
    }
    for s in sessions:
        if s.id in joined_ids:
            s.user_joined = True
    return sessions

# Haftalık takvim route'u
@app.route("/sessions/calendar")
def sessions_calendar():
    # ?d=YYYY-MM-DD desteği (örn: /sessions/calendar?d=2025-08-11)
    qd = request.args.get("d")
    try:
        anchor = datetime.fromisoformat(qd) if qd else datetime.now()
    except Exception:
        anchor = datetime.now()

    # Tüm seansları getir
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    # Takvim gridini anchor ile başlat
    week_start, _ = week_bounds(anchor)

    _mark_user_joined(sessions, getattr(g, "member_name", None))

    # Hücre eşlemesi: aynı gün-saatte birden fazla seans olabilir
    by_cell = defaultdict(list)
    for s in sessions:
        # Template'de gün için d.date().isoformat() kullanılıyor
        # s.date zaten date objesi, doğrudan isoformat ile uyumlu
        day_key = s.date.isoformat()
        # Template'de saat için t.strftime('%H:%M') kullanılıyor
        time_key = s.time.strftime('%H:%M')
        by_cell[(day_key, time_key)].append(s)

    days  = _make_days(week_start)
    slots = _time_range(start_h=8, end_h=21, step_min=60)  # 1 saatlik slotlar, 08:00-21:00 arası

    # Template'e hazır stringler
    prev_week = (week_start - timedelta(days=7)).date().isoformat()
    next_week = (week_start + timedelta(days=7)).date().isoformat()
    week_label = f"{week_start.strftime('%d.%m.%Y')} - {(week_start + timedelta(days=5)).strftime('%d.%m.%Y')}"

    return render_template(
        "sessions_calendar.html",
        days=days,
        slots=slots,
        by_cell=by_cell,
        week_label=week_label,
        prev_week=prev_week,
        next_week=next_week,
        role='member' if 'user_name' in flask_session and not flask_session.get('is_admin') else 'admin' if 'is_admin' in flask_session else None,
    )

# (İsteğe bağlı) /sessions -> takvime yönlendir
# @app.route("/sessions")
# def sessions_redirect_to_calendar():
#     return redirect(url_for("sessions_calendar"))

# =====================[ CALENDAR INTEGRATION - END ]=====================

# --- 5.12 Admin API Rotaları ---

# Admin için seans detay API endpoint'i
@app.route('/api/session/<int:session_id>/details', methods=['GET'])
@admin_required
def get_session_details_api(session_id):
    """Admin için seans detaylarını döndürür"""
    session = Session.query.get_or_404(session_id)

    # Seansa katılan üyeler
    reservations = Reservation.query.filter(
        Reservation.session_id == session_id
    ).all()

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

    # Kalan yer hesapla
    remaining = session.capacity - len(reservations)

    # Tarih ve saati birleştir
    start_at = datetime.combine(session.date, session.time).isoformat()

    return jsonify({
        'start_at': start_at,
        'capacity': session.capacity,
        'remaining': remaining,
        'participants': participants,
        'notes': session.notes or ''
    })

## create_session_and_join importunu globalden kaldırdık
## admin_completed_sessions ve get_session_details importunu globalden kaldırdık


# --- 5.13 Kullanıcı Profil Rotası ---


@app.route('/profile')
@login_required
def profile():
    name = flask_session['user_name']
    member = Member.query.filter(func.lower(Member.full_name) == name.lower()).first()
    measurements = []
    weeks = []
    if member:
        measurements = (Measurement.query
            .filter_by(member_id=member.id)
            .order_by(Measurement.date.desc()).all())
        weeks = build_attendance_weeks(member.id)
    return render_template('profile.html', member=member, measurements=measurements, weeks=weeks)


# --- 5.14 Komut Satırı / Yardımcı Fonksiyonlar ---

if __name__ == '__main__':
    app.run(debug=True)

def create_weekly_series(start_at, capacity, notes, weeks=12):
    from uuid import uuid4
    created = 0
    group_id = str(uuid4())
    for i in range(weeks):
        dt = start_at + timedelta(days=7*i)
        exists = Session.query.filter_by(date=dt.date(), time=dt.time()).first()
        if exists:
            continue
        s = Session(
            date=dt.date(),
            time=dt.time(),
            capacity=capacity,
            spots_left=capacity,
            notes=notes,
            is_recurring=True,
            recur_group_id=group_id
        )
        db.session.add(s)
        db.session.flush()
        created += 1
    db.session.commit()
    return group_id, created

def auto_reserve(session, member_ids):
    for mid in member_ids or []:
        m = Member.query.get(mid)
        if m and session.spots_left > 0:
            db.session.add(Reservation(
                user_name=m.full_name,
                session_id=session.id,
                status='active'
            ))
            session.spots_left -= 1
    db.session.commit()


    #oldu mu yaw. 25.08.2024 .1.14 27.08 olll
    
