import os
import csv
import logging
import pandas as pd
from datetime import datetime
from config import DENTIST_LEADS_FILE, SAAS_LEADS_FILE, OUTPUT_DIR

class LeadManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._ensure_output_dir()
        self.email_dir = os.path.join(OUTPUT_DIR, 'emails')
        self._ensure_email_dir()

    def _ensure_output_dir(self):
        """Ensure output directory exists"""
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

    def _ensure_email_dir(self):
        """Ensure email output directory exists"""
        if not os.path.exists(self.email_dir):
            os.makedirs(self.email_dir)

    def save_leads(self, leads, lead_type):
        """Save leads to CSV file"""
        try:
            if not leads:
                self.logger.warning(f"No {lead_type} leads to save")
                return False

            filename = DENTIST_LEADS_FILE if lead_type == 'dentist' else SAAS_LEADS_FILE

            # Add timestamp to leads
            for lead in leads:
                lead['timestamp'] = datetime.now().isoformat()

            # Determine if file exists to handle headers
            file_exists = os.path.exists(filename)

            mode = 'a' if file_exists else 'w'
            with open(filename, mode, newline='') as f:
                writer = csv.DictWriter(f, fieldnames=leads[0].keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerows(leads)

            self.logger.info(f"Saved {len(leads)} {lead_type} leads to {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving {lead_type} leads: {str(e)}")
            return False

    def save_email(self, lead_id, lead_type, subject, content):
        """Save generated email content to file"""
        try:
            if not lead_id or not lead_type or not content:
                self.logger.warning("Missing required parameters for saving email")
                return False

            filename = os.path.join(
                self.email_dir, 
                f"{lead_type}_{lead_id}_email.txt"
            )

            with open(filename, 'w') as f:
                f.write(f"Subject: {subject}\n\n")
                f.write(content)

            self.logger.info(f"Saved email content to {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving email content: {str(e)}")
            return False

    def get_leads(self, lead_type, limit=None):
        """Retrieve leads from CSV file"""
        try:
            filename = DENTIST_LEADS_FILE if lead_type == 'dentist' else SAAS_LEADS_FILE
            if not os.path.exists(filename):
                self.logger.warning(f"Leads file {filename} does not exist")
                return []

            df = pd.read_csv(filename)
            if limit:
                df = df.head(limit)

            return df.to_dict('records')

        except Exception as e:
            self.logger.error(f"Error retrieving {lead_type} leads: {str(e)}")
            return []

    def mark_lead_contacted(self, lead_id, lead_type, status):
        """Mark a lead as contacted"""
        try:
            if not lead_id:
                self.logger.warning("No lead ID provided for marking as contacted")
                return False

            filename = DENTIST_LEADS_FILE if lead_type == 'dentist' else SAAS_LEADS_FILE
            df = pd.read_csv(filename)
            df.loc[df['id'] == lead_id, 'contacted'] = status
            df.loc[df['id'] == lead_id, 'contacted_date'] = datetime.now().isoformat()
            df.to_csv(filename, index=False)
            return True

        except Exception as e:
            self.logger.error(f"Error marking lead as contacted: {str(e)}")
            return False