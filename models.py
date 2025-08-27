from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, CheckConstraint
from datetime import date, datetime, time, timedelta
from sqlalchemy.orm import validates

db = SQLAlchemy()

ALLOWED_STATUSES = ('active', 'canceled', 'moved', 'attended', 'no_show')
ALLOWED_CANCEL = ('none', 'pending', 'approved', 'rejected')

class Measurement(db.Model):
    __tablename__ = "measurements"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    weight = db.Column(db.Float, nullable=False)  # kg
    waist = db.Column(db.Float)  # cm
    hip = db.Column(db.Float)  # cm
    chest = db.Column(db.Float)  # cm

class Session(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    spots_left = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.String(255))
    is_recurring = db.Column(db.Boolean, default=False, nullable=False)
    recur_group_id = db.Column(db.String(36), nullable=True)
    completed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_reserved = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint('capacity >= 0'),
        CheckConstraint('spots_left >= 0'),
        CheckConstraint('spots_left <= capacity'),
    )
    
    # Reservasyon ilişkisi
    reservations = db.relationship("Reservation", backref="session", lazy=True)
    
    @property
    def datetime(self):
        return datetime.combine(self.date, self.time)
    
    @property
    def is_past(self):
        now = datetime.now()
        session_datetime = datetime.combine(self.date, self.time)
        return session_datetime < now
    
    def __repr__(self):
        return f"<Session {self.date} {self.time} cap={self.capacity} left={self.spots_left}>"

class Reservation(db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(120), nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(Enum(*ALLOWED_STATUSES, name="reservation_status"), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    cancel_reason = db.Column(db.Text, nullable=True)
    cancel_status = db.Column(Enum(*ALLOWED_CANCEL, name="cancel_status"), default="none", nullable=False)
    
    @validates("user_name")
    def normalize_name(self, key, value):
        return value.strip()

class Member(db.Model):
    __tablename__ = "members"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, unique=True, index=True)
    credits = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    
    # İlişkiler
    measurements = db.relationship("Measurement", backref="member", lazy=True)
    
    @staticmethod
    def canonical(name: str) -> str:
        # trim + tek boşluk + title-case (İ/ı Türkçe başlıklama için özel durumları atlıyoruz)
        return " ".join(name.strip().split())

class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("members.id"), index=True, nullable=False)
    date = db.Column(db.Date, index=True, nullable=False)
    status = db.Column(db.String(20), default="attended", nullable=False)
