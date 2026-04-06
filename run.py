from app import create_app, db, socketio
from app.models import User, School, Class, Section, Subject, Student

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'School': School,
            'Class': Class, 'Section': Section, 'Subject': Subject, 'Student': Student}

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
