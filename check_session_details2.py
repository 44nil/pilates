from app import app, db, Session
from datetime import date, datetime, timedelta

with app.app_context():
    try:
        # Planlanmış tek sefere mahsus seanslar
        planned_sessions = Session.query.filter(
            Session.date >= date.today(),
            Session.is_recurring == False
        ).all()
        
        print(f"Planlanmış seans sayısı: {len(planned_sessions)}")
        for s in planned_sessions[:3]:  # İlk 3 tanesi
            print(f"- Tarih: {s.date}, Saat: {s.time}, Kapasite: {s.capacity}, Kalan: {s.spots_left}, Tamamlanmış: {s.completed}")
        
        # Haftalık seriler
        weekly_sessions = Session.query.filter(
            Session.date >= date.today(),
            Session.is_recurring == True
        ).all()
        
        print(f"\nHaftalık seri seans sayısı: {len(weekly_sessions)}")
        for s in weekly_sessions[:3]:  # İlk 3 tanesi
            print(f"- Tarih: {s.date}, Saat: {s.time}, Kapasite: {s.capacity}, Kalan: {s.spots_left}, Tamamlanmış: {s.completed}")
        
        # Tamamlanmış seanslar
        completed_sessions = Session.query.filter(
            Session.completed == True
        ).all()
        
        print(f"\nTamamlanmış seans sayısı: {len(completed_sessions)}")
        for s in completed_sessions[:3]:  # İlk 3 tanesi
            print(f"- Tarih: {s.date}, Saat: {s.time}, Kapasite: {s.capacity}, Kalan: {s.spots_left}, Tamamlanmış: {s.completed}")
            
    except Exception as e:
        print(f"Hata: {e}")
