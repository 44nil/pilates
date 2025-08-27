from app import app, db, Session
from datetime import date, datetime, timedelta

with app.app_context():
    # Bugün olan seanslar
    today_sessions = Session.query.filter(Session.date == date.today()).count()
    
    # Bu hafta olan seanslar
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())  # Pazartesi
    end_of_week = start_of_week + timedelta(days=6)  # Pazar
    week_sessions = Session.query.filter(Session.date >= start_of_week, 
                                        Session.date <= end_of_week).count()
    
    # Gelecek hafta olan seanslar
    next_start = start_of_week + timedelta(days=7)
    next_end = next_start + timedelta(days=6)
    next_week_sessions = Session.query.filter(Session.date >= next_start, 
                                             Session.date <= next_end).count()
    
    # Tamamlanmış seanslar
    completed_sessions = Session.query.filter(Session.completed == True).count()
    
    # Tekrarlanan ve planlanmış seanslar
    planned_sessions = Session.query.filter(Session.is_recurring == True).count()
    
    print(f"Tüm Seanslar: {Session.query.count()}")
    print(f"Bugün olan seanslar: {today_sessions}")
    print(f"Bu hafta olan seanslar: {week_sessions}")
    print(f"Gelecek hafta olan seanslar: {next_week_sessions}")
    print(f"Tamamlanmış seanslar: {completed_sessions}")
    print(f"Planlanmış tekrarlı seanslar: {planned_sessions}")
