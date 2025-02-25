from flask_login import UserMixin
import json
import os
import sys
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
            print(f"Attempting to load user with ID: {user_id}", file=sys.stderr)
            with open('data/users.json', 'r') as f:
                users = json.load(f)
                user_data = users.get(str(user_id))
                if user_data:
                    print(f"Found user data: {user_data['email']}", file=sys.stderr)
                    return User(
                        id=user_id,
                        email=user_data['email'],
                        password_hash=user_data['password_hash'],
                        name=user_data.get('name')
                    )
        except FileNotFoundError:
            print("users.json not found, creating empty file", file=sys.stderr)
            # Create the file if it doesn't exist
            with open('data/users.json', 'w') as f:
                json.dump({}, f)
            return None
        except Exception as e:
            print(f"Error loading user: {str(e)}", file=sys.stderr)
            return None
        print(f"User {user_id} not found", file=sys.stderr)
        return None

    @staticmethod
    def get_by_email(email):
        try:
            print(f"Looking up user by email: {email}", file=sys.stderr)
            with open('data/users.json', 'r') as f:
                users = json.load(f)
                for user_id, user_data in users.items():
                    if user_data['email'] == email:
                        print(f"Found user with matching email", file=sys.stderr)
                        return User(
                            id=user_id,
                            email=user_data['email'],
                            password_hash=user_data['password_hash'],
                            name=user_data.get('name')
                        )
        except FileNotFoundError:
            print("users.json not found, creating empty file", file=sys.stderr)
            # Create the file if it doesn't exist
            with open('data/users.json', 'w') as f:
                json.dump({}, f)
            return None
        except Exception as e:
            print(f"Error looking up user by email: {str(e)}", file=sys.stderr)
            return None
        print(f"No user found with email: {email}", file=sys.stderr)
        return None

    @staticmethod
    def create(email, password, name=None):
        try:
            print(f"Attempting to create user with email: {email}", file=sys.stderr)
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)

            # Load existing users
            try:
                with open('data/users.json', 'r') as f:
                    users = json.load(f)
                    print(f"Loaded existing users: {len(users)} found", file=sys.stderr)
            except FileNotFoundError:
                print("users.json not found, starting with empty dict", file=sys.stderr)
                users = {}

            # Check if email already exists
            for user_data in users.values():
                if user_data['email'] == email:
                    print(f"Email {email} already registered", file=sys.stderr)
                    return None

            # Generate new user ID
            user_id = str(len(users) + 1)
            password_hash = generate_password_hash(password, method='scrypt')

            # Create new user
            users[user_id] = {
                'email': email,
                'password_hash': password_hash,
                'name': name
            }

            # Save to file
            with open('data/users.json', 'w') as f:
                json.dump(users, f, indent=4)
            print(f"Successfully created user with ID: {user_id}", file=sys.stderr)

            return User(
                id=user_id,
                email=email,
                password_hash=password_hash,
                name=name
            )
        except Exception as e:
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