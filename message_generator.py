
import os
import logging
import openai
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up OpenAI API key
openai.api_key = os.environ.get('OPENAI_API_KEY')

class MessageGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_message(self, lead):
        """Generate a personalized outreach message based on lead data"""
        try:
            # Extract lead details
            name = lead.get('name', 'your business')
            niche = lead.get('niche', 'your industry')
            city = lead.get('city', 'your area')
            source = lead.get('source', 'our research')
            
            # For testing/fallback without API calls
            if not openai.api_key:
                return self._generate_template_message(name, niche, city, source)
            
            # Generate with OpenAI
            prompt = f"""
            Create a friendly, concise outreach message (max 3 sentences) for a lead with these details:
            - Business Name: {name}
            - Industry/Niche: {niche}
            - Location: {city}
            - Found via: {source}
            
            The message should sound natural and personalized, mention their location and industry, 
            and briefly suggest how we can help grow their business. Don't use emojis or hashtags.
            """
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at crafting personalized business outreach messages."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            message = response.choices[0].message.content.strip()
            self.logger.info(f"Generated personalized message for {name}")
            return message
            
        except Exception as e:
            self.logger.error(f"Error generating message: {str(e)}")
            # Fallback to template
            return self._generate_template_message(name, niche, city, source)
    
    def _generate_template_message(self, name, niche, city, source):
        """Fallback template-based message generation"""
        templates = [
            f"Hi {name}, I noticed your {niche} business in {city} and wanted to reach out about how we can help increase your customer base by up to 30% this quarter.",
            f"Hello from Leadzap! As a {niche} business in {city}, we thought you'd be interested in our lead generation services that can boost your revenue.",
            f"I came across your {niche} business while researching successful companies in {city}, and wanted to discuss how our lead generation services can help you scale."
        ]
        
        # Use the business name to consistently select one of the templates
        index = sum(ord(c) for c in name) % len(templates) if name else 0
        return templates[index]
    
    def generate_email_template(self, lead):
        """Generate a more detailed email template"""
        try:
            # Extract lead details
            name = lead.get('name', 'your business')
            niche = lead.get('niche', 'your industry')
            city = lead.get('city', 'your area')
            
            # For testing/fallback without API calls
            if not openai.api_key:
                return self._generate_template_email(name, niche, city)
            
            # Generate with OpenAI
            prompt = f"""
            Create a professional email template for outreach to a {niche} business called {name} in {city}.
            The email should:
            1. Have a subject line
            2. Greet them personally
            3. Briefly introduce our lead generation service
            4. Mention a specific benefit for their {niche} business
            5. Include a clear call to action
            6. Have a professional signature
            
            Keep it under 200 words total.
            """
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at crafting business development emails."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            email = response.choices[0].message.content.strip()
            self.logger.info(f"Generated email template for {name}")
            return email
            
        except Exception as e:
            self.logger.error(f"Error generating email template: {str(e)}")
            # Fallback to template
            return self._generate_template_email(name, niche, city)
    
    def _generate_template_email(self, name, niche, city):
        """Fallback template-based email generation"""
        current_year = datetime.now().year
        
        return f"""
Subject: Increase Your {niche.title()} Business Revenue in {city}

Hello {name},

I hope this email finds you well. I'm reaching out because we've been helping {niche} businesses in {city} generate more qualified leads, and I thought you might be interested.

Our Leadzap platform helps businesses like yours:
• Identify and connect with your ideal customers
• Generate 25-40% more qualified leads monthly
• Reduce customer acquisition costs

Many {niche} businesses in {city} are already seeing 3-4x ROI with our service. Would you be open to a quick 15-minute call this week to see if we might be a good fit for your business goals in {current_year}?

Simply reply with a time that works for you.

Best regards,
Alex Johnson
Lead Generation Specialist
Leadzap
Phone: (555) 123-4567
"""
import logging
import random
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageGenerator:
    """
    Generate personalized outreach messages for leads
    """
    
    def __init__(self):
        """Initialize message generator with templates"""
        self.email_templates = {
            'default': "Hi {name},\n\nI noticed {company_name} while researching {industry} companies in {location}. I'd love to connect and learn more about your business needs.\n\nBest regards,\n{sender_name}"
        }
        
        self.linkedin_templates = {
            'default': "Hi {name}, I came across {company_name} while looking at {industry} businesses in {location}. Would love to connect!"
        }
    
    def generate_message(self, lead):
        """Generate a personalized message for a lead"""
        try:
            # Extract lead details
            name = lead.get('name', 'there')
            company_name = lead.get('name', 'your company')
            industry = lead.get('niche', 'your industry')
            location = lead.get('city', 'your area')
            score = lead.get('score', 50)
            
            # Base message formula
            if score > 75:
                # High-quality lead gets premium template
                message = f"Hi {name},\n\nI was impressed by {company_name} when researching leading {industry} providers in {location}. Your approach to {self._generate_industry_insight(industry)} caught my attention.\n\nI'd love to connect and discuss how we might be able to support your growth goals this quarter.\n\nLooking forward to connecting,\nYour Name"
            else:
                # Standard template for regular leads
                message = f"Hello {name},\n\nI came across {company_name} while looking into {industry} companies in {location}. Would you be open to a quick conversation about how we've helped similar businesses improve their results?\n\nBest regards,\nYour Name"
                
            return message
            
        except Exception as e:
            logger.error(f"Error generating message: {str(e)}")
            # Fallback template
            return f"Hello, I found your business online and would like to connect. Best regards, Your Name"
    
    def generate_email_template(self, lead):
        """Generate a personalized email template for a lead"""
        try:
            # Extract lead details
            name = lead.get('name', 'there')
            company_name = lead.get('name', 'your company')
            industry = lead.get('niche', 'your industry')
            location = lead.get('city', 'your area')
            score = lead.get('score', 50)
            source = lead.get('source', 'online')
            
            # Email subject options
            subject_lines = [
                f"Quick question about {company_name}",
                f"Connecting with {industry} leaders in {location}",
                f"{name}, let's connect",
                f"Opportunity for {company_name}"
            ]
            
            # Pick random subject
            subject = random.choice(subject_lines)
            
            # Generate body based on lead quality
            if score > 75:
                body = f"""
                <p>Hi {name},</p>
                
                <p>I came across {company_name} while researching leading {industry} businesses in {location} and was particularly impressed by your {self._generate_company_strength(industry)}.</p>
                
                <p>I've been working with several {industry} businesses in {location} to help them {self._generate_industry_benefit(industry)}, and I thought there might be some synergy in us connecting.</p>
                
                <p>Would you be open to a quick 15-minute call this week to explore if there's a fit?</p>
                
                <p>Best regards,<br>
                Your Name<br>
                Your Company</p>
                """
            else:
                body = f"""
                <p>Hello {name},</p>
                
                <p>I noticed {company_name} while looking at {industry} companies in {location}.</p>
                
                <p>We specialize in helping businesses like yours {self._generate_industry_benefit(industry)}.</p>
                
                <p>Would you be interested in learning more about how we've helped similar companies?</p>
                
                <p>Regards,<br>
                Your Name<br>
                Your Company</p>
                """
                
            # Clean up whitespace
            body = "\n".join([line.strip() for line in body.split("\n")])
            
            return {
                "subject": subject,
                "body": body
            }
            
        except Exception as e:
            logger.error(f"Error generating email template: {str(e)}")
            # Fallback template
            return {
                "subject": "Connecting with your business",
                "body": "<p>Hello,</p><p>I found your business online and would like to connect.</p><p>Best regards,<br>Your Name</p>"
            }
    
    def generate_linkedin_dm(self, lead, package_name="Launch"):
        """Generate a personalized LinkedIn DM for a lead"""
        try:
            # Extract lead details
            name = lead.get('name', 'there').split()[0]  # First name only for LinkedIn
            company_name = lead.get('name', 'your company')
            industry = lead.get('niche', 'your industry')
            
            # Different templates based on package level
            if package_name.lower() in ['empire', 'accelerator']:
                message = f"Hi {name}, I noticed {company_name}'s work in the {industry} space. I've been helping similar businesses improve their results. Would you be open to connecting?"
            else:
                message = f"Hi {name}, I came across {company_name} and would like to connect. I work with {industry} businesses and thought we might benefit from networking."
                
            return message
            
        except Exception as e:
            logger.error(f"Error generating LinkedIn DM: {str(e)}")
            return f"Hi, I found your profile while researching {industry} professionals. Would you be open to connecting?"
    
    def _generate_industry_insight(self, industry):
        """Generate industry-specific insight"""
        insights = {
            "plumbing": "customer service and quick response times",
            "dental": "patient-centered care approach",
            "saas": "innovative product solutions",
            "marketing": "creative campaign strategies",
            "real estate": "property presentation and client communication",
            "fitness": "personalized training programs",
            "restaurant": "unique customer experience",
            "consulting": "data-driven approach to client challenges"
        }
        
        # Default insight if industry not in dict
        return insights.get(industry.lower(), "professional approach to customer service")
    
    def _generate_company_strength(self, industry):
        """Generate company-specific strength based on industry"""
        strengths = {
            "plumbing": "reputation for reliability",
            "dental": "commitment to patient comfort",
            "saas": "innovative platform",
            "marketing": "creative portfolio",
            "real estate": "impressive property listings",
            "fitness": "community-focused approach",
            "restaurant": "unique menu offerings",
            "consulting": "expert team"
        }
        
        return strengths.get(industry.lower(), "professional online presence")
    
    def _generate_industry_benefit(self, industry):
        """Generate industry-specific benefit"""
        benefits = {
            "plumbing": "increase customer bookings by 30% within 90 days",
            "dental": "attract 20+ new patients per month",
            "saas": "streamline their lead generation process",
            "marketing": "increase campaign ROI by 40%",
            "real estate": "connect with qualified buyers faster",
            "fitness": "increase membership retention rates",
            "restaurant": "boost online orders and reservations",
            "consulting": "scale their client acquisition process"
        }
        
        return benefits.get(industry.lower(), "grow their business more efficiently")
