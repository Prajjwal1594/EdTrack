from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app.teacher import bp
from app.models import (User, TeacherAssignment, Student, Grade, Attendance,
                         Assignment, AssignmentSubmission, AcademicTerm, ReportComment,
                         Section, Subject, Notification, Exam, ExamQuestion, ParentStudentLink, 
                         MicroCredential, SoftSkillMetric)
from app import db
from app.email import send_email
from app.utils.algorithms import evaluate_student_risk
from app.utils.realtime import broadcast_student_update, broadcast_notification
from datetime import datetime, date, timedelta
import json


def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('teacher', 'admin'):
            flash('Teacher access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return login_required(decorated)


def get_teacher_sections():
    return (Section.query.join(TeacherAssignment, TeacherAssignment.section_id == Section.id)
            .filter(TeacherAssignment.teacher_id == current_user.id)
            .distinct().all())


def get_teacher_assignments_list():
    return TeacherAssignment.query.filter_by(teacher_id=current_user.id).all()


@bp.route('/dashboard')
@teacher_required
def dashboard():
    assignments = get_teacher_assignments_list()
    sections = get_teacher_sections()
    today = date.today()

    # Today's attendance status for each section
    attendance_done = {}
    for s in sections:
        count = Attendance.query.filter_by(section_id=s.id, date=today).count()
        attendance_done[s.id] = count > 0

    # Pending assignments
    pending_grading = (AssignmentSubmission.query
                       .join(Assignment)
                       .filter(Assignment.created_by == current_user.id,
                               AssignmentSubmission.grade == None)
                       .count())

    # Recent grades
    recent_grades = (Grade.query.filter_by(created_by=current_user.id)
                     .order_by(Grade.created_at.desc()).limit(5).all())

    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()
    total_students = sum(s.students.count() for s in sections)

    # Analytics Data
    from sqlalchemy import func
    # 1. Subject Averages for this teacher
    subject_avg_data = db.session.query(
        Subject.name, func.avg(Grade.score)
    ).join(Grade).filter(Grade.created_by == current_user.id).group_by(Subject.id).all()
    subject_averages = [{"subject": row[0], "avg": round(row[1], 1)} for row in subject_avg_data]

    # 2. At-Risk Students in teacher's sections
    at_risk_count = 0
    thirty_days_ago = date.today() - timedelta(days=30)
    
    for s in sections:
        for student in s.students.all():
            # Holistic check
            holistic = student.holistic_growth_score()
            
            # Academic check
            grade_records = student.grades.all()
            avg_academic = sum(g.percentage for g in grade_records) / len(grade_records) if grade_records else 100.0
            
            # Absence check
            recent_absences = student.attendance_records.filter(
                Attendance.date >= thirty_days_ago,
                Attendance.status == 'absent'
            ).count()
            
            if (holistic < 60) or (avg_academic < 50) or (recent_absences >= 3):
                at_risk_count += 1

    # 3. Section Attendance Averages
    section_attendance = []
    for s in sections:
        att_total = s.attendance_records.count()
        att_present = s.attendance_records.filter_by(status='present').count()
        pct = (att_present / att_total * 100) if att_total > 0 else 100.0
        section_attendance.append({"section": s.full_name, "pct": round(pct, 1)})

    return render_template('teacher/dashboard.html',
                           assignments=assignments, sections=sections,
                           attendance_done=attendance_done,
                           pending_grading=pending_grading,
                           recent_grades=recent_grades,
                           active_term=active_term,
                           total_students=total_students,
                           subject_averages=subject_averages,
                           at_risk_count=at_risk_count,
                           section_attendance=section_attendance)


# ─── Grades ──────────────────────────────────────────────────────────────────
@bp.route('/grades')
@teacher_required
def grades():
    ta_list = get_teacher_assignments_list()
    selected_ta_id = request.args.get('ta_id', type=int)
    selected_term_id = request.args.get('term_id', type=int)
    grades = []
    selected_ta = None
    students = []

    terms = AcademicTerm.query.filter_by(school_id=current_user.school_id).order_by(AcademicTerm.start_date.desc()).all()
    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()

    if selected_ta_id:
        selected_ta = TeacherAssignment.query.get(selected_ta_id)
        if selected_ta:
            students = Student.query.filter_by(section_id=selected_ta.section_id).all()
            if selected_term_id:
                grades = (Grade.query.filter_by(subject_id=selected_ta.subject_id, term_id=selected_term_id)
                          .filter(Grade.student_id.in_([s.id for s in students]))
                          .order_by(Grade.date.desc()).all())

    return render_template('teacher/grades.html', ta_list=ta_list, selected_ta=selected_ta,
                           grades=grades, students=students, terms=terms,
                           active_term=active_term, selected_ta_id=selected_ta_id,
                           selected_term_id=selected_term_id or (active_term.id if active_term else None))


@bp.route('/grades/add', methods=['POST'])
@teacher_required
def add_grade():
    student_id = request.form.get('student_id', type=int)
    subject_id = request.form.get('subject_id', type=int)
    term_id = request.form.get('term_id', type=int)
    exam_name = request.form.get('exam_name', '').strip()
    score = request.form.get('score', type=float)
    max_score = request.form.get('max_score', 100, type=float)
    date_str = request.form.get('date')
    grade_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()

    grade = Grade(
        student_id=student_id,
        subject_id=subject_id,
        term_id=term_id,
        exam_name=exam_name,
        score=score,
        max_score=max_score,
        date=grade_date,
        remarks=request.form.get('remarks', ''),
        created_by=current_user.id
    )
    db.session.add(grade)

    # Send notification if low grade
    if grade.percentage < 40:
        student = Student.query.get(student_id)
        if student:
            notif = Notification(
                user_id=student.user_id,
                type='low_grade',
                title='Low Grade Alert',
                message=f'You scored {grade.percentage}% in {grade.subject.name} ({exam_name}). Please speak with your teacher.',
                link=url_for('student.grades')
            )
            db.session.add(notif)

            # Emails to student and parents
            recipients = [student.user.email]
            parents = User.query.join(ParentStudentLink, ParentStudentLink.parent_id == User.id)\
                                .filter(ParentStudentLink.student_id == student.id).all()
            recipients.extend([p.email for p in parents])
            
            send_email(
                subject='Low Grade Alert - ElWood Tracking',
                sender='no-reply@gmail.com',
                recipients=recipients,
                text_body=f"Hello {student.user.name} and parents,\n\nA low grade alert has been triggered: {notif.message}\n\nPlease log in to the portal for more details."
            )

    db.session.commit()
    
    # Evaluate for Early Warning risk
    evaluate_student_risk(student_id)
    
    # Real-time broadcast
    student = Student.query.get(student_id)
    if student:
        broadcast_student_update(student)
    
    flash('Grade recorded.', 'success')
    return redirect(request.referrer or url_for('teacher.grades'))


@bp.route('/grades/<int:gid>/edit', methods=['POST'])
@teacher_required
def edit_grade(gid):
    grade = Grade.query.get_or_404(gid)
    grade.score = request.form.get('score', grade.score, type=float)
    grade.remarks = request.form.get('remarks', grade.remarks)
    db.session.commit()
    flash('Grade updated.', 'success')
    return redirect(request.referrer or url_for('teacher.grades'))


@bp.route('/grades/<int:gid>/delete', methods=['POST'])
@teacher_required
def delete_grade(gid):
    grade = Grade.query.get_or_404(gid)
    db.session.delete(grade)
    db.session.commit()
    flash('Grade deleted.', 'info')
    return redirect(request.referrer or url_for('teacher.grades'))


# ─── Attendance ───────────────────────────────────────────────────────────────
@bp.route('/attendance')
@teacher_required
def attendance():
    sections = get_teacher_sections()
    selected_section_id = request.args.get('section_id', type=int)
    selected_date_str = request.args.get('date', date.today().isoformat())
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()

    students = []
    attendance_map = {}

    if selected_section_id:
        students = Student.query.filter_by(section_id=selected_section_id).all()
        records = Attendance.query.filter_by(section_id=selected_section_id, date=selected_date).all()
        attendance_map = {r.student_id: r for r in records}

    return render_template('teacher/attendance.html',
                           sections=sections, students=students,
                           attendance_map=attendance_map,
                           selected_section_id=selected_section_id,
                           selected_date=selected_date)


@bp.route('/attendance/save', methods=['POST'])
@teacher_required
def save_attendance():
    section_id = request.form.get('section_id', type=int)
    date_str = request.form.get('date')
    att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    students = Student.query.filter_by(section_id=section_id).all()

    for student in students:
        status = request.form.get(f'status_{student.id}', 'present')
        remarks = request.form.get(f'remarks_{student.id}', '')

        existing = Attendance.query.filter_by(student_id=student.id, date=att_date).first()
        if existing:
            existing.status = status
            existing.remarks = remarks
            existing.marked_by = current_user.id
        else:
            att = Attendance(
                student_id=student.id,
                section_id=section_id,
                date=att_date,
                status=status,
                remarks=remarks,
                marked_by=current_user.id
            )
            db.session.add(att)

        # Notify on absence
        if status == 'absent':
            notif = Notification(
                user_id=student.user_id,
                type='absent',
                title='Absence Recorded',
                message=f'Your attendance was marked as absent on {att_date.strftime("%B %d, %Y")}.',
                link=url_for('student.attendance')
            )
            db.session.add(notif)

            # Emails to student and parents
            recipients = [student.user.email]
            parents = User.query.join(ParentStudentLink, ParentStudentLink.parent_id == User.id)\
                                .filter(ParentStudentLink.student_id == student.id).all()
            recipients.extend([p.email for p in parents])
            
            send_email(
                subject='Absence Alert - ElWood Tracking',
                sender='no-reply@gmail.com',
                recipients=recipients,
                text_body=f"Hello {student.user.name} and parents,\n\n{notif.message}\n\nIf this absence is unexpected, please contact the school administration immediately."
            )

    db.session.commit()
    
    # Evaluate for Early Warning risk & Broadcast
    for student in students:
        evaluate_student_risk(student.id)
        broadcast_student_update(student)
        
    flash('Attendance saved successfully.', 'success')
    return redirect(url_for('teacher.attendance', section_id=section_id, date=date_str))


# ─── Assignments ──────────────────────────────────────────────────────────────
@bp.route('/assignments')
@teacher_required
def assignments():
    ta_list = get_teacher_assignments_list()
    my_assignments = (Assignment.query.filter_by(created_by=current_user.id)
                      .order_by(Assignment.due_date.desc()).all())
    return render_template('teacher/assignments.html',
                           my_assignments=my_assignments, ta_list=ta_list)


@bp.route('/assignments/add', methods=['POST'])
@teacher_required
def add_assignment():
    due_str = request.form.get('due_date')
    due_date = datetime.strptime(due_str, '%Y-%m-%dT%H:%M') if due_str else datetime.utcnow()
    a = Assignment(
        subject_id=request.form.get('subject_id', type=int),
        section_id=request.form.get('section_id', type=int),
        title=request.form.get('title', '').strip(),
        description=request.form.get('description', '').strip(),
        due_date=due_date,
        max_score=request.form.get('max_score', 100, type=float),
        created_by=current_user.id
    )
    db.session.add(a)
    db.session.commit()
    flash('Assignment created.', 'success')
    return redirect(url_for('teacher.assignments'))


@bp.route('/assignments/<int:aid>/submissions')
@teacher_required
def assignment_submissions(aid):
    assignment = Assignment.query.get_or_404(aid)
    students = Student.query.filter_by(section_id=assignment.section_id).all()
    submissions = {s.student_id: s for s in assignment.submissions.all()}
    return render_template('teacher/submissions.html',
                           assignment=assignment, students=students, submissions=submissions)


@bp.route('/assignments/<int:aid>/grade', methods=['POST'])
@teacher_required
def grade_submission(aid):
    student_id = request.form.get('student_id', type=int)
    sub = AssignmentSubmission.query.filter_by(assignment_id=aid, student_id=student_id).first()
    if not sub:
        sub = AssignmentSubmission(assignment_id=aid, student_id=student_id, submitted_at=datetime.utcnow())
        db.session.add(sub)
    sub.grade = request.form.get('grade', type=float)
    sub.feedback = request.form.get('feedback', '')
    sub.graded_at = datetime.utcnow()
    sub.graded_by = current_user.id
    db.session.commit()

    if sub.grade == 0:
        student = Student.query.get(student_id)
        if student:
            recipients = [student.user.email]
            parents = User.query.join(ParentStudentLink, ParentStudentLink.parent_id == User.id)\
                                .filter(ParentStudentLink.student_id == student_id).all()
            recipients.extend([p.email for p in parents])
            assignment = Assignment.query.get(aid)
            send_email(
                subject='Missing/Failed Assignment Alert - ElWood Tracking',
                sender='no-reply@gmail.com',
                recipients=recipients,
                text_body=f"Hello {student.user.name} and parents,\n\nYou have received a 0 on '{assignment.title}'. Please ensure this assignment is submitted or contact your teacher."
            )

    flash('Grade saved.', 'success')
    return redirect(url_for('teacher.assignment_submissions', aid=aid))


@bp.route('/assignments/<int:aid>/delete', methods=['POST'])
@teacher_required
def delete_assignment(aid):
    a = Assignment.query.get_or_404(aid)
    db.session.delete(a)
    db.session.commit()
    flash('Assignment deleted.', 'info')
    return redirect(url_for('teacher.assignments'))


# ─── Report Comments ──────────────────────────────────────────────────────────
@bp.route('/report-comments')
@teacher_required
def report_comments():
    sections = get_teacher_sections()
    selected_section_id = request.args.get('section_id', type=int)
    selected_term_id = request.args.get('term_id', type=int)
    terms = AcademicTerm.query.filter_by(school_id=current_user.school_id).all()
    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()
    students = []
    comment_map = {}

    if selected_section_id:
        students = Student.query.filter_by(section_id=selected_section_id).all()
        tid = selected_term_id or (active_term.id if active_term else None)
        if tid:
            comments = ReportComment.query.filter_by(teacher_id=current_user.id, term_id=tid)\
                .filter(ReportComment.student_id.in_([s.id for s in students])).all()
            comment_map = {c.student_id: c for c in comments}

    return render_template('teacher/report_comments.html',
                           sections=sections, students=students, comment_map=comment_map,
                           terms=terms, active_term=active_term,
                           selected_section_id=selected_section_id,
                           selected_term_id=selected_term_id)


@bp.route('/report-comments/save', methods=['POST'])
@teacher_required
def save_report_comments():
    section_id = request.form.get('section_id', type=int)
    term_id = request.form.get('term_id', type=int)
    students = Student.query.filter_by(section_id=section_id).all()

    for student in students:
        comment_text = request.form.get(f'comment_{student.id}', '').strip()
        if comment_text:
            existing = ReportComment.query.filter_by(
                student_id=student.id, teacher_id=current_user.id, term_id=term_id).first()
            if existing:
                existing.comment = comment_text
            else:
                c = ReportComment(
                    student_id=student.id,
                    teacher_id=current_user.id,
                    term_id=term_id,
                    comment=comment_text
                )
                db.session.add(c)

    db.session.commit()
    flash('Comments saved.', 'success')
    return redirect(url_for('teacher.report_comments',
                            section_id=section_id, term_id=term_id))


# ─── Student Details ──────────────────────────────────────────────────────────
@bp.route('/student/<int:student_id>')
@teacher_required
def student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    terms = AcademicTerm.query.filter_by(school_id=current_user.school_id).all()
    active_term = AcademicTerm.query.filter_by(school_id=current_user.school_id, is_active=True).first()
    grades = Grade.query.filter_by(student_id=student_id).order_by(Grade.date.desc()).all()
    attendance = Attendance.query.filter_by(student_id=student_id).order_by(Attendance.date.desc()).limit(30).all()

    # Attendance summary
    total = Attendance.query.filter_by(student_id=student_id).count()
    present = Attendance.query.filter_by(student_id=student_id, status='present').count()
    att_pct = round((present / total * 100), 1) if total > 0 else 0

    return render_template('teacher/student_detail.html',
                           student=student, grades=grades, attendance=attendance,
                           terms=terms, active_term=active_term,
                           att_pct=att_pct, total_att=total)


# ─── Micro-Credentials ────────────────────────────────────────────────────────
@bp.route('/credentials')
@teacher_required
def credentials():
    sections = get_teacher_sections()
    students_by_section = {}
    for sec in sections:
        students_by_section[sec.id] = Student.query.filter_by(section_id=sec.id).all()
        
    my_issued = MicroCredential.query.filter_by(issued_by=current_user.id).order_by(MicroCredential.issued_date.desc()).all()
    return render_template('teacher/credentials.html', sections=sections, students_by_section=students_by_section, my_issued=my_issued)

@bp.route('/credentials/issue', methods=['POST'])
@teacher_required
def issue_credential():
    c = MicroCredential(
        student_id=request.form.get('student_id', type=int),
        title=request.form.get('title', '').strip(),
        description=request.form.get('description', '').strip(),
        category=request.form.get('category', 'Skill'),
        issued_date=date.today(),
        issued_by=current_user.id
    )
    db.session.add(c)
    db.session.commit()
    flash('Micro-Credential successfully generated and issued to the student!', 'success')
    return redirect(url_for('teacher.credentials'))


# ─── Soft Skills ──────────────────────────────────────────────────────────────
@bp.route('/soft-skills')
@teacher_required
def soft_skills():
    sections = get_teacher_sections()
    selected_section_id = request.args.get('section_id', type=int)
    selected_date_str = request.args.get('date', date.today().isoformat())
    selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()

    students = []
    skills_map = {}

    if selected_section_id:
        students = Student.query.filter_by(section_id=selected_section_id).all()
        # Find metrics for the week of selected_date
        records = SoftSkillMetric.query.filter(
            SoftSkillMetric.student_id.in_([s.id for s in students]), 
            SoftSkillMetric.week_ending == selected_date
        ).all()
        skills_map = {r.student_id: r for r in records}

    return render_template('teacher/soft_skills.html',
                           sections=sections, students=students,
                           skills_map=skills_map,
                           selected_section_id=selected_section_id,
                           selected_date=selected_date)


@bp.route('/soft-skills/save', methods=['POST'])
@teacher_required
def save_soft_skills():
    section_id = request.form.get('section_id', type=int)
    date_str = request.form.get('date')
    week_ending = datetime.strptime(date_str, '%Y-%m-%d').date()
    students = Student.query.filter_by(section_id=section_id).all()

    for student in students:
        leadership = request.form.get(f'leadership_{student.id}', 5.0, type=float)
        discipline = request.form.get(f'discipline_{student.id}', 5.0, type=float)
        communication = request.form.get(f'communication_{student.id}', 5.0, type=float)
        teamwork = request.form.get(f'teamwork_{student.id}', 5.0, type=float)
        hours = request.form.get(f'hours_{student.id}', 0.0, type=float)

        existing = SoftSkillMetric.query.filter_by(student_id=student.id, week_ending=week_ending).first()
        if existing:
            existing.leadership = leadership
            existing.discipline = discipline
            existing.communication = communication
            existing.teamwork = teamwork
            existing.participation_hours = hours
            existing.recorded_by = current_user.id
        else:
            metric = SoftSkillMetric(
                student_id=student.id,
                week_ending=week_ending,
                leadership=leadership,
                discipline=discipline,
                communication=communication,
                teamwork=teamwork,
                participation_hours=hours,
                recorded_by=current_user.id
            )
            db.session.add(metric)
        
        broadcast_student_update(student)

    db.session.commit()
    flash('Soft skills recorded and holistic scores updated!', 'success')
    return redirect(url_for('teacher.soft_skills', section_id=section_id, date=date_str))
