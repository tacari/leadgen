import os
import sys
import json
import csv
from datetime import datetime, timedelta
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session, jsonify
import stripe

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
stripe.api_key = os.environ.get('STRIPE_API_KEY')

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

@app.route('/')
def landing():
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

@app.route('/dashboard')
def dashboard():
    # Sample data for development
    now = datetime.now()
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
    subscription = {
        'package_name': 'Lead Engine',
        'lead_volume': 150,
    }
    analytics = {
        'total': 2,
        'emailed': 1,
        'replies': 0,
        'conversions': 0
    }

    return render_template(
        'dashboard.html',
        leads=leads,
        subscription=subscription,
        analytics=analytics,
        delivery_status="Next 37-38 leads: Weekly delivery",
        username="Developer",  # Hardcoded for development
        now=now  # Pass current time for delivery calculations
    )

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
    if 'user_id' not in session:
        flash('Please log in to purchase a plan.')
        return redirect(url_for('login'))

    prices = {
        'launch': 'price_1QwcjxGsSuGLiAUEuP63WhPh',  # Lead Launch
        'engine': 'price_1Qwcl0GsSuGLiAUEr9cJ8TtG',  # Lead Engine
        'accelerator': 'price_1QwclsGsSuGLiAUELcCnSDHQ',  # Lead Accelerator
        'empire': 'price_1Qwcn5GsSuGLiAUE3qhtbxxy'  # Lead Empire
    }

    if package not in prices:
        flash('Invalid package selected.')
        return redirect(url_for('pricing'))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': prices[package],
                'quantity': 1,
            }],
            mode='payment' if package == 'launch' else 'subscription',
            success_url=url_for('success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('pricing', _external=True),
            metadata={
                'user_id': session['user_id'],
                'package': package
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        flash(f"Checkout failed: {str(e)}")
        return redirect(url_for('pricing'))

@app.route('/success')
def success():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    session_id = request.args.get('session_id')
    if not session_id:
        flash('Invalid session. Please try again.')
        return redirect(url_for('pricing'))

    try:
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        package = stripe_session.metadata.get('package')
        user_id = stripe_session.metadata.get('user_id')

        if not user_id or not package:
            flash('Payment metadata missing.')
            return redirect(url_for('dashboard'))

        # Trigger scraper in background
        generate_leads(user_id, package)

        # Update subscription
        volumes = {'launch': 50, 'engine': 150, 'accelerator': 300, 'empire': 600}
        subscription = {
            'user_id': user_id,
            'package_name': package,
            'lead_volume': volumes.get(package, 0),
            'stripe_subscription_id': stripe_session.subscription if package != 'launch' else None
        }

        # Update subscription in database (replace with your database logic)
        flash('Payment successful! Leads are being scraped—check your dashboard soon.')
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"Payment confirmation failed: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    event = None
    try:
        event = stripe.Event.construct_from(request.get_json(), stripe.api_key)
    except Exception as e:
        print(f"Webhook error: {e}")
        return '', 400

    if event.type in ['charge.succeeded', 'customer.subscription.created']:
        user_id = event.data.object.metadata.get('user_id')
        package = event.data.object.metadata.get('package')
        if user_id and package:
            generate_leads(user_id, package)

    return '', 200

if __name__ == '__main__':
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