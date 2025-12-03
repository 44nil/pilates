from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy import func
from app.models import Member

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def home():
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))
    if 'user_name' in session:
        return redirect(url_for('user.user_dashboard'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form.get('user_name', '').strip()
        if not name:
            flash('Lütfen ad–soyad girin.', 'error')
            return redirect(url_for('auth.login'))

        canon = Member.canonical(name)
        member = Member.query.filter(func.lower(Member.full_name) == canon.lower()).first()
        if not member:
            flash('Üyeler listesinde bulunmuyorsunuz.', 'error')
            return redirect(url_for('auth.login'))

        session['user_name'] = member.full_name
        session['member_name'] = member.full_name
        flash(f'Hoş geldin, {member.full_name}!', 'success')
        return redirect(url_for('user.user_dashboard'))
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Çıkış yapıldı.', 'info')
    return redirect(url_for('auth.login'))