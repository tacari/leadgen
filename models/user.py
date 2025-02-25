from flask_login import UserMixin
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, id, email, password_hash, name=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.name = name

    @staticmethod
    def get(user_id):
        try:
            with open('data/users.json', 'r') as f:
                users = json.load(f)
                user_data = users.get(str(user_id))
                if user_data:
                    return User(
                        id=user_id,
                        email=user_data['email'],
                        password_hash=user_data['password_hash'],
                        name=user_data.get('name')
                    )
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def get_by_email(email):
        try:
            with open('data/users.json', 'r') as f:
                users = json.load(f)
                for user_id, user_data in users.items():
                    if user_data['email'] == email:
                        return User(
                            id=user_id,
                            email=user_data['email'],
                            password_hash=user_data['password_hash'],
                            name=user_data.get('name')
                        )
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def create(email, password, name=None):
        try:
            with open('data/users.json', 'r') as f:
                users = json.load(f)
        except FileNotFoundError:
            users = {}

        # Check if email already exists
        for user_data in users.values():
            if user_data['email'] == email:
                return None

        # Generate new user ID
        user_id = str(len(users) + 1)
        password_hash = generate_password_hash(password)

        # Create new user
        users[user_id] = {
            'email': email,
            'password_hash': password_hash,
            'name': name
        }

        # Save to file
        with open('data/users.json', 'w') as f:
            json.dump(users, f, indent=4)

        return User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            name=name
        )

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)