import json
from datetime import datetime

class UserPackage:
    def __init__(self, id, user_id, package_name, lead_volume, stripe_subscription_id=None):
        self.id = id
        self.user_id = user_id
        self.package_name = package_name
        self.lead_volume = lead_volume
        self.stripe_subscription_id = stripe_subscription_id

    @staticmethod
    def get_by_user_id(user_id):
        try:
            with open('data/user_packages.json', 'r') as f:
                packages = json.load(f)
                for package_id, package_data in packages.items():
                    if package_data['user_id'] == user_id:
                        return UserPackage(
                            id=package_id,
                            user_id=user_id,
                            package_name=package_data['package_name'],
                            lead_volume=package_data['lead_volume'],
                            stripe_subscription_id=package_data.get('stripe_subscription_id')
                        )
        except FileNotFoundError:
            return None
        return None

    @staticmethod
    def create(user_id, package_name, lead_volume, stripe_subscription_id=None):
        try:
            with open('data/user_packages.json', 'r') as f:
                packages = json.load(f)
        except FileNotFoundError:
            packages = {}

        package_id = str(len(packages) + 1)
        packages[package_id] = {
            'user_id': user_id,
            'package_name': package_name,
            'lead_volume': lead_volume,
            'stripe_subscription_id': stripe_subscription_id
        }

        with open('data/user_packages.json', 'w') as f:
            json.dump(packages, f, indent=4)

        return UserPackage(
            id=package_id,
            user_id=user_id,
            package_name=package_name,
            lead_volume=lead_volume,
            stripe_subscription_id=stripe_subscription_id
        )
