from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.superadmin import bp
from app.models import School, User, Class, Section, Subject, AcademicTerm, Student, Grade, Attendance
from app import db
from datetime import datetime
from sqlalchemy import func


# ── Guard decorator ──────────────────────────────────────────────────────────

def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Super-admin access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)


# ── Dashboard ────────────────────────────────────────────────────────────────

@bp.route('/dashboard')
@superadmin_required
def dashboard():
    schools = School.query.order_by(School.created_at.desc()).all()

    # Cross-school aggregate stats
    totals = {
        'schools': len(schools),
        'students': User.query.filter_by(role='student').count(),
        'teachers': User.query.filter_by(role='teacher').count(),
        'admins':   User.query.filter_by(role='admin').count(),
    }

    # Per-school summary cards
    school_summaries = []
    for s in schools:
        school_summaries.append({
            'school': s,
            'students': User.query.filter_by(school_id=s.id, role='student').count(),
            'teachers': User.query.filter_by(school_id=s.id, role='teacher').count(),
            'classes':  Class.query.filter_by(school_id=s.id).count(),
            'active_term': AcademicTerm.query.filter_by(school_id=s.id, is_active=True).first(),
        })

    # Recently registered users across all schools
    recent_users = (User.query
                    .filter(User.role != 'superadmin')
                    .order_by(User.created_at.desc())
                    .limit(10).all())

    return render_template('superadmin/dashboard.html',
                           totals=totals,
                           school_summaries=school_summaries,
                           recent_users=recent_users)


# ── School list ───────────────────────────────────────────────────────────────

@bp.route('/schools')
@superadmin_required
def schools():
    all_schools = School.query.order_by(School.name).all()
    summaries = []
    for s in all_schools:
        summaries.append({
            'school': s,
            'users':    User.query.filter_by(school_id=s.id).filter(User.role != 'superadmin').count(),
            'students': User.query.filter_by(school_id=s.id, role='student').count(),
            'teachers': User.query.filter_by(school_id=s.id, role='teacher').count(),
        })
    return render_template('superadmin/schools.html', summaries=summaries)


# ── Create school ─────────────────────────────────────────────────────────────

@bp.route('/schools/new', methods=['GET', 'POST'])
@superadmin_required
def new_school():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        if School.query.filter_by(code=code).first():
            flash(f'School code "{code}" is already in use.', 'danger')
            return redirect(url_for('superadmin.new_school'))

        school = School(
            name    = request.form.get('name', '').strip(),
            code    = code,
            address = request.form.get('address', '').strip(),
            phone   = request.form.get('phone', '').strip(),
            email   = request.form.get('email', '').strip().lower(),
        )
        db.session.add(school)
        db.session.flush()

        # Optionally create the first admin user for this school
        admin_email = request.form.get('admin_email', '').strip().lower()
        admin_name  = request.form.get('admin_name', '').strip()
        admin_pwd   = request.form.get('admin_password', 'ChangeMe123!')
        if admin_email and admin_name:
            if User.query.filter_by(email=admin_email).first():
                flash(f'Admin email "{admin_email}" already exists — school created without an admin user.', 'warning')
            else:
                admin_user = User(
                    name      = admin_name,
                    email     = admin_email,
                    role      = 'admin',
                    school_id = school.id,
                )
                admin_user.set_password(admin_pwd)
                db.session.add(admin_user)

        db.session.commit()
        flash(f'School "{school.name}" created successfully.', 'success')
        return redirect(url_for('superadmin.school_detail', school_id=school.id))

    return render_template('superadmin/school_form.html', school=None, action='create')


# ── School detail ──────────────────────────────────────────────────────────────

