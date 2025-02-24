import logging
import argparse
from datetime import datetime
from config import LOG_FILE, LOG_LEVEL
from scraper import LeadScraper
from email_generator import EmailGenerator
from email_sender import EmailSender
from lead_manager import LeadManager

def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        filename=LOG_FILE,
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    parser = argparse.ArgumentParser(description='Lead Generation Tool')
    parser.add_argument('--type', choices=['dentist', 'saas'], required=True,
                      help='Type of leads to generate')
    parser.add_argument('--city', help='City for dentist leads')
    parser.add_argument('--limit', type=int, help='Number of leads to generate')
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize components
        scraper = LeadScraper()
        email_gen = EmailGenerator()
        email_sender = EmailSender()
        lead_manager = LeadManager()

        # Scrape leads
        if args.type == 'dentist':
            if not args.city:
                raise ValueError("City is required for dentist leads")
            leads = scraper.scrape_dentists(args.city, args.limit)
        else:
            leads = scraper.scrape_saas(args.limit)

        # Save leads
        lead_manager.save_leads(leads, args.type)

        # Generate and send emails
        for lead in leads:
            if lead.get('email'):
                # Generate email content
                email_content = (email_gen.generate_dentist_email(lead) 
                               if args.type == 'dentist' 
                               else email_gen.generate_saas_email(lead))
                
                if email_content:
                    # Send email
                    subject = f"Grow your {'Dental Practice' if args.type == 'dentist' else 'SaaS Business'}"
                    success = email_sender.send_email(
                        lead['email'],
                        subject,
                        email_content
                    )
                    
                    # Update lead status
                    if success:
                        lead_manager.mark_lead_contacted(
                            lead.get('id'),
                            args.type,
                            True
                        )

        logger.info(f"Lead generation completed for {args.type}")

    except Exception as e:
        logger.error(f"Error in lead generation process: {str(e)}")
        raise

if __name__ == "__main__":
    main()
