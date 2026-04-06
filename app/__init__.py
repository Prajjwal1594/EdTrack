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
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="gevent")

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

    @app.errorhandler(404)
    def not_found_error(error):
        print(f"DEBUG: 404 ERROR at {request.path} | Headers: {dict(request.headers)}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Resource not found", "path": request.path}), 404
        return render_template('errors/404.html'), 404

    with app.app_context():
        db.create_all()

    return app
