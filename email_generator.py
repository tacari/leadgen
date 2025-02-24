import logging
from openai import OpenAI
from config import OPENAI_API_KEY

class EmailGenerator:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise ValueError("OpenAI API key is not set")
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
            generated_content = response.choices[0].message.content
            self.logger.info(f"Successfully generated email for dentist: {lead_data.get('name')}")
            return generated_content
        except Exception as e:
            self.logger.error(f"Error generating dentist email: {str(e)}")
            return self._get_fallback_dentist_email(lead_data)

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
            generated_content = response.choices[0].message.content
            self.logger.info(f"Successfully generated email for SaaS company: {lead_data.get('business_name')}")
            return generated_content
        except Exception as e:
            self.logger.error(f"Error generating SaaS email: {str(e)}")
            return self._get_fallback_saas_email(lead_data)

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

    def _get_fallback_dentist_email(self, lead_data):
        """Return a template-based email when API fails"""
        with open('templates/dentist_email.txt', 'r') as f:
            template = f.read()
        return template.format(
            name=lead_data.get('name', 'Doctor'),
            business_name=lead_data.get('business_name', 'your practice'),
            city=lead_data.get('city', 'your city'),
            sender_name="Your Lead Generation Expert"
        )

    def _get_fallback_saas_email(self, lead_data):
        """Return a template-based email when API fails"""
        with open('templates/saas_email.txt', 'r') as f:
            template = f.read()
        return template.format(
            name=lead_data.get('name', 'there'),
            business_name=lead_data.get('business_name', 'your company'),
            sender_name="Your Lead Generation Expert"
        )