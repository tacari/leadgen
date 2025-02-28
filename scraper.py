import time
import random
import logging
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
import os
import psycopg2
import json
from faker import Faker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fake = Faker()

class LeadScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        # Add console handler if not already added
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()
        self.sources = ['LinkedIn', 'Google Maps', 'Yellow Pages', 'Facebook', 'Instagram']
        self.statuses = ['New', 'Contacted', 'Qualified', 'Proposal', 'Closed']
        self.intent_phrases = ['looking for', 'interested in', 'need help with', 'seeking', 'want to improve']


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

        # Reviews/ratings bonus (Google Maps specific)
        if lead_data.get('rating'):
            score += min(10, lead_data.get('rating', 0) * 2)  # Up to 10 points for 5-star rating

        # Normalize score to 0-100 range
        return min(max(score, 0), 100)

    def score_lead(self, lead_data):
        """Calculate a lead score from 1-100 based on various factors"""
        # Start with a baseline score
        score = 50

        # Score based on source (where the lead came from)
        source = lead_data.get('source', '').lower()
        source_scores = {
            'linkedin': 20,
            'google': 10,
            'google maps': 10,
            'yellow pages': 5,
            'facebook': 8,
            'instagram': 7,
            'twitter': 5
        }

        # Add source score
        for src, points in source_scores.items():
            if src in source.lower():
                score += points
                break

        # Add points for verified email
        if lead_data.get('verified', False):
            score += 10

        # Check for intent signals in name or other fields
        intent_keywords = ['looking for', 'need', 'want', 'searching', 'interested', 'inquiry', 'request']
        lead_name = lead_data.get('name', '').lower()

        for keyword in intent_keywords:
            if keyword in lead_name:
                score += 15
                break

        # Cap the score at 100
        return min(100, score)

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
                    self.logger.info(f"Scraped YP lead: {name}")

                except Exception as e:
                    self.logger.error(f"Error scraping YP listing: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Yellow Pages scraping error: {str(e)}")

        return leads

    def scrape_google_maps(self, niche="plumbers", location="Austin, TX", limit=50):
        """Scrape leads from Google Maps via SerpApi"""
        self.logger.info(f"Starting Google Maps scraping for {niche} in {location}")
        leads = []

        if not self.serpapi_key:
            self.logger.warning("No SerpApi key found, skipping Google Maps scraping")
            return []

        try:
            params = {
                "engine": "google_maps",
                "q": f"{niche} in {location}",
                "type": "search",
                "api_key": self.serpapi_key
            }

            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()

            if "error" in data:
                self.logger.error(f"SerpApi error: {data['error']}")
                return []

            local_results = data.get('local_results', [])[:limit]

            for result in local_results:
                try:
                    name = result.get('title', '')
                    if not name:
                        continue

                    lead = {
                        'name': name,
                        'phone': result.get('phone', ''),
                        'website': result.get('website', ''),
                        'description': result.get('description', ''),
                        'address': result.get('address', ''),
                        'rating': result.get('rating', 0),
                        'reviews': result.get('reviews', 0),
                        'source': 'Google Maps',
                        'verified': True,
                        'date_added': datetime.now().isoformat()
                    }

                    # Generate email from website domain if available
                    if lead['website']:
                        domain = lead['website'].replace('http://', '').replace('https://', '').split('/')[0]
                        lead['email'] = f"contact@{domain}"
                    else:
                        lead['email'] = f"contact@{name.lower().replace(' ', '').replace('&', 'and')}.com"

                    lead['score'] = self._calculate_lead_score(lead)
                    leads.append(lead)
                    self.logger.info(f"Scraped Google Maps lead: {name}")

                except Exception as e:
                    self.logger.error(f"Error processing Google Maps result: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Google Maps API error: {str(e)}")

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
            self.logger.error(f"Database error: {str(e)}")
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

        # Prioritize Google Maps leads when SerpApi is available
        if self.serpapi_key:
            gm_volume = min(volume, 50)  # Cap Google Maps to 50 per batch to manage API usage
            yp_volume = volume - gm_volume
        else:
            gm_volume = 0
            yp_volume = volume

        self.logger.info(f"Generating {volume} leads for user {user_id} (Package: {package_name})")
        self.logger.info(f"Split: {gm_volume} Google Maps, {yp_volume} Yellow Pages")

        all_leads = []

        # Get Google Maps leads first (higher quality)
        if gm_volume > 0:
            gm_leads = self.scrape_google_maps(limit=gm_volume)
            self.logger.info(f"Scraped {len(gm_leads)} leads from Google Maps")
            all_leads.extend(gm_leads)

        # Fill remaining with Yellow Pages leads
        if yp_volume > 0:
            yp_leads = self.scrape_yellow_pages(limit=yp_volume)
            self.logger.info(f"Scraped {len(yp_leads)} leads from Yellow Pages")
            all_leads.extend(yp_leads)

        if all_leads:
            if self.save_leads_to_db(all_leads, user_id):
                self.logger.info(f"Successfully generated {len(all_leads)} leads for user {user_id}")
                return len(all_leads)
        return 0

    def _save_leads(self, leads):
        """Save generated leads to database or file"""
        try:
            from web_app import supabase

            # Try to save to Supabase
            for lead in leads:
                # Ensure each lead has a score
                if 'score' not in lead:
                    lead['score'] = self.score_lead(lead)

                supabase.table('leads').insert(lead).execute()

            logger.info(f"Saved {len(leads)} leads to Supabase")
            return True
        except Exception as e:
            logger.error(f"Error saving to Supabase: {str(e)}")

            # Fallback to file storage
            try:
                leads_file = 'data/leads.json'

                # Load existing leads
                existing_leads = []
                if os.path.exists(leads_file):
                    with open(leads_file, 'r') as f:
                        existing_leads = json.load(f)

                # Make sure each lead has a score before adding
                for lead in leads:
                    if 'score' not in lead:
                        lead['score'] = self.score_lead(lead)

                # Add new leads
                existing_leads.extend(leads)

                # Save updated leads
                with open(leads_file, 'w') as f:
                    json.dump(existing_leads, f, indent=2)

                logger.info(f"Saved {len(leads)} leads to file")
                return True
            except Exception as file_e:
                logger.error(f"Error saving to file: {str(file_e)}")
                return False

    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()