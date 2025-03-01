
import os
import logging
import openai
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MessageGenerator:
    """Generates personalized outreach messages for leads using GPT"""
    
    def __init__(self):
        # Initialize with OpenAI API key from environment variable
        self.api_key = os.environ.get('OPENAI_API_KEY', '')
        if self.api_key:
            openai.api_key = self.api_key
        else:
            logger.warning("No OpenAI API key found. Message generation will use fallback templates.")
    
    def generate_message(self, lead):
        """Generate a personalized outreach message for a lead"""
        try:
            if not self.api_key:
                return self._generate_fallback_message(lead)
                
            # Prepare lead data for prompt
            lead_name = lead.get('name', 'the business')
            niche = lead.get('niche', 'your industry')
            city = lead.get('city', 'your area')
            source = lead.get('source', 'online')
            
            # Construct prompt for GPT
            prompt = f"""
            Create a short, friendly, and personalized outreach message for a potential client with the following information:
            
            Business Name: {lead_name}
            Industry/Niche: {niche}
            Location: {city}
            Source: {source}
            
            The message should be concise (60-80 words), friendly but professional, and tailored to their specific business.
            Focus on how we can help them grow their {niche} business in {city}. 
            Don't use generic phrases like "I hope this email finds you well".
            Don't use obvious templates or formal language. Make it conversational and genuine.
            """
            
            # Call OpenAI API
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at writing personalized business outreach messages that sound natural and get responses."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            # Extract and return the message
            message = response.choices[0].message.content.strip()
            logger.info(f"Generated personalized message for {lead_name}")
            return message
            
        except Exception as e:
            logger.error(f"Error generating message with GPT: {str(e)}")
            return self._generate_fallback_message(lead)
    
    def _generate_fallback_message(self, lead):
        """Generate a fallback message if API is unavailable"""
        lead_name = lead.get('name', 'the business')
        niche = lead.get('niche', 'your industry')
        city = lead.get('city', 'your area')
        
        templates = [
            f"Hi {lead_name}, I noticed your {niche} business in {city} and wanted to connect. We've helped similar businesses increase their leads by 30-50%. Would you be open to a quick chat about how we might be able to do the same for you?",
            
            f"Hey there {lead_name}! I work with {niche} businesses in {city} to generate more qualified leads. Our clients typically see a 40% increase in new business within 90 days. Are you currently looking to grow your customer base?",
            
            f"I came across {lead_name} while researching top {niche} providers in {city}. We specialize in connecting businesses like yours with customers actively looking for your services. Would you be interested in learning how we're helping similar businesses grow?"
        ]
        
        # Select template based on business name to ensure consistency
        template_index = sum(ord(c) for c in lead_name) % len(templates)
        return templates[template_index]
    
    def generate_email_template(self, lead):
        """Generate an email template for the lead"""
        message = self.generate_message(lead)
        lead_name = lead.get('name', 'the business')
        
        email_template = f"""
Subject: Growing Your Business at {lead_name}

{message}

Looking forward to connecting,
[Your Name]
Lead Generation Specialist
Leadzap
[Your Phone]
        """
        
        return email_template.strip()
