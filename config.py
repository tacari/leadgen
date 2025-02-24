import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

# Scraping Configuration
YELP_BASE_URL = "https://www.yelp.com/search?find_desc=Dentists&find_loc="
CRUNCHBASE_BASE_URL = "https://www.crunchbase.com/discover/organization.companies"
SCRAPING_DELAY = 2  # seconds between requests

# Email Configuration
FROM_EMAIL = os.getenv('FROM_EMAIL', 'your@email.com')
MAX_EMAILS_PER_DAY = 100

# Output Configuration
OUTPUT_DIR = "output"
DENTIST_LEADS_FILE = f"{OUTPUT_DIR}/dentist_leads.csv"
SAAS_LEADS_FILE = f"{OUTPUT_DIR}/saas_leads.csv"

# Logging Configuration
LOG_FILE = "leadgen.log"
LOG_LEVEL = "INFO"
