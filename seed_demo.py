import random
from datetime import date, datetime, timedelta, time as dtime
from app import create_app
from app.models import db, Member, Session, Reservation, Measurement

# Uygulamayı başlat
app = create_app()

def seed_data():
    with app.app_context():
        print("🌱 Veritabanı temizleniyor ve hazırlanıyor...")
        
        # Önce eski verileri temizleyelim (İstersen bu kısmı silebilirsin)
        db.drop_all()
        db.create_all()

        # --- 1. ÜYELER (Members) ---
        print("👤 Üyeler ekleniyor...")
        names = [
            "Zeynep Kaya", "Ayşe Yılmaz", "Mehmet Demir", "Ali Çelik", 
            "Fatma Şahin", "Mustafa Öztürk", "Emine Arslan", "Burak Doğan",
            "Selin Yıldız", "Canan Koç", "Derya Bulut", "Eren Kara",
            "Gamze Tekin", "Hakan Yavuz", "İrem Polat", "Kemal Sönmez",
            "Leyla Aksoy", "Mert Güler", "Nilüfer Çetin", "Ozan Baş"
        ]
        
        members = []
        for name in names:
            m = Member(full_name=name, credits=random.randint(0, 20))
            db.session.add(m)
            members.append(m)
        
        db.session.commit() # ID'leri almak için kaydet

        # --- 2. SEANSLAR (Sessions) - Son 3 ay ve Gelecek 1 ay ---
        print("📅 Seanslar oluşturuluyor...")
        sessions = []
        start_date = date.today() - timedelta(days=90) # 3 ay önce
        end_date = date.today() + timedelta(days=30)   # 1 ay sonra
        
        # Haftanın her günü, günde 3-4 seans
        curr = start_date
        while curr <= end_date:
            # Pazar günleri tatil olsun (Opsiyonel)
            if curr.weekday() != 6: 
                # Günde rastgele saatlerde 3 seans
                times = [dtime(9, 0), dtime(12, 0), dtime(18, 0), dtime(19, 30)]
                for t in times:
                    # Geçmiş seanslar tamamlandı, gelecekler açık
                    is_past = (curr < date.today()) or (curr == date.today() and t < datetime.now().time())
                    
                    s = Session(
                        date=curr,
                        time=t,
                        capacity=10,
                        spots_left=10, # Birazdan rezervasyonlarla düşecek
                        completed=is_past
                    )
                    db.session.add(s)
                    sessions.append(s)
            curr += timedelta(days=1)
        
        db.session.commit()

        # --- 3. REZERVASYONLAR (Reservations) ---
        print("🎟️ Rastgele rezervasyonlar yapılıyor...")
        
        # Zeynep Kaya (Bizim Demo Kullanıcımız olsun)
        demo_user = members[0] 
        
        for s in sessions:
            # Her seansa rastgele 0 ile 8 kişi kaydedelim
            participant_count = random.randint(0, 8)
            chosen_members = random.sample(members, participant_count)
            
            # Demo kullanıcımız (Zeynep) haftada 3-4 derse gelsin (Grafik güzel görünsün)
            if s.date.weekday() in [0, 2, 4] and s.time.hour == 18: # Pzt, Çar, Cum 18:00
                if demo_user not in chosen_members:
                    chosen_members.append(demo_user)

            for m in chosen_members:
                status = 'attended' if s.completed else 'active'
                
                # Bazen gelmemiş olsun (no_show)
                if s.completed and random.random() < 0.1:
                    status = 'canceled'

                r = Reservation(
                    user_name=m.full_name,
                    session_id=s.id,
                    status=status
                )
                db.session.add(r)
                s.spots_left -= 1
        
        db.session.commit()

        # --- 4. ÖLÇÜMLER (Measurements) - Demo Kullanıcı İçin ---
        print("📏 Vücut ölçümleri giriliyor...")
        
        # Zeynep için son 3 ayda 2 haftada bir ölçüm
        m_curr = start_date
        weight = 65.0
        waist = 75.0
        hip = 100.0
        
        while m_curr <= date.today():
            measurement = Measurement(
                member_id=demo_user.id,
                date=m_curr,
                weight=round(weight, 1),
                waist=round(waist, 1),
                hip=round(hip, 1),
                chest=90.0
            )
            db.session.add(measurement)
            
            # Zamanla zayıflasın (Grafik aşağı doğru insin diye)
            weight -= random.uniform(0.2, 0.5)
            waist -= random.uniform(0.1, 0.4)
            hip -= random.uniform(0.1, 0.3)
            
            m_curr += timedelta(days=14) # 2 haftada bir

        db.session.commit()
        
        print(f"✅ İŞLEM TAMAM! Demo Kullanıcısı: {demo_user.full_name}")
        print("🚀 Şimdi 'python run.py' diyip Zeynep Kaya ismiyle giriş yapabilirsin.")

if __name__ == '__main__':
    seed_data()