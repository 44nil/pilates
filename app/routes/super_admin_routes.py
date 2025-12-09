from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Tenant

# BU SATIR EKSİK OLABİLİR 👇
super_admin_bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')

@super_admin_bp.route('/dashboard')
def dashboard():
    studios = Tenant.query.order_by(Tenant.created_at.desc()).all()
    total_studios = len(studios)
    active_studios = sum(1 for s in studios if s.is_active)
    
    return render_template('super_admin/dashboard.html', 
                         studios=studios, 
                         total=total_studios, 
                         active=active_studios)

@super_admin_bp.route('/add-studio', methods=['POST'])
def add_studio():
    name = request.form.get('name')
    prefix = request.form.get('domain_prefix')
    
    if name and prefix:
        existing = Tenant.query.filter((Tenant.name == name) | (Tenant.domain_prefix == prefix)).first()
        if existing:
            flash('Bu stüdyo adı veya prefix zaten kullanılıyor!', 'danger')
        else:
            try:
                new_studio = Tenant(name=name, domain_prefix=prefix)
                db.session.add(new_studio)
                db.session.commit()
                flash('Yeni stüdyo başarıyla oluşturuldu!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Hata: {str(e)}', 'danger')
            
    return redirect(url_for('super_admin.dashboard'))


@super_admin_bp.route('/delete-studio/<int:id>', methods=['POST'])
def delete_studio(id):
    # Silinecek stüdyoyu bul
    studio = Tenant.query.get_or_404(id)
    try:
        # Veritabanından sil
        db.session.delete(studio)
        db.session.commit()
        flash('Stüdyo başarıyla silindi.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Silinirken hata oluştu: {str(e)}', 'danger')
        
    return redirect(url_for('super_admin.dashboard'))