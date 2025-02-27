import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from supabase import create_client, Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import stripe
import psycopg2
import threading
from datetime import datetime, timedelta
import json
import sys
import logging
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
            existing_user = supabase.table('users').select('username').eq('username', username).execute()
            if existing_user.data:
                flash('Username already taken.')
                return redirect(url_for('signup'))

            # Create user in Supabase Auth
            auth_response = supabase.auth.sign_up({
                'email': email,
                'password': password
            })

            if not auth_response.user:
                logger.error("Supabase auth signup failed - no user returned")
                flash('Signup failed. Please try again.')
                return redirect(url_for('signup'))

            # Store user data in users table
            supabase.table('users').insert({
                'id': auth_response.user.id,
                'username': username,
                'email': email,
                'created_at': datetime.utcnow().isoformat()
            }).execute()

            # Set session
            session['user_id'] = auth_response.user.id
            session.modified = True

            logger.info(f"Signup successful for {email}")
            flash('Signed up successfully! Welcome to Leadzap.')
            return redirect(url_for('dashboard'))

        except Exception as e:
            logger.error(f"Signup error: {str(e)}")
            flash('Signup failed. Please try again.')
            return redirect(url_for('signup'))

    return render_template('signup.html')

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
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)

        logger.info(f"Sent lead email to {email} with status code {response.status_code}")
        return response.status_code == 202

    except Exception as e:
        logger.error(f"Error sending lead email: {str(e)}")
        return False

def schedule_lead_delivery():
    """Schedule lead delivery based on package type"""
    try:
        users = supabase.table('user_packages').select('user_id, package_name').eq('status', 'active').execute().data

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

