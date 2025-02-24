import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from config import SENDGRID_API_KEY, FROM_EMAIL, MAX_EMAILS_PER_DAY

class EmailSender:
    def __init__(self):
        self.sg = SendGridAPIClient(SENDGRID_API_KEY)
        self.logger = logging.getLogger(__name__)
        self.emails_sent_today = 0

    def send_email(self, to_email, subject, content):
        """Send email using SendGrid"""
        if self.emails_sent_today >= MAX_EMAILS_PER_DAY:
            self.logger.warning("Daily email limit reached")
            return False

        try:
            message = Mail(
                from_email=Email(FROM_EMAIL),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", content)
            )

            response = self.sg.send(message)
            if response.status_code in [200, 201, 202]:
                self.emails_sent_today += 1
                self.logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                self.logger.error(f"Failed to send email to {to_email}: {response.status_code}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False

    def send_batch(self, emails):
        """Send a batch of emails"""
        results = []
        for email in emails:
            success = self.send_email(
                email['to_email'],
                email['subject'],
                email['content']
            )
            results.append({
                'to_email': email['to_email'],
                'success': success
            })
        return results
