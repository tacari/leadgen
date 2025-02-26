import os
import logging

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Scraping Configuration
YELP_BASE_URL = "https://www.yelp.com/search?find_desc=Dentists&find_loc="
CRUNCHBASE_BASE_URL = "https://www.crunchbase.com/discover/organization.companies"
GOOGLE_MAPS_URL = "https://www.google.com/maps/search/dentists+in+"
SCRAPING_DELAY = 3  # seconds between requests

# Package Volumes
PACKAGE_VOLUMES = {
    'Lead Launch': 50,
    'Engine': 150,
    'Accelerator': 300,
    'Empire': 600
}

# Scoring Weights
SOURCE_SCORES = {
    'LinkedIn': 20,
    'Yelp': 15,
    'Crunchbase': 18,
    'Yellow Pages': 12,
    'Google Maps': 16
}

# Output Configuration
OUTPUT_DIR = "output"
DENTIST_LEADS_FILE = os.path.join(OUTPUT_DIR, "dentist_leads.csv")
SAAS_LEADS_FILE = os.path.join(OUTPUT_DIR, "saas_leads.csv")

# Logging Configuration
LOG_FILE = "leadgen.log"
LOG_LEVEL = "INFO"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Initialize logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)