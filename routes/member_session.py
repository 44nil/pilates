from flask import request, redirect, url_for, flash, session as flask_session
from app import app, db, login_required, Session, Reservation, Member
from datetime import datetime
from sqlalchemy import func

@app.route('/create-session-and-join', methods=['POST'])
@login_required
def create_session_and_join():
    date_str = request.form.get('date')
    time_str = request.form.get('time')
    
    if not date_str or not time_str:
        flash('Tarih ve saat bilgisi gereklidir.', 'error')
        return redirect(url_for('sessions_calendar'))
    
    # Tarih ve saat kontrolü
    try:
        date_obj = datetime.fromisoformat(date_str).date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        session_datetime = datetime.combine(date_obj, time_obj)
        
        # Geçmiş tarih kontrolü
        if session_datetime < datetime.now():
            flash('Geçmiş tarihte seans oluşturamazsınız.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Üyenin yeterli kredisi var mı?
        member = Member.query.filter(
            func.lower(Member.full_name) == flask_session['user_name'].lower()
        ).first()
        
        if not member or member.credits <= 0:
            flash('Yeterli krediniz bulunmuyor.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Bu tarih ve saatte başka seans var mı?
        existing = Session.query.filter_by(date=date_obj, time=time_obj).first()
        if existing:
            flash('Bu tarih ve saatte zaten bir seans mevcut.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Yeni seans oluştur - kapasiteyi 5 kişilik yap
        new_session = Session(
            date=date_obj,
            time=time_obj,
            capacity=5,
            spots_left=4,  # 5 kişilik kapasite, 1 kişi (oluşturan) zaten katılmış olacak
            notes=f"{member.full_name} tarafından oluşturuldu"
        )
        
        db.session.add(new_session)
        db.session.flush()  # ID almak için
        
        # Kullanıcıyı seansa kaydet
        reservation = Reservation(
            user_name=flask_session['user_name'], 
            session_id=new_session.id, 
            status='active'
        )
        
        db.session.add(reservation)
        
        # Üye kredisinden düş
        member.credits -= 1
        
        db.session.commit()
        flash('Seans başarıyla oluşturuldu ve kaydoldunuz ✅', 'success')
        return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Seans oluşturulurken hata: {str(e)}', 'error')
        return redirect(url_for('sessions_calendar'))
