from app import app, db, Session
from datetime import date, datetime, timedelta

with app.app_context():
    # Toplam seans sayısı
    total_sessions = Session.query.count()
    print(f"Toplam seans sayısı: {total_sessions}")
    
    # Seansları türlerine göre ayırma
    planned_sessions = Session.query.filter(
        Session.date >= date.today(), 
        Session.is_recurring == False
    ).count()
    
    weekly_sessions = Session.query.filter(
        Session.date >= date.today(), 
        Session.is_recurring == True
    ).count()
    
    completed_sessions = Session.query.filter(
        Session.completed == True
    ).count()
    
    print(f"Planlanmış seanslar: {planned_sessions}")
    print(f"Haftalık seri seanslar: {weekly_sessions}")
    print(f"Tamamlanmış seanslar: {completed_sessions}")
