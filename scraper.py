import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import psycopg2
import json

class LeadScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
        self.logger = logging.getLogger(__name__)
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()

    def _delay_request(self):
        """Add delay between requests to avoid rate limiting"""
        delay = random.uniform(2, 5)
        time.sleep(delay)

    def _calculate_lead_score(self, lead_data):
        """Calculate lead score based on various factors"""
        score = 50  # Base score

        # Source quality
        source_scores = {
            'Yellow Pages': 10,
            'Google Maps': 20,
            'LinkedIn': 30  # Future implementation
        }
        score += source_scores.get(lead_data.get('source', ''), 0)

        # Website bonus
        if lead_data.get('website'):
            score += 15

        # Email verification
        if lead_data.get('email') and '@' in lead_data.get('email', ''):
            score += 10

        # Phone number bonus
        if lead_data.get('phone'):
            score += 5

        # Business description bonus
        if lead_data.get('description'):
            score += 5

        # Normalize score to 0-100 range
        return min(max(score, 0), 100)

    def scrape_yellow_pages(self, niche="plumbers", location="Austin, TX", limit=50):
        """Scrape leads from Yellow Pages"""
        self.logger.info(f"Starting Yellow Pages scraping for {niche} in {location}")
        leads = []

        try:
            url = f"https://www.yellowpages.com/search?search_terms={niche}&geo_location_terms={location}"
            self._delay_request()
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all business listings
            business_listings = soup.find_all('div', {'class': 'result'})[:limit]

            for listing in business_listings:
                try:
                    # Extract business name
                    name_elem = listing.find('a', {'class': 'business-name'})
                    if not name_elem:
                        continue
                    name = name_elem.text.strip()

                    # Extract phone number
                    phone_elem = listing.find('div', {'class': 'phone'})
                    phone = phone_elem.text.strip() if phone_elem else None

                    # Extract website if available
                    website_elem = listing.find('a', {'class': 'track-visit-website'})
                    website = website_elem['href'] if website_elem else None

                    # Extract description
                    desc_elem = listing.find('div', {'class': 'description'})
                    description = desc_elem.text.strip() if desc_elem else None

                    # Generate business email (could be enhanced with website domain if available)
                    email = f"contact@{name.lower().replace(' ', '').replace('&', 'and')}.com"

                    lead = {
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'website': website,
                        'description': description,
                        'source': 'Yellow Pages',
                        'verified': False,
                        'date_added': datetime.now().isoformat()
                    }

                    lead['score'] = self._calculate_lead_score(lead)
                    leads.append(lead)
                    self.logger.info(f"Scraped lead: {name}")

                except Exception as e:
                    self.logger.error(f"Error scraping individual listing: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Yellow Pages scraping error: {str(e)}")

        return leads

    def scrape_google_maps(self, niche="plumbers", location="Austin, TX", limit=50):
        """Scrape leads from Google Maps"""
        self.logger.info(f"Starting Google Maps scraping for {niche} in {location}")
        leads = []

        try:
            search_url = f"https://www.google.com/maps/search/{niche}+in+{location}"
            self._delay_request()
            response = self.session.get(search_url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Since Google Maps requires JavaScript, we'll use a more basic approach
            businesses = soup.find_all('div', {'class': 'section-result'})[:limit]

            for business in businesses:
                try:
                    name_elem = business.find('h3', {'class': 'section-result-title'})
                    if not name_elem:
                        continue

                    name = name_elem.text.strip()
                    website = None  # Would need JavaScript rendering to get this
                    email = f"contact@{name.lower().replace(' ', '').replace('&', 'and')}.com"

                    lead = {
                        'name': name,
                        'email': email,
                        'website': website,
                        'source': 'Google Maps',
                        'verified': False,
                        'date_added': datetime.now().isoformat()
                    }

                    lead['score'] = self._calculate_lead_score(lead)
                    leads.append(lead)
                    self.logger.info(f"Scraped lead from Google Maps: {name}")

                except Exception as e:
                    self.logger.error(f"Error scraping Google Maps listing: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Google Maps scraping error: {str(e)}")

        return leads

    def save_leads_to_db(self, leads, user_id):
        """Save scraped leads to PostgreSQL database"""
        try:
            for lead in leads:
                self.cur.execute("""
                    INSERT INTO leads (
                        user_id, name, email, source, score,
                        verified, status, date_added, website,
                        phone, description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    lead['name'],
                    lead['email'],
                    lead['source'],
                    lead['score'],
                    lead['verified'],
                    'Pending',
                    datetime.now(),
                    lead.get('website'),
                    lead.get('phone'),
                    lead.get('description')
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
            'launch': 50,
            'engine': 150,
            'accelerator': 300,
            'empire': 600
        }

        volume = volumes.get(package_name.lower(), 50)
        yp_volume = volume // 2
        gm_volume = volume - yp_volume

        self.logger.info(f"Generating {volume} leads for user {user_id} (Package: {package_name})")

        # Get mix of leads from different sources
        yp_leads = self.scrape_yellow_pages(limit=yp_volume)
        self.logger.info(f"Scraped {len(yp_leads)} leads from Yellow Pages")

        gm_leads = self.scrape_google_maps(limit=gm_volume)
        self.logger.info(f"Scraped {len(gm_leads)} leads from Google Maps")

        # Combine leads
        all_leads = yp_leads + gm_leads

        # Save to database
        if self.save_leads_to_db(all_leads, user_id):
            self.logger.info(f"Successfully generated {len(all_leads)} leads for user {user_id}")
            return len(all_leads)
        return 0

    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()

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