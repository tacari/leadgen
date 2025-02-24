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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = logging.getLogger(__name__)

    def _delay_request(self):
        time.sleep(SCRAPING_DELAY + random.random())

    def scrape_dentists(self, city, limit=50):
        """Scrape dentist leads from Yelp"""
        self.logger.info(f"Scraping dentists in {city}")
        leads = []
        url = f"{YELP_BASE_URL}{city}"
        
        try:
            self._delay_request()
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            business_elements = soup.find_all('div', {'class': 'business-name'})
            for element in business_elements[:limit]:
                name = element.get_text(strip=True)
                contact = self._extract_contact_info(element.parent)
                leads.append({
                    'name': name,
                    'business_name': name,
                    'email': contact.get('email', ''),
                    'phone': contact.get('phone', ''),
                    'city': city,
                    'source': 'Yelp'
                })
                
        except Exception as e:
            self.logger.error(f"Error scraping dentists: {str(e)}")
            
        return leads

    def scrape_saas(self, limit=100):
        """Scrape SaaS company leads from Crunchbase"""
        self.logger.info("Scraping SaaS companies")
        leads = []
        
        try:
            self._delay_request()
            response = self.session.get(CRUNCHBASE_BASE_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            company_elements = soup.find_all('div', {'class': 'company-card'})
            for element in company_elements[:limit]:
                company_data = self._extract_company_data(element)
                leads.append({
                    'name': company_data.get('contact_name', ''),
                    'business_name': company_data.get('company_name', ''),
                    'email': company_data.get('email', ''),
                    'website': company_data.get('website', ''),
                    'source': 'Crunchbase'
                })
                
        except Exception as e:
            self.logger.error(f"Error scraping SaaS companies: {str(e)}")
            
        return leads

    def _extract_contact_info(self, element):
        """Extract contact information from HTML element"""
        contact_info = {}
        try:
            email_elem = element.find('a', {'class': 'email'})
            if email_elem:
                contact_info['email'] = email_elem.get_text(strip=True)
            
            phone_elem = element.find('span', {'class': 'phone'})
            if phone_elem:
                contact_info['phone'] = phone_elem.get_text(strip=True)
        except Exception as e:
            self.logger.error(f"Error extracting contact info: {str(e)}")
            
        return contact_info

    def _extract_company_data(self, element):
        """Extract company data from HTML element"""
        company_data = {}
        try:
            name_elem = element.find('h2', {'class': 'company-name'})
            if name_elem:
                company_data['company_name'] = name_elem.get_text(strip=True)
            
            website_elem = element.find('a', {'class': 'website'})
            if website_elem:
                company_data['website'] = website_elem['href']
        except Exception as e:
            self.logger.error(f"Error extracting company data: {str(e)}")
            
        return company_data
