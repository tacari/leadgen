import os
import sys
import logging
import json
import psutil
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify
from supabase import create_client, Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import stripe
import psycopg2
import threading
import csv
import io
import base64
from flask_apscheduler import APScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    try:
        logger.info(f"Checking for processes using port {port}")
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        logger.info(f"Found process {proc.pid} using port {port}")
                        proc.terminate()
                        proc.wait(timeout=5)
                        logger.info(f"Terminated process {proc.pid}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        logger.error(f"Error checking/terminating port {port}: {str(e)}")
    return False

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')

# Add current_user to all template contexts
@app.context_processor
def inject_user():
    class User:
        is_authenticated = False
        
    current_user = User()
    if 'user_id' in session:
        current_user.is_authenticated = True
        
    return {
        'current_user': current_user, 
        'user': session.get('username'),
        'username': session.get('username')
    }

# Initialize Supabase client
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_API_KEY')
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')


def ensure_tables_exist():
    """Ensure all required tables exist"""
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()

        # Create users table first
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(255) PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                hubspot_api_key VARCHAR(255),
                slack_webhook_url VARCHAR(255),
                competitor_urls TEXT[]
            );
        """)

        # Create user_packages table with foreign key to users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_packages (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) REFERENCES users(id),
                package_name VARCHAR(255) NOT NULL,
                lead_volume INTEGER NOT NULL,
                stripe_subscription_id VARCHAR(255),
                status VARCHAR(50) NOT NULL,
                next_delivery TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create leads table with foreign key to users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(255) REFERENCES users(id),
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                source VARCHAR(255),
                score INTEGER DEFAULT 50,
                verified BOOLEAN DEFAULT FALSE,
                status VARCHAR(50) DEFAULT 'new',
                date_added TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                competitor_source VARCHAR(255),
                conversion_probability REAL
            );
        """)

        conn.commit()
        logger.info("Database tables created successfully")

    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()

def ensure_local_data_files():
    """Ensure local data files exist"""
    data_dir = 'data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"Created data directory: {data_dir}")

    for file_name in ['users.json', 'user_packages.json', 'leads.json']:
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump([], f)
            logger.info(f"Created empty JSON file: {file_path}")
        else:
            # Validate the JSON format and fix if needed
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    if not content:  # Empty file
                        with open(file_path, 'w') as f:
                            json.dump([], f)
                            logger.info(f"Fixed empty file: {file_path}")
                    else:
                        json.loads(content)  # Try to parse JSON
            except json.JSONDecodeError:
                # Invalid JSON, reset it
                logger.error(f"Invalid JSON in {file_path}, resetting to empty array")
                with open(file_path, 'w') as f:
                    json.dump([], f)

# Initialize local files and database tables
ensure_local_data_files()
ensure_tables_exist()

def schedule_lead_delivery():
    """Schedule lead delivery based on package type"""
    try:
        # Try to fetch from Supabase
        try:
            users = supabase.table('user_packages').select('user_id, package_name').eq('status', 'active').execute().data
        except Exception as e:
            logger.error(f"Error in lead delivery schedule: {str(e)}")
            # Fallback to file-based data
            with open('data/user_packages.json', 'r') as f:
                users = json.load(f)
                users = [u for u in users if u.get('status') == 'active']

        for user in users:
            user_id = user['user_id']
            package = user['package_name']

            # Only deliver on appropriate schedule
            if package == 'engine' and datetime.now().weekday() == 0:  # Monday
                from scraper import LeadScraper
                scraper = LeadScraper()
                scraper.generate_leads_for_package(user_id, 38)  # Weekly batch
                send_lead_email(user_id, package)

            elif package in ['accelerator', 'empire']:  # Daily delivery
                from scraper import LeadScraper
                scraper = LeadScraper()
                volume = 12 if package == 'accelerator' else 25
                scraper.generate_leads_for_package(user_id, volume)
                send_lead_email(user_id, package)

    except Exception as e:
        logger.error(f"Error in lead delivery schedule: {str(e)}")

def score_lead(lead_data):
    """Calculate a lead score from 1-100 based on various factors using AI-powered analysis

    Factors considered:
    - Source quality (LinkedIn, Google, etc.)
    - Email verification status
    - Intent signals (keywords in name, description or other fields)
    - Company profile (website, size, industry)
    - Behavioral data (if available)
    - ML prediction (if model is available)

    Returns:
        int: Score between 1-100
    """
    try:
        # Try using ML model for scoring
        from ml_engine import lead_model
        
        # Use ML model if it's ready (singleton)
        if lead_model.pipeline is not None:
            # Get ML prediction for this lead
            ml_scores = lead_model.predict([lead_data])
            if ml_scores and len(ml_scores) > 0:
                return ml_scores[0]
    except Exception as e:
        logger.error(f"ML scoring error: {str(e)}. Falling back to rule-based scoring.")
    
    # Fallback to rule-based scoring if ML fails
    
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
        if src in source:
            score += points
            break

    # Add points for verified contact methods
    if lead_data.get('verified', False):
        score += 10
    if lead_data.get('phone_verified', False):
        score += 12
    if lead_data.get('linkedin_verified', False):
        score += 15

    # Email domain analysis
    if lead_data.get('email'):
        email = lead_data.get('email', '').lower()
        if '@' in email:
            domain = email.split('@')[1]
            # Company domains score higher than free email providers
            if any(provider in domain for provider in ['gmail', 'yahoo', 'hotmail', 'outlook']):
                score += 5
            else:
                score += 12

    # Check for intent signals in name or other fields
    intent_keywords = ['looking for', 'need', 'want', 'searching', 'interested',
                      'inquiry', 'request', 'seeking', 'explore', 'considering']

    # Check name for intent signals
    lead_name = lead_data.get('name', '').lower()
    for keyword in intent_keywords:
        if keyword in lead_name:
            score += 15
            break

    # Check description for intent signals if available
    description = lead_data.get('description', '').lower()
    if description:
        for keyword in intent_keywords:
            if keyword in description:
                score += 20
                break
        # Basic points for having a description
        score += 5

    # Website availability bonus
    if lead_data.get('website'):
        score += 8

    # Phone availability bonus
    if lead_data.get('phone'):
        score += 5

    # Industry relevance (if available)
    industry = lead_data.get('industry', '').lower()
    if industry:
        # Add logic here to score based on target industries
        score += 5

    # Competitor source bonus
    if lead_data.get('competitor_source'):
        score += 10

    # Cap the score at 100
    return min(100, score)

