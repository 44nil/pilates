from app import app, db, Session
from datetime import datetime

with app.app_context():
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    
    # Kategorileri oluştur
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
        },
        {
            'name': 'Tamamlandı',
            'icon': '✓',
            'bg': 'green-100',
            'color': 'green-800',
            'items': [s for s in sessions if s.completed]
        }
    ]
    
    # Kategorileri yazdır
    print(f"Tüm seanslar: {len(sessions)}")
    
    for cat in categories:
        print(f"\n{cat['name']} ({len(cat['items'])} seans):")
        for s in cat['items'][:5]:  # İlk 5 seansı göster
            print(f"- ID: {s.id}, Tarih: {s.date}, Saat: {s.time}, Tamamlandı: {s.completed}, Recurring: {s.is_recurring}")
