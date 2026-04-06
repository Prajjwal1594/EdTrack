from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class School(db.Model):
    __tablename__ = 'schools'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    logo_url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship('User', backref='school', lazy='dynamic')
    classes = db.relationship('Class', backref='school', lazy='dynamic')
    subjects = db.relationship('Subject', backref='school', lazy='dynamic')
    terms = db.relationship('AcademicTerm', backref='school', lazy='dynamic')
    fee_types = db.relationship('FeeType', backref='school', lazy='dynamic')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student, parent
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    is_active = db.Column(db.Boolean, default=True)
    avatar = db.Column(db.String(300))
    phone = db.Column(db.String(30))
    wallet_balance = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    # Relationships
    student_profile = db.relationship('Student', foreign_keys='Student.user_id', backref='user', uselist=False)
    teacher_assignments = db.relationship('TeacherAssignment', foreign_keys='TeacherAssignment.teacher_id', backref='teacher')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    student_links = db.relationship('ParentStudentLink', foreign_keys='ParentStudentLink.parent_id', backref='parent', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def unread_message_count(self):
        return Message.query.filter_by(recipient_id=self.id, read_at=None).count()

    @property
    def unread_notification_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def __repr__(self):
        return f'<User {self.name} ({self.role})>'


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sections = db.relationship('Section', backref='class_', lazy='dynamic')

    def __repr__(self):
        return f'<Class {self.name}>'


class Section(db.Model):
    __tablename__ = 'sections'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    name = db.Column(db.String(10), nullable=False)
    room_number = db.Column(db.String(20))
    capacity = db.Column(db.Integer, default=40)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='section', lazy='dynamic')
    teacher_assignments = db.relationship('TeacherAssignment', backref='section')
    attendance_records = db.relationship('Attendance', backref='section', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='section', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.class_.name} - {self.name}"

    def __repr__(self):
        return f'<Section {self.full_name}>'


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20))
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher_assignments = db.relationship('TeacherAssignment', backref='subject')
    grades = db.relationship('Grade', backref='subject', lazy='dynamic')
    assignments = db.relationship('Assignment', backref='subject', lazy='dynamic')
    exams = db.relationship('Exam', backref='subject', lazy='dynamic')

    def __repr__(self):
        return f'<Subject {self.name}>'


class TeacherAssignment(db.Model):
    __tablename__ = 'teacher_assignments'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    academic_year = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    enrollment_number = db.Column(db.String(30), unique=True)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    address = db.Column(db.Text)
    enrollment_date = db.Column(db.Date, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    parent_links = db.relationship('ParentStudentLink', backref='student', lazy='dynamic')
    grades = db.relationship('Grade', backref='student', lazy='dynamic')
    attendance_records = db.relationship('Attendance', backref='student', lazy='dynamic')
    assignment_submissions = db.relationship('AssignmentSubmission', backref='student', lazy='dynamic')
    exam_submissions = db.relationship('ExamSubmission', backref='student', lazy='dynamic')
    fee_payments = db.relationship('FeePayment', backref='student', lazy='dynamic')
    report_comments = db.relationship('ReportComment', backref='student', lazy='dynamic')
    credentials = db.relationship('MicroCredential', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    soft_skills = db.relationship('SoftSkillMetric', backref='student', lazy='dynamic', cascade='all, delete-orphan')

    def holistic_growth_score(self):
        """
        Calculates a 0-100 Holistic Growth Score:
        40% Academic (Avg Grade % + Attendance %)
        35% Soft Skills (Avg of Leadership, Discipline, etc.)
        25% Co-Curricular (Micro-Credentials & Participation Hours)
        """
        # 1. Academic (40%)
        # Calculate avg grade percentage
        grade_records = self.grades.all()
        avg_grade = sum(g.percentage for g in grade_records) / len(grade_records) if grade_records else 75.0
        
        # Calculate attendance percentage
        att_total = self.attendance_records.count()
        att_present = self.attendance_records.filter(Attendance.status.in_(['present', 'late'])).count()
        attendance_pct = (att_present / att_total * 100) if att_total > 0 else 100.0
        
        academic_comp = (0.7 * avg_grade / 100.0) + (0.3 * attendance_pct / 100.0)

        # 2. Soft Skills (35%)
        latest_skills = self.soft_skills.order_by(SoftSkillMetric.week_ending.desc()).first()
        if latest_skills:
            skills_avg = (latest_skills.leadership + latest_skills.discipline + 
                          latest_skills.communication + latest_skills.teamwork) / 40.0 # 0-1 scale
            participation_hours = min(latest_skills.participation_hours / 15.0, 1.0)
        else:
            skills_avg = 0.5
            participation_hours = 0.0

        # 3. Co-Curricular (25%)
        # Each credential adds a bonus
        cred_count = self.credentials.count()
        cred_bonus = min(cred_count * 2.0, 10.0) # Max 10 points bonus

        raw_score = (0.40 * academic_comp + 0.35 * skills_avg + 0.25 * participation_hours) * 100.0
        final_score = min(raw_score + cred_bonus, 100.0)
        
        return round(final_score, 1)

    @property
    def holistic_rating(self):
        score = self.holistic_growth_score()
        if score >= 90: return 'Exceptional'
        if score >= 80: return 'Excellent'
        if score >= 70: return 'Good'
        if score >= 60: return 'Average'
        return 'Needs Focus'


class ParentStudentLink(db.Model):
    __tablename__ = 'parent_student_links'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    relationship_type = db.Column(db.String(30), default='parent')


class AcademicTerm(db.Model):
    __tablename__ = 'academic_terms'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    name = db.Column(db.String(50), nullable=False)
    term_type = db.Column(db.String(20), default='term')  # term, semester, quarter
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    academic_year = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    grades = db.relationship('Grade', backref='term', lazy='dynamic')
    report_comments = db.relationship('ReportComment', backref='term', lazy='dynamic')
    fee_payments = db.relationship('FeePayment', backref='term', lazy='dynamic')


class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('academic_terms.id'))
    exam_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Float, nullable=False)  # 0-100
    max_score = db.Column(db.Float, default=100)
    date = db.Column(db.Date, default=datetime.utcnow)
    remarks = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def percentage(self):
        if self.max_score and self.max_score > 0:
            return round((self.score / self.max_score) * 100, 1)
        return self.score

    @property
    def letter_grade(self):
        p = self.percentage
        if p >= 90: return 'A+'
        elif p >= 80: return 'A'
        elif p >= 70: return 'B+'
        elif p >= 60: return 'B'
        elif p >= 50: return 'C'
        elif p >= 40: return 'D'
        else: return 'F'


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=False)
    max_score = db.Column(db.Float, default=100)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    submissions = db.relationship('AssignmentSubmission', backref='assignment', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def is_overdue(self):
        return datetime.utcnow() > self.due_date


class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    grade = db.Column(db.Float)
    feedback = db.Column(db.Text)
    content = db.Column(db.Text)  # submission text
    is_late = db.Column(db.Boolean, default=False)
    graded_at = db.Column(db.DateTime)
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'))


class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # present, absent, late, excused
    remarks = db.Column(db.String(200))
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('student_id', 'date', name='uq_student_date'),)

    marker = db.relationship('User', foreign_keys=[marked_by])


