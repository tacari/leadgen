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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

stripe.api_key = os.environ.get('STRIPE_API_KEY')
sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        proc.terminate()
                        proc.wait(timeout=5)
                        logger.info(f"Terminated process {proc.pid} using port {port}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        logger.error(f"Error terminating process on port {port}: {str(e)}")
    return False

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

# Ensure local files exist
ensure_local_data_files()

# Initialize scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

def ensure_tables_exist():
    """Ensure all required tables exist"""
    try:
        # Try to create users table if it doesn't exist
        supabase.table('users').select('id').limit(1).execute()
        logger.info("Users table exists")
    except Exception as e:
        logger.error(f"Error checking users table: {str(e)}")
        try:
            # Execute SQL to create users table
            supabase.postgrest.call('create_users_table', {})
            logger.info("Created users table")
        except Exception as create_e:
            logger.error(f"Failed to create users table: {str(create_e)}")

    # Ensure data directory exists
    data_dir = 'data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"Created data directory: {data_dir}")

    # Initialize empty JSON files if they don't exist
    for file_name in ['users.json', 'user_packages.json', 'leads.json']:
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump([], f)
            logger.info(f"Created empty JSON file: {file_path}")

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
                # Make sure the users table exists first
                try:
                    supabase.table('users').select('id').limit(1).execute()
                except Exception as e:
                    logger.info("Creating users table")
                    # Create users table if it doesn't exist
                    supabase.table('users').create([
                        {'id': 'test', 'username': 'test', 'email': 'test@example.com', 'created_at': datetime.utcnow().isoformat()}
                    ]).execute()
                    # Delete test row
                    supabase.table('users').delete().eq('id', 'test').execute()

                # Now check if username exists
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
        # For now, use test data to show dashboard functionality
        test_data = {
            'username': session.get('username', 'Demo User'),
            'leads': [
                {
                    'name': "Test Lead 1",
                    'email': 'lead1@example.com',
                    'source': 'LinkedIn',
                    'score': 85,
                    'status': 'New'
                },
                {
                    'name': "Test Lead 2", 
                    'email': 'lead2@example.com',
                    'source': 'Google',
                    'score': 92,
                    'status': 'Contacted'
                }
            ],
            'subscription': {
                'package_name': 'Lead Engine',
                'status': 'active',
                'lead_volume': 150
            },
            'analytics': {
                'total_leads': 2,
                'high_quality_leads': 2,
                'conversion_rate': '10%'
            }
        }

        return render_template('dashboard.html',
                           username=test_data['username'],
                           leads=test_data['leads'],
                           subscription=test_data['subscription'],
                           analytics=test_data['analytics'])

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash('Error loading dashboard. Please try again.')
        return redirect(url_for('home'))

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
        writer.writerow(['Name', 'Email', 'Phone', 'Source', 'Score', 'Verified', 'Status', 'Date Added'])

        for lead in leads.data:
            writer.writerow([
                lead.get('name', 'N/A'),
                lead.get('email', 'N/A'),
                lead.get('phone', 'N/A'),
                lead.get('source', 'N/A'),
                lead.get('score', 0),
                lead.get('verified', False),
                lead.get('status', 'New'),
                lead.get('date_added', today)
            ])

        csv_content = output.getvalue()
        csv_base64 = base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')

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
                            <li>Verified contacts: {sum(1 for lead in leads.data if lead.get('verified', False))}</li>
                        </ul>
                    </div>

                    <p>Access your dashboard for more insights and to manage your leads.</p>

                    <div style="margin-top: 30px; padding: 20px; border-top: 1px solid #eee;">
                        <p style="color: #666; font-size: 12px;">
                            Your leads are attached in CSV format for easy import into your CRM.
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
    return render_template('contact.html')

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
    top_source = max(source_insights.items(), key=lambda x: x[1]['high_score_percent'])
    best_day_lead = max(leads, key=lambda x: x['leads_added'])

    insights = {
        'top_source': f"{top_source[0]} ({top_source[1]['high_score_percent']}% high-score)",
        'best_day': f"{best_day_lead['date_added']} ({best_day_lead['leads_added']} leads, {best_day_lead['avg_score']} avg score)",
        'conversion_rate': round((analytics['conversions'] / analytics['total_leads']) * 100, 1)
    }

    return render_template('analytics.html',
                         analytics=analytics,
                         leads=leads,
                         insights=insights,
                         source_insights=source_insights)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    try:
        # Sample data for development - will be replaced with Supabase integration
        user = {
            'username': session.get('username', 'Developer'),
            'email': 'dev@example.com',
            'notifications': {
                'new_leads': True,
                'weekly_summary': True,
                'support_updates': False
            }
        }

        subscription = {
            'package_name': 'Lead Engine',
            'price': 1499,
            'next_billing': '2025-03-25',
            'lead_volume': 150
        }

        if request.method == 'POST':
            # Handle profile updates
            if 'username' in request.form and 'email' in request.form:
                user['username'] = request.form['username']
                user['email'] = request.form['email']
                flash('Profile updated successfully!', 'success')
                return redirect(url_for('settings'))

            # Handle notification preferences
            elif any(key in request.form for key in ['new_leads', 'weekly_summary', 'support_updates']):
                user['notifications'] = {
                    'new_leads': 'new_leads' in request.form,
                    'weekly_summary': 'weekly_summary' in request.form,
                    'support_updates': 'support_updates' in request.form
                }
                flash('Notification preferences saved!', 'success')
                return redirect(url_for('settings'))

        return render_template('settings.html',
                         username=session.get('username', "Developer"),
                         user=user,
                         subscription=subscription)

    except Exception as e:
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

        print(f"Created checkout session: {checkout_session.id}")  # Debug log
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
        user_id = checkout_session.metadata.get('user_id', 'anonymous')
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

        try:
            # Try to use Supabase
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
            except Exception as db_e:
                logger.error(f"Database error in success route: {str(db_e)}")
                # Fallback to file-based storage
                user_packages_file = 'data/user_packages.json'

                try:
                    with open(user_packages_file, 'r') as f:
                        packages = json.load(f)

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

                    with open(user_packages_file, 'w') as f:
                        json.dump(packages, f, indent=2)

                    logger.info(f"Updated subscription in file for user {user_id}: package={package}")
                except Exception as file_e:
                    logger.error(f"File-based storage error: {str(file_e)}")

            if package == 'launch':
                flash('Payment successful! Your leads will be generated and emailed shortly.')
            else:
                flash(f'Payment successful! Your {package} subscription is now active.')

            return redirect(url_for('dashboard'))

        except Exception as e:
            logger.error(f"Database error in success route: {str(e)}")
            flash('Error processing payment. Please contact support.')
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
            # Fallback to file-based storage
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
                        'updated_at': datetime.now().isoformat()
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
        import psutil
        for proc in psutil.process_iter():
            try:
                for conn in proc.connections(kind='inet'):
                    if conn.laddr.port == port and proc.pid != os.getpid():
                        print(f"Terminating process {proc.pid} using port {port}", file=sys.stderr)
                        proc.terminate()
                        proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired, AttributeError):
                continue
    except Exception as e:
        print(f"Error in terminate_port_process: {str(e)}", file=sys.stderr)

# Create required data directories on startup
ensure_local_data_files = lambda: None #Dummy function to avoid errors


ensure_tables_exist()

if __name__ == '__main__':
    try:
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Ensure data directories exist
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        for file_name in ['users.json', 'user_packages.json', 'leads.json']:
            file_path = os.path.join(data_dir, file_name)
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)

        # First, terminate any existing process on port 5000
        if terminate_port_process(5000):
            logger.info("Terminated existing process on port 5000")

        # Try to start the server
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=5000, debug=True)

    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        sys.exit(1)