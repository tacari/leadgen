
import logging
import threading
from datetime import datetime, timedelta
import os
import psycopg2
import json
from scraper import LeadScraper

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LeadScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.conn = psycopg2.connect(os.environ['DATABASE_URL'])
        self.cur = self.conn.cursor()
        self.scraper = LeadScraper()
        
        # Define common niches and cities for lead pool
        self.common_niches = ['plumbers', 'saas', 'gyms', 'restaurants', 'dentists', 'lawyers']
        self.common_cities = ['Austin', 'New York', 'Los Angeles', 'Chicago', 'Dallas', 'Miami']
        
    def create_lead_pool_table(self):
        """Create lead pool table if it doesn't exist"""
        try:
            self.cur.execute("""
                CREATE TABLE IF NOT EXISTS lead_pool (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    source VARCHAR(255),
                    score INTEGER DEFAULT 50,
                    verified BOOLEAN DEFAULT FALSE,
                    status VARCHAR(50) DEFAULT 'Available',
                    niche VARCHAR(100),
                    city VARCHAR(100),
                    date_added TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()
            self.logger.info("Lead pool table created or already exists")
            return True
        except Exception as e:
            self.logger.error(f"Error creating lead pool table: {str(e)}")
            self.conn.rollback()
            return False
    
    def generate_lead_pool(self, niche='general', city='general', count=100):
        """Generate leads for the lead pool"""
        self.logger.info(f"Generating {count} leads for {niche} in {city}")
        
        # Use existing scraper to generate leads
        leads = []
        
        try:
            # Generate leads from multiple sources
            if niche.lower() in ['saas', 'startup', 'tech']:
                # Use LinkedIn for SaaS and tech
                leads.extend(self.scraper.scrape_linkedin(niche, city, count//2))
            
            # Use Google Maps for local businesses
            leads.extend(self.scraper.scrape_google_maps(niche, city, count//3))
            
            # Use Yellow Pages as a fallback
            leads.extend(self.scraper.scrape_yellow_pages(niche, city, count//3))
            
            # Remove duplicates based on name and source
            unique_leads = []
            seen = set()
            for lead in leads:
                key = (lead.get('name', '').lower(), lead.get('source', '').lower())
                if key not in seen and lead.get('name') and lead.get('email'):
                    seen.add(key)
                    unique_leads.append(lead)
            
            # Add to lead pool
            for lead in unique_leads[:count]:
                self.cur.execute("""
                    INSERT INTO lead_pool (
                        name, email, source, score, verified, 
                        status, niche, city
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    lead.get('name', ''),
                    lead.get('email', ''),
                    lead.get('source', ''),
                    lead.get('score', 50),
                    lead.get('verified', False),
                    'Available',
                    niche,
                    city
                ))
            
            self.conn.commit()
            self.logger.info(f"Added {len(unique_leads[:count])} leads to pool for {niche} in {city}")
            return len(unique_leads[:count])
        
        except Exception as e:
            self.logger.error(f"Error generating lead pool: {str(e)}")
            self.conn.rollback()
            return 0
    
    def populate_initial_pool(self):
        """Populate initial lead pool with common niches and cities"""
        total_leads = 0
        
        for niche in self.common_niches:
            for city in self.common_cities:
                # Generate 20 leads per niche/city combination for initial pool
                count = self.generate_lead_pool(niche, city, 20)
                total_leads += count
                
        self.logger.info(f"Initial lead pool populated with {total_leads} leads")
        return total_leads
    
    def get_user_preferences(self, user_id):
        """Get user's niche and location preferences"""
        try:
            self.cur.execute("""
                SELECT niche, location FROM users WHERE id = %s
            """, (user_id,))
            
            result = self.cur.fetchone()
            if result:
                return {'niche': result[0], 'city': result[1]}
            
            return {'niche': 'general', 'city': 'general'}
        
        except Exception as e:
            self.logger.error(f"Error getting user preferences: {str(e)}")
            return {'niche': 'general', 'city': 'general'}
    
    def assign_leads_to_user(self, user_id, num_leads):
        """Assign leads from pool to a specific user"""
        try:
            # Get user preferences
            prefs = self.get_user_preferences(user_id)
            niche = prefs.get('niche', 'general') 
            city = prefs.get('city', 'general')
            
            # Find available leads in the pool that match preferences
            self.cur.execute("""
                SELECT id, name, email, source, score, verified, niche, city 
                FROM lead_pool 
                WHERE status = 'Available' 
                  AND (niche = %s OR %s = 'general')
                  AND (city = %s OR %s = 'general')
                ORDER BY score DESC
                LIMIT %s
            """, (niche, niche, city, city, num_leads))
            
            available_leads = self.cur.fetchall()
            
            if len(available_leads) < num_leads:
                # Not enough leads in pool, generate more
                self.logger.info(f"Not enough leads in pool for {user_id}, generating more")
                
            # Get user's CRM settings
            self.cur.execute("""
                SELECT hubspot_api_key, slack_webhook_url
                FROM users
                WHERE id = %s
            """, (user_id,))
            
            user_settings = self.cur.fetchone()
            hubspot_api_key = user_settings[0] if user_settings else None
            slack_webhook_url = user_settings[1] if user_settings else None
            
            self.generate_lead_pool(niche, city, num_leads - len(available_leads))
            
            # Try again to get leads
            self.cur.execute("""
                SELECT id, name, email, source, score, verified, niche, city 
                FROM lead_pool 
                WHERE status = 'Available' 
                  AND (niche = %s OR %s = 'general')
                  AND (city = %s OR %s = 'general')
                ORDER BY score DESC
                LIMIT %s
            """, (niche, niche, city, city, num_leads - len(available_leads)))
            
            additional_leads = self.cur.fetchall()
            available_leads.extend(additional_leads)
            
            # Mark leads as assigned in pool
            for lead in available_leads:
                lead_id = lead[0]
                self.cur.execute("""
                    UPDATE lead_pool SET status = 'Assigned' WHERE id = %s
                """, (lead_id,))
            
            # Insert into user's leads
            for lead in available_leads:
                lead_name = lead[1]
                lead_email = lead[2]
                lead_source = lead[3]
                lead_score = lead[4]
                lead_verified = lead[5]
                
                self.cur.execute("""
                    INSERT INTO leads (
                        user_id, name, email, source, score,
                        verified, status, date_added
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_id,
                    lead_name,
                    lead_email,
                    lead_source,
                    lead_score,
                    lead_verified,
                    'New',
                    datetime.now()
                ))
            
            self.conn.commit()
            self.logger.info(f"Assigned {len(available_leads)} leads to user {user_id}")
            return len(available_leads)
        
        except Exception as e:
            self.logger.error(f"Error assigning leads to user: {str(e)}")
            self.conn.rollback()
            return 0
    
    def process_lead_deliveries(self):
        """Process all scheduled lead deliveries"""
        try:
            # Get all active packages
            self.cur.execute("""
                SELECT up.id, up.user_id, up.package_name, up.lead_volume, 
                       up.created_at, up.next_delivery
                FROM user_packages up
                WHERE up.status = 'active'
            """)
            
            packages = self.cur.fetchall()
            
            for package in packages:
                package_id, user_id, package_name, lead_volume, created_at, next_delivery = package
                
                # Convert package_name to lowercase for comparison
                package_name_lower = package_name.lower() if package_name else ''
                
                # Check if it's time for delivery
                now = datetime.now()
                should_deliver = False
                
                if next_delivery is None or now >= next_delivery:
                    should_deliver = True
                
                if not should_deliver:
                    continue
                
                # Calculate leads to deliver and next delivery date
                leads_to_deliver = 0
                next_delivery_date = now
                
                if package_name_lower == 'launch':
                    # Lead Launch: One-time delivery of 50 leads
                    created_date = created_at if created_at else now - timedelta(days=8)
                    days_since_creation = (now - created_date).days
                    
                    if days_since_creation >= 7:
                        leads_to_deliver = 50
                        next_delivery_date = now + timedelta(days=365)  # Far future, one-time
                
                elif package_name_lower == 'engine':
                    # Lead Engine: Weekly delivery (150/month ÷ 4 = ~38 per week)
                    leads_to_deliver = 38
                    next_delivery_date = now + timedelta(days=7)
                
                elif package_name_lower == 'accelerator':
                    # Lead Accelerator: Daily delivery (300/month ÷ 30 = 10 per day)
                    leads_to_deliver = 10
                    next_delivery_date = now + timedelta(days=1)
                
                elif package_name_lower == 'empire':
                    # Lead Empire: Daily delivery (600/month ÷ 30 = 20 per day)
                    leads_to_deliver = 20
                    next_delivery_date = now + timedelta(days=1)
                
                if leads_to_deliver > 0:
                    # Assign leads to the user
                    leads_assigned = self.assign_leads_to_user(user_id, leads_to_deliver)
                    
                    if leads_assigned > 0:
                        # Update next delivery date
                        self.cur.execute("""
                            UPDATE user_packages 
                            SET next_delivery = %s 
                            WHERE id = %s
                        """, (next_delivery_date, package_id))
                        
                        self.conn.commit()
                        
                        # Send notification email (via web_app.py send_lead_email function)
                        from web_app import send_lead_email
                        threading.Thread(
                            target=send_lead_email,
                            args=(user_id, package_name)
                        ).start()
                        
                        self.logger.info(f"Delivered {leads_assigned} leads to user {user_id} ({package_name})")
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error processing lead deliveries: {str(e)}")
            self.conn.rollback()
            return False
    
    def schedule_weekly_pool_refresh(self):
        """Run this to refresh the lead pool weekly with new leads"""
        for niche in self.common_niches:
            for city in self.common_cities:
                self.generate_lead_pool(niche, city, 50)
        
        self.logger.info("Weekly lead pool refresh completed")
        
    def __del__(self):
        """Clean up database connections"""
        if hasattr(self, 'cur') and self.cur:
            self.cur.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
def sync_lead_to_crm(lead, user):
    """
    Sync a lead to the user's configured CRM system
    """
    try:
        # Check if user has configured HubSpot integration
        if hasattr(user, 'hubspot_api_key') and user.hubspot_api_key:
            # Add the lead to HubSpot
            crm_id = add_lead_to_hubspot(lead, user.hubspot_api_key)
            if crm_id:
                # Update the lead with the CRM ID
                lead.crm_id = crm_id
                
                # Send Slack notification if configured
                if hasattr(user, 'slack_webhook_url') and user.slack_webhook_url:
                    notify_slack(lead, user.slack_webhook_url)
                
                # Update status if needed
                if lead.status == 'Emailed':
                    update_lead_status(lead, 'Contacted', user.hubspot_api_key)
                    
                return True
    except Exception as e:
        self.logger.error(f"Error syncing lead to CRM: {str(e)}")
    
    return False

def sync_leads_to_crm(leads, user):
    """
    Sync multiple leads to a user's CRM
    """
    synced_count = 0
    for lead in leads:
        if sync_lead_to_crm(lead, user):
            synced_count += 1
    
    self.logger.info(f"Synced {synced_count} of {len(leads)} leads to CRM for user {user.id}")
    return synced_count