class ReportComment(db.Model):
    __tablename__ = 'report_comments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('academic_terms.id'))
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship('User', foreign_keys=[teacher_id])


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)
    parent_id = db.Column(db.Integer, db.ForeignKey('messages.id'))
    message_type = db.Column(db.String(20), default='regular')  # regular, digest
    is_deleted_sender = db.Column(db.Boolean, default=False)
    is_deleted_recipient = db.Column(db.Boolean, default=False)

    replies = db.relationship('Message', backref=db.backref('parent', remote_side=[id]))


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    type = db.Column(db.String(50))  # low_grade, absent, missing_assignment, fee_due
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    description = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, default=60)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    total_marks = db.Column(db.Float, default=100)
    is_published = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('ExamQuestion', backref='exam', lazy='dynamic', cascade='all, delete-orphan')
    submissions = db.relationship('ExamSubmission', backref='exam', lazy='dynamic')
    creator = db.relationship('User', foreign_keys=[created_by])
    section = db.relationship('Section', foreign_keys=[section_id])

    @property
    def is_active(self):
        now = datetime.utcnow()
        if self.start_time and self.end_time:
            return self.start_time <= now <= self.end_time and self.is_published
        return self.is_published


class ExamQuestion(db.Model):
    __tablename__ = 'exam_questions'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'))
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='mcq')  # mcq, true_false, short_answer
    options_json = db.Column(db.Text)  # JSON list of options for MCQ
    correct_answer = db.Column(db.String(500))
    marks = db.Column(db.Float, default=1)
    order_num = db.Column(db.Integer, default=0)

    @property
    def options(self):
        if self.options_json:
            return json.loads(self.options_json)
        return []

    @options.setter
    def options(self, value):
        self.options_json = json.dumps(value)


class ExamSubmission(db.Model):
    __tablename__ = 'exam_submissions'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'))
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Float)
    answers_json = db.Column(db.Text)
    is_graded = db.Column(db.Boolean, default=False)

    @property
    def answers(self):
        if self.answers_json:
            return json.loads(self.answers_json)
        return {}

    @answers.setter
    def answers(self, value):
        self.answers_json = json.dumps(value)

    @property
    def percentage(self):
        if self.exam and self.exam.total_marks and self.score is not None:
            return round((self.score / self.exam.total_marks) * 100, 1)
        return None


class FeeType(db.Model):
    __tablename__ = 'fee_types'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), default='term')  # monthly, term, annual
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship('FeePayment', backref='fee_type', lazy='dynamic')


class FeePayment(db.Model):
    __tablename__ = 'fee_payments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'))
    term_id = db.Column(db.Integer, db.ForeignKey('academic_terms.id'))
    amount = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.DateTime)
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')  # pending, paid, overdue, waived
    payment_method = db.Column(db.String(50))
    transaction_ref = db.Column(db.String(100))
    notes = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MicroCredential(db.Model):
    __tablename__ = 'micro_credentials'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='Skill')  # Leadership, Tech, Arts, etc.
    issued_date = db.Column(db.Date)
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    issuer = db.relationship('User', foreign_keys=[issued_by])


class SoftSkillMetric(db.Model):
    __tablename__ = 'soft_skill_metrics'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    week_ending = db.Column(db.Date, nullable=False)
    leadership = db.Column(db.Float, default=5.0)  # 0-10
    discipline = db.Column(db.Float, default=5.0)
    communication = db.Column(db.Float, default=5.0)
    teamwork = db.Column(db.Float, default=5.0)
    participation_hours = db.Column(db.Float, default=0.0)
    remarks = db.Column(db.Text)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recorder = db.relationship('User', foreign_keys=[recorded_by])


class TimetableSlot(db.Model):
    __tablename__ = 'timetable_slots'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'))
    section_id = db.Column(db.Integer, db.ForeignKey('sections.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    day_of_week = db.Column(db.String(10), nullable=False)  # Monday, Tuesday, etc.
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room_number = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school = db.relationship('School')
    section = db.relationship('Section')
    subject = db.relationship('Subject')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