# Start scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.add_job(
    id='lead_delivery',
    func=schedule_lead_delivery,
    trigger='interval',
    hours=24,
    next_run_time=datetime.now() + timedelta(seconds=10)
)
scheduler.start()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            auth_response = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password
            })

            if auth_response.user:
                session['user_id'] = auth_response.user.id
                session.modified = True
                flash('Successfully logged in!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.')
                return redirect(url_for('login'))

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('Invalid email or password.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")

    session.pop('user_id', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    try:
        # Test user data for demonstration
        test_user = {
            'id': '12345',
            'username': 'test_user',
            'email': 'test@example.com'
        }

        # Get sample leads
        leads = [
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
                'source': 'Yellow Pages',
                'score': 92,
                'verified': True,
                'status': 'Contacted',
                'date_added': datetime.now().isoformat()
            }
        ]

        # Sample subscription data
        subscription = {
            'package_name': 'Lead Engine',
            'status': 'active',
            'lead_volume': 150,
            'next_delivery': (datetime.now() + timedelta(days=1)).isoformat()
        }

        return render_template('dashboard.html',
                            username=test_user['username'],
                            leads=leads,
                            subscription=subscription)

    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        flash('An error occurred while loading the dashboard.')
        return redirect(url_for('home'))

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
            'username': 'Developer',
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
                         username="Developer",  # For navbar
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

        return render_template('support.html', username="Developer")  # For navbar

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
            'accelerator': 'price_1QwclsGsSuGLiAUELcCnSDHQ',  # Lead Accelerator
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
        package = checkout_session.metadata.get('package')
        user_id = checkout_session.metadata.get('user_id')

        if not user_id or not package:
            logger.error("Missing user_id or package in session metadata")
            flash('Session data missing.')
            return redirect(url_for('dashboard'))

        # Connect to database
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()

        try:
            # Calculate lead volume based on package
            lead_volume = {
                'launch': 50,
                'engine': 150,
                'accelerator': 300,
                'empire': 600
            }.get(package, 50)

            # Get subscription ID if it exists
            subscription_id = None
            if hasattr(checkout_session, 'subscription'):
                subscription_id = checkout_session.subscription.id

            # Insert or update user package
            cur.execute("""
                INSERT INTO user_packages 
                (user_id, package_name, lead_volume, stripe_subscription_id, status, next_delivery, updated_at)
                VALUES (%s, %s, %s, %s, 'active', NOW(), NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    package_name = EXCLUDED.package_name,
                    lead_volume = EXCLUDED.lead_volume,
                    stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                    status = 'active',
                    next_delivery = NOW(),
                    updated_at = NOW()
            """, (user_id, package, lead_volume, subscription_id))

            conn.commit()
            logger.info(f"Successfully updated subscription for user {user_id} with package {package}")

            # For Lead Launch package, generate and send leads immediately
            if package == 'launch':
                from scraper import LeadScraper
                scraper = LeadScraper()
                leads_generated = scraper.generate_leads_for_package(user_id, lead_volume)
                if leads_generated:
                    send_lead_email(user_id, package)
                    flash('Payment successful! Your leads have been generated and emailed to you.')
                else:
                    flash('Payment successful! Your leads are being generated and will be emailed shortly.')
            else:
                flash(f'Payment successful! Your {package} subscription is active.')

            return redirect(url_for('dashboard'))

        except Exception as e:
            conn.rollback()
            logger.error(f"Database error in success route: {str(e)}")
            flash('Warning: Your payment was successful but subscription update failed. Please contact support.')
            return redirect(url_for('dashboard'))
        finally:
            cur.close()
            conn.close()

    except Exception as e:
        logger.error(f"Error in success route: {str(e)}")
        flash(f"An error occurred: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_json()
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET')
        )
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return '', 400

    # Handle successful payments
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_successful_payment(session)

    # Handle subscription updates
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        handle_subscription_update(subscription)

    return '', 200

def handle_successful_payment(session):
    try:
        user_id = session.metadata.get('user_id')
        package = session.metadata.get('package')

        if not user_id or not package:
            logger.error("Missing user_id or package in session metadata")
            return

        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()

        try:
            # Calculate lead volume
            lead_volume = {
                'launch': 50,
                'engine': 150,
                'accelerator': 300,
                'empire': 600
            }.get(package, 50)

            # Update subscription status
            cur.execute("""
                INSERT INTO user_packages 
                (user_id, package_name, lead_volume, status, created_at)
                VALUES (%s, %s, %s, 'active', NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    package_name = EXCLUDED.package_name,
                    lead_volume = EXCLUDED.lead_volume,
                    status = 'active',
                    updated_at = NOW()
            """, (user_id, package, lead_volume))
            conn.commit()

            # Start lead generation in background
            from scraper import LeadScraper
            scraper = LeadScraper()
            threading.Thread(
                target=scraper.generate_leads_for_package,
                args=(user_id, lead_volume)
            ).start()

        finally:
            cur.close()
            conn.close()

    except Exception as e:
        logger.error(f"Error handling successful payment: {str(e)}")

def handle_subscription_update(subscription):
    try:
        user_id = subscription.metadata.get('user_id')
        if not user_id:
            logger.error("No user_id in subscription metadata")
            return

        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE user_packages 
                SET stripe_subscription_id = %s,
                    status = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            """, (
                subscription.id,
                'active' if subscription.status == 'active' else 'inactive',
                user_id
            ))
            conn.commit()

        finally:
            cur.close()
            conn.close()

    except Exception as e:
        logger.error(f"Error handling subscription update: {str(e)}")

from flask import jsonify
import csv
from io import StringIO

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    try:
        for proc in psutil.process_iter():
            try:
                # Check each process
                proc_info = proc.as_dict(attrs=['pid', 'name', 'connections'])
                if proc_info['connections']:  # Check if process has connections
                    for conn in proc_info['connections']:
                        if conn.laddr.port == port and proc.pid != os.getpid():
                            print(f"Terminating process {proc.pid} using port {port}", file=sys.stderr)
                            proc.terminate()
                            proc.wait(timeout=3)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                continue
    except Exception as e:
        print(f"Error in terminate_port_process: {str(e)}", file=sys.stderr)

if __name__ == '__main__':
    import psutil
    try:
        # Create required JSON files if they don't exist
        for file_path in ['data/leads.json', 'data/user_packages.json']:
            try:
                if not os.path.exists(file_path):
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, 'w') as f:
                        json.dump({}, f)
                    print(f"Created {file_path}", file=sys.stderr)
            except Exception as e:
                print(f"Errorcreating file {file_path}: {str(e)}", file=sys.stderr)

        # First, terminate any existing process on port 5000
        terminate_port_process(5000)
        print("Starting Flask server...", file=sys.stderr)

        # ALWAYS serve the app on port 5000
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Failed to start server: {str(e)}", file=sys.stderr)
        sys.exit(1)