from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app.timetable import bp
from app.models import db, TimetableSlot, Section, Subject, User, School, Class
from datetime import datetime, time

@bp.route('/')
@login_required
def index():
    if current_user.role == 'student':
        section_id = current_user.student_profile.section_id
        return redirect(url_for('timetable.view_section', section_id=section_id))
    elif current_user.role == 'parent':
        # For simplicity, view first student's timetable
        link = current_user.student_links.first()
        if not link:
            flash('No students linked to your account.', 'warning')
            return redirect(url_for('auth.dashboard'))
        return redirect(url_for('timetable.view_section', section_id=link.student.section_id))
    elif current_user.role in ['admin', 'teacher']:
        sections = Section.query.join(Class).filter(Class.school_id == current_user.school_id).all()
        return render_template('timetable/index.html', sections=sections)
    return abort(403)

@bp.route('/section/<int:section_id>')
@login_required
def view_section(section_id):
    section = Section.query.get_or_404(section_id)
    if section.class_.school_id != current_user.school_id:
        abort(403)
    
    slots = TimetableSlot.query.filter_by(section_id=section_id).all()
    
    # Organize slots by day and time
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    timetable = {day: [] for day in days}
    for slot in slots:
        if slot.day_of_week in timetable:
            timetable[slot.day_of_week].append(slot)
            
    # Sort slots by start time
    for day in timetable:
        timetable[day].sort(key=lambda x: x.start_time)
        
    return render_template('timetable/view.html', section=section, timetable=timetable, days=days)

@bp.route('/manage/<int:section_id>', methods=['GET', 'POST'])
@login_required
def manage(section_id):
    if current_user.role not in ['admin', 'teacher']:
        abort(403)
        
    section = Section.query.get_or_404(section_id)
    if section.class_.school_id != current_user.school_id:
        abort(403)
        
    if request.method == 'POST':
        day = request.form.get('day')
        subject_id = request.form.get('subject_id')
        teacher_id = request.form.get('teacher_id')
        start_str = request.form.get('start_time')
        end_str = request.form.get('end_time')
        room = request.form.get('room_number')
        
        try:
            start_time = datetime.strptime(start_str, '%H:%M').time()
            end_time = datetime.strptime(end_str, '%H:%M').time()
            
            new_slot = TimetableSlot(
                school_id=current_user.school_id,
                section_id=section_id,
                subject_id=subject_id,
                teacher_id=teacher_id,
                day_of_week=day,
                start_time=start_time,
                end_time=end_time,
                room_number=room
            )
            db.session.add(new_slot)
            db.session.commit()
            flash('Timetable slot added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding slot: {str(e)}', 'danger')
            
        return redirect(url_for('timetable.manage', section_id=section_id))
        
    slots = TimetableSlot.query.filter_by(section_id=section_id).order_by(TimetableSlot.start_time).all()
    subjects = Subject.query.filter_by(school_id=current_user.school_id).all()
    teachers = User.query.filter_by(school_id=current_user.school_id, role='teacher').all()
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    return render_template('timetable/manage.html', 
                           section=section, 
                           slots=slots, 
                           subjects=subjects, 
                           teachers=teachers,
                           days=days)

@bp.route('/delete/<int:slot_id>', methods=['POST'])
@login_required
def delete_slot(slot_id):
    if current_user.role not in ['admin', 'teacher']:
        abort(403)
    slot = TimetableSlot.query.get_or_404(slot_id)
    if slot.school_id != current_user.school_id:
        abort(403)
    
    section_id = slot.section_id
    db.session.delete(slot)
    db.session.commit()
    flash('Slot deleted.', 'info')
    return redirect(url_for('timetable.manage', section_id=section_id))
