from app import app, db, Session, Member
from datetime import datetime
import json

with app.app_context():
    sessions = Session.query.order_by(Session.date.asc(), Session.time.asc()).all()
    members = Member.query.order_by(Member.full_name.asc()).all()
    
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
    
    # Basit HTML oluştur
    with open("debug_output.html", "w") as f:
        f.write("<html><head><title>Debug Seanslar</title></head><body>")
        f.write("<h1>Seans Kategorileri</h1>")
        
        for cat in categories:
            f.write(f"<h2>{cat['name']} ({len(cat['items'])} seans)</h2>")
            f.write("<ul>")
            for s in cat['items'][:10]:  # İlk 10 seansı göster
                f.write(f"<li>ID: {s.id}, Tarih: {s.date}, Saat: {s.time}</li>")
            f.write("</ul>")
            
        f.write("</body></html>")
        
    print("Debug HTML oluşturuldu: debug_output.html")
