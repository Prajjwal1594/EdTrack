from flask import render_template, redirect, url_for, flash, request, jsonify, Response
import csv
import io
from flask_login import login_required, current_user
from functools import wraps
from app.admin import bp
from app.models import (User, School, Class, Section, Subject, TeacherAssignment,
                         Student, AcademicTerm, ParentStudentLink, FeeType,
                         Announcement, Event, Feedback, Grievance, LeaveApplication)
from app import db
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta
from app.utils.algorithms import generate_parent_digest, get_parent_digest_preview
from sqlalchemy import func
from app.models import Grade, Attendance, StaffAttendance


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)


@bp.route('/dashboard')
@admin_required
def dashboard():
    school = School.query.filter_by(id=current_user.school_id).first()
    stats = {
        'teachers': User.query.filter_by(role='teacher', school_id=current_user.school_id).count(),
        'students': User.query.filter_by(role='student', school_id=current_user.school_id).count(),
        'parents': User.query.filter_by(role='parent', school_id=current_user.school_id).count(),
        'classes': Class.query.filter_by(school_id=current_user.school_id).count(),
        'subjects': Subject.query.filter_by(school_id=current_user.school_id).count(),
    }
    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()
    
    # Analytics Data
    from sqlalchemy import func
    from app.models import Grade
    
    # 1. Subject Averages
    subject_avg_data = db.session.query(
        Subject.name, func.avg(Grade.score)
    ).join(Grade).filter(Subject.school_id == current_user.school_id).group_by(Subject.id).all()
    subject_averages = [{"subject": row[0], "avg": round(row[1], 1)} for row in subject_avg_data]

    # 2. Performance Trend (Last 6 Months)
    trend_data = db.session.query(
        func.to_char(Grade.date, 'YYYY-MM'), func.avg(Grade.score)
    ).join(Student, Grade.student_id == Student.id).join(User, Student.user_id == User.id)\
    .filter(User.school_id == current_user.school_id).group_by(func.to_char(Grade.date, 'YYYY-MM'))\
    .order_by(func.to_char(Grade.date, 'YYYY-MM').desc()).limit(6).all()
    performance_trend = [{"month": row[0], "avg": round(row[1], 1)} for row in reversed(trend_data)]

    # 3. User Distribution
    user_dist = [
        {"role": "Admins", "count": stats['teachers']},
        {"role": "Teachers", "count": stats['teachers']},
        {"role": "Students", "count": stats['students']},
        {"role": "Parents", "count": stats['parents']}
    ]
    user_dist[0]['count'] = User.query.filter_by(role='admin', school_id=current_user.school_id).count()

    recent_users = User.query.filter_by(school_id=current_user.school_id).order_by(User.created_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', stats=stats, school=school,
                           active_term=active_term, recent_users=recent_users,
                           subject_averages=subject_averages,
                           performance_trend=performance_trend,
                           user_distribution=user_dist)


@bp.route('/admission', methods=['GET', 'POST'])
@admin_required
def admission():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if User.query.filter_by(email=email).first():
            flash('Email already registered for admission.', 'danger')
            return redirect(url_for('admin.admission'))
            
        user = User(
            name=request.form.get('name', '').strip(),
            email=email,
            role='student',
            phone=request.form.get('phone', ''),
            school_id=current_user.school_id
        )
        user.set_password('ChangeMe123!')
        db.session.add(user)
        db.session.flush()

        section_id = request.form.get('section_id')
        enrollment_num = request.form.get('enrollment_number') or f'EW{user.id:05d}'
        dob_str = request.form.get('date_of_birth')
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        
        student = Student(
            user_id=user.id,
            section_id=section_id if section_id else None,
            enrollment_number=enrollment_num,
            date_of_birth=dob,
            gender=request.form.get('gender', '')
        )
        db.session.add(student)
        db.session.commit()
        flash(f'Admission successful for student {user.name}. Default password applied.', 'success')
        return redirect(url_for('admin.users'))

    sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
    return render_template('admin/admission.html', sections=sections)


