import sys
import traceback
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_socketio import SocketIO
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
socketio = SocketIO()

def create_app(config_class=Config):
    print("[STARTUP] Creating Flask app...", flush=True)
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)
    print(f"[STARTUP] DATABASE_URL set: {'DATABASE_URL' in app.config and bool(app.config.get('SQLALCHEMY_DATABASE_URI'))}", flush=True)
    print(f"[STARTUP] DB URI prefix: {app.config.get('SQLALCHEMY_DATABASE_URI', '')[:20]}...", flush=True)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'

    @socketio.on('connect')
    def on_connect():
        print(f"[WS] Client connected")

    @socketio.on('subscribe_student')
    def on_subscribe(data):
        from flask_socketio import join_room
        sid = data.get('student_id')
        if sid:
            join_room(f"student_{sid}")

    @socketio.on('subscribe_user')
    def on_subscribe_user(data):
        from flask_socketio import join_room
        uid = data.get('user_id')
        if uid:
            join_room(f"user_{uid}")

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    from app.student import bp as student_bp
    app.register_blueprint(student_bp, url_prefix='/student')

    from app.parent import bp as parent_bp
    app.register_blueprint(parent_bp, url_prefix='/parent')

    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')

    from app.exams import bp as exams_bp
    app.register_blueprint(exams_bp, url_prefix='/exams')

    from app.messages import bp as messages_bp
    app.register_blueprint(messages_bp, url_prefix='/messages')

    from app.fees import bp as fees_bp
    app.register_blueprint(fees_bp, url_prefix='/fees')

    from app.timetable import bp as timetable_bp
    app.register_blueprint(timetable_bp, url_prefix='/timetable')

    from app.ai import bp as ai_bp
    app.register_blueprint(ai_bp, url_prefix='/api/ai')

    # ── Multi-tenant: Super Admin blueprint ──────────────────────────────────
    from app.superadmin import bp as superadmin_bp
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')

    # ── Enterprise ERP Module Blueprints ─────────────────────────────────────
    from app.admissions import bp as admissions_bp
    app.register_blueprint(admissions_bp, url_prefix='/admissions')

    from app.infra import bp as infra_bp
    app.register_blueprint(infra_bp, url_prefix='/infra')

    from app.hr import bp as hr_bp
    app.register_blueprint(hr_bp, url_prefix='/hr')

    from app.finance import bp as finance_bp
    app.register_blueprint(finance_bp, url_prefix='/finance')

    @app.route('/health')
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.errorhandler(404)
    def not_found_error(error):
        print(f"DEBUG: 404 ERROR at {request.path} | Headers: {dict(request.headers)}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found", "path": request.path}), 404
        return render_template('errors/404.html'), 404

    with app.app_context():
        try:
            print("[STARTUP] Running db.create_all()...", flush=True)
            db.create_all()
            print("[STARTUP] db.create_all() completed successfully.", flush=True)
            
            from app.models import User
            if not User.query.first():
                print("[STARTUP] Database is completely empty. Running auto-seed...", flush=True)
                from seed import seed
                seed(app, auto=True)

            # CRITICAL: Dispose the engine so connections aren't shared across Gunicorn forks!
            db.engine.dispose()
        except Exception as e:
            print(f"[STARTUP] ERROR during db.create_all(): {e}", flush=True)
            traceback.print_exc()

    print("[STARTUP] App creation complete. Ready to serve requests.", flush=True)
    return app
