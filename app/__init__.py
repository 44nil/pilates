import os
from flask import Flask, session, g, abort, request
from app.extensions import db, migrate, csrf
from app.models import Tenant

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
    
    # URL'den stüdyoyu bul (URL DEDEKTİFİ)
    @app.url_value_preprocessor
    def pull_tenant_from_url(endpoint, values):
        g.tenant = None
        if values and 'tenant_prefix' in values:
            prefix = values.pop('tenant_prefix')
            # Stüdyoyu veritabanında ara
            tenant = Tenant.query.filter_by(domain_prefix=prefix).first()
            if not tenant:
                abort(404, description="Böyle bir stüdyo bulunamadı.")
            g.tenant = tenant

    @app.url_defaults
    def add_language_code(endpoint, values):
        if 'tenant_prefix' in values or not g.tenant:
            return
        if app.url_map.is_endpoint_expecting(endpoint, 'tenant_prefix'):
            values['tenant_prefix'] = g.tenant.domain_prefix

    @app.before_request
    def before_request_hooks():
        g.member_name = session.get('member_name')
        if g.tenant:
            close_past_sessions_logic()

    # Blueprint'leri Çağır
    from app.routes.auth_routes import auth_bp
    from app.routes.user_routes import user_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.super_admin_routes import super_admin_bp

    # Ana Sayfa Yönlendirmesi
    @app.route('/')
    def global_home():
        return """
        <div style="text-align:center; margin-top:50px; font-family:sans-serif;">
            <h1>🤸‍♀️ Pilates SaaS Platformu</h1>
            <p>Lütfen gitmek istediğiniz stüdyonun adresini giriniz.</p>
            <p>Örnek: <a href="/nil">/nil</a></p>
            <br>
            <a href="/super-admin/dashboard" style="color:red; font-weight:bold;">Süper Admin Girişi</a>
        </div>
        """

    # Blueprint'leri Kaydet (URL PREFIX İLE)
    app.register_blueprint(auth_bp, url_prefix='/<string:tenant_prefix>/auth')
    app.register_blueprint(user_bp, url_prefix='/<string:tenant_prefix>') 
    app.register_blueprint(admin_bp, url_prefix='/<string:tenant_prefix>/admin')
    app.register_blueprint(super_admin_bp)

    return app