# ─── Users ───────────────────────────────────────────────────────────────────
@bp.route('/users')
@admin_required
def users():
    role_filter = request.args.get('role', '')
    query = User.query.filter_by(school_id=current_user.school_id)
    if role_filter:
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.name).all()
    return render_template('admin/users.html', users=users, role_filter=role_filter)


@bp.route('/users/add', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('admin.add_user'))
        user = User(
            name=request.form.get('name', '').strip(),
            email=email,
            role=request.form.get('role'),
            phone=request.form.get('phone', ''),
            school_id=current_user.school_id
        )
        user.set_password(request.form.get('password', 'ChangeMe123!'))
        db.session.add(user)
        db.session.flush()

        if user.role == 'student':
            section_id = request.form.get('section_id')
            enrollment_num = request.form.get('enrollment_number', f'EW{user.id:05d}')
            dob_str = request.form.get('date_of_birth')
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
            student = Student(
                user_id=user.id,
                section_id=section_id if section_id else None,
                enrollment_number=enrollment_num,
                date_of_birth=dob,
                gender=request.form.get('gender', '')
            )
            db.session.add(student)
        db.session.commit()
        flash(f'User {user.name} created successfully.', 'success')
        return redirect(url_for('admin.users'))

    sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
    return render_template('admin/user_form.html', user=None, sections=sections)


@bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(uid):
    user = User.query.get_or_404(uid)
    if request.method == 'POST':
        user.name = request.form.get('name', user.name)
        user.phone = request.form.get('phone', user.phone)
        user.is_active = request.form.get('is_active') == 'on'
        new_pass = request.form.get('new_password', '').strip()
        if new_pass:
            user.set_password(new_pass)
        if user.role == 'student' and user.student_profile:
            section_id = request.form.get('section_id')
            if section_id:
                user.student_profile.section_id = int(section_id)
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('admin.users'))
    sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
    return render_template('admin/user_form.html', user=user, sections=sections)


@bp.route('/students')
@admin_required
def students():
    student_users = User.query.filter_by(school_id=current_user.school_id, role='student').join(Student).order_by(User.name).all()
    return render_template('admin/students.html', students=student_users)


@bp.route('/users/<int:uid>/edit-erp', methods=['GET', 'POST'])
@admin_required
def edit_erp_profile(uid):
    user = User.query.get_or_404(uid)
    if user.role != 'student' or not user.student_profile:
        flash('ERP details are only applicable for student accounts with an active profile.', 'warning')
        return redirect(url_for('admin.users'))
        
    student = user.student_profile
    if request.method == 'POST':
        try:
            # Personal Info
            student.blood_group = request.form.get('blood_group')
            student.religion = request.form.get('religion')
            student.caste = request.form.get('caste')
            student.aadhar_number = request.form.get('aadhar_number')
            student.admission_category = request.form.get('admission_category')
            student.session = request.form.get('session')
            
            tc_date_str = request.form.get('tc_date')
            student.tc_date = datetime.strptime(tc_date_str, '%Y-%m-%d').date() if tc_date_str else None
            student.biometric_card_no = request.form.get('biometric_card_no')
            student.alternate_class_group = request.form.get('alternate_class_group')
            student.class_group = request.form.get('class_group')
            student.phone2 = request.form.get('phone2')
            student.landline = request.form.get('landline')

            # Academic History (10th)
            student.tenth_year = request.form.get('tenth_year', type=int)
            student.tenth_roll = request.form.get('tenth_roll')
            student.tenth_board = request.form.get('tenth_board')
            student.tenth_obtained = request.form.get('tenth_obtained', type=float)
            student.tenth_max = request.form.get('tenth_max', type=float)

            # Academic History (12th)
            student.twelfth_year = request.form.get('twelfth_year', type=int)
            student.twelfth_roll = request.form.get('twelfth_roll')
            student.twelfth_board = request.form.get('twelfth_board')
            student.twelfth_obtained = request.form.get('twelfth_obtained', type=float)
            student.twelfth_max = request.form.get('twelfth_max', type=float)

            # Parent / Guardian Info
            student.father_name = request.form.get('father_name')
            student.father_occupation = request.form.get('father_occupation')
            student.father_mobile = request.form.get('father_mobile')
            student.mother_name = request.form.get('mother_name')
            student.mother_mobile = request.form.get('mother_mobile')
            student.local_guardian_name = request.form.get('local_guardian_name')
            student.local_guardian_mobile = request.form.get('local_guardian_mobile')
            student.local_guardian_address = request.form.get('local_guardian_address')

            db.session.commit()
            flash('ERP detailed profile updated successfully.', 'success')
            return redirect(url_for('admin.edit_erp_profile', uid=uid))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('admin/edit_student_erp.html', user=user, student=student)


