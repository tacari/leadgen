
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
