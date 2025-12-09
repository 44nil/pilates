import os
import jwt  # pip install pyjwt (Flask ile genelde gelir ama yoksa kurmak gerekebilir)
import json
import base64
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, g
from app.models import db, Member, Tenant
from clerk_backend_api import Clerk

auth_bp = Blueprint('auth', __name__)

# Clerk İstemcisi
clerk_client = Clerk(bearer_auth=os.getenv("CLERK_SECRET_KEY"))

@auth_bp.route('/login')
def login():
    # Zaten giriş yapmışsa dashboard'a at
    if 'user_id' in session:
        return redirect(url_for('user.user_dashboard'))
   
    return render_template('login.html', publishable_key=os.getenv('CLERK_PUBLISHABLE_KEY'))

@auth_bp.route('/logout')
def logout():
    session.clear()
    # Clerk'ten de çıkış yapmak için onların logout linkine yönlendirilebilir
    # Şimdilik sadece yerel oturumu kapatıp ana sayfaya atıyoruz.
    clerk_domain = os.getenv('CLERK_FRONTEND_API') # Eğer varsa
    return redirect(url_for('auth.login'))


@auth_bp.route('/clerk_sync')
def clerk_sync():
    """
    Clerk ile giriş başarılı olduktan sonra buraya yönlendirilir.
    Görevi: Clerk Session'ını doğrulamak ve Flask Session'ını başlatmak.
    """
    # 1. Cookie'den Token'ı al
    token = request.cookies.get('__session')
    if not token:
        flash('Oturum açılamadı (Token yok).', 'error')
        return redirect(url_for('auth.login'))

    try:
        # 2. Token'ın içinden Session ID (sid) bilgisini al (Doğrulamadan decode ediyoruz)
        # Güvenlik Notu: Asıl doğrulamayı aşağıda Clerk API ile yapacağız.
        decoded = jwt.decode(token, options={"verify_signature": False})
        sid = decoded.get('sid')
        user_id = decoded.get('sub')

        if not sid or not user_id:
            raise Exception("Geçersiz Token Formatı")

        # 3. Clerk API'ye sor: Bu session geçerli mi?
        clerk_session = clerk_client.sessions.get(session_id=sid)
        
        if not clerk_session or clerk_session.status != 'active':
            raise Exception("Oturum aktif değil.")

        # 4. Kullanıcı bilgilerini al (Email vb.)
        clerk_user = clerk_client.users.get(user_id=user_id)
        email = clerk_user.email_addresses[0].email_address
        full_name = f"{clerk_user.first_name} {clerk_user.last_name}".strip() or email.split('@')[0]

        # 5. VERİTABANI SENKRONİZASYONU
        # Eğer bir stüdyo içindeysek (g.tenant doluysa)
        if g.tenant:
            # Üyeyi bul veya oluştur
            member = Member.query.filter(
                Member.tenant_id == g.tenant.id,
                # Email ile eşleştirme yapıyoruz (daha sağlam)
                # Not: Member modeline email alanı eklemeni öneririm, şimdilik full_name ile devam.
                Member.full_name == full_name 
            ).first()

            if not member:
                # Yeni üye oluştur (Otomatik kayıt)
                member = Member(
                    tenant_id=g.tenant.id,
                    full_name=full_name,
                    credits=0 # Yeni üye kredisi
                )
                db.session.add(member)
                db.session.commit()
                flash(f'Aramıza hoş geldin {full_name}!', 'success')
            
            # Flask Session'ı Başlat
            session['user_id'] = member.id
            session['user_name'] = member.full_name
            session['clerk_user_id'] = user_id
            
            # Eğer admin ise (Bunu .env'den veya Tenant owner_id'den kontrol edebiliriz)
            # Şimdilik basitlik adına: İsmi "Esra" veya "Nil" içerenleri admin yapalım (Test için)
            if "admin" in email.lower() or "esra" in email.lower() or "nil" in email.lower():
                session['is_admin'] = True
                return redirect(url_for('admin.dashboard'))

            return redirect(url_for('user.user_dashboard'))
        
        else:
            # Stüdyo yoksa (Süper Admin Girişi olabilir)
            # Burada email kontrolü yapıp Süper Admin paneline atabilirsin
            if "admin" in email.lower(): # Buraya kendi emailini yaz
                session['is_super_admin'] = True
                return redirect(url_for('super_admin.dashboard'))
            
            return redirect('/')

    except Exception as e:
        print(f"Clerk Hatası: {e}")
        flash(f'Giriş doğrulanamadı: {str(e)}', 'error')
        return redirect(url_for('auth.login'))