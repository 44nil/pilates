import os
from flask import Flask, session, g
from app.extensions import db, migrate, csrf

def create_app():
    app = Flask(__name__)
    
    # Konfigürasyon
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-gizli-anahtar')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///pilates.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Eklentileri başlat
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Context Processor ve Hook'lar
    from app.utils import close_past_sessions_logic
    
    @app.before_request
    def before_request_hooks():
        g.member_name = session.get('member_name')
        close_past_sessions_logic()

    # Blueprint'leri Kaydet
    from app.routes.auth_routes import auth_bp
    from app.routes.user_routes import user_bp
    from app.routes.admin_routes import admin_bp
    # from app.routes.calendar_routes import calendar_bp (eğer oluşturduysan)
    
    # Mevcut blueprintlerin (bunları routes klasörüne taşıman iyi olur ama şimdilik import edelim)
    # from app.routes.completed_sessions import completed_sessions_bp
    # app.register_blueprint(completed_sessions_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)

    return app