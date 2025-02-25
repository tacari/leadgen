import json
from datetime import datetime

class Lead:
    def __init__(self, id, name, email, source, score, status, date_added, user_id):
        self.id = id
        self.name = name
        self.email = email
        self.source = source
        self.score = score
        self.status = status
        self.date_added = date_added
        self.user_id = user_id

    @staticmethod
    def create(name, email, source, score, user_id, status="Pending"):
        try:
            with open('data/leads.json', 'r') as f:
                leads = json.load(f)
        except FileNotFoundError:
            leads = {}

        lead_id = str(len(leads) + 1)
        leads[lead_id] = {
            'name': name,
            'email': email,
            'source': source,
            'score': score,
            'status': status,
            'date_added': datetime.utcnow().isoformat(),
            'user_id': user_id
        }

        with open('data/leads.json', 'w') as f:
            json.dump(leads, f, indent=4)

        return Lead(
            id=lead_id,
            name=name,
            email=email,
            source=source,
            score=score,
            status=status,
            date_added=datetime.utcnow(),
            user_id=user_id
        )

    @staticmethod
    def get_by_user_id(user_id):
        try:
            with open('data/leads.json', 'r') as f:
                leads = json.load(f)
                user_leads = []
                for lead_id, lead_data in leads.items():
                    if lead_data['user_id'] == user_id:
                        user_leads.append(Lead(
                            id=lead_id,
                            name=lead_data['name'],
                            email=lead_data['email'],
                            source=lead_data['source'],
                            score=lead_data['score'],
                            status=lead_data['status'],
                            date_added=datetime.fromisoformat(lead_data['date_added']),
                            user_id=lead_data['user_id']
                        ))
                return user_leads
        except FileNotFoundError:
            return []