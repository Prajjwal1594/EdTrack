from app import create_app, db
from app.models import User, StaffProfile

app = create_app()
with app.app_context():
    u = User.query.filter_by(email='hr@elwood.com').first()
    if not u:
        u = User(
            name='HR Manager',
            email='hr@elwood.com',
            role='hr',
            school_id=1
        )
        u.set_password('Password123!')
        db.session.add(u)
        db.session.commit()
        print('Success: Created hr@elwood.com')
    else:
        u.set_password('Password123!')
        db.session.commit()
        print('User already exists, password reset to Password123!')
