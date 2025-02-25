# Leadzap - AI-Powered Lead Generation Platform

An advanced lead generation platform leveraging AI to automate lead collection and outreach for dentists and SaaS startups.

## Features

- AI-powered lead targeting and collection
- Multi-channel outreach automation
- Lead scoring and analytics
- Responsive dark-mode interface
- Secure user authentication

## Packages

- **Lead Launch** ($499) - 50 qualified leads
- **Lead Engine** ($1,499/month) - 150 leads/month
- **Lead Accelerator** ($2,999/month) - 300 leads/month
- **Lead Empire** ($5,999/month) - 600 leads/month

## Tech Stack

- Python/Flask
- AI-driven lead generation
- SendGrid for email automation
- Stripe for payments
- PostgreSQL database

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```
4. Run the application:
```bash
python web_app.py
```

## Environment Variables

- `SECRET_KEY` - Flask secret key
- `OPENAI_API_KEY` - OpenAI API key for AI features
- `DATABASE_URL` - PostgreSQL database URL
- `SENDGRID_API_KEY` - SendGrid API key for email automation
- `STRIPE_SECRET_KEY` - Stripe secret key for payments

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
