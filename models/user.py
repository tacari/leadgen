from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import sys

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(120))

    def __init__(self, email, password_hash, name=None):
        self.email = email
        self.password_hash = password_hash
        self.name = name

    @staticmethod
    def get(user_id):
        try:
            print(f"Loading user with ID: {user_id}", file=sys.stderr)
            user = User.query.get(int(user_id))
            print(f"User loaded: {user is not None}", file=sys.stderr)
            return user
        except Exception as e:
            print(f"Error loading user: {str(e)}", file=sys.stderr)
            return None

    @staticmethod
    def get_by_email(email):
        try:
            print(f"Looking up user by email: {email}", file=sys.stderr)
            user = User.query.filter_by(email=email).first()
            print(f"User found: {user is not None}", file=sys.stderr)
            return user
        except Exception as e:
            print(f"Error looking up user by email: {str(e)}", file=sys.stderr)
            return None

    @staticmethod
    def create(email, password, name=None):
        try:
            print(f"Attempting to create user with email: {email}", file=sys.stderr)
            if User.query.filter_by(email=email).first():
                print(f"Email {email} already registered", file=sys.stderr)
                return None

            password_hash = generate_password_hash(password, method='scrypt')
            user = User(email=email, password_hash=password_hash, name=name)
            db.session.add(user)
            db.session.commit()
            print(f"Successfully created user with ID: {user.id}", file=sys.stderr)
            return user
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {str(e)}", file=sys.stderr)
            return None

    def check_password(self, password):
        try:
            print(f"Checking password for user: {self.email}", file=sys.stderr)
            result = check_password_hash(self.password_hash, password)
            print(f"Password check result: {result}", file=sys.stderr)
            return result
        except Exception as e:
            print(f"Error checking password: {str(e)}", file=sys.stderr)
            return False