@bp.route('/schools/<int:school_id>')
@superadmin_required
def school_detail(school_id):
    school = School.query.get_or_404(school_id)

    stats = {
        'students': User.query.filter_by(school_id=school.id, role='student').count(),
        'teachers': User.query.filter_by(school_id=school.id, role='teacher').count(),
        'parents':  User.query.filter_by(school_id=school.id, role='parent').count(),
        'admins':   User.query.filter_by(school_id=school.id, role='admin').count(),
        'classes':  Class.query.filter_by(school_id=school.id).count(),
        'subjects': Subject.query.filter_by(school_id=school.id).count(),
    }

    terms   = AcademicTerm.query.filter_by(school_id=school.id).order_by(AcademicTerm.start_date.desc()).all()
    admins  = User.query.filter_by(school_id=school.id, role='admin').all()
    recent  = (User.query.filter_by(school_id=school.id)
               .filter(User.role != 'superadmin')
               .order_by(User.created_at.desc()).limit(8).all())

    # Grade distribution for this school
    grade_dist = (db.session.query(Grade.score)
                  .join(Student, Grade.student_id == Student.id)
                  .join(User, Student.user_id == User.id)
                  .filter(User.school_id == school.id)
                  .all())
    buckets = {'A+ (90-100)': 0, 'A (80-89)': 0, 'B+ (70-79)': 0,
               'B (60-69)': 0, 'C (50-59)': 0, 'Below 50': 0}
    for (score,) in grade_dist:
        if score >= 90:   buckets['A+ (90-100)'] += 1
        elif score >= 80: buckets['A (80-89)'] += 1
        elif score >= 70: buckets['B+ (70-79)'] += 1
        elif score >= 60: buckets['B (60-69)'] += 1
        elif score >= 50: buckets['C (50-59)'] += 1
        else:             buckets['Below 50'] += 1

    return render_template('superadmin/school_detail.html',
                           school=school, stats=stats, terms=terms,
                           admins=admins, recent_users=recent,
                           grade_dist=buckets)


# ── Edit school ────────────────────────────────────────────────────────────────

@bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@superadmin_required
def edit_school(school_id):
    school = School.query.get_or_404(school_id)
    if request.method == 'POST':
        new_code = request.form.get('code', '').strip().upper()
        existing = School.query.filter_by(code=new_code).first()
        if existing and existing.id != school.id:
            flash(f'School code "{new_code}" is already taken.', 'danger')
            return redirect(url_for('superadmin.edit_school', school_id=school.id))

        school.name    = request.form.get('name', school.name).strip()
        school.code    = new_code
        school.address = request.form.get('address', school.address).strip()
        school.phone   = request.form.get('phone', school.phone).strip()
        school.email   = request.form.get('email', school.email).strip().lower()
        db.session.commit()
        flash('School updated.', 'success')
        return redirect(url_for('superadmin.school_detail', school_id=school.id))

    return render_template('superadmin/school_form.html', school=school, action='edit')


# ── Add admin user to a school ─────────────────────────────────────────────────

@bp.route('/schools/<int:school_id>/add-admin', methods=['POST'])
@superadmin_required
def add_school_admin(school_id):
    school = School.query.get_or_404(school_id)
    email  = request.form.get('email', '').strip().lower()
    name   = request.form.get('name', '').strip()
    pwd    = request.form.get('password', 'ChangeMe123!')
    role   = request.form.get('role', 'admin')

    if not email or not name:
        flash('Name and email are required.', 'danger')
        return redirect(url_for('superadmin.school_detail', school_id=school_id))

    if User.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already registered.', 'danger')
        return redirect(url_for('superadmin.school_detail', school_id=school_id))

    user = User(name=name, email=email, role=role, school_id=school.id)
    user.set_password(pwd)
    db.session.add(user)
    db.session.commit()
    flash(f'{role.title()} user "{name}" added to {school.name}.', 'success')
    return redirect(url_for('superadmin.school_detail', school_id=school_id))


# ── Delete / deactivate school ─────────────────────────────────────────────────

@bp.route('/schools/<int:school_id>/delete', methods=['POST'])
@superadmin_required
def delete_school(school_id):
    school = School.query.get_or_404(school_id)
    # Safety: only allow deletion if school has no users
    user_count = User.query.filter_by(school_id=school.id).count()
    if user_count > 0:
        flash(f'Cannot delete "{school.name}" — it still has {user_count} user(s). '
              'Remove all users first or deactivate instead.', 'danger')
        return redirect(url_for('superadmin.school_detail', school_id=school_id))
    db.session.delete(school)
    db.session.commit()
    flash(f'School "{school.name}" deleted.', 'success')
    return redirect(url_for('superadmin.schools'))


# ── Cross-school analytics (JSON for charts) ───────────────────────────────────

@bp.route('/api/stats')
@superadmin_required
def api_stats():
    schools = School.query.order_by(School.name).all()
    data = []
    for s in schools:
        data.append({
            'name':     s.name,
            'students': User.query.filter_by(school_id=s.id, role='student').count(),
            'teachers': User.query.filter_by(school_id=s.id, role='teacher').count(),
        })
    return jsonify(data)
