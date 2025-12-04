from flask import Blueprint, request, render_template, redirect, url_for, abort
from datetime import datetime
import traceback
from sqlalchemy import func  # Eğer func kullanıyorsan

from app.models import db, Member, Measurement
from app.decorators import admin_required

admin_measurements_bp = Blueprint(
    "admin_measurements",
    __name__,
    url_prefix="/admin",
)


@admin_measurements_bp.route('/delete-measurement', methods=['POST'])
@admin_required
def delete_measurement():
    mid = request.form.get("measurement_id", type=int)
    member_id = request.form.get("member_id", type=int)
    if not mid or not member_id:
        return "measurement_id and member_id required", 400
    m = Measurement.query.get(mid)
    if not m or m.member_id != member_id:
        abort(404)
    db.session.delete(m)
    db.session.commit()
    # AJAX ise güncel tablo partial'ını döndür
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        items = (
            Measurement.query
            .filter_by(member_id=member_id)
            .order_by(Measurement.date.desc())
            .all()
        )
        return render_template(
            "partials/_measurement_table.html",
            items=items,
            member_id=member_id,
            show_delete=True,
        )
    return redirect(url_for("admin_dashboard"))


@admin_measurements_bp.route('/add-measurement', methods=['GET', 'POST'])
@admin_required
def add_measurement():
    try:
        if request.method == 'POST':
            print("Form Data:", request.form)
            member_id = request.form.get('member_id', type=int)
            date_str = request.form.get('date')
            date_val = (
                datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_str
                else None
            )
            weight = request.form.get('weight', type=float)
            waist = request.form.get('waist', type=float)
            hip = request.form.get('hip', type=float)
            chest = request.form.get('chest', type=float)

            if not member_id:
                return "member_id required", 400

            m = Measurement(
                member_id=member_id,
                date=date_val,
                weight=weight,
                waist=waist,
                hip=hip,
                chest=chest,
            )
            db.session.add(m)
            db.session.commit()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                items = (
                    Measurement.query
                    .filter_by(member_id=member_id)
                    .order_by(Measurement.date.desc())
                    .all()
                )
                return render_template(
                    "partials/_measurement_table.html",
                    items=items,
                    show_delete=True,
                )

            return redirect(url_for("admin_dashboard"))

        # GET
        member_id = request.args.get("member_id", type=int)
        return render_template("partials/_measurement_form.html", member_id=member_id)

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()
        return f"Error: {e}", 500


# Ölçüm listeleme (admin)
@admin_measurements_bp.route('/measurement-list', methods=['GET'])
@admin_required
def admin_measurement_list():
    members = Member.query.order_by(Member.full_name.asc()).all()
    member_id = request.args.get('member_id', type=int)
    measurements = []
    selected_id = None
    if member_id:
        measurements = (
            Measurement.query
            .filter_by(member_id=member_id)
            .order_by(Measurement.date.desc())
            .all()
        )
        selected_id = member_id
    return render_template(
        'admin_measurement_list.html',
        members=members,
        measurements=measurements,
        selected_id=selected_id,
    )
