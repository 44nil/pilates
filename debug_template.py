from app import app, db, Session, Member
from flask import render_template
from datetime import datetime

with app.app_context():
    # Veritabanındaki tüm seansları al
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
    
    try:
        # Şablonu test et
        rendered = render_template('admin_sessions.html', sessions=sessions, members=members, categories=categories)
        print("Şablon başarıyla render edildi!")
        print(f"Şablon uzunluğu: {len(rendered)} karakter")
        
        # Kategorileri kontrol et
        for idx, cat in enumerate(categories):
            print(f"{cat['name']}: {len(cat['items'])} seans")
            
    except Exception as e:
        import traceback
        print(f"HATA: {e}")
        traceback.print_exc()