def send_lead_email(user_id, package_name):
    """Send leads via email using SendGrid"""
    try:
        # Get user email
        user_data = supabase.table('users').select('email').eq('id', user_id).execute()
        if not user_data.data:
            logger.error(f"No user found for ID {user_id}")
            return False

        email = user_data.data[0]['email']
        today = datetime.now().date().isoformat()

        # Get today's leads
        leads = supabase.table('leads').select('*').eq('user_id', user_id).gte('date_added', today).execute()

        if not leads.data:
            logger.warning(f"No leads to send for user {user_id}")
            return False

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Email', 'Phone', 'LinkedIn URL', 'Source', 'Competitor Source', 'Score', 'Email Verified', 'Phone Verified', 'LinkedIn Verified', 'Status', 'Date Added'])

        for lead in leads.data:
            writer.writerow([
                lead.get('name', 'N/A'),
                lead.get('email', 'N/A'),
                lead.get('phone', 'N/A'),
                lead.get('linkedin_url', 'N/A'),
                lead.get('source', 'N/A'),
                lead.get('competitor_source', 'N/A'),
                lead.get('score', 0),
                lead.get('verified', False),
                lead.get('phone_verified', False),
                lead.get('linkedin_verified', False),
                lead.get('status', 'New'),
                lead.get('date_added', today)
            ])

        csv_content = output.getvalue()
        csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')

        # Calculate competitor leads
        competitor_leads_count = sum(1 for lead in leads.data if lead.get('competitor_source'))

        # Create email with HTML template
        message = Mail(
            from_email='leads@leadzap.io',
            to_emails=email,
            subject=f'Your {package_name} Leads - {today}',
            html_content=f'''
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #7B00FF;">Here are your latest {package_name} leads!</h2>
                    <p>We've generated {len(leads.data)} fresh leads for your business.</p>

                    <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #333;">Quick Stats:</h3>
                        <ul>
                            <li>High-scoring leads (75+): {sum(1 for lead in leads.data if lead.get('score', 0) > 75)}</li>
                            <li>Email verified: {sum(1 for lead in leads.data if lead.get('verified', False))}</li>
                            <li>Phone verified: {sum(1 for lead in leads.data if lead.get('phone_verified', False))}</li>
                            <li>LinkedIn verified: {sum(1 for lead in leads.data if lead.get('linkedin_verified', False))}</li>
                            <li>Fully verified leads: {sum(1 for lead in leads.data if lead.get('verified', False) and lead.get('phone_verified', False) and lead.get('linkedin_verified', False))}</li>
                            {f'<li>Competitor insight leads: {competitor_leads_count}</li>' if competitor_leads_count > 0 and package_name.lower() != 'launch' else ''}
                        </ul>
                    </div>

                    <p>Access your dashboard for more insights and to manage your leads.</p>

                    <div style="margin-top: 30px; padding: 20px; border-top: 1px solid #eee;">
                        <p style="color: #666; font-size: 12px;">
                            Your leads are attached in CSV format for easy import into your CRM.
                            {f'<br><br><strong>Pro Tip:</strong> We have included leads from your competitors websites to give you an edge!' if competitor_leads_count > 0 and package_name.lower() != 'launch' else ''}
                        </p>
                    </div>
                </div>
            '''
        )

        # Attach CSV
        attachment = Attachment(
            FileContent(csv_base64),
            FileName(f'leadzap_leads_{today}.csv'),
            FileType('text/csv'),
            Disposition('attachment')
        )
        message.attachment = attachment

        # Send email
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)

        logger.info(f"Sent lead email to {email} with status code {response.status_code}")
        return response.status_code == 202

    except Exception as e:
        logger.error(f"Error sending lead email: {str(e)}")
        return False

