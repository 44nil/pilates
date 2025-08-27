@app.route('/create_empty_session_and_join', methods=['POST'])
@login_required
def create_empty_session_and_join():
    # Form verilerini al
    day_str = request.form.get('day')
    time_str = request.form.get('time')
    
    if not day_str or not time_str:
        flash('Geçersiz istek.', 'error')
        return redirect(url_for('sessions_calendar'))
    
    try:
        # Tarih ve saat alanlarını doğru formata çevir
        session_date = datetime.fromisoformat(day_str).date()
        session_time = datetime.strptime(time_str, '%H:%M').time()
        
        # Geçmiş tarih kontrolü
        now = datetime.now()
        session_datetime = datetime.combine(session_date, session_time)
        if session_datetime < now:
            flash('Geçmiş tarihte seans oluşturamazsınız.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Aynı gün ve saatte başka bir seans var mı kontrol et
        existing_session = Session.query.filter_by(date=session_date, time=session_time).first()
        if existing_session:
            flash('Bu gün ve saatte zaten bir seans mevcut.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Üye kredi kontrolü
        member = Member.query.filter(
            func.lower(Member.full_name) == flask_session['user_name'].lower()
        ).first()
        
        if not member or member.credits <= 0:
            flash('Seans hakkınız kalmamış. Lütfen hocanızla iletişime geçin.', 'error')
            return redirect(url_for('sessions_calendar'))
        
        # Yeni bir seans oluştur - varsayılan kapasite 5 kişilik
        new_session = Session(
            date=session_date,
            time=session_time,
            capacity=5,
            spots_left=4,  # Bir spot şimdiden rezerve edilmiş olacak
            notes=f"{flask_session['user_name']} tarafından oluşturuldu"
        )
        
        db.session.add(new_session)
        db.session.flush()  # Session ID almak için flush yap
        
        # Üye için rezervasyon oluştur
        reservation = Reservation(
            user_name=flask_session['user_name'], 
            session_id=new_session.id, 
            status='active'
        )
        db.session.add(reservation)
        
        # Üyenin kredisini azalt
        member.credits -= 1
        
        # Değişiklikleri kaydet
        db.session.commit()
        
        flash(f'{session_date.strftime("%d.%m.%Y")} tarihinde {time_str} saatinde yeni bir seans oluşturuldu ve kaydınız yapıldı ✅', 'success')
        return redirect(url_for('user_dashboard'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Bir hata oluştu: {str(e)}', 'error')
        return redirect(url_for('sessions_calendar'))
