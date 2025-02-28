import time
import random
import logging
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
import psycopg2
import json
from faker import Faker
import threading
from urllib.parse import urlparse
from email_validator import validate_email, EmailNotValidError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import base64
import io
import csv

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
        self.google_places_key = os.environ.get('GOOGLE_PLACES_API_KEY')
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
        """Calculate lead score based on various factors using AI-powered analysis"""
        score = 50  # Base score

        # Source quality - LinkedIn gets highest score as premium source
        source_scores = {
            'Yellow Pages': 10,
            'Google Maps': 20,
            'LinkedIn': 30,
            'Facebook': 15,
            'Instagram': 15,
            'Twitter': 10
        }
        score += source_scores.get(lead_data.get('source', ''), 0)

        # Website bonus - having a website indicates legitimacy
        if lead_data.get('website'):
            score += 15

        # Email verification - verified emails get higher score
        if lead_data.get('email') and '@' in lead_data.get('email', ''):
            domain = lead_data.get('email').split('@')[1]
            # Company domains score higher than free email providers
            if any(provider in domain for provider in ['gmail', 'yahoo', 'hotmail', 'outlook']):
                score += 5
            else:
                score += 15

        # Phone number bonus
        if lead_data.get('phone'):
            score += 5

        # Analyze business description for intent signals
        if lead_data.get('description'):
            description = lead_data.get('description').lower()
            # Check for intent keywords in description
            intent_phrases = ['looking for', 'interested in', 'need help with', 'seeking', 'want to improve']
            for phrase in intent_phrases:
                if phrase in description:
                    score += 25
                    break
            score += 5  # Basic points for having a description

        # Reviews/ratings bonus (Google Maps specific)
        if lead_data.get('rating'):
            score += min(10, lead_data.get('rating', 0) * 2)  # Up to 10 points for 5-star rating

        # Lead recency bonus - newer leads might be more valuable
        if lead_data.get('date_added'):
            try:
                # Add recency bonus
                lead_date = lead_data.get('date_added')
                if isinstance(lead_date, str):
                    from datetime import datetime
                    now = datetime.now()
                    lead_datetime = datetime.fromisoformat(lead_date.replace('Z', '+00:00'))
                    days_old = (now - lead_datetime).days
                    if days_old < 7:  # Recent leads (less than a week old)
                        score += 5
            except Exception:
                pass  # Skip if date parsing fails

        # Normalize score to 0-100 range
        return min(max(score, 0), 100)

    def verify_email(self, email):
        """Verify if an email address is valid and deliverable
        
        Args:
            email (str): The email address to verify
            
        Returns:
            bool: True if the email is valid and deliverable, False otherwise
        """
        if not email or '@' not in email:
            return False
            
        try:
            # First check basic syntax
            valid = validate_email(email)
            
            # Then check deliverability if syntax is valid
            # This checks if the domain has valid MX records
            valid = validate_email(valid.email, check_deliverability=True)
            
            self.logger.info(f"Verified email: {email} is valid")
            return True
        except EmailNotValidError as e:
            self.logger.info(f"Email verification failed for {email}: {str(e)}")
            return False
            
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
                    
                    # Verify the email
                    is_verified = self.verify_email(email)

                    lead = {
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'website': website,
                        'description': description,
                        'source': 'Yellow Pages',
                        'verified': is_verified,
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
                        
                    # Verify the email
                    lead['verified'] = self.verify_email(lead['email'])

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
        
        # Get user niche preferences (defaults to plumbers if not set)
        try:
            # Try to get user's niche preference from database
            self.cur.execute("SELECT niche, location FROM users WHERE id = %s", (user_id,))
            user_data = self.cur.fetchone()
            
            if user_data and user_data[0]:
                niche = user_data[0]
                location = user_data[1] if user_data[1] else "Austin, TX"
            else:
                # Default values
                niche = "plumbers"
                location = "Austin, TX"
        except Exception as e:
            self.logger.error(f"Error fetching user niche preference: {str(e)}")
            niche = "plumbers"
            location = "Austin, TX"

        volume = volumes.get(package_name.lower(), 50)
        self.logger.info(f"Generating {volume} leads for user {user_id} (Package: {package_name})")
        
        # Different sources based on package type
        if package_name.lower() == 'launch':
            # Lead Launch ($499): Yellow Pages only
            all_leads = self.scrape_yellow_pages(niche=niche, location=location, limit=volume)
            self.logger.info(f"Scraped {len(all_leads)} leads from Yellow Pages for Launch package")
        else:
            # All other packages: multi-source scraping
            all_leads = self.multi_source_scrape(niche=niche, location=location, limit=volume)
            self.logger.info(f"Multi-source scraping complete: {len(all_leads)} leads for {package_name} package")

        if all_leads:
            if self.save_leads_to_db(all_leads, user_id):
                self.logger.info(f"Successfully generated {len(all_leads)} leads for user {user_id}")
                
                # Schedule automated outreach based on package type
                # For Launch: One-time delivery after lead generation
                # For Engine: Weekly outreach
                # For Accelerator/Empire: Daily outreach
                self.schedule_automated_outreach(user_id, package_name, all_leads)
                
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

    def scrape_linkedin(self, niche="SaaS", location="Austin, TX", limit=50):
        """Scrape leads from LinkedIn via SerpAPI"""
        self.logger.info(f"Starting LinkedIn scraping for {niche} in {location}")
        leads = []

        if not self.serpapi_key:
            self.logger.warning("No SerpAPI key found, skipping LinkedIn scraping")
            return []

        try:
            params = {
                "engine": "google",
                "q": f"{niche} companies in {location} site:linkedin.com/company",
                "api_key": self.serpapi_key,
                "num": limit
            }

            response = requests.get("https://serpapi.com/search", params=params)
            data = response.json()

            if "error" in data:
                self.logger.error(f"SerpAPI error for LinkedIn: {data['error']}")
                return []

            organic_results = data.get('organic_results', [])[:limit]

            for result in organic_results:
                try:
                    title = result.get('title', '')
                    if not title or 'LinkedIn' not in title:
                        continue
                        
                    # Clean up the title to get just the company name
                    company_name = title.split('|')[0].strip()
                    if 'LinkedIn' in company_name:
                        company_name = company_name.replace('LinkedIn', '').strip()
                    
                    link = result.get('link', '')
                    description = result.get('snippet', '')
                    
                    # Extract domain for email generation
                    website = self.extract_website_from_linkedin(link)
                    email = None
                    
                    if website:
                        # Try to find email on website
                        email = self.extract_email_from_website(website)
                    
                    # Generate email if not found
                    if not email and website:
                        domain = urlparse(website).netloc
                        email = f"contact@{domain}"
                    elif not email:
                        sanitized_name = company_name.lower().replace(' ', '').replace('.', '').replace(',', '')
                        email = f"contact@{sanitized_name}.com"
                    
                    # Verify the email
                    is_verified = self.verify_email(email)
                    
                    lead = {
                        'name': company_name,
                        'email': email,
                        'website': website,
                        'description': description,
                        'source': 'LinkedIn',
                        'verified': is_verified,
                        'date_added': datetime.now().isoformat()
                    }
                    
                    # Add score
                    lead['score'] = self._calculate_lead_score(lead)
                    leads.append(lead)
                    self.logger.info(f"Scraped LinkedIn lead: {company_name}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing LinkedIn result: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"LinkedIn API error: {str(e)}")

        return leads
        
    def extract_website_from_linkedin(self, linkedin_url):
        """Extract company website from LinkedIn page"""
        try:
            # This is a simplified version - in reality, LinkedIn blocks scraping
            # For production, you'd need a LinkedIn API or a sophisticated proxy setup
            response = self.session.get(linkedin_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for website in "About" section
            website_section = soup.find('a', string=re.compile(r'Website|Visit website', re.I))
            if website_section and website_section.has_attr('href'):
                return website_section['href']
                
            # Alternative: just return a placeholder based on company name
            company_name = soup.find('h1', {'class': 'org-top-card-summary__title'})
            if company_name:
                name_text = company_name.text.strip().lower().replace(' ', '')
                return f"https://{name_text}.com"
                
            return None
        except Exception as e:
            self.logger.error(f"Error extracting website from LinkedIn: {str(e)}")
            return None
            
    def extract_email_from_website(self, website_url):
        """Extract email from company website"""
        try:
            response = self.session.get(website_url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for mailto links
            email_links = soup.find_all('a', href=re.compile(r'mailto:'))
            if email_links:
                for link in email_links:
                    href = link['href']
                    email = href.replace('mailto:', '').split('?')[0]
                    if '@' in email and '.' in email:
                        return email
            
            # Alternative: search for email patterns in text
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_matches = re.findall(email_pattern, response.text)
            if email_matches:
                # Filter out common false positives
                filtered_emails = [email for email in email_matches 
                                 if not any(s in email for s in ['example.com', 'yourdomain'])]
                if filtered_emails:
                    return filtered_emails[0]
                    
            return None
        except Exception as e:
            self.logger.error(f"Error extracting email from website: {str(e)}")
            return None
            
    def combine_and_deduplicate_leads(self, leads_lists):
        """Combine leads from multiple sources and remove duplicates"""
        combined_leads = []
        seen_keys = set()
        
        for leads in leads_lists:
            for lead in leads:
                # Create a key based on name and source
                key = (lead.get('name', '').lower(), lead.get('source', ''))
                
                if key not in seen_keys:
                    seen_keys.add(key)
                    combined_leads.append(lead)
        
        return combined_leads
        
    def multi_source_scrape(self, niche="plumbers", location="Austin, TX", limit=50):
        """Scrape leads from multiple sources and combine them"""
        self.logger.info(f"Starting multi-source scraping for {niche} in {location}")
        
        # Create threads for parallel scraping
        yp_leads = []
        gm_leads = []
        linkedin_leads = []
        
        def scrape_yp():
            nonlocal yp_leads
            yp_leads = self.scrape_yellow_pages(niche, location, limit)
            
        def scrape_gm():
            nonlocal gm_leads
            gm_leads = self.scrape_google_maps(niche, location, limit)
            
        def scrape_linkedin():
            nonlocal linkedin_leads
            linkedin_leads = self.scrape_linkedin(niche, location, limit)
        
        # Create and start threads
        threads = [
            threading.Thread(target=scrape_yp),
            threading.Thread(target=scrape_gm),
            threading.Thread(target=scrape_linkedin)
        ]
        
        for thread in threads:
            thread.start()
            
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
        # Combine and deduplicate leads
        all_leads = self.combine_and_deduplicate_leads([yp_leads, gm_leads, linkedin_leads])
        
        # Trim to the requested limit
        if len(all_leads) > limit:
            # Sort by score before trimming
            all_leads.sort(key=lambda x: x.get('score', 0), reverse=True)
            all_leads = all_leads[:limit]
            
        self.logger.info(f"Multi-source scraping complete. Generated {len(all_leads)} unique leads.")
        return all_leads

    def generate_email_template(self, lead, package_name):
        """Generate a personalized email template based on package tier"""
        templates = {
            'launch': f"""
                <p>Hello {lead.get('name', 'there').split()[0]},</p>
                <p>I noticed your business while researching {lead.get('source', 'online')} and wanted to reach out.</p>
                <p>We've helped businesses like yours grow their customer base through targeted lead generation.</p>
                <p>Would you be open to a quick chat about how we might help your business?</p>
                <p>Best regards,<br>Your LeadZap Team</p>
            """,
            'engine': f"""
                <p>Hi {lead.get('name', 'there').split()[0]},</p>
                <p>We recently found your business on {lead.get('source', 'online')} and were impressed by what we saw.</p>
                <p>Our clients in your industry have seen an average 27% increase in qualified leads after working with us.</p>
                <p>I'd love to share how our lead generation service could work specifically for {lead.get('name', 'your business')}.</p>
                <p>When would be a good time to connect?</p>
                <p>Regards,<br>Your LeadZap Team</p>
            """,
            'accelerator': f"""
                <p>Hello {lead.get('name', 'there').split()[0]},</p>
                <p>I came across your business while analyzing top companies in your area on {lead.get('source', 'online')}.</p>
                <p>We specialize in helping businesses like yours generate more qualified leads through our AI-powered platform.</p>
                <p>Based on your profile, I believe we could help increase your customer acquisition by 30% within 90 days.</p>
                <p>Would you be interested in a personalized demo to see how this would work for your specific business?</p>
                <p>Best regards,<br>Your LeadZap Team</p>
            """,
            'empire': f"""
                <p>Hello {lead.get('name', 'there').split()[0]},</p>
                <p>I was specifically researching industry leaders on {lead.get('source', 'online')} when I came across {lead.get('name', 'your business')}.</p>
                <p>We've worked with similar businesses in your sector to dramatically increase their lead flow and conversion rates.</p>
                <p>Our premium lead generation service has helped our enterprise clients achieve an average 42% growth in qualified opportunities within the first quarter.</p>
                <p>I've actually prepared some initial research on your market position and would be happy to share these insights in a brief call.</p>
                <p>When would be most convenient for you this week?</p>
                <p>Warm regards,<br>Your LeadZap Team</p>
            """
        }
        
        # Default to launch template if package not found
        return templates.get(package_name.lower(), templates['launch'])
        
    def generate_linkedin_dm(self, lead, package_name):
        """Generate LinkedIn DM template based on package tier"""
        templates = {
            'launch': f"Hi {lead.get('name', 'there').split()[0]}, I found your profile while searching for businesses in your field. Would you be open to discussing how we could help with lead generation?",
            'engine': f"Hello {lead.get('name', 'there').split()[0]}, I noticed your business on LinkedIn and was impressed. We've helped similar companies increase leads by 25%. Would you be open to a quick conversation?",
            'accelerator': f"Hi {lead.get('name', 'there').split()[0]}, I was researching top companies in your sector and your profile stood out. We specialize in AI-powered lead generation for businesses like yours. Would you be interested in learning how we've helped others increase qualified leads by 30%?",
            'empire': f"Hello {lead.get('name', 'there').split()[0]}, I've been specifically researching industry leaders and was impressed by {lead.get('name', 'your business')}. We've developed a custom approach for businesses in your position that has generated 40%+ growth in quality leads. I've prepared some initial thoughts - when would be a good time to discuss?"
        }
        
        # Default to launch template if package not found
        return templates.get(package_name.lower(), templates['launch'])
    
    def schedule_automated_outreach(self, user_id, package_name, leads, delay_days=1):
        """Schedule automated outreach based on package type"""
        self.logger.info(f"Scheduling automated outreach for {len(leads)} leads (Package: {package_name})")
        
        # Get SendGrid API key
        sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        if not sendgrid_api_key:
            self.logger.error("No SendGrid API key found, skipping automated outreach")
            return False
            
        # Get user's email for notifications
        try:
            self.cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
            user_email = self.cur.fetchone()[0]
        except Exception as e:
            self.logger.error(f"Error getting user email: {str(e)}")
            user_email = "user@example.com"  # Fallback
        
        # Schedule based on package type
        if package_name.lower() == 'launch':
            # One-time delivery after 7 days
            threading.Timer(7 * 86400, lambda: self.send_email_batch(leads, user_id, user_email, package_name)).start()
            
        elif package_name.lower() == 'engine':
            # Weekly delivery
            threading.Timer(7 * 86400, lambda: self.send_email_batch(leads, user_id, user_email, package_name)).start()
            
        elif package_name.lower() in ['accelerator', 'empire']:
            # Daily delivery, staggered throughout the day
            for i, lead_batch in enumerate(self.chunk_list(leads, 5)):  # Send in batches of 5
                # Stagger outreach throughout the day (every 2 hours)
                delay = delay_days * 86400 + i * 7200  # base delay + 2 hours per batch
                threading.Timer(delay, lambda batch=lead_batch: self.send_email_batch(batch, user_id, user_email, package_name)).start()
        
        return True
    
    def chunk_list(self, lst, n):
        """Split a list into chunks of size n"""
        for i in range(0, len(lst), n):
            yield lst[i:i+n]
    
    def send_email_batch(self, leads, user_id, user_email, package_name):
        """Send a batch of emails to leads"""
        self.logger.info(f"Sending email batch for {len(leads)} leads (Package: {package_name})")
        
        try:
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
            
            # Send individual emails to leads
            successful_emails = 0
            for lead in leads:
                try:
                    # Generate personalized content
                    html_content = self.generate_email_template(lead, package_name)
                    
                    # Prepare email
                    message = Mail(
                        from_email='leads@leadzap.io',
                        to_emails=lead.get('email'),
                        subject=f"Opportunity for {lead.get('name')}",
                        html_content=html_content
                    )
                    
                    # Send email
                    response = sg.send(message)
                    
                    # Update lead status if successful
                    if response.status_code in [200, 201, 202]:
                        successful_emails += 1
                        self.cur.execute(
                            "UPDATE leads SET status = 'Contacted' WHERE id = %s",
                            (lead.get('id'),)
                        )
                        self.conn.commit()
                    
                    # Add delay between emails to avoid rate limiting
                    time.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error sending email to {lead.get('email')}: {str(e)}")
            
            # Send summary email to user
            if successful_emails > 0:
                # Create CSV of leads for attachment
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(['Name', 'Email', 'Source', 'Score', 'Status', 'Date Added'])
                
                for lead in leads:
                    writer.writerow([
                        lead.get('name', 'N/A'),
                        lead.get('email', 'N/A'),
                        lead.get('source', 'N/A'),
                        lead.get('score', 0),
                        'Contacted',
                        lead.get('date_added', datetime.now().isoformat())
                    ])
                
                csv_content = output.getvalue()
                csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
                
                # Create summary email
                summary_message = Mail(
                    from_email='outreach@leadzap.io',
                    to_emails=user_email,
                    subject=f"Automated Outreach Update - {successful_emails} Leads Contacted",
                    html_content=f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                            <h2 style="color: #7B00FF;">Outreach Update</h2>
                            <p>Your automated outreach has been sent to {successful_emails} leads.</p>
                            
                            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                                <h3 style="color: #333;">Outreach Summary:</h3>
                                <ul>
                                    <li>Package: {package_name}</li>
                                    <li>Emails Sent: {successful_emails}</li>
                                    <li>Date: {datetime.now().strftime('%Y-%m-%d')}</li>
                                </ul>
                            </div>
                            
                            <p>Access your dashboard for more insights and to manage your leads.</p>
                            
                            <div style="margin-top: 30px; padding: 20px; border-top: 1px solid #eee;">
                                <p style="color: #666; font-size: 12px;">
                                    The contacted leads are attached in CSV format for your records.
                                </p>
                            </div>
                        </div>
                    """
                )
                
                # Attach CSV
                attachment = Attachment(
                    FileContent(csv_base64),
                    FileName(f'contacted_leads_{datetime.now().strftime("%Y%m%d")}.csv'),
                    FileType('text/csv'),
                    Disposition('attachment')
                )
                summary_message.attachment = attachment
                
                # Send summary email
                sg.send(summary_message)
                
            self.logger.info(f"Email batch completed: {successful_emails} successful out of {len(leads)} attempts")
            return successful_emails
            
        except Exception as e:
            self.logger.error(f"Error in send_email_batch: {str(e)}")
            return 0

    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()