import os
import sys
import json
import csv
from datetime import datetime
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session

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
    # For development, using sample data
    leads = []  # Empty for now
    subscription = None  # No subscription data for now
    analytics = {
        'total': 0,
        'emailed': 0,
        'replies': 0,
        'conversions': 0
    }
    delivery_status = "Development Mode"

    return render_template(
        'dashboard.html',
        leads=leads,
        subscription=subscription,
        analytics=analytics,
        delivery_status=delivery_status,
        username="Developer"  # Hardcoded for development
    )

@app.route('/download_leads')
def download_leads():
    # For development, return empty CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Source', 'Score', 'Status', 'Date Added'])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=leads.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

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