@app.route('/')
def home():
    return render_template('landing.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    # Create a mock current_user object for templates
    class User:
        is_authenticated = False
        
    current_user = User()
    if 'user_id' in session:
        current_user.is_authenticated = True
        
    return render_template('contact.html', current_user=current_user)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')


@app.route('/lead-history')
def lead_history():
    # Sample historical data for development
    leads = [
        {
            'name': "Joe's Plumbing",
            'email': 'joe@example.com',
            'source': 'Yellow Pages',
            'score': 85,
            'status': 'Emailed',
            'date_added': '2025-02-25',
            'notes': 'Called 2/26',
            'outcome': 'Meeting scheduled'
        },
        {
            'name': "Sarah's Dental",
            'email': 'sarah@example.com',
            'source': 'LinkedIn',
            'score': 92,
            'status': 'Pending',
            'date_added': '2025-02-24',
            'notes': 'High priority lead',
            'outcome': 'Pending contact'
        },
        {
            'name': "Tech Solutions Inc",
            'email': 'info@techsolutions.com',
            'source': 'Google Ads',
            'score': 78,
            'status': 'Replied',
            'date_added': '2025-02-23',
            'notes': 'Interested in Enterprise plan',
            'outcome': 'In negotiations'
        }
    ]

    # Quick stats and source insights
    total_leads = len(leads)
    high_score = sum(1 for lead in leads if lead['score'] > 75)
    converted = sum(1 for lead in leads if lead['status'] == 'Converted')
    avg_score = round(sum(lead['score'] for lead in leads) / total_leads, 2) if total_leads > 0 else 0
    stats = {'total': total_leads, 'high_score': high_score, 'converted': converted, 'avg_score': avg_score}

    # Calculate source insights
    sources = {}
    for lead in leads:
        source = lead['source']
        if source not in sources:
            sources[source] = {'count': 0, 'high_score': 0}
        sources[source]['count'] += 1
        if lead['score'] > 75:
            sources[source]['high_score'] += 1
    source_insights = {k: {'count': v['count'], 'high_score_percent': round(v['high_score'] / v['count'] * 100, 1)}
                      for k, v in sources.items()}

    return render_template('lead_history.html',
                         leads=leads,
                         stats=stats,
                         source_insights=source_insights)

@app.route('/download_leads')
def download_leads():
    # Sample data for CSV export
    leads = [
        {
            'name': "Joe's Plumbing",
            'email': 'joe@example.com',
            'source': 'Yellow Pages',
            'score': 85,
            'status': 'Emailed',
            'date_added': '2025-02-25'
        },
        {
            'name': "Sarah's Dental",
            'email': 'sarah@example.com',
            'source': 'LinkedIn',
            'score': 92,
            'status': 'Pending',
            'date_added': '2025-02-24'
        }
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Source', 'Score', 'Status', 'Date Added'])

    for lead in leads:
        writer.writerow([
            lead['name'],
            lead['email'],
            lead['source'],
            lead['score'],
            lead['status'],
            lead['date_added']
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=leads.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/analytics')
def analytics():
    if 'user_id' not in session:
        flash('Please log in to view analytics.')
        return redirect(url_for('login'))
        
    try:
        # Sample analytics data for development
        leads = [
            {
                'date_added': '2025-02-25',
                'leads_added': 10,
                'emailed': 8,
                'replies': 2,
                'conversions': 1,
                'avg_score': 82,
                'source': 'LinkedIn'
            },
            {
                'date_added': '2025-02-24',
                'leads_added': 15,
                'emailed': 12,
                'replies': 3,
                'conversions': 1,
                'avg_score': 78,
                'source': 'Yellow Pages'
            }
        ]

        analytics = {
            'total_leads': 25,
            'emailed': 20,
            'replies': 5,
            'conversions': 2,
            'charts': {
                'daily': [10, 15],
                'dates': ['Feb 24', 'Feb 25'],
                'status': {
                    'labels': ['Pending', 'Emailed', 'Replied', 'Converted'],
                    'data': [5, 15, 3, 2]
                }
            }
        }

        # Calculate source insights
        sources = {}
        for lead in leads:
            source = lead['source']
            if source not in sources:
                sources[source] = {'count': 0, 'high_score_leads': 0, 'total_score': 0}
            sources[source]['count'] += lead['leads_added']
            sources[source]['high_score_leads'] += lead['leads_added'] if lead['avg_score'] > 75 else 0
            sources[source]['total_score'] += lead['avg_score'] * lead['leads_added']

        source_insights = {}
        for source, data in sources.items():
            avg_score = data['total_score'] / data['count'] if data['count'] > 0 else 0
            high_score_percent = (data['high_score_leads'] / data['count'] * 100) if data['count'] > 0 else 0
            source_insights[source] = {
                'count': data['count'],
                'avg_score': round(avg_score, 1),
                'high_score_percent': round(high_score_percent, 1)
            }

        # Top source is the one with highest high_score_percent
        top_source = max(source_insights.items(), key=lambda x: x[1]['high_score_percent']) if source_insights else ('None', {'high_score_percent': 0})
        best_day_lead = max(leads, key=lambda x: x['leads_added']) if leads else {'date_added': 'No data', 'leads_added': 0, 'avg_score': 0}

        insights = {
            'top_source': f"{top_source[0]} ({top_source[1]['high_score_percent']}% high-score)",
            'best_day': f"{best_day_lead['date_added']} ({best_day_lead['leads_added']} leads, {best_day_lead['avg_score']} avg score)",
            'conversion_rate': round((analytics['conversions'] / analytics['total_leads']) * 100, 1) if analytics['total_leads'] > 0 else 0
        }

        # Add ML stats
        stats = {
            'total': analytics['total_leads'],
            'high_score': sum(1 for lead in leads if lead.get('avg_score', 0) > 75) if leads else 0
        }

        return render_template('analytics.html',
                            analytics=analytics,
                            leads=leads,
                            insights=insights,
                            source_insights=source_insights,
                            stats=stats)
    except Exception as e:
        logger.error(f"Error rendering analytics page: {str(e)}")
        flash(f"Error loading analytics. Please try again.")
        return redirect(url_for('dashboard'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        logger.info(f"Starting signup process for email: {email}")

        # Validate inputs
        if len(username) < 4 or len(username) > 20:
            flash('Username must be 4–20 characters.')
            return redirect(url_for('signup'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.')
            return redirect(url_for('signup'))
        if not '@' in email or not '.' in email:
            flash('Invalid email format.')
            return redirect(url_for('signup'))

        try:
            # Check username uniqueness
            try:
                existing_user = supabase.table('users').select('username').eq('username', username).execute()
                if existing_user.data:
                    flash('Username already taken.')
                    return redirect(url_for('signup'))
            except Exception as e:
                logger.error(f"Error checking username uniqueness in Supabase: {str(e)}")
                # Fallback to file-based check
                try:
                    with open('data/users.json', 'r') as f:
                        users = json.load(f)
                        if any(user.get('username') == username for user in users):
                            flash('Username already taken.')
                            return redirect(url_for('signup'))
                except Exception as file_e:
                    logger.error(f"Error checking file-based users: {str(file_e)}")
                    # If file doesn't exist, create it
                    if not os.path.exists('data'):
                        os.makedirs('data')
                    if not os.path.exists('data/users.json'):
                        with open('data/users.json', 'w') as f:
                            json.dump([], f)

            # Attempt Supabase Auth
            user_id = None
            try:
                auth_response = supabase.auth.sign_up({
                    'email': email,
                    'password': password
                })

                if hasattr(auth_response, 'user') and auth_response.user:
                    user_id = auth_response.user.id
                    logger.info(f"Supabase Auth signup successful for {email} with ID {user_id}")
                else:
                    logger.error(f"Supabase Auth signup failed - no user returned: {auth_response}")
                    # Fall back to file-based auth
                    user_id = f"local_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            except Exception as auth_e:
                logger.error(f"Supabase auth signup error: {str(auth_e)}")
                # Generate a unique ID for file-based users
                user_id = f"local_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Store user data with fallbacks
            db_success = False
            try:
                if user_id:
                    supabase.table('users').insert({
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'created_at': datetime.utcnow().isoformat()
                    }).execute()
                    db_success = True
                    logger.info(f"User data stored in Supabase for {email}")
            except Exception as db_e:
                logger.error(f"Error inserting user in Supabase: {str(db_e)}")

            # Fallback to file-based storage if Supabase failed
            if not db_success:
                try:
                    with open('data/users.json', 'r') as f:
                        users = json.load(f)

                    users.append({
                        'id': user_id,
                        'username': username,
                        'email': email,
                        'created_at': datetime.utcnow().isoformat(),
                        'password': password  # Store password for file-based auth
                    })

                    with open('data/users.json', 'w') as f:
                        json.dump(users, f, indent=2)

                    logger.info(f"User data stored in file for {email}")
                except Exception as file_e:
                    logger.error(f"Error storing user in file: {str(file_e)}")
                    flash('Error creating account. Please try again.')
                    return redirect(url_for('signup'))

            # Set session
            session['user_id'] = user_id
            session['username'] = username
            session.modified = True

            logger.info(f"Signup successful for {email}")
            flash('Signed up successfully! Welcome to Leadzap.')
            return redirect(url_for('dashboard'))

        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            flash('Signup failed. Please try again.')
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        logger.info(f"Login attempt for email: {email}")

        try:
            # First try with Supabase Auth
            supabase_login_success = False
            try:
                auth_response = supabase.auth.sign_in_with_password({
                    'email': email,
                    'password': password
                })

                if hasattr(auth_response, 'user') and auth_response.user:
                    # Fetch username from users table
                    try:
                        user_data = supabase.table('users').select('username').eq('id', auth_response.user.id).execute()
                        username = user_data.data[0]['username'] if user_data.data else "User"

                        session['user_id'] = auth_response.user.id
                        session['username'] = username
                        session.modified = True
                        flash('Successfully logged in!')
                        logger.info(f"Supabase login successful for {email}")
                        supabase_login_success = True
                        return redirect(url_for('dashboard'))
                    except Exception as fetch_e:
                        logger.error(f"Error fetching username after login: {str(fetch_e)}")
                        # If we can't get the username, but auth succeeded, still log them in
                        session['user_id'] = auth_response.user.id
                        session['username'] = email.split('@')[0]  # Use part of email as username
                        session.modified = True
                        flash('Successfully logged in!')
                        logger.info(f"Supabase login successful for {email}, using email-based username")
                        supabase_login_success = True
                        return redirect(url_for('dashboard'))
            except Exception as auth_e:
                logger.error(f"Supabase login error: {str(auth_e)}")

            # If Supabase login failed, try file-based login
            if not supabase_login_success:
                try:
                    with open('data/users.json', 'r') as f:
                        users = json.load(f)

                    user = next((u for u in users if u.get('email') == email and u.get('password') == password), None)
                    if user:
                        session['user_id'] = user.get('id', f"local_{datetime.now().strftime('%Y%m%d%H%M%S')}")
                        session['username'] = user.get('username', email.split('@')[0])
                        session.modified = True
                        flash('Successfully logged in!')
                        logger.info(f"File-based login successful for {email}")
                        return redirect(url_for('dashboard'))
                except Exception as file_e:
                    logger.error(f"File-based login error: {str(file_e)}")

            # If we reach here, both login methods failed
            flash('Invalid email or password.')
            logger.warning(f"Failed login attempt for {email}")
            return redirect(url_for('login'))

        except Exception as e:
            logger.error(f"Unexpected login error: {str(e)}")
            flash('An error occurred during login. Please try again.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")

    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access the dashboard.')
        return redirect(url_for('login'))

    try:
        user_id = session.get('user_id')
        username = session.get('username', 'Demo User')

        # Get filter type from request
        filter_type = request.args.get('filter', 'all')

        # Get user's leads from database or fallback to sample data
        real_leads = []
        try:
            # Try to fetch from Supabase
            leads_result = supabase.table('leads').select('*').eq('user_id', user_id).execute()
            if leads_result.data:
                real_leads = leads_result.data
                logger.info(f"Found {len(real_leads)} leads for user {user_id}")
        except Exception as e:
            logger.error(f"Error fetching leads from Supabase: {str(e)}")
            # Don't break the flow, continue with empty leads list

        # Fallback to sample data if no real leads
        if not real_leads:
            real_leads = [
                {
                    'name': "Test Lead 1",
                    'email': 'lead1@example.com',
                    'source': 'LinkedIn',
                    'score': 85,
                    'verified': True,
                    'status': 'New',
                    'date_added': datetime.now().isoformat()
                },
                {
                    'name': "Test Lead 2",
                    'email': 'lead2@example.com',
                    'source': 'Google Maps',
                    'score': 70,
                    'verified': True,
                    'status': 'New',
                    'date_added': datetime.now().isoformat()
                },
                {
                    'name': "Test Lead 3",
                    'email': 'lead3@example.com',
                    'source': 'Yellow Pages',
                    'score': 55,
                    'verified': False,
                    'status': 'New',
                    'date_added': datetime.now().isoformat()
                }
            ]

        # Apply filters - safely handle potential invalid data
        leads = []
        for lead in real_leads:
            try:
                # Convert date_added to datetime if it's a string
                if isinstance(lead.get('date_added'), str):
                    try:
                        lead_date = datetime.fromisoformat(lead['date_added'].replace('Z', '+00:00'))
                    except:
                        lead_date = datetime.now()
                else:
                    lead_date = datetime.now()

                # Apply the selected filter
                if filter_type == 'verified' and not lead.get('verified', False):
                    continue
                elif filter_type == 'unverified' and lead.get('verified', False):
                    continue
                elif filter_type == 'phone_verified' and not lead.get('phone_verified', False):
                    continue
                elif filter_type == 'linkedin_verified' and not lead.get('linkedin_verified', False):
                    continue
                elif filter_type == 'fully_verified' and not (lead.get('verified', False) and lead.get('phone_verified', False) and lead.get('linkedin_verified', False)):
                    continue
                elif filter_type == 'high_score' and lead.get('score', 0) <= 75:
                    continue
                elif filter_type == 'high_conversion' and lead.get('conversion_probability', 0) <= 50:
                    continue
                elif filter_type == 'last_week' and (datetime.now() - lead_date).days > 7:
                    continue
                # Source-based filters
                elif filter_type == 'linkedin' and lead.get('source', '').lower() != 'linkedin':
                    continue
                elif filter_type == 'google_maps' and lead.get('source', '').lower() != 'google maps':
                    continue
                elif filter_type == 'yellow_pages' and lead.get('source', '').lower() != 'yellow pages':
                    continue

                leads.append(lead)
            except Exception as lead_e:
                logger.error(f"Error processing lead: {str(lead_e)}")
                # Skip problematic leads but continue processing others
                continue

        # Get user's subscription data with safe fallbacks
        subscription = None
        try:
            # Try to fetch from Supabase
            package_result = supabase.table('user_packages').select('*').eq('user_id', user_id).eq('status', 'active').execute()
            if package_result.data:
                package_data = package_result.data[0]
                subscription = {
                    'package_name': package_data.get('package_name', 'Lead Engine'),
                    'status': 'active',
                    'lead_volume': package_data.get('lead_volume', 150)
                }
                logger.info(f"Found subscription for user {user_id}: {subscription}")
        except Exception as e:
            logger.error(f"Error fetching subscription from Supabase: {str(e)}")
            # Continue with file backup

        # Fallback to file for subscription
        if not subscription:
            try:
                with open('data/user_packages.json', 'r') as f:
                    packages = json.load(f)

                    if not packages:
                        logger.warning(f"Empty packages in user_packages.json")
                    elif isinstance(packages, list):
                        package_data = next((p for p in packages if p.get('user_id') == user_id and p.get('status') == 'active'), None)
                        if package_data:
                            subscription = {
                                'package_name': package_data.get('package_name', 'Lead Engine'),
                                'status': 'active',
                                'lead_volume': package_data.get('lead_volume', 150)
                            }
                            logger.info(f"Found subscription in file (list) for user {user_id}: {subscription}")
                    else:
                        # Handle dict format
                        matching_packages = [packages[pid] for pid in packages
                                           if packages[pid].get('user_id') == user_id
                                           and packages[pid].get('status') == 'active']
                        if matching_packages:
                            package_data = matching_packages[0]
                            subscription = {
                                'package_name': package_data.get('package_name', 'Lead Engine'),
                                'status': 'active',
                                'lead_volume': package_data.get('lead_volume', 150)
                            }
                            logger.info(f"Found subscription in file (dict) for user {user_id}: {subscription}")
            except Exception as file_e:
                logger.error(f"Error reading subscription data from file: {str(file_e)}")
                # Continue with default fallback

        # If we still don't have subscription data, use defaults
        if not subscription:
            subscription = {
                'package_name': 'No Active Plan',
                'status': 'inactive',
                'lead_volume': 0
            }

        # Simple analytics - safe calculations with fallbacks
        try:
            analytics = {
                'total_leads': len(leads),
                'high_quality_leads': sum(1 for lead in leads if lead.get('score', 0) > 75),
                'conversion_rate': '10%'  # Placeholder
            }
        except Exception as analytics_e:
            logger.error(f"Error calculating analytics: {str(analytics_e)}")
            analytics = {
                'total_leads': 0,
                'high_quality_leads': 0,
                'conversion_rate': '0%'
            }

        # Use a try/except for the template rendering as well
        try:
            return render_template('dashboard.html',
                               username=username,
                               leads=leads,
                               subscription=subscription,
                               analytics=analytics,
                               now=datetime.now())
        except Exception as render_e:
            logger.error(f"Template rendering error: {str(render_e)}")
            flash('Error displaying dashboard. Please contact support.')
            return redirect(url_for('home'))

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard. Please try again.')
        return redirect(url_for('home'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']

        # Get user preferences from Supabase
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        user_data = response.data[0] if response.data else {}

        # Get active package
        package_response = supabase.table('user_packages').select('*').eq('user_id', user_id).eq('status', 'active').execute()
        package = package_response.data[0] if package_response.data else {}

        # Generate a fake API key for now
        api_key = f"lz_{user_id}_{'x' * 30}"

        # Get CRM settings
        hubspot_api_key = user_data.get('hubspot_api_key', '')
        slack_webhook_url = user_data.get('slack_webhook_url', '')

        # Create user notifications dummy data for template
        user_notifications = {
            'new_leads': True,
            'weekly_summary': True,
            'support_updates': False
        }

        return render_template(
            'settings.html',
            username=session.get('username', 'User'),
            user_data=user_data,
            api_key=api_key,
            package=package,
            hubspot_api_key=hubspot_api_key,
            slack_webhook_url=slack_webhook_url,
            user={'notifications': user_notifications}
        )
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/update_crm_settings', methods=['POST'])
def update_crm_settings():
    if 'user_id' not in session:
        flash('You must be logged in to update settings', 'error')
        return redirect(url_for('login'))

    try:
        # Get form data
        hubspot_api_key = request.form.get('hubspot_api_key', '')
        slack_webhook_url = request.form.get('slack_webhook_url', '')

        # Update user settings in database
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if settings already exist for user
        cur.execute("SELECT id FROM user_settings WHERE user_id = %s", (session['user_id'],))
        settings_exist = cur.fetchone()

        if settings_exist:
            # Update existing settings
            cur.execute("""
                UPDATE user_settings
                SET hubspot_api_key = %s, slack_webhook_url = %s
                WHERE user_id = %s
            """, (hubspot_api_key, slack_webhook_url, session['user_id']))
        else:
            # Insert new settings
            cur.execute("""
                INSERT INTO user_settings (user_id, hubspot_api_key, slack_webhook_url)
                VALUES (%s, %s, %s)
            """, (session['user_id'], hubspot_api_key, slack_webhook_url))

        conn.commit()
        cur.close()
        conn.close()

        flash('CRM settings updated successfully', 'success')
        return redirect(url_for('settings'))
    except Exception as e:
        logger.error(f"Error updating CRM settings: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('settings'))
def update_crm_settings():
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_id = session['user_id']
        hubspot_api_key = request.form.get('hubspot_api_key', '')
        slack_webhook_url = request.form.get('slack_webhook_url', '')

        # Update user settings in Supabase
        try:
            supabase.table('users').update({
                'hubspot_api_key': hubspot_api_key,
                'slack_webhook_url': slack_webhook_url
            }).eq('id', user_id).execute()

            flash('CRM settings updated successfully!', 'success')
        except Exception as e:
            logger.error(f"Error updating CRM settings in database: {str(e)}")
            flash('Error saving settings. Please try again.', 'error')

        return redirect(url_for('settings'))
    except Exception as e:
        logger.error(f"Error in update_crm_settings: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/update_competitor_settings', methods=['POST'])
def update_competitor_settings():
    if 'user_id' not in session:
        flash('Please log in to update competitor settings.')
        return redirect(url_for('login'))

    try:
        user_id = session.get('user_id')
        competitor_urls = request.form.get('competitor_urls', '').splitlines()
        competitor_urls = [url.strip() for url in competitor_urls if url.strip()]

        # Update in Supabase
        try:
            supabase.table('users').update({
                'competitor_urls': competitor_urls
            }).eq('id', user_id).execute()

            logger.info(f"Updated competitor URLs for user {user_id}: {competitor_urls}")
        except Exception as e:
            logger.error(f"Error updating competitor URLs in Supabase: {str(e)}")
            # Fallback to file storage
            try:
                with open('data/users.json', 'r') as f:
                    users = json.load(f)

                for user in users:
                    if user.get('id') == user_id:
                        user['competitor_urls'] = competitor_urls
                        break

                with open('data/users.json', 'w') as f:
                    json.dump(users, f, indent=2)

                logger.info(f"Updated competitor URLs in file for user {user_id}")
            except Exception as file_e:
                logger.error(f"Error updating competitor URLs in file: {str(file_e)}")
                flash('Error updating competitor settings. Please try again.')
                return redirect(url_for('settings'))

        flash('Competitor settings updated successfully!')
        return redirect(url_for('settings'))

    except Exception as e:
        logger.error(f"Error in update_competitor_settings: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('settings'))

@app.route('/support', methods=['GET', 'POST'])
def support():
    try:
        if request.method == 'POST':
            subject = request.form['subject']
            message = request.form['message']

            # Store in session for now (will be replaced with Supabase later)
            flash('Message sent! We\'ll reply within 24 hours.')
            return redirect(url_for('support'))

        return render_template('support.html', username=session.get('username', "Developer"))

    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('support'))

@app.route('/generate-custom-leads', methods=['GET', 'POST'])
def generate_custom_leads():
    if 'user_id' not in session:
        flash('Please log in to generate leads.')
        return redirect(url_for('login'))

    try:
        user_id = session.get('user_id')

        # Get user's subscription to determine lead volume
        user_subscription = None
        try:
            package_result = supabase.table('user_packages').select('*').eq('user_id', user_id).eq('status', 'active').execute()
            if package_result.data:
                user_subscription = package_result.data[0]
        except Exception as e:
            logger.error(f"Error fetching subscription from Supabase: {str(e)}")

        # Fallback to file for subscription
        if not user_subscription:
            try:
                with open('data/user_packages.json', 'r') as f:
                    packages = json.load(f)
                    if isinstance(packages, list):
                        user_subscription = next((p for p in packages if p.get('user_id') == user_id and p.get('status') == 'active'), None)
            except Exception as file_e:
                logger.error(f"Error reading subscription data from file: {str(file_e)}")

        # Use default values if no subscription found
        package_name = user_subscription.get('package_name', 'Lead Launch') if user_subscription else 'Lead Launch'

        if request.method == 'POST':
            niche = request.form.get('niche')
            location = request.form.get('location')
            enable_outreach = request.form.get('enable_outreach') == 'on'

            if not niche or not location:
                flash('Please provide both niche and location.')
                return redirect(url_for('generate_custom_leads'))

            # Save user preferences
            try:
                supabase.table('users').update({
                    'niche': niche,
                    'location': location,
                    'enable_outreach': enable_outreach
                }).eq('id', user_id).execute()
            except Exception as update_e:
                logger.error(f"Error updating user preferences: {str(update_e)}")

            # Generate leads
            from scraper import LeadScraper
            scraper = LeadScraper()

            # Run in a background thread to not block the UI
            def generate_leads_task():
                scraper.generate_leads_for_package(user_id, package_name)

            threading.Thread(target=generate_leads_task).start()

            if enable_outreach:
                flash(f'Lead generation with automated outreach started for "{niche}" in "{location}". Check your dashboard in a few minutes.')
            else:
                flash(f'Lead generation started for "{niche}" in "{location}". Check your dashboard in a few minutes.')
            return redirect(url_for('dashboard'))

        return render_template('generate_leads.html', username=session.get('username', "Developer"))

    except Exception as e:
        logger.error(f"Error in generate_custom_leads: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/outreach-templates', methods=['GET'])
def outreach_templates():
    if 'user_id' not in session:
        flash('Please log in to view outreach templates.')
        return redirect(url_for('login'))

    try:
        user_id = session.get('user_id')
        username = session.get('username', 'Demo User')

        # Get user's subscription to determine template access
        user_subscription = None
        try:
            package_result = supabase.table('user_packages').select('*').eq('user_id', user_id).eq('status', 'active').execute()
            if package_result.data:
                user_subscription = package_result.data[0]
        except Exception as e:
            logger.error(f"Error fetching subscription from Supabase: {str(e)}")

        # Fallback to file for subscription
        if not user_subscription:
            try:
                with open('data/user_packages.json', 'r') as f:
                    packages = json.load(f)
                    if isinstance(packages, list):
                        user_subscription = next((p for p in packages if p.get('user_id') == user_id and p.get('status') == 'active'), None)
            except Exception as file_e:
                logger.error(f"Error reading subscription data from file: {str(file_e)}")

        # Use default values if no subscription found
        package_name = user_subscription.get('package_name', 'Lead Launch') if user_subscription else 'Lead Launch'

        # Get a sample lead for template preview
        sample_lead = {
            'name': 'Acme Company',
            'email': 'contact@acme.com',
            'source': 'LinkedIn',
            'score': 85,
            'verified': True
        }

        # Get templates based on package
        from scraper import LeadScraper
        scraper = LeadScraper()
        email_template = scraper.generate_email_template(sample_lead, package_name)
        linkedin_template = scraper.generate_linkedin_dm(sample_lead, package_name)

        # Determine how many templates are available based on package
        template_counts = {
            'launch': {'email': 1, 'linkedin': 0, 'sms': 0},
            'engine': {'email': 3, 'linkedin': 0, 'sms': 0},
            'accelerator': {'email': 5, 'linkedin': 1, 'sms': 0},
            'empire': {'email': 7, 'linkedin': 1, 'sms': 1}
        }

        template_access = template_counts.get(package_name.lower(), template_counts['launch'])

        return render_template('outreach_templates.html',
                            username=username,
                            email_template=email_template,
                            linkedin_template=linkedin_template,
                            package_name=package_name,
                            template_access=template_access)

    except Exception as e:
        logger.error(f"Error in outreach_templates: {str(e)}")
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

# Add the necessary route to trigger lead generation after payment
@app.route('/generate_leads/<user_id>/<package>')
def generate_leads(user_id, package):
    try:
        # Placeholder for LeadScraper class -  needs to be implemented separately.
        class LeadScraper:
            def generate_leads_for_package(self, user_id, package):
                # Replace with actual scraping logic
                # This is a placeholder,  replace with your scraper implementation.
                if package == "Lead Launch":
                    return 10  # Simulate 10 leads generated
                elif package == "Lead Engine":
                    return 150 #Simulate 150 leads generated
                else:
                    return 0

        scraper = LeadScraper()
        leads_generated = scraper.generate_leads_for_package(user_id, package)

        if leads_generated > 0:
            return jsonify({
                'status': 'success',
                'message': f'Generated {leads_generated} leads',
                'leads_count': leads_generated
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to generate leads'
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/checkout/<string:package>')
def checkout(package):
    try:
        # Check if package is valid
        prices = {
            'launch': 'price_1QwcjxGsSuGLiAUEuP63WhPh',  # Lead Launch
            'engine': 'price_1Qwcl0GsSuGLiAUEr9cJ8TtG',  # Lead Engine
            'accelerator': 'price_1QwclsGsSuGLiAUELcCnSDHQ', # Lead Accelerator
            'empire': 'price_1Qwcn5GsSuGLiAUE3qhtbxxy'  # Lead Empire
        }

        if package not in prices:
            flash('Invalid package selected.')
            return redirect(url_for('pricing'))

        # Store user's selected package
        session['selected_package'] = package

        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            line_items=[{
                'price': prices[package],
                'quantity': 1,
            }],
            mode='payment' if package == 'launch' else 'subscription',
            success_url=request.host_url.rstrip('/') + url_for('success') + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.host_url.rstrip('/') + url_for('pricing'),
            metadata={
                'package': package,
                'user_id': session.get('user_id', 'anonymous')  # Include user_id in metadata
            }
        )

        print(f"Createdcheckout session: {checkout_session.id}")  # Debug log
        return redirect(checkout_session.url)

    except Exception as e:
        print(f"Checkout error: {str(e)}")  # Debug log
        flash(f"Checkout failed: {str(e)}")
        return redirect(url_for('pricing'))

# Update the success route to include immediate lead delivery
@app.route('/success')
def success():
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Invalid session. Please try again.')
            return redirect(url_for('pricing'))

        # Retrieve the checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)

        # Get user and package from metadata
        user_id = checkout_session.metadata.get('user_id', session.get('user_id', 'anonymous'))
        package = checkout_session.metadata.get('package')

        if not package:
            logger.error(f"Missing package in session {session_id}")
            flash('Session data missing.')
            return redirect(url_for('dashboard'))

        # Calculate lead volume based on package
        lead_volumes = {
            'launch': 50,
            'engine': 150,
            'accelerator': 300,
            'empire': 600
        }
        lead_volume = lead_volumes.get(package, 50)

        # Get subscription ID if it exists
        subscription_id = checkout_session.subscription if hasattr(checkout_session, 'subscription') else None

        package_created = False

        # Try to use Supabase first
        try:
            # Generate a unique ID for the user_package
            package_id = f"pkg_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Insert or update user package with explicit ID
            supabase.table('user_packages').upsert({
                'id': package_id,
                'user_id': user_id,
                'package_name': package,
                'lead_volume': lead_volume,
                'stripe_subscription_id': subscription_id,
                'status': 'active',
                'next_delivery': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }).execute()

            logger.info(f"Updated subscription for user {user_id}: package={package}")
            package_created = True
        except Exception as db_e:
            logger.error(f"Database error in success route: {str(db_e)}")
            # Continue to file-based storage

        # Fallback to file-based storage if Supabase failed
        if not package_created:
            try:
                user_packages_file = 'data/user_packages.json'

                # Make sure the file exists
                if not os.path.exists('data'):
                    os.makedirs('data')
                if not os.path.exists(user_packages_file):
                    with open(user_packages_file, 'w') as f:
                        json.dump([], f)

                # Read existing packages
                with open(user_packages_file, 'r') as f:
                    try:
                        packages = json.load(f)
                    except json.JSONDecodeError:
                        packages = []

                # Ensure packages is a list
                if not isinstance(packages, list):
                    packages = []

                # Update or add package
                package_found = False
                for p in packages:
                    if p.get('user_id') == user_id:
                        p.update({
                            'package_name': package,
                            'lead_volume': lead_volume,
                            'stripe_subscription_id': subscription_id,
                            'status': 'active',
                            'next_delivery': datetime.now().isoformat(),
                            'updated_at': datetime.now().isoformat()
                        })
                        package_found = True
                        break

                if not package_found:
                    packages.append({
                        'user_id': user_id,
                        'package_name': package,
                        'lead_volume': lead_volume,
                        'stripe_subscription_id': subscription_id,
                        'status': 'active',
                        'next_delivery': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    })

                # Write updated packages back to file
                with open(user_packages_file, 'w') as f:
                    json.dump(packages, f, indent=2)

                logger.info(f"Updated subscription in file for user {user_id}: package={package}")
                package_created = True
            except Exception as file_e:
                logger.error(f"File-based storage error: {str(file_e)}")
                # Continue to flash message even if storage failed

        # Prepare appropriate flash message
        if package == 'launch':
            flash('Payment successful! Your leads will be generated and emailed shortly.')
        else:
            flash(f'Payment successful! Your {package} subscription is now active.')

        return redirect(url_for('dashboard'))

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        flash('Payment processing error. Please try again.')
        return redirect(url_for('pricing'))

    except Exception as e:
        logger.error(f"Error in success route: {str(e)}")
        flash('An unexpected error occurred. Please contact support.')
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Log debugging information
    logger.info(f"Webhook received")
    if sig_header:
        logger.info(f"Signature header present: {sig_header[:10]}...")
    logger.info(f"Webhook secret is set: {webhook_secret is not None}")

    # For development, we'll process the webhook even without verification
    # This allows testing while you're setting up the webhook secret
    if not webhook_secret:
        logger.warning("STRIPE_WEBHOOK_SECRET is not set - processing webhook without verification")
        try:
            event_data = json.loads(payload)
            event_type = event_data.get('type')
            logger.info(f"Processing unverified webhook event: {event_type}")

            if event_type == 'checkout.session.completed':
                session = event_data.get('data', {}).get('object', {})
                if session:
                    logger.info(f"Processing completed checkout session: {session.get('id')}")
                    handle_successful_payment(session)
            elif event_type == 'customer.subscription.updated':
                subscription = event_data.get('data', {}).get('object', {})
                if subscription:
                    logger.info(f"Processing subscription update: {subscription.get('id')}")
                    handle_subscription_update(subscription)

            return jsonify({"status": "processed_without_verification"}), 200
        except json.JSONDecodeError:
            logger.error("Invalid JSON payload received")
            return jsonify({"status": "error", "message": "Invalid payload"}), 400
        except Exception as e:
            logger.error(f"Error processing webhook without verification: {str(e)}")
            return jsonify({"status": "error", "message": str(e)}), 400

    # If we have a webhook secret, use it to verify the signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        logger.info(f"Received verified webhook event: {event.type}")

        if event.type == 'checkout.session.completed':
            session = event.data.object
            logger.info(f"Processing completed checkout session: {session.id}")
            handle_successful_payment(session)
        elif event.type == 'customer.subscription.updated':
            subscription = event.data.object
            logger.info(f"Processing subscription update: {subscription.id}")
            handle_subscription_update(subscription)

        return '', 200
    except ValueError as e:
        # Invalid payload
        logger.error(f"Webhook validation error (invalid payload): {str(e)}")
        return jsonify({"status": "error", "message": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Webhook signature verification error: {str(e)}")
        return jsonify({"status": "error", "message": "Invalid signature"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 400

def handle_successful_payment(session):
    try:
        user_id = session.metadata.get('user_id')
        package = session.metadata.get('package')

        if not user_id or not package:
            logger.error(f"Missing metadata in webhook session {session.id}")
            return

        lead_volumes = {
            'launch': 50,
            'engine': 150,
            'accelerator': 300,
            'empire': 600
        }
        lead_volume = lead_volumes.get(package, 50)

        try:
            # Try Supabase
            supabase.table('user_packages').upsert({
                'user_id': user_id,
                'package_name': package,
                'lead_volume': lead_volume,
                'status': 'active',
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }).execute()

            logger.info(f"Webhook: Updated subscription for user {user_id}: package={package}")

        except Exception as db_e:
            logger.error(f"Database error in webhook: {str(db_e)}")
            # Fallback to filebased storage
            user_packages_file = 'data/user_packages.json'

            with open(user_packages_file, 'r') as f:
                packages = json.load(f)

            # Update or add package
            package_found = False
            for p in packages:
                if p.get('user_id') == user_id:
                    p.update({
                        'package_name': package,
                        'lead_volume': lead_volume,
                        'status': 'active',
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    })
                    package_found = True
                    break

            if not package_found:
                packages.append({
                    'user_id': user_id,
                    'package_name': package,
                    'lead_volume': lead_volume,
                    'status': 'active',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                })

            with open(user_packages_file, 'w') as f:
                json.dump(packages, f, indent=2)

        # Start lead generation in background
        from scraper import LeadScraper
        scraper = LeadScraper()
        threading.Thread(
            target=scraper.generate_leads_for_package,
            args=(user_id, lead_volume)
        ).start()

    except Exception as e:
        logger.error(f"Error handling webhook payment: {str(e)}")

def handle_subscription_update(subscription):
    try:
        user_id = subscription.metadata.get('user_id')
        if not user_id:
            logger.error(f"No user_id in subscription {subscription.id}")
            return

        try:
            # Try Supabase
            supabase.table('user_packages').update({
                'stripe_subscription_id': subscription.id,
                'status': 'active' if subscription.status == 'active' else 'inactive',
                'updated_at': datetime.now().isoformat()
            }).eq('user_id', user_id).execute()

            logger.info(f"Updated subscription status for user {user_id}: subscription={subscription.id}")

        except Exception as db_e:
            logger.error(f"Database error in subscription update: {str(db_e)}")
            # Fallback to file-based storage
            user_packages_file = 'data/user_packages.json'

            with open(user_packages_file, 'r') as f:
                packages = json.load(f)

            # Update package status
            for p in packages:
                if p.get('user_id') == user_id:
                    p.update({
                        'stripe_subscription_id': subscription.id,
                        'status': 'active' if subscription.status == 'active' else 'inactive',
                        'next_delivery': datetime.now() + timedelta(days=7) # Example: Next delivery in 7 days
                    })
                    break

            with open(user_packages_file, 'w') as f:
                json.dump(packages, f, indent=2)

    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")

from flask import jsonify
import csv
from io import StringIO

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    try:
        logger.info(f"Checking for processes using port {port}")
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        logger.info(f"Found process {proc.pid} using port {port}")
                        proc.terminate()
                        proc.wait(timeout=5)
                        logger.info(f"Terminated process {proc.pid}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        logger.error(f"Error checking/terminating port {port}: {str(e)}")
    return False

# Configure data directories first
ensure_local_data_files()
ensure_tables_exist()

# Then add the scheduled job
scheduler = APScheduler()
scheduler.init_app(app)

@app.route('/hubspot/webhook', methods=['POST'])
def hubspot_webhook():
    """Handle webhook notifications from HubSpot"""
    try:
        # Verify the request is from HubSpot (replace with actual verification logic)
        hubspot_signature = request.headers.get('X-HubSpot-Signature')
        if not hubspot_signature:
            logger.warning("Received webhook request without HubSpot signature")
            return jsonify({'status': 'error', 'message': 'Invalid request'}), 401

        # Process the webhook payload
        webhook_data = request.json

        # Log the webhook event
        logger.info(f"Received HubSpot webhook: {webhook_data.get('eventType', 'unknown event')}")

        # Handle different types of notifications
        event_type = webhook_data.get('eventType')
        if event_type == 'contact.creation':
            # Handle new contact creation
            contact_data = webhook_data.get('data', {})
            logger.info(f"New contact created in HubSpot: {contact_data}")
            # Add logic to process the new contact data, such as adding it to your database
        elif event_type == 'contact.propertyChange':
            # Handle contact property changes
            contact_data = webhook_data.get('data', {})
            logger.info(f"Contact property changed in HubSpot: {contact_data}")
            # Add logic to process contact property changes
        # Add more event type handling as needed

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Error processing HubSpot webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    try:
        # First, terminate any existing process on port 5000
        logger.info("Checking for existing processes on port 5000")
        terminate_port_process(5000)

        # Initialize the scheduler
        logger.info("Initializing scheduler")
        scheduler = APScheduler()
        scheduler.init_app(app)

        # Initialize lead scheduler
        from lead_scheduler import LeadScheduler
        lead_scheduler = LeadScheduler()
        lead_scheduler.create_lead_pool_table()

        # Schedule lead delivery job
        scheduler.add_job(
            id='lead_delivery',
            func=lead_scheduler.process_lead_deliveries,
            trigger='interval',
            hours=6,  # Run every 6 hours to catch all delivery times
            next_run_time=datetime.now() + timedelta(minutes=1)
        )

        # Schedule weekly lead pool refresh
        scheduler.add_job(
            id='lead_pool_refresh',
            func=lead_scheduler.schedule_weekly_pool_refresh,
            trigger='interval',
            days=7,  # Run weekly
            next_run_time=datetime.now() + timedelta(minutes=5)  # Start after 5 minutes
        )
        
        # Schedule lead prediction updates
        scheduler.add_job(
            id='lead_prediction_update',
            func=lambda: lead_model.update_lead_predictions(psycopg2.connect(os.environ['DATABASE_URL'])),
            trigger='interval',
            hours=12,  # Run twice daily
            next_run_time=datetime.now() + timedelta(minutes=10)  # Start after 10 minutes
        )

        # Initial population of lead pool (in background thread to not block startup)
        threading.Thread(target=lead_scheduler.populate_initial_pool).start()

        # Start the scheduler
        logger.info("Starting scheduler")
        scheduler.start()

        # Start the Flask server
        logger.info("Starting Flask server on port 8080")
        app.run(host='0.0.0.0', port=8080, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)


@app.route('/train_ml_model', methods=['GET', 'POST'])
def train_ml_model():
    """Train the ML model with available lead data"""
    if 'user_id' not in session:
        flash('Please log in to access this feature.')
        return redirect(url_for('login'))
        
    try:
        from ml_engine import lead_model
        
        # Train the model with database connection
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        success = lead_model.train_from_database(conn)
        
        if success:
            # Update lead predictions with new model
            updated_count = lead_model.update_lead_predictions(conn)
            flash(f'Machine learning models trained successfully! Updated {updated_count} lead predictions.', 'success')
        else:
            flash('Not enough data to train the model yet. Keep adding leads with status updates.', 'warning')
            
        return redirect(url_for('analytics'))
        
    except Exception as e:
        logger.error(f"Error training ML model: {str(e)}")
        flash(f'Error training model: {str(e)}', 'error')
        return redirect(url_for('analytics'))

@app.route('/generate_message/<int:lead_id>', methods=['GET'])
def generate_message(lead_id):
    """Generate a personalized message for a specific lead"""
    if 'user_id' not in session:
        flash('Please log in to access this feature.')
        return redirect(url_for('login'))
    
    try:
        user_id = session.get('user_id')
        
        # Get lead data from database
        try:
            lead_data = supabase.table('leads').select('*').eq('id', lead_id).eq('user_id', user_id).execute()
            if not lead_data.data:
                flash('Lead not found or you do not have permission to access it.')
                return redirect(url_for('dashboard'))
            
            lead = lead_data.data[0]
        except Exception as db_e:
            logger.error(f"Database error in generate_message: {str(db_e)}")
            # Fallback to sample data for testing
            lead = {
                'id': lead_id,
                'name': 'Sample Lead',
                'email': 'sample@example.com',
                'source': 'LinkedIn',
                'niche': 'Plumbing',
                'city': 'Austin',
                'score': 85
            }
        
        # Generate personalized message
        from message_generator import MessageGenerator
        message_gen = MessageGenerator()
        message = message_gen.generate_message(lead)
        email_template = message_gen.generate_email_template(lead)
        
        return render_template('personalized_message.html', 
                             lead=lead, 
                             message=message,
                             email_template=email_template)
        
    except Exception as e:
        logger.error(f"Error generating personalized message: {str(e)}")
        flash(f'Error generating message: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/message_api/<int:lead_id>', methods=['GET'])
def message_api(lead_id):
    """API endpoint to get a personalized message for a lead"""
    if 'user_id' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        user_id = session.get('user_id')
        
        # Get lead data
        try:
            lead_data = supabase.table('leads').select('*').eq('id', lead_id).eq('user_id', user_id).execute()
            if not lead_data.data:
                return jsonify({'error': 'Lead not found'}), 404
            
            lead = lead_data.data[0]
        except Exception as db_e:
            logger.error(f"Database error in message_api: {str(db_e)}")
            return jsonify({'error': 'Database error'}), 500
        
        # Generate message
        from message_generator import MessageGenerator
        message_gen = MessageGenerator()
        message = message_gen.generate_message(lead)
        
        return jsonify({'message': message, 'lead': lead})
        
    except Exception as e:
        logger.error(f"API error: {str(e)}")
        return jsonify({'error': str(e)}), 500
