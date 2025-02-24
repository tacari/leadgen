import os
import logging
import argparse
from datetime import datetime
from config import LOG_FILE, LOG_LEVEL, OUTPUT_DIR
from scraper import LeadScraper
from email_generator import EmailGenerator
from lead_manager import LeadManager

def setup_logging():
    """Configure logging"""
    # No need to create directory for files in current directory
    if os.path.dirname(LOG_FILE):  # Only create dir if log file is in a subdirectory
        log_dir = os.path.dirname(LOG_FILE)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    logging.basicConfig(
        filename=LOG_FILE,
        level=getattr(logging, LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def ensure_output_dir():
    """Ensure output directory exists"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

def main():
    parser = argparse.ArgumentParser(description='Lead Generation Tool')
    parser.add_argument('--type', choices=['dentist', 'saas'], required=True,
                      help='Type of leads to generate')
    parser.add_argument('--city', help='City for dentist leads')
    parser.add_argument('--limit', type=int, default=5, help='Number of leads to generate')
    args = parser.parse_args()

    setup_logging()
    ensure_output_dir()
    logger = logging.getLogger(__name__)
    logger.info(f"Starting lead generation for {args.type}")

    try:
        # Initialize components
        scraper = LeadScraper()
        email_gen = EmailGenerator()
        lead_manager = LeadManager()

        # Validate arguments
        if args.type == 'dentist' and not args.city:
            raise ValueError("City is required for dentist leads")

        # Scrape leads
        logger.info(f"Starting lead scraping for {args.type}")
        if args.type == 'dentist':
            leads = scraper.scrape_dentists(args.city, args.limit)
        else:
            leads = scraper.scrape_saas(args.limit)

        if not leads:
            logger.warning("No leads were found")
            return

        # Save leads
        logger.info(f"Saving {len(leads)} leads")
        lead_manager.save_leads(leads, args.type)

        # Generate emails and save to output directory
        logger.info("Generating email content")
        for lead in leads:
            # Generate email content
            email_content = (email_gen.generate_dentist_email(lead) 
                           if args.type == 'dentist' 
                           else email_gen.generate_saas_email(lead))

            if email_content:
                # Save email to file
                subject = f"Grow your {'Dental Practice' if args.type == 'dentist' else 'SaaS Business'}"
                lead_manager.save_email(
                    lead.get('id', datetime.now().strftime('%Y%m%d_%H%M%S')),
                    args.type,
                    subject,
                    email_content
                )

        logger.info(f"Lead generation completed for {args.type}")

    except Exception as e:
        logger.error(f"Error in lead generation process: {str(e)}")
        raise

if __name__ == "__main__":
    main()