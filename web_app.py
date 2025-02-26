from datetime import datetime, timedelta
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from fpdf import FPDF
from collections import defaultdict
import os
import sys
import json
import csv

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class for development
class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.name = "Developer"
        self.email = "dev@example.com"

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

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

@app.route('/login')
def login():
    # For development, auto-login a test user
    user = User("1")
    login_user(user)
    return redirect(url_for('dashboard'))

@app.route('/register')
def register():
    # For development, redirect to login which auto-logs in
    return redirect(url_for('login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Sample data for development
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
    now = datetime.now()

    return render_template(
        'dashboard.html',
        leads=leads,
        subscription=subscription,
        analytics=analytics,
        delivery_status="Next 37-38 leads: Weekly delivery",
        username=current_user.name,
        now=now
    )

@app.route('/lead-history')
@login_required
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
@login_required
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
@login_required
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
            'source': 'LinkedIn',
            'status': 'Emailed'
        },
        {
            'date_added': '2025-02-24',
            'leads_added': 15,
            'emailed': 12,
            'replies': 3,
            'conversions': 1,
            'avg_score': 78,
            'source': 'Google Ads',
            'status': 'Converted'
        }
    ]

    # Overview Stats
    total_leads = len(leads)
    emailed = sum(1 for lead in leads if lead['status'] == 'Emailed')
    replies = 0  # Placeholder—SendGrid later
    conversions = sum(1 for lead in leads if lead['status'] == 'Converted')
    analytics = {
        'total_leads': total_leads,
        'emailed': emailed,
        'replies': replies,
        'conversions': conversions,
        'charts': {
            'daily': [lead['leads_added'] for lead in leads],
            'dates': [lead['date_added'] for lead in leads],
            'status': {
                'labels': ['Pending', 'Emailed', 'Replied', 'Converted'],
                'data': [
                    total_leads - emailed - conversions,
                    emailed - conversions,
                    replies,
                    conversions
                ]
            }
        }
    }

    # Daily Breakdown (last 30 days for simplicity—expand with filters)
    daily_data = defaultdict(lambda: {'added': 0, 'emailed': 0, 'replies': 0, 'conversions': 0, 'scores': []})
    for lead in leads:
        date = lead['date_added'][:10]  # YYYY-MM-DD
        daily_data[date]['added'] += 1
        if lead['status'] == 'Emailed':
            daily_data[date]['emailed'] += 1
        if lead['status'] == 'Converted':
            daily_data[date]['conversions'] += 1
        daily_data[date]['scores'].append(lead['score'])

    table_data = [
        {
            'date': date,
            'added': data['added'],
            'emailed': data['emailed'],
            'replies': data['replies'],
            'conversions': data['conversions'],
            'avg_score': round(sum(data['scores']) / len(data['scores']), 1) if data['scores'] else 0
        }
        for date, data in daily_data.items()
    ]

    # Insights
    sources = defaultdict(lambda: {'count': 0, 'high_score': 0})
    for lead in leads:
        source = lead['source']
        sources[source]['count'] += 1
        if lead['score'] > 75:
            sources[source]['high_score'] += 1
    top_source = max(sources.items(), key=lambda x: x[1]['high_score'] / x[1]['count'] if x[1]['count'] > 0 else 0)
    top_day = max(daily_data.items(), key=lambda x: x[1]['added'])
    insights = {
        'top_source': f"{top_source[0]} ({round(top_source[1]['high_score'] / top_source[1]['count'] * 100, 1)}% high-score)",
        'best_day': f"{top_day[0]} ({top_day[1]['added']} leads, {round(sum(top_day[1]['scores']) / len(top_day[1]['scores']), 1) if top_day[1]['scores'] else 0} avg score)",
        'conversion_rate': round(conversions / total_leads * 100, 1) if total_leads > 0 else 0
    }

    return render_template('analytics.html',
                         analytics=analytics,
                         table_data=table_data,
                         insights=insights)

@app.route('/download_analytics_pdf')
@login_required
def download_analytics_pdf():
    # Sample data for PDF export
    leads = [
        {
            'date_added': '2025-02-25',
            'leads_added': 10,
            'emailed': 8,
            'replies': 2,
            'conversions': 1,
            'avg_score': 82
        }
    ]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 24)
    pdf.set_text_color(123, 0, 255)
    pdf.cell(0, 10, "Leadzap Analytics Report", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(161, 169, 184)
    pdf.cell(0, 10, f"Generated on {datetime.now().strftime('%Y-%m-%d')}", ln=True, align='C')
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 14)
    headers = ["Date", "Leads Added", "Emailed", "Replies", "Conversions", "Avg Score"]
    col_widths = [40, 30, 30, 30, 30, 30]
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 10, header, border=1, align='C')
    pdf.ln()
    pdf.set_font("Arial", size=12)
    for lead in leads:
        pdf.cell(40, 10, lead['date_added'], border=1)
        pdf.cell(30, 10, str(lead['leads_added']), border=1, align='C')
        pdf.cell(30, 10, str(lead['emailed']), border=1, align='C')
        pdf.cell(30, 10, str(lead['replies']), border=1, align='C')
        pdf.cell(30, 10, str(lead['conversions']), border=1, align='C')
        pdf.cell(30, 10, str(lead['avg_score']), border=1, align='C')
        pdf.ln()

    pdf.ln(10)
    pdf.cell(0, 10, "Powered by Leadzap AI", ln=True, align='C')

    pdf_output = pdf.output(dest='S').encode('latin-1')
    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=analytics_report_{datetime.now().strftime("%Y%m%d")}.pdf'
    return response


@app.route('/settings', methods=['GET', 'POST'])
@login_required
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

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    try:
        for proc in psutil.process_iter():
            try:
                proc_info = proc.as_dict(attrs=['pid', 'name', 'connections'])
                if proc_info['connections']:
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