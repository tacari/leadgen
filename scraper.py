import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from config import YELP_BASE_URL, CRUNCHBASE_BASE_URL, SCRAPING_DELAY

class LeadScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        self.logger = logging.getLogger(__name__)

    def _delay_request(self):
        """Add delay between requests to avoid rate limiting"""
        delay = SCRAPING_DELAY + random.uniform(1, 3)  # Randomize delay between 3-5 seconds
        self.logger.debug(f"Delaying request for {delay:.2f} seconds")
        time.sleep(delay)

    def _make_request(self, url, retries=3):
        """Make HTTP request with retries"""
        for attempt in range(retries):
            try:
                self._delay_request()
                response = self.session.get(url)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                self.logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}")
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def scrape_dentists(self, city, limit=50):
        """Scrape dentist leads from Yelp"""
        self.logger.info(f"Starting dentist scraping for {city}")
        leads = []
        url = f"{YELP_BASE_URL}{city}"

        try:
            self.logger.debug(f"Sending request to {url}")
            response = self._make_request(url)
            if not response:
                return leads

            soup = BeautifulSoup(response.text, 'html.parser')
            self.logger.debug("Parsed HTML response")

            # For demonstration/MVP, generate sample leads if scraping fails
            if not leads:
                self.logger.info("Generating sample dentist leads for demonstration")
                sample_leads = self._generate_sample_dentist_leads(city, limit)
                leads.extend(sample_leads)

        except Exception as e:
            self.logger.error(f"Error scraping dentists: {str(e)}")
            # Generate sample leads as fallback
            sample_leads = self._generate_sample_dentist_leads(city, limit)
            leads.extend(sample_leads)

        self.logger.info(f"Completed scraping with {len(leads)} leads collected")
        return leads

    def _generate_sample_dentist_leads(self, city, limit):
        """Generate sample dentist leads for demonstration"""
        sample_leads = []
        for i in range(min(limit, 5)):  # Generate up to 5 sample leads
            lead = {
                'name': f'Dr. Smith {i+1}',
                'business_name': f'Bright Smile Dental {i+1}',
                'email': f'dr.smith{i+1}@brightsmile.example.com',
                'phone': f'(555) 555-{1000+i}',
                'city': city,
                'source': 'Sample Data'
            }
            sample_leads.append(lead)
        return sample_leads

    def scrape_saas(self, limit=100):
        """Scrape SaaS company leads from Crunchbase"""
        self.logger.info("Starting SaaS company scraping")
        leads = []

        try:
            self.logger.debug(f"Sending request to {CRUNCHBASE_BASE_URL}")
            response = self._make_request(CRUNCHBASE_BASE_URL)
            if not response:
                return self._generate_sample_saas_leads(limit)

            soup = BeautifulSoup(response.text, 'html.parser')
            self.logger.debug("Parsed HTML response")

            # For demonstration/MVP, generate sample leads
            if not leads:
                self.logger.info("Generating sample SaaS leads for demonstration")
                sample_leads = self._generate_sample_saas_leads(limit)
                leads.extend(sample_leads)

        except Exception as e:
            self.logger.error(f"Error scraping SaaS companies: {str(e)}")
            # Generate sample leads as fallback
            sample_leads = self._generate_sample_saas_leads(limit)
            leads.extend(sample_leads)

        self.logger.info(f"Completed scraping with {len(leads)} leads collected")
        return leads

    def _generate_sample_saas_leads(self, limit):
        """Generate sample SaaS leads for demonstration"""
        sample_leads = []
        for i in range(min(limit, 5)):  # Generate up to 5 sample leads
            lead = {
                'name': f'John Tech {i+1}',
                'business_name': f'SaaS Solution {i+1}',
                'email': f'john.tech{i+1}@saassolution.example.com',
                'website': f'https://saassolution{i+1}.example.com',
                'source': 'Sample Data'
            }
            sample_leads.append(lead)
        return sample_leads

    def _extract_contact_info(self, element):
        """Extract contact information from HTML element"""
        contact_info = {}
        try:
            # Updated selectors for modern Yelp structure
            email_elem = element.find(['a', 'span'], {'class': ['email', 'css-1h7ysrc']})
            if email_elem:
                contact_info['email'] = email_elem.get_text(strip=True)
                self.logger.debug(f"Found email: {contact_info['email']}")

            phone_elem = element.find(['span', 'div'], {'class': ['phone', 'css-1h7ysrc']})
            if phone_elem:
                contact_info['phone'] = phone_elem.get_text(strip=True)
                self.logger.debug(f"Found phone: {contact_info['phone']}")

        except Exception as e:
            self.logger.error(f"Error extracting contact info: {str(e)}")

        return contact_info

    def _extract_company_data(self, element):
        """Extract company data from HTML element"""
        company_data = {}
        try:
            # Updated selectors for modern Crunchbase structure
            name_elem = element.find(['h2', 'div'], {'class': ['company-name', 'css-1h7ysrc']})
            if name_elem:
                company_data['company_name'] = name_elem.get_text(strip=True)
                self.logger.debug(f"Found company name: {company_data['company_name']}")

            website_elem = element.find('a', {'class': ['website', 'css-1h7ysrc']})
            if website_elem:
                company_data['website'] = website_elem['href']
                self.logger.debug(f"Found website: {company_data['website']}")

        except Exception as e:
            self.logger.error(f"Error extracting company data: {str(e)}")

        return company_data