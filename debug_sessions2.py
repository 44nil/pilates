from app import app, db, Session, Reservation, Member

with app.app_context():
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    
    planned = [s for s in sessions if not s.completed and not s.is_recurring]
    weekly_series = [s for s in sessions if not s.completed and s.is_recurring]
    completed = [s for s in sessions if s.completed]
    
    print(f"Tüm seanslar: {len(sessions)}")
    print(f"Planlandı (completed=False, is_recurring=False): {len(planned)}")
    print(f"Haftalık Seri (completed=False, is_recurring=True): {len(weekly_series)}")
    print(f"Tamamlandı (completed=True): {len(completed)}")
    
    # Daha detaylı inceleme:
    print("\nPlanlandı seansları:")
    for s in planned[:3]:
        print(f"- ID: {s.id}, Tarih: {s.date}, Saat: {s.time}")
        
    print("\nHaftalık seri seansları:")
    for s in weekly_series[:3]:
        print(f"- ID: {s.id}, Tarih: {s.date}, Saat: {s.time}")
        
    print("\nTamamlandı seansları:")
    for s in completed[:3]:
        print(f"- ID: {s.id}, Tarih: {s.date}, Saat: {s.time}")
