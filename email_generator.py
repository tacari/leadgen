import logging
from openai import OpenAI
from config import OPENAI_API_KEY

class EmailGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.logger = logging.getLogger(__name__)
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        self.model = "gpt-4o"

    def generate_dentist_email(self, lead_data):
        """Generate personalized email for dentist leads"""
        try:
            prompt = self._create_dentist_prompt(lead_data)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in dental marketing."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error generating dentist email: {str(e)}")
            return None

    def generate_saas_email(self, lead_data):
        """Generate personalized email for SaaS leads"""
        try:
            prompt = self._create_saas_prompt(lead_data)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a B2B SaaS marketing expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error generating SaaS email: {str(e)}")
            return None

    def _create_dentist_prompt(self, lead_data):
        return f"""
        Create a personalized cold email for a dentist with the following information:
        Name: {lead_data.get('name', 'Doctor')}
        Business: {lead_data.get('business_name', '')}
        City: {lead_data.get('city', '')}

        The email should:
        1. Highlight our lead generation service for dentists
        2. Mention our $500/month pilot program
        3. Focus on getting 50 new patients per month
        4. Include a clear call to action
        5. Keep it concise and professional
        """

    def _create_saas_prompt(self, lead_data):
        return f"""
        Create a personalized cold email for a SaaS company with the following information:
        Company: {lead_data.get('business_name', '')}
        Contact: {lead_data.get('name', '')}

        The email should:
        1. Highlight our B2B lead generation service
        2. Mention our $500/month pilot program
        3. Focus on generating 100 qualified leads per month
        4. Include specific SaaS industry understanding
        5. Keep it concise and professional
        """
