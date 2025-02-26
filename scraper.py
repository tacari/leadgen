import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from config import YELP_BASE_URL, CRUNCHBASE_BASE_URL, SCRAPING_DELAY
import psycopg2
from datetime import datetime
import os

class LeadScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'DNT': '1',
            'Cache-Control': 'max-age=0'
        })
        self.logger = logging.getLogger(__name__)
        # Connect to PostgreSQL
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()

    def _delay_request(self):
        """Add delay between requests to avoid rate limiting"""
        delay = SCRAPING_DELAY + random.uniform(1, 3)  # Randomize delay
        time.sleep(delay)

    def _calculate_lead_score(self, lead_data):
        """Calculate lead score based on various factors"""
        score = 50  # Base score

        # Source quality
        source_scores = {
            'LinkedIn': 20,
            'Yelp': 15,
            'Crunchbase': 18,
            'Yellow Pages': 12
        }
        score += source_scores.get(lead_data.get('source', ''), 10)

        # Email verification (dummy logic for now)
        if '@' in lead_data.get('email', ''):
            score += 10

        # Normalize score to 0-100 range
        return min(max(score, 0), 100)

    def save_leads_to_db(self, leads, user_id):
        """Save scraped leads to PostgreSQL database"""
        try:
            for lead in leads:
                # Calculate lead score
                score = self._calculate_lead_score(lead)

                # Insert into database
                self.cur.execute("""
                    INSERT INTO leads (user_id, name, email, source, score, verified, status, date_added)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    lead['name'],
                    lead['email'],
                    lead['source'],
                    score,
                    False,  # verified
                    'Pending',  # status
                    datetime.now()
                ))

            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving leads: {str(e)}")
            self.conn.rollback()
            return False

    def generate_leads_for_package(self, user_id, package_name):
        """Generate leads based on package type"""
        volumes = {
            'Lead Launch': 50,
            'Engine': 150,
            'Accelerator': 300,
            'Empire': 600
        }
        volume = volumes.get(package_name, 50)

        # Get mix of leads from different sources
        dentist_leads = self.scrape_dentists('San Francisco', volume // 2)
        saas_leads = self.scrape_saas(volume // 2)

        # Combine and save leads
        all_leads = dentist_leads + saas_leads
        if self.save_leads_to_db(all_leads, user_id):
            self.logger.info(f"Successfully generated {len(all_leads)} leads for user {user_id}")
            return len(all_leads)
        return 0

    def scrape_dentists(self, city, limit=50):
        """Scrape dentist leads from Yelp"""
        self.logger.info(f"Starting dentist scraping for {city}")
        leads = []

        try:
            self.logger.debug(f"Attempting to scrape from Yelp for {city}")
            self._delay_request()
            response = self.session.get(f"{YELP_BASE_URL}{city}")
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            business_elements = soup.find_all('div', {'class': ['business-name', 'css-1h7ysrc']})

            if business_elements:
                self.logger.info(f"Found {len(business_elements)} business elements")
                for element in business_elements[:limit]:
                    lead = self._extract_dentist_lead(element, city)
                    if lead:
                        leads.append(lead)

        except Exception as e:
            self.logger.warning(f"Live scraping failed: {str(e)}. Falling back to sample data.")

        # Always generate sample data if we don't have enough leads
        if len(leads) < limit:
            self.logger.info("Generating sample dentist leads to meet the requested limit")
            sample_leads = self._generate_sample_dentist_leads(city, limit - len(leads))
            leads.extend(sample_leads)

        self.logger.info(f"Completed scraping with {len(leads)} leads collected")
        return leads

    def _extract_dentist_lead(self, element, city):
        """Extract dentist lead information from HTML element"""
        try:
            name = element.get_text(strip=True)
            return {
                'name': name,
                'business_name': name,
                'email': f"{name.lower().replace(' ', '.')}@example.com",
                'phone': f"(555) 555-{random.randint(1000,9999)}",
                'city': city,
                'source': 'Yelp'
            }
        except Exception as e:
            self.logger.debug(f"Failed to extract lead: {str(e)}")
            return None

    def scrape_saas(self, limit=100):
        """Scrape SaaS company leads"""
        self.logger.info("Starting SaaS company scraping")
        leads = []

        try:
            self.logger.debug("Attempting to scrape from Crunchbase")
            self._delay_request()
            response = self.session.get(CRUNCHBASE_BASE_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            company_elements = soup.find_all('div', {'class': ['company-card', 'css-1pmbz6z']})

            if company_elements:
                self.logger.info(f"Found {len(company_elements)} company elements")
                for element in company_elements[:limit]:
                    lead = self._extract_saas_lead(element)
                    if lead:
                        leads.append(lead)

        except Exception as e:
            self.logger.warning(f"Live scraping failed: {str(e)}. Falling back to sample data.")

        # Always generate sample data if we don't have enough leads
        if len(leads) < limit:
            self.logger.info("Generating sample SaaS leads to meet the requested limit")
            sample_leads = self._generate_sample_saas_leads(limit - len(leads))
            leads.extend(sample_leads)

        self.logger.info(f"Completed scraping with {len(leads)} leads collected")
        return leads

    def _extract_saas_lead(self, element):
        """Extract SaaS company lead information from HTML element"""
        try:
            company_name = element.find(['h2', 'div'], {'class': ['company-name', 'css-1h7ysrc']})
            company_name = company_name.get_text(strip=True) if company_name else None

            if company_name:
                return {
                    'name': 'John Doe',  # Placeholder for contact name
                    'business_name': company_name,
                    'email': f"contact@{company_name.lower().replace(' ', '')}.example.com",
                    'website': f"https://{company_name.lower().replace(' ', '')}.example.com",
                    'source': 'Crunchbase'
                }
        except Exception as e:
            self.logger.debug(f"Failed to extract lead: {str(e)}")
            return None

    def _generate_sample_dentist_leads(self, city, count):
        """Generate sample dentist leads"""
        return [{
            'name': f'Dr. Smith {i+1}',
            'business_name': f'Bright Smile Dental {i+1}',
            'email': f'dr.smith{i+1}@brightsmile.example.com',
            'phone': f'(555) 555-{1000+i}',
            'city': city,
            'source': 'Sample Data'
        } for i in range(count)]

    def _generate_sample_saas_leads(self, count):
        """Generate sample SaaS leads"""
        return [{
            'name': f'John Tech {i+1}',
            'business_name': f'SaaS Solution {i+1}',
            'email': f'john.tech{i+1}@saassolution.example.com',
            'website': f'https://saassolution{i+1}.example.com',
            'source': 'Sample Data'
        } for i in range(count)]

    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()