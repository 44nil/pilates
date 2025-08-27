from app import app, db, Session, Member

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
    
    # Kategorileri yazdır
    print(f"Tüm seanslar: {len(sessions)}")
    
    for cat in categories:
        print(f"\n{cat['name']} ({len(cat['items'])} seans):")
        for s in cat['items'][:3]:  # İlk 3 seansı göster
            print(f"- ID: {s.id}, Tarih: {s.date}, Saat: {s.time}, Tamamlandı: {s.completed}, Tekrarlı: {s.is_recurring}")
            
    # Seans niteliklerini kontrol et
    print("\nSeans nitelikleri kontrol:")
    if sessions:
        s = sessions[0]
        print(f"İlk seans: ID={s.id}")
        print(f"Nitelikler: {dir(s)}")
        print(f"completed niteliği var mı? {'completed' in dir(s)}")
        print(f"completed değeri: {getattr(s, 'completed', 'YOK')}")
        print(f"is_recurring niteliği var mı? {'is_recurring' in dir(s)}")
        print(f"is_recurring değeri: {getattr(s, 'is_recurring', 'YOK')}")
