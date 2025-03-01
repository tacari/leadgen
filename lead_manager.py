import os
import logging
import psycopg2
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
import csv
import io
from crm_integration import add_lead_to_hubspot, update_lead_status, notify_slack

class LeadManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()
        self.sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))

    def get_due_deliveries(self):
        """Get all packages due for lead delivery"""
        try:
            self.cur.execute("""
                SELECT up.user_id, up.package_name, up.lead_volume, u.email
                FROM user_packages up
                JOIN users u ON u.id = up.user_id
                WHERE up.next_delivery <= NOW()
            """)
            return self.cur.fetchall()
        except Exception as e:
            self.logger.error(f"Error getting due deliveries: {str(e)}")
            return []

    def get_leads_for_user(self, user_id, limit=None):
        """Get leads for a specific user"""
        try:
            query = """
                SELECT id, name, email, source, score, verified, status, date_added
                FROM leads
                WHERE user_id = %s AND status = 'Pending'
                ORDER BY date_added DESC
            """
            if limit:
                query += " LIMIT %s"
                self.cur.execute(query, (user_id, limit))
            else:
                self.cur.execute(query, (user_id,))

            return [dict(zip([
                'id', 'name', 'email', 'source', 'score',
                'verified', 'status', 'date_added'
            ], row)) for row in self.cur.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting leads for user: {str(e)}")
            return []

    def send_lead_email(self, user_email, leads, package_name):
        """Send leads via email"""
        try:
            # Generate CSV
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Name', 'Email', 'Source', 'Score', 'Verified', 'Status', 'Date Added'])
            for lead in leads:
                writer.writerow([
                    lead['name'], lead['email'], lead['source'],
                    lead['score'], lead['verified'], lead['status'],
                    lead['date_added'].strftime('%Y-%m-%d %H:%M:%S')
                ])
            csv_content = output.getvalue()
            csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')

            # Create email
            message = Mail(
                from_email='leads@leadzap.io',
                to_emails=user_email,
                subject=f'Your {package_name} Lead Update - {datetime.now().strftime("%Y-%m-%d")}',
                html_content=f'<p>Here are your latest leads for your {package_name} package!</p>'
            )

            # Attach CSV
            attachment = Attachment(
                FileContent(csv_base64),
                FileName(f'leads_{datetime.now().strftime("%Y%m%d")}.csv'),
                FileType('text/csv'),
                Disposition('attachment')
            )
            message.attachment = attachment

            # Send email
            self.sg.send(message)
            return True
        except Exception as e:
            self.logger.error(f"Error sending lead email: {str(e)}")
            return False

    def process_scheduled_deliveries(self):
        """Process all scheduled lead deliveries"""
        deliveries = self.get_due_deliveries()
        for user_id, package_name, lead_volume, user_email in deliveries:
            try:
                # Get leads
                leads = self.get_leads_for_user(user_id, lead_volume)
                if not leads:
                    continue

                # Send email
                if self.send_lead_email(user_email, leads, package_name):
                    # Update lead status and next delivery
                    self.cur.execute("""
                        UPDATE leads SET status = 'Emailed'
                        WHERE id = ANY(%s)
                    """, ([lead['id'] for lead in leads],))

                    # Calculate next delivery based on package
                    next_delivery = datetime.now()
                    if package_name in ['Accelerator', 'Empire']:
                        next_delivery += timedelta(days=1)  # Daily
                    elif package_name == 'Engine':
                        next_delivery += timedelta(days=7)  # Weekly
                    else:  # Lead Launch
                        next_delivery += timedelta(days=30)  # One-time, set far future

                    self.cur.execute("""
                        UPDATE user_packages
                        SET next_delivery = %s
                        WHERE user_id = %s
                    """, (next_delivery, user_id))

                    # CRM Integration
                    for lead in leads:
                        try:
                            add_lead_to_hubspot(lead)
                            update_lead_status(lead['id'], 'Emailed')
                            notify_slack(f"Lead {lead['id']} sent to {user_email}")
                        except Exception as crm_error:
                            self.logger.error(f"CRM Error processing lead {lead['id']}: {crm_error}")


                    self.conn.commit()

            except Exception as e:
                self.logger.error(f"Error processing delivery for user {user_id}: {str(e)}")
                self.conn.rollback()

    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

if __name__ == "__main__":
    lead_manager = LeadManager()
    lead_manager.process_scheduled_deliveries()