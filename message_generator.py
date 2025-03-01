
import os
import logging
import openai
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageGenerator:
    def __init__(self):
        self.api_key = os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            logger.warning("OpenAI API key not found. Personalized messaging will use fallback templates.")
        else:
            openai.api_key = self.api_key
            logger.info("OpenAI API initialized for personalized messaging")
            
    def generate_message(self, lead):
        """Generate a personalized message for a lead using OpenAI"""
        try:
            if not self.api_key:
                return self._generate_template_message(lead)
                
            # Extract lead data
            name = lead.get('name', 'there')
            niche = lead.get('niche', lead.get('source', 'business'))
            city = lead.get('city', 'your area')
            source = lead.get('source', 'online')
            score = lead.get('score', 75)
            
            # Create prompt
            prompt = f"""
            Generate a personalized outreach message for a lead named {name}, who is a {niche} in {city} found on {source}.
            The lead has a quality score of {score}/100.
            The message should be friendly, concise (under 100 words), and encourage them to learn more about our lead generation services.
            Write as if you're sending them an initial outreach message.
            """
            
            # Call OpenAI API
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=prompt,
                max_tokens=150,
                temperature=0.7,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            message = response.choices[0].text.strip()
            logger.info(f"Generated personalized message for {name}")
            return message
        
        except Exception as e:
            logger.error(f"Error generating message with OpenAI: {str(e)}")
            return self._generate_template_message(lead)
    
    def _generate_template_message(self, lead):
        """Fallback to template-based message if API fails"""
        name = lead.get('name', 'there')
        niche = lead.get('niche', lead.get('source', 'business'))
        city = lead.get('city', 'your area')
        
        templates = [
            f"Hi {name}, I noticed your {niche} business in {city} and wanted to reach out. Our lead generation service has helped similar businesses increase customer acquisition by 35%. Would you be open to a quick chat about how we could help you grow?",
            
            f"Hello {name}, I came across your {niche} services while researching businesses in {city}. We specialize in delivering qualified leads to businesses like yours. I'd love to share how we can help you reach more customers.",
            
            f"Hi {name}, as a {niche} professional in {city}, you might be interested in our lead generation service that's delivering great results for others in your industry. Would you be available for a brief conversation about growing your client base?"
        ]
        
        # Choose template based on name length (predictable but seems random)
        index = len(name) % len(templates)
        return templates[index]
    
    def generate_email_template(self, lead):
        """Generate a longer email template"""
        message = self.generate_message(lead)
        name = lead.get('name', 'there').split()[0]  # Get first name
        
        email_template = f"""
Subject: Helping Your Business Grow in {lead.get('city', 'Your Area')}

Hi {name},

{message}

Our lead generation service has helped businesses like yours:
• Increase qualified leads by 35%
• Reduce customer acquisition costs
• Grow revenue predictably

When would be a good time for a quick 15-minute call this week?

Best regards,
The LeadZap Team
        """
        
        return email_template.strip()