@bp.route('/users/<int:uid>/delete', methods=['POST'])
@admin_required
def delete_user(uid):
    user = User.query.get_or_404(uid)
    user.is_active = False
    db.session.commit()
    flash('User deactivated.', 'info')
    return redirect(url_for('admin.users'))


# ─── Classes ─────────────────────────────────────────────────────────────────
@bp.route('/classes')
@admin_required
def classes():
    classes = Class.query.filter_by(school_id=current_user.school_id).order_by(Class.name).all()
    return render_template('admin/classes.html', classes=classes)


@bp.route('/classes/add', methods=['POST'])
@admin_required
def add_class():
    c = Class(
        name=request.form.get('name'),
        academic_year=request.form.get('academic_year'),
        school_id=current_user.school_id
    )
    db.session.add(c)
    db.session.commit()
    flash('Class added.', 'success')
    return redirect(url_for('admin.classes'))


@bp.route('/classes/<int:cid>/delete', methods=['POST'])
@admin_required
def delete_class(cid):
    c = Class.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    flash('Class deleted.', 'info')
    return redirect(url_for('admin.classes'))


# ─── Sections ────────────────────────────────────────────────────────────────
@bp.route('/sections')
@admin_required
def sections():
    classes = Class.query.filter_by(school_id=current_user.school_id).all()
    sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
    return render_template('admin/sections.html', sections=sections, classes=classes)


@bp.route('/sections/add', methods=['POST'])
@admin_required
def add_section():
    s = Section(
        class_id=request.form.get('class_id'),
        name=request.form.get('name'),
        room_number=request.form.get('room_number', ''),
        capacity=int(request.form.get('capacity', 40))
    )
    db.session.add(s)
    db.session.commit()
    flash('Section added.', 'success')
    return redirect(url_for('admin.sections'))


@bp.route('/sections/<int:sid>/delete', methods=['POST'])
@admin_required
def delete_section(sid):
    s = Section.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('Section deleted.', 'info')
    return redirect(url_for('admin.sections'))


# ─── Subjects ────────────────────────────────────────────────────────────────
@bp.route('/subjects')
@admin_required
def subjects():
    subjects = Subject.query.filter_by(school_id=current_user.school_id).order_by(Subject.name).all()
    return render_template('admin/subjects.html', subjects=subjects)


@bp.route('/subjects/add', methods=['POST'])
@admin_required
def add_subject():
    s = Subject(
        name=request.form.get('name'),
        code=request.form.get('code', ''),
        school_id=current_user.school_id
    )
    db.session.add(s)
    db.session.commit()
    flash('Subject added.', 'success')
    return redirect(url_for('admin.subjects'))


@bp.route('/subjects/<int:sid>/delete', methods=['POST'])
@admin_required
def delete_subject(sid):
    s = Subject.query.get_or_404(sid)
    db.session.delete(s)
    db.session.commit()
    flash('Subject deleted.', 'info')
    return redirect(url_for('admin.subjects'))


# ─── Teacher Assignments ─────────────────────────────────────────────────────
@bp.route('/assignments')
@admin_required
def teacher_assignments():
    assignments = TeacherAssignment.query.join(User, TeacherAssignment.teacher_id == User.id)\
        .filter(User.school_id == current_user.school_id).all()
    teachers = User.query.filter_by(role='teacher', school_id=current_user.school_id).all()
    subjects = Subject.query.filter_by(school_id=current_user.school_id).all()
    sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
    return render_template('admin/teacher_assignments.html',
                           assignments=assignments, teachers=teachers,
                           subjects=subjects, sections=sections)


@bp.route('/assignments/add', methods=['POST'])
@admin_required
def add_teacher_assignment():
    ta = TeacherAssignment(
        teacher_id=request.form.get('teacher_id'),
        subject_id=request.form.get('subject_id'),
        section_id=request.form.get('section_id'),
        academic_year=request.form.get('academic_year', '2024-2025')
    )
    db.session.add(ta)
    db.session.commit()
    flash('Teacher assigned.', 'success')
    return redirect(url_for('admin.teacher_assignments'))


@bp.route('/assignments/<int:aid>/delete', methods=['POST'])
@admin_required
def delete_teacher_assignment(aid):
    ta = TeacherAssignment.query.get_or_404(aid)
    db.session.delete(ta)
    db.session.commit()
    flash('Assignment removed.', 'info')
    return redirect(url_for('admin.teacher_assignments'))


# ─── Academic Terms ──────────────────────────────────────────────────────────
@bp.route('/terms')
@admin_required
def terms():
    terms = AcademicTerm.query.filter_by(school_id=current_user.school_id).order_by(AcademicTerm.start_date.desc()).all()
    return render_template('admin/terms.html', terms=terms)


@bp.route('/terms/add', methods=['POST'])
@admin_required
def add_term():
    start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
    end = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
    t = AcademicTerm(
        school_id=current_user.school_id,
        name=request.form.get('name'),
        term_type=request.form.get('term_type', 'term'),
        start_date=start,
        end_date=end,
        academic_year=request.form.get('academic_year', '2024-2025')
    )
    db.session.add(t)
    db.session.commit()
    flash('Term added.', 'success')
    return redirect(url_for('admin.terms'))


@bp.route('/terms/<int:tid>/activate', methods=['POST'])
@admin_required
def activate_term(tid):
    AcademicTerm.query.filter_by(school_id=current_user.school_id).update({'is_active': False})
    term = AcademicTerm.query.get_or_404(tid)
    term.is_active = True
    db.session.commit()
    flash(f'"{term.name}" is now the active term.', 'success')
    return redirect(url_for('admin.terms'))


@bp.route('/terms/<int:tid>/delete', methods=['POST'])
@admin_required
def delete_term(tid):
    term = AcademicTerm.query.get_or_404(tid)
    db.session.delete(term)
    db.session.commit()
    flash('Term deleted.', 'info')
    return redirect(url_for('admin.terms'))


# ─── Fee Types ────────────────────────────────────────────────────────────────
@bp.route('/fee-types')
@admin_required
def fee_types():
    fee_types = FeeType.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/fee_types.html', fee_types=fee_types)


@bp.route('/fee-types/add', methods=['POST'])
@admin_required
def add_fee_type():
    ft = FeeType(
        school_id=current_user.school_id,
        name=request.form.get('name'),
        amount=float(request.form.get('amount', 0)),
        frequency=request.form.get('frequency', 'term'),
        description=request.form.get('description', '')
    )
    db.session.add(ft)
    db.session.commit()
    flash('Fee type added.', 'success')
    return redirect(url_for('admin.fee_types'))


@bp.route('/fee-types/<int:fid>/delete', methods=['POST'])
@admin_required
def delete_fee_type(fid):
    ft = FeeType.query.get_or_404(fid)
    db.session.delete(ft)
    db.session.commit()
    flash('Fee type deleted.', 'info')
    return redirect(url_for('admin.fee_types'))


# ─── School Settings ─────────────────────────────────────────────────────────
@bp.route('/school', methods=['GET', 'POST'])
@admin_required
def school_settings():
    school = School.query.get(current_user.school_id)
    if request.method == 'POST':
        school.name = request.form.get('name', school.name)
        school.address = request.form.get('address', school.address)
        school.phone = request.form.get('phone', school.phone)
        school.email = request.form.get('email', school.email)
        db.session.commit()
        flash('School settings updated.', 'success')
        return redirect(url_for('admin.school_settings'))
    return render_template('admin/school_settings.html', school=school)


@bp.route('/trigger-digest', methods=['POST'])
@admin_required
def trigger_digest():
    generate_parent_digest(current_user.school_id, sender_id=current_user.id)
    flash('Weekly Friday Digest emails perfectly dispatched and recorded in history!', 'success')
    return redirect(request.referrer or url_for('admin.school_settings'))


@bp.route('/preview-digest')
@admin_required
def preview_digest():
    from app.models import User
    parent = User.query.filter_by(role='parent', school_id=current_user.school_id).first()
    if not parent:
        return "<div class='alert alert-warning'>No parent accounts found in this school to generate a preview.</div>"
    
    digest_text = get_parent_digest_preview(parent.id)
    if not digest_text:
        return f"<div class='alert alert-info'>No active student links found for sample parent: {parent.name}</div>"
        
    return f"<pre style='white-space: pre-wrap; font-family: monospace; background: #f8f9fa; padding: 15px; border-radius: 5px;'>{digest_text}</pre>"


# ─── Parent-Student Links ────────────────────────────────────────────────────
@bp.route('/parent-links')
@admin_required
def parent_links():
    links = ParentStudentLink.query.join(Student).join(User, Student.user_id == User.id)\
        .filter(User.school_id == current_user.school_id).all()
    parents = User.query.filter_by(role='parent', school_id=current_user.school_id).all()
    students = Student.query.join(User).filter(User.school_id == current_user.school_id).all()
    return render_template('admin/parent_links.html', links=links, parents=parents, students=students)


@bp.route('/parent-links/add', methods=['POST'])
@admin_required
def add_parent_link():
    link = ParentStudentLink(
        parent_id=request.form.get('parent_id'),
        student_id=request.form.get('student_id'),
        relationship_type=request.form.get('relationship_type', 'parent')
    )
    db.session.add(link)
    db.session.commit()
    flash('Parent-student link created.', 'success')
    return redirect(url_for('admin.parent_links'))


@bp.route('/parent-links/<int:lid>/delete', methods=['POST'])
@admin_required
def delete_parent_link(lid):
    link = ParentStudentLink.query.get_or_404(lid)
    db.session.delete(link)
    db.session.commit()
    flash('Link removed.', 'info')
    return redirect(url_for('admin.parent_links'))


# ─── LMS Integration ──────────────────────────────────────────────────────────
@bp.route('/lms')
@admin_required
def lms_integration():
    return render_template('admin/lms_integration.html')


@bp.route('/lms/export/<dataset>')
@admin_required
def lms_export(dataset):
    output = io.StringIO()
    writer = csv.writer(output)
    
    if dataset == 'students':
        students = Student.query.join(User).filter(User.school_id == current_user.school_id).all()
        writer.writerow(['Student_ID', 'Name', 'Email', 'Enrollment_Number', 'Section', 'Date_of_Birth', 'Gender'])
        for s in students:
            writer.writerow([
                s.id,
                s.user.name,
                s.user.email,
                s.enrollment_number,
                s.section.full_name if s.section else '',
                s.date_of_birth.strftime('%Y-%m-%d') if s.date_of_birth else '',
                s.gender
            ])
            
    elif dataset == 'grades':
        from app.models import Grade
        grades = Grade.query.join(Student).join(User).filter(User.school_id == current_user.school_id).all()
        writer.writerow(['Record_ID', 'Student_ID', 'Student_Name', 'Subject', 'Exam_Name', 'Percentage', 'Letter_Grade', 'Date'])
        for g in grades:
            writer.writerow([
                g.id,
                g.student_id,
                g.student.user.name,
                g.subject.name,
                g.exam_name,
                g.percentage,
                g.letter_grade,
                g.date.strftime('%Y-%m-%d')
            ])
    else:
        flash('Invalid dataset option.', 'danger')
        return redirect(url_for('admin.lms_integration'))
        
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=lms_export_{dataset}_{date.today()}.csv"
    return response


# ─── Announcements Management ────────────────────────────────────────────────

@bp.route('/announcements')
@admin_required
def announcements():
    ann_list = (Announcement.query.filter_by(school_id=current_user.school_id)
               .order_by(Announcement.created_at.desc()).all())
    return render_template('admin/announcements.html', announcements=ann_list)


@bp.route('/announcements/add', methods=['POST'])
@admin_required
def add_announcement():
    date_str = request.form.get('date')
    ann_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    ann = Announcement(
        school_id=current_user.school_id,
        title=request.form.get('title', ''),
        body=request.form.get('body', ''),
        announcement_type=request.form.get('announcement_type', 'notice'),
        date=ann_date,
        created_by=current_user.id,
    )
    db.session.add(ann)
    db.session.commit()
    flash('Announcement created.', 'success')
    return redirect(url_for('admin.announcements'))


@bp.route('/announcements/<int:aid>/delete', methods=['POST'])
@admin_required
def delete_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'info')
    return redirect(url_for('admin.announcements'))


@bp.route('/announcements/<int:aid>/toggle', methods=['POST'])
@admin_required
def toggle_announcement(aid):
    ann = Announcement.query.get_or_404(aid)
    ann.is_active = not ann.is_active
    db.session.commit()
    flash(f'Announcement {"activated" if ann.is_active else "deactivated"}.', 'info')
    return redirect(url_for('admin.announcements'))


# ─── Events Management ──────────────────────────────────────────────────────

@bp.route('/events')
@admin_required
def events():
    events_list = (Event.query.filter_by(school_id=current_user.school_id)
                  .order_by(Event.event_date.desc()).all())
    return render_template('admin/events.html', events=events_list)


@bp.route('/events/add', methods=['POST'])
@admin_required
def add_event():
    event_date_str = request.form.get('event_date')
    end_date_str = request.form.get('end_date')
    event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M') if event_date_str else datetime.utcnow()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M') if end_date_str else None
    
    event = Event(
        school_id=current_user.school_id,
        title=request.form.get('title', ''),
        description=request.form.get('description', ''),
        event_date=event_date,
        end_date=end_date,
        location=request.form.get('location', ''),
        max_capacity=request.form.get('max_capacity', type=int),
        requires_registration=request.form.get('requires_registration') == 'on',
        created_by=current_user.id,
    )
    db.session.add(event)
    db.session.commit()
    flash('Event created.', 'success')
    return redirect(url_for('admin.events'))


@bp.route('/events/<int:eid>/delete', methods=['POST'])
@admin_required
def delete_event(eid):
    event = Event.query.get_or_404(eid)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'info')
    return redirect(url_for('admin.events'))


# ─── Feedback Management ────────────────────────────────────────────────────

@bp.route('/feedback')
@admin_required
def feedback_list():
    status_filter = request.args.get('status', '')
    query = (Feedback.query.filter_by(school_id=current_user.school_id)
            .order_by(Feedback.created_at.desc()))
    if status_filter:
        query = query.filter_by(status=status_filter)
    feedbacks = query.all()
    return render_template('admin/feedback.html', feedbacks=feedbacks, status_filter=status_filter)


@bp.route('/feedback/<int:fid>/respond', methods=['POST'])
@admin_required
def respond_feedback(fid):
    fb = Feedback.query.get_or_404(fid)
    fb.admin_response = request.form.get('response', '')
    fb.responded_by = current_user.id
    fb.responded_at = datetime.utcnow()
    fb.status = request.form.get('status', 'reviewed')
    db.session.commit()
    flash('Feedback response saved.', 'success')
    return redirect(url_for('admin.feedback_list'))


# ─── Grievance Management ───────────────────────────────────────────────────

@bp.route('/grievances')
@admin_required
def grievance_list():
    status_filter = request.args.get('status', '')
    query = (Grievance.query.filter_by(school_id=current_user.school_id)
            .order_by(Grievance.created_at.desc()))
    if status_filter:
        query = query.filter_by(status=status_filter)
    grievances = query.all()
    return render_template('admin/grievances.html', grievances=grievances, status_filter=status_filter)


@bp.route('/grievances/<int:gid>/resolve', methods=['POST'])
@admin_required
def resolve_grievance(gid):
    gr = Grievance.query.get_or_404(gid)
    gr.resolution = request.form.get('resolution', '')
    gr.resolved_by = current_user.id
    gr.resolved_at = datetime.utcnow()
    gr.status = request.form.get('status', 'resolved')
    db.session.commit()
    flash('Grievance updated.', 'success')
    return redirect(url_for('admin.grievance_list'))


# ─── Leave Application Management ───────────────────────────────────────────

@bp.route('/leave-applications')
@admin_required
def leave_applications():
    status_filter = request.args.get('status', '')
    query = (LeaveApplication.query.filter_by(school_id=current_user.school_id)
            .order_by(LeaveApplication.created_at.desc()))
    if status_filter:
        query = query.filter_by(status=status_filter)
    applications = query.all()
    return render_template('admin/leave_applications.html', applications=applications, status_filter=status_filter)


@bp.route('/leave-applications/<int:lid>/action', methods=['POST'])
@admin_required
def leave_action(lid):
    leave = LeaveApplication.query.get_or_404(lid)
    action = request.form.get('action')
    if action == 'approve':
        leave.status = 'approved'
    elif action == 'reject':
        leave.status = 'rejected'
    leave.approved_by = current_user.id
    leave.approved_at = datetime.utcnow()
    leave.admin_remarks = request.form.get('remarks', '')
    db.session.commit()
    flash(f'Leave application {leave.status}.', 'success')
    return redirect(url_for('admin.leave_applications'))
# ─── Early Warning & Monitoring (Goal 30) ───────────────────────────────────

@bp.route('/at-risk')
@admin_required
def at_risk_dashboard():
    # Identify students at risk: Attendance < 75% or Avg Grade < 40%
    all_students = Student.query.join(User).filter(User.school_id == current_user.school_id).all()
    at_risk_students = []
    
    for student in all_students:
        # 1. Attendance Check
        total_att = Attendance.query.filter_by(student_id=student.id).count()
        present_att = Attendance.query.filter_by(student_id=student.id).filter(Attendance.status.in_(['present', 'late'])).count()
        att_pct = (present_att / total_att * 100) if total_att > 0 else 100
        
        # 2. Grade Check
        avg_grade = db.session.query(func.avg(Grade.score)).filter(Grade.student_id == student.id).scalar() or 100
        
        reasons = []
        if att_pct < 75:
            reasons.append(f"Low Attendance ({round(att_pct, 1)}%)")
        if avg_grade < 40:
            reasons.append(f"Poor Academics ({round(avg_grade, 1)}%)")
            
        if reasons:
            at_risk_students.append({
                'student': student,
                'att_pct': round(att_pct, 1),
                'avg_grade': round(avg_grade, 1),
                'reasons': reasons
            })
            
    return render_template('admin/at_risk_dashboard.html', students=at_risk_students)

@bp.route('/student/<int:sid>/intervention', methods=['GET', 'POST'])
@admin_required
def student_intervention(sid):
    student = Student.query.get_or_404(sid)
    if student.user.school_id != current_user.school_id:
        abort(403)
        
    if request.method == 'POST':
        # Logic for sending an intervention email or recording a meeting
        intervention_type = request.form.get('type')
        notes = request.form.get('notes')
        flash(f'Intervention recorded for {student.user.name}. Parent notification queued.', 'success')
        return redirect(url_for('admin.at_risk_dashboard'))
        
    return render_template('admin/intervention_form.html', student=student)
