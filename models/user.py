from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import json
import os
import logging

class User(UserMixin):
    """User class for authentication"""
    USERS_FILE = 'data/users.json'
    logger = logging.getLogger(__name__)

    def __init__(self, id, email, password_hash, name=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.name = name

    @staticmethod
    def get(user_id):
        try:
            users = User.load_users()
            user_data = users.get(str(user_id))
            if user_data:
                return User(
                    id=user_id,
                    email=user_data['email'],
                    password_hash=user_data['password_hash'],
                    name=user_data.get('name')
                )
            User.logger.warning(f"No user found with ID: {user_id}")
            return None
        except Exception as e:
            User.logger.error(f"Error getting user {user_id}: {str(e)}")
            return None

    @staticmethod
    def get_by_email(email):
        try:
            users = User.load_users()
            for user_id, user_data in users.items():
                if user_data['email'] == email:
                    return User(
                        id=user_id,
                        email=user_data['email'],
                        password_hash=user_data['password_hash'],
                        name=user_data.get('name')
                    )
            User.logger.warning(f"No user found with email: {email}")
            return None
        except Exception as e:
            User.logger.error(f"Error getting user by email {email}: {str(e)}")
            return None

    def set_password(self, password):
        try:
            self.password_hash = generate_password_hash(password)
        except Exception as e:
            User.logger.error(f"Error setting password: {str(e)}")
            raise

    def check_password(self, password):
        try:
            return check_password_hash(self.password_hash, password)
        except Exception as e:
            User.logger.error(f"Error checking password: {str(e)}")
            return False

    def save(self):
        try:
            users = self.load_users()
            users[str(self.id)] = {
                'email': self.email,
                'password_hash': self.password_hash,
                'name': self.name
            }
            self.save_users(users)
            User.logger.info(f"User {self.id} saved successfully")
            return True
        except Exception as e:
            User.logger.error(f"Error saving user {self.id}: {str(e)}")
            return False

    @staticmethod
    def load_users():
        try:
            if not os.path.exists('data'):
                os.makedirs('data')
                User.logger.info("Created data directory")

            if not os.path.exists(User.USERS_FILE):
                User.logger.info("Users file not found, creating empty file")
                User.save_users({})

            with open(User.USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            User.logger.error(f"Error loading users: {str(e)}")
            return {}

    @staticmethod
    def save_users(users):
        try:
            if not os.path.exists('data'):
                os.makedirs('data')

            with open(User.USERS_FILE, 'w') as f:
                json.dump(users, f, indent=4)
            User.logger.info("Users saved successfully")
        except Exception as e:
            User.logger.error(f"Error saving users: {str(e)}")
            raise

    @staticmethod
    def create(email, password, name=None):
        try:
            users = User.load_users()
            # Check if email already exists
            for user_data in users.values():
                if user_data['email'] == email:
                    User.logger.warning(f"Email already exists: {email}")
                    return None

            # Generate new user ID
            user_id = str(len(users) + 1)
            user = User(id=user_id, email=email, password_hash=None, name=name)
            user.set_password(password)
            if user.save():
                User.logger.info(f"Created new user with ID: {user_id}")
                return user
            return None
        except Exception as e:
            User.logger.error(f"Error creating user: {str(e)}")
            return None