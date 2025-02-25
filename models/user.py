from flask_login import UserMixin
import json
import os

class User(UserMixin):
    def __init__(self, id, email, password_hash, name=None):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.name = name

    @staticmethod
    def get(user_id):
        return None

    @staticmethod
    def get_by_email(email):
        return None

    @staticmethod
    def create(email, password, name=None):
        return None