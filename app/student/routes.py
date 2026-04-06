from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.student import bp
from app.models import (Student, Grade, Attendance, Assignment, AssignmentSubmission,
                         AcademicTerm, Exam, ExamSubmission, ExamQuestion, Notification, MicroCredential)
from app import db
from datetime import datetime, date
import json
from flask import make_response


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)


def get_current_student():
    return Student.query.filter_by(user_id=current_user.id).first()


@bp.route('/dashboard')
@student_required
def dashboard():
    student = get_current_student()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('auth.login'))

    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()

    # Recent grades
    recent_grades = (Grade.query.filter_by(student_id=student.id)
                     .order_by(Grade.date.desc()).limit(6).all())

    # Attendance summary (last 30 days)
    from datetime import timedelta
    thirty_ago = date.today() - timedelta(days=30)
    total_att = Attendance.query.filter_by(student_id=student.id).filter(Attendance.date >= thirty_ago).count()
    present_att = Attendance.query.filter_by(student_id=student.id, status='present').filter(Attendance.date >= thirty_ago).count()
    att_pct = round((present_att / total_att * 100), 1) if total_att > 0 else 100

    # Pending assignments
    if student.section_id:
        assignments = (Assignment.query.filter_by(section_id=student.section_id, is_active=True)
                       .filter(Assignment.due_date >= datetime.utcnow()).all())
        submitted_ids = {s.assignment_id for s in AssignmentSubmission.query.filter_by(student_id=student.id).all()}
        pending_assignments = [a for a in assignments if a.id not in submitted_ids]
    else:
        pending_assignments = []

    # Upcoming exams
    upcoming_exams = (Exam.query.filter_by(section_id=student.section_id, is_published=True)
                      .filter(Exam.end_time >= datetime.utcnow()).order_by(Exam.start_time).limit(3).all()
                      if student.section_id else [])

    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template('student/dashboard.html', student=student,
                           recent_grades=recent_grades, att_pct=att_pct,
                           pending_assignments=pending_assignments,
                           upcoming_exams=upcoming_exams,
                           notifications=notifications,
                           active_term=active_term)


@bp.route('/grades')
@student_required
def grades():
    student = get_current_student()
    term_id = request.args.get('term_id', type=int)
    terms = AcademicTerm.query.filter_by(school_id=current_user.school_id).order_by(AcademicTerm.start_date.desc()).all()
    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()

    query = Grade.query.filter_by(student_id=student.id)
    if term_id:
        query = query.filter_by(term_id=term_id)
    grades = query.order_by(Grade.date.desc()).all()

    # Group by subject
    by_subject = {}
    for g in grades:
        subj = g.subject.name
        if subj not in by_subject:
            by_subject[subj] = []
        by_subject[subj].append(g)

    # Chart data
    chart_labels = []
    chart_data = {}
    for g in sorted(grades, key=lambda x: x.date):
        label = f"{g.exam_name} ({g.date.strftime('%b %d')})"
        if label not in chart_labels:
            chart_labels.append(label)
        subj = g.subject.name
        if subj not in chart_data:
            chart_data[subj] = []
        chart_data[subj].append(g.percentage)

    return render_template('student/grades.html', student=student, grades=grades,
                           by_subject=by_subject, terms=terms, active_term=active_term,
                           selected_term_id=term_id,
                           chart_labels=chart_labels, chart_data=chart_data)


@bp.route('/attendance')
@student_required
def attendance():
    student = get_current_student()
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)

    records = (Attendance.query.filter_by(student_id=student.id)
               .filter(db.extract('month', Attendance.date) == month,
                       db.extract('year', Attendance.date) == year)
               .order_by(Attendance.date).all())

    total = Attendance.query.filter_by(student_id=student.id).count()
    present = Attendance.query.filter_by(student_id=student.id, status='present').count()
    absent = Attendance.query.filter_by(student_id=student.id, status='absent').count()
    late = Attendance.query.filter_by(student_id=student.id, status='late').count()
    att_pct = round((present / total * 100), 1) if total > 0 else 0

    return render_template('student/attendance.html', student=student, records=records,
                           month=month, year=year, total=total, present=present,
                           absent=absent, late=late, att_pct=att_pct)


@bp.route('/assignments')
@student_required
def assignments():
    student = get_current_student()
    all_assignments = (Assignment.query.filter_by(section_id=student.section_id, is_active=True)
                       .order_by(Assignment.due_date).all() if student.section_id else [])
    submissions = {s.assignment_id: s for s in
                   AssignmentSubmission.query.filter_by(student_id=student.id).all()}
    return render_template('student/assignments.html', assignments=all_assignments,
                           submissions=submissions, student=student)


@bp.route('/assignments/<int:aid>/submit', methods=['GET', 'POST'])
@student_required
def submit_assignment(aid):
    student = get_current_student()
    assignment = Assignment.query.get_or_404(aid)
    existing_sub = AssignmentSubmission.query.filter_by(assignment_id=aid, student_id=student.id).first()

    if request.method == 'POST':
        if existing_sub:
            flash('Already submitted.', 'info')
        else:
            sub = AssignmentSubmission(
                assignment_id=aid,
                student_id=student.id,
                content=request.form.get('content', ''),
                is_late=datetime.utcnow() > assignment.due_date,
                submitted_at=datetime.utcnow()
            )
            db.session.add(sub)
            db.session.commit()
            flash('Assignment submitted!', 'success')
        return redirect(url_for('student.assignments'))
    return render_template('student/submit_assignment.html', assignment=assignment, existing_sub=existing_sub)


@bp.route('/notifications/mark-read', methods=['POST'])
@student_required
def mark_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


# ─── Micro-Credentials ────────────────────────────────────────────────────────
@bp.route('/credentials')
@student_required
def credentials():
    student = get_current_student()
    creds = MicroCredential.query.filter_by(student_id=student.id).order_by(MicroCredential.issued_date.desc()).all()
    return render_template('student/credentials.html', student=student, credentials=creds)


@bp.route('/credentials/<int:cid>/download')
@login_required
def download_credential(cid):
    c = MicroCredential.query.get_or_404(cid)
    
    # Check access permission (only the student or their parent can view)
    if current_user.role == 'student':
        if c.student.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('student.dashboard'))
    elif current_user.role == 'parent':
        from app.models import ParentStudentLink
        link = ParentStudentLink.query.filter_by(parent_id=current_user.id, student_id=c.student_id).first()
        if not link:
            flash('Access denied.', 'danger')
            return redirect(url_for('parent.dashboard'))
            
    html = render_template('credentials/certificate_pdf.html', credential=c, today=date.today())
    
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=credential_{c.id}_{c.category}.pdf'
        return response
    except Exception as e:
        flash(f'PDF generation failed: {e}. Showing HTML version instead.', 'warning')
        return html
