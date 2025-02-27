import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from supabase import create_client, Client
import stripe
import psycopg2
import threading
from datetime import datetime, timedelta
import json
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key')  # Ensure this is set in Replit Secrets
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)
stripe.api_key = os.environ.get('STRIPE_API_KEY')

# Test Supabase connection
try:
    response = supabase.auth.get_session()
    print("Supabase connection successful!")
except Exception as e:
    print(f"Supabase connection error: {str(e)}")
    if "401" in str(e):
        print("Auth failed - check SUPABASE_KEY")
    elif "404" in str(e):
        print("API not found - check SUPABASE_URL")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Validate inputs
        if len(username) < 4 or len(username) > 20:
            flash('Username must be 4–20 characters.')
            return redirect(url_for('signup'))
        if len(password) < 8:
            flash('Password must be at least 8 characters.')
            return redirect(url_for('signup'))

        try:
            # Sign up with Supabase Auth
            auth_response = supabase.auth.sign_up({
                'email': email,
                'password': password,
                'options': {
                    'data': {
                        'username': username
                    }
                }
            })

            if auth_response.user:
                # Store additional user data
                supabase.table('users').insert({
                    'id': auth_response.user.id,
                    'username': username,
                    'email': email,
                    'created_at': datetime.utcnow().isoformat()
                }).execute()

                session['user_id'] = auth_response.user.id
                flash('Signup successful! Welcome to Leadzap.')
                return redirect(url_for('dashboard'))
            else:
                flash('Error creating account. Please try again.')
                return redirect(url_for('signup'))

        except Exception as e:
            print(f"Signup error: {str(e)}")
            flash('Error creating account. Please try again.')
            return redirect(url_for('signup'))

    return render_template('signup.html')

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
                flash('Successfully logged in!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.')
                return redirect(url_for('login'))

        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('Invalid email or password.')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Logout error: {str(e)}")

    session.pop('user_id', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = supabase.auth.get_user(session['user_id'])
    username = supabase.table('users').select('username').eq('id', user.user.id).execute().data[0]['username']
    leads = supabase.table('leads').select('*').eq('user_id', user.user.id).order('date_added', desc=True).limit(25).execute().data
    subscription = supabase.table('user_packages').select('*').eq('user_id', user.user.id).execute().data
    subscription = subscription[0] if subscription else None

    total_leads = len(leads)
    emailed = sum(1 for lead in leads if lead['status'] == 'Emailed')
    high_score = sum(1 for lead in leads if lead['score'] > 75)
    analytics = {'total': total_leads, 'emailed': emailed, 'high_score': high_score}

    if subscription:
        package = subscription['package_name']
        delivery_status = {
            'launch': "Your 50 leads arrived!",
            'engine': f"Next 37–38 leads: {(datetime.now() + timedelta(days=(7 - datetime.now().weekday()))).strftime('%Y-%m-%d')}",
            'accelerator': "Next 10–12 leads: Tomorrow",
            'empire': "Next 20–25 leads: Tomorrow"
        }.get(package, "Processing your leads...")
    else:
        delivery_status = "No leads scheduled—choose a plan!"

    return render_template('dashboard.html', 
                         username=username, 
                         leads=leads, 
                         subscription=subscription, 
                         analytics=analytics, 
                         delivery_status=delivery_status)

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

    output = StringIO()
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

@app.route('/success')
def success():
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            flash('Invalid session. Please try again.')
            return redirect(url_for('pricing'))

        print(f"Retrieved session ID: {session_id}")  # Debug log
        checkout_session = stripe.checkout.Session.retrieve(session_id)

        # Get package and user info
        package = checkout_session.metadata.get('package')
        user_id = checkout_session.metadata.get('user_id')

        print(f"Package: {package}, User ID: {user_id}")  # Debug log

        if not user_id or not package:
            flash('Session data missing.')
            return redirect(url_for('dashboard'))

        # Update subscription in database
        volumes = {'launch': 50, 'engine': 150, 'accelerator': 300, 'empire': 600}
        try:
            # Update user_packages table
            with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO user_packages 
                        (user_id, package_name, lead_volume, stripe_subscription_id, status, next_delivery)
                        VALUES (%s, %s, %s, %s, 'active', NOW())
                        ON CONFLICT (user_id) 
                        DO UPDATE SET 
                            package_name = EXCLUDED.package_name,
                            lead_volume = EXCLUDED.lead_volume,
                            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
                            status = EXCLUDED.status,
                            next_delivery = EXCLUDED.next_delivery,
                            updated_at = NOW()
                    """, (
                        user_id,
                        package,
                        volumes.get(package, 50),
                        checkout_session.subscription.id if hasattr(checkout_session, 'subscription') else None
                    ))
                conn.commit()
                print(f"Updated subscription in database for user {user_id}")  # Debug log
        except Exception as e:
            print(f"Database error: {str(e)}")
            flash('Warning: Your payment was successful but subscription update failed. Please contact support.')
            # Continue even if database update fails

        # Trigger scraper in background
        threading.Thread(target=generate_leads, args=(user_id, package)).start()

        flash('Payment successful! Your leads are being generated—check your dashboard soon.')
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Success handler error: {str(e)}")  # Debug log
        flash(f"Payment confirmation failed: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    event = None
    payload = request.get_json()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Event.construct_from(payload, stripe.api_key)
    except Exception as e:
        print(f"Webhook error: {e}")
        return '', 400

    # Handle successful one-time payment
    if event.type == 'charge.succeeded':
        session = event.data.object
        user_id = session.metadata.get('user_id')
        package = session.metadata.get('package')

        if user_id and package:
            try:
                with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
                    with conn.cursor() as cur:
                        # Update subscription status
                        cur.execute("""
                            INSERT INTO user_packages 
                            (user_id, package_name, lead_volume, status, created_at)
                            VALUES (%s, %s, %s, 'active', NOW())
                            ON CONFLICT (user_id) 
                            DO UPDATE SET 
                                package_name = EXCLUDED.package_name,
                                lead_volume = EXCLUDED.lead_volume,
                                status = EXCLUDED.status,
                                updated_at = NOW()
                        """, (
                            user_id,
                            package,
                            50 if package == 'launch' else (150 if package == 'engine' else (300 if package == 'accelerator' else 600))
                        ))
                        conn.commit()
                        print(f"Updated one-time payment subscription for user {user_id}")  # Debug log

                # Trigger lead generation
                threading.Thread(target=generate_leads, args=(user_id, package)).start()
            except Exception as e:
                print(f"Database error in webhook: {str(e)}")

    # Handle new subscription
    elif event.type == 'customer.subscription.created':
        subscription = event.data.object
        user_id = subscription.metadata.get('user_id')
        package = subscription.metadata.get('package')

        if user_id and package:
            try:
                with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE user_packages 
                            SET stripe_subscription_id = %s,
                                status = 'active',
                                next_delivery = NOW() + INTERVAL '1 day',
                                updated_at = NOW()
                            WHERE user_id = %s
                        """, (subscription.id, user_id))
                        conn.commit()
                        print(f"Updated subscription details for user {user_id}")  # Debug log

                # Start lead generation
                threading.Thread(target=generate_leads, args=(user_id, package)).start()
            except Exception as e:
                print(f"Subscription update error: {str(e)}")

    return '', 200

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
                print(f"Error creating file {file_path}: {str(e)}", file=sys.stderr)

        # First, terminate any existing process on port 5000
        terminate_port_process(5000)
        print("Starting Flask server...", file=sys.stderr)

        # ALWAYS serve the app on port 5000
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"Failed to start server: {str(e)}", file=sys.stderr)
        sys.exit(1)