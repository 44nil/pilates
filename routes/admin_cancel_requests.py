# routes/admin_cancel_requests.py

from flask import Blueprint, render_template, redirect, url_for, flash
from app.models import db, Session, Reservation
from app.decorators import admin_required

admin_cancel_requests_bp = Blueprint(
    "admin_cancel_requests",
    __name__,
    url_prefix="/admin",
)


@admin_cancel_requests_bp.route('/cancel-requests')
@admin_required
def admin_cancel_requests():
    pending = (
        Reservation.query
        .filter_by(cancel_status='pending')
        .join(Session)
        .order_by(Session.date.asc(), Session.time.asc())
        .all()
    )
    return render_template('admin_cancel_requests.html', pending=pending)


@admin_cancel_requests_bp.route('/cancel-requests/<int:rid>/approve', methods=['POST'])
@admin_required
def admin_cancel_approve(rid):
    r = Reservation.query.get_or_404(rid)
    if r.cancel_status != 'pending':
        flash('Talep durumu uygun değil.', 'error')
        return redirect(url_for('admin_cancel_requests'))

    # Rezervasyonu iptal et + yer aç
    if r.status == 'active':
        r.status = 'canceled'
        if not r.session.is_past and r.session.spots_left < r.session.capacity:
            r.session.spots_left += 1

    r.cancel_status = 'approved'
    db.session.commit()
    flash('İptal onaylandı.', 'success')
    return redirect(url_for('admin_cancel_requests'))


@admin_cancel_requests_bp.route('/cancel-requests/<int:rid>/reject', methods=['POST'])
@admin_required
def admin_cancel_reject(rid):
    r = Reservation.query.get_or_404(rid)
    if r.cancel_status != 'pending':
        flash('Talep durumu uygun değil.', 'error')
        return redirect(url_for('admin_cancel_requests'))

    r.cancel_status = 'rejected'
    db.session.commit()
    flash('İptal talebi reddedildi.', 'info')
    return redirect(url_for('admin_cancel_requests'))
