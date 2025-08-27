from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta
from sqlalchemy import func
from models import db, Session, Reservation, ALLOWED_STATUSES
from decorators import admin_required

completed_sessions_bp = Blueprint('completed_sessions_bp', __name__)

@completed_sessions_bp.route('/admin/completed-sessions')
@admin_required
def admin_completed_sessions():
    """Tamamlanmış seansları listeler ve filtreleme imkanı sunar"""
    # Filtre parametrelerini al
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Sorgulama
    query = Session.query.filter(Session.completed == True)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(Session.date >= date_from_obj)
        except ValueError:
            pass  # Geçersiz tarih formatı, filtreleme yapma
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(Session.date <= date_to_obj)
        except ValueError:
            pass  # Geçersiz tarih formatı, filtreleme yapma
    
    # Seansları tarihe göre sırala
    completed_sessions = query.order_by(Session.date.desc(), Session.time.desc()).all()
    
    # İstatistikler için hesaplamalar
    total_attendance = 0
    total_capacity = 0
    
    for session in completed_sessions:
        attendance_count = session.get_attendance_count() if hasattr(session, 'get_attendance_count') else 0
        total_attendance += attendance_count
        total_capacity += session.capacity
    
    # Doluluk oranı
    completion_rate = round((total_attendance / total_capacity * 100)) if total_capacity > 0 else 0
    
    return render_template(
        'admin_completed_sessions.html',
        completed_sessions=completed_sessions,
        total_attendance=total_attendance,
        completion_rate=completion_rate
    )

@completed_sessions_bp.route('/api/session/<int:session_id>/details', methods=['GET'])
@admin_required
def get_session_details(session_id):
    """Belirli bir seansın detaylı bilgilerini döndürür"""
    
    session = Session.query.get_or_404(session_id)
    
    # Seansa katılan üyeler
    reservations = Reservation.query.filter(
        Reservation.session_id == session_id
    ).all()
    
    attendees = []
    for res in reservations:
        attendees.append({
            'name': res.user_name,
            'status': res.status,
        })
    
    # Toplam katılım
    attendance_count = sum(1 for res in reservations if res.status == 'attended')
    
    # Doluluk oranı
    attendance_rate = round((attendance_count / session.capacity * 100)) if session.capacity > 0 else 0
    
    return jsonify({
        'date': session.date.strftime('%d.%m.%Y'),
        'time': session.time.strftime('%H:%M'),
        'capacity': session.capacity,
        'attendanceRate': attendance_rate,
        'notes': session.notes,
        'attendees': attendees,
    })

# Helper fonksiyon - Session nesnesine yardımcı metot eklemek için
def get_attendance_count(self):
    """Bir seansa katılan üyelerin sayısını döndürür"""
    return Reservation.query.filter(
        Reservation.session_id == self.id,
        Reservation.status == 'attended'
    ).count()

# Session sınıfına metodu ekle
Session.get_attendance_count = get_attendance_count

