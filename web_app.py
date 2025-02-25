import os
import sys
import json
import csv
from datetime import datetime, timedelta
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

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
    return render_template('lead_history.html', leads=leads)

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
            'avg_score': 82
        },
        {
            'date_added': '2025-02-24',
            'leads_added': 15,
            'emailed': 12,
            'replies': 3,
            'conversions': 1,
            'avg_score': 78
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

    insights = {
        'top_source': 'LinkedIn',
        'high_score_percentage': 80
    }

    return render_template('analytics.html', 
                         analytics=analytics, 
                         leads=leads, 
                         insights=insights)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # Sample user data for development
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
        # Handle form submissions (just flash a message for now)
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('settings'))

    return render_template('settings.html', 
                         user=user, 
                         subscription=subscription)

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