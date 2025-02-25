import os
import sys
import json
import csv
from datetime import datetime
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response, session
from supabase import create_client, Client
from models.lead import Lead
from models.user_package import UserPackage

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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            print(f"Attempting login with email: {email}", file=sys.stderr)
            user = supabase.auth.sign_in_with_password({
                'email': email,
                'password': password
            })
            print(f"Login successful for user: {email}", file=sys.stderr)
            session['user_id'] = user.user.id
            session['user_email'] = user.user.email
            flash('Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            print(f"Login failed: {str(e)}", file=sys.stderr)
            flash('Invalid email or password', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']

        try:
            print(f"Attempting to register user: {email}", file=sys.stderr)

            # First, check if email already exists in Supabase auth
            try:
                existing_user = supabase.auth.admin.list_users(
                    filters={'email': email}
                )
                if existing_user:
                    flash('Email already registered', 'error')
                    return render_template('register.html')
            except Exception as e:
                print(f"Error checking existing user: {str(e)}", file=sys.stderr)

            # Create new user in Supabase Auth
            user = supabase.auth.sign_up({
                'email': email,
                'password': password,
                'options': {
                    'data': {
                        'username': username
                    }
                }
            })

            if not user.user:
                flash('Registration failed. Please try again.', 'error')
                return render_template('register.html')

            print(f"Registration successful for user: {email}", file=sys.stderr)

            # Store additional user data in custom table
            try:
                supabase.table('profiles').insert({
                    'id': user.user.id,
                    'username': username,
                    'email': email,
                    'created_at': datetime.now().isoformat()
                }).execute()
            except Exception as e:
                print(f"Error creating profile: {str(e)}", file=sys.stderr)
                # Don't fail registration if profile creation fails
                pass

            # Set session data
            session['user_id'] = user.user.id
            session['user_email'] = user.user.email
            flash('Registration successful! Welcome to Leadzap.', 'success')
            return redirect(url_for('welcome'))

        except Exception as e:
            print(f"Registration failed: {str(e)}", file=sys.stderr)
            error_message = str(e)
            if 'already registered' in error_message.lower():
                flash('Email already registered', 'error')
            else:
                flash('Registration failed. Please try again.', 'error')
            return render_template('register.html')

    return render_template('register.html')

@app.route('/welcome')
def welcome():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user = supabase.auth.get_user(session['user_id'])
        user_data = supabase.table('users').select('username').eq('id', user.user.id).execute()
        username = user_data.data[0]['username'] if user_data.data else user.user.email.split('@')[0]
        return render_template('welcome.html', username=username)
    except Exception as e:
        print(f"Error getting user data: {str(e)}", file=sys.stderr)
        session.clear()
        return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user = supabase.auth.get_user(session['user_id'])
        user_data = supabase.table('users').select('*').eq('id', user.user.id).execute()
        username = user_data.data[0]['username'] if user_data.data else user.user.email.split('@')[0]
    except Exception as e:
        print(f"Error fetching user data: {str(e)}", file=sys.stderr)
        return redirect(url_for('logout'))

    # Get user's leads
    leads = Lead.get_by_user_id(session['user_id'])

    # Get user's subscription
    subscription = UserPackage.get_by_user_id(session['user_id'])

    # Calculate analytics
    total_leads = len(leads)
    emailed_leads = sum(1 for lead in leads if lead.status == 'Emailed')
    replies = sum(1 for lead in leads if lead.status == 'Replied')

    analytics = {
        'total': total_leads,
        'emailed': emailed_leads,
        'replies': replies,
        'conversions': 0  # Placeholder for now
    }

    # Set delivery status based on package
    if subscription:
        if subscription.package_name == 'Lead Launch':
            delivery_status = f"Your 50 leads arrive by {(datetime.now().date().strftime('%Y-%m-%d'))}"
        elif subscription.package_name == 'Lead Engine':
            delivery_status = "Next 37-38 leads: Weekly delivery"
        else:
            delivery_status = "Next 10-25 leads: Tomorrow"
    else:
        delivery_status = "No active subscription"

    return render_template(
        'dashboard.html',
        leads=leads,
        subscription=subscription,
        analytics=analytics,
        delivery_status=delivery_status,
        username=username
    )

@app.route('/download_leads')
def download_leads():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    leads = Lead.get_by_user_id(session['user_id'])

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Source', 'Score', 'Status', 'Date Added'])

    for lead in leads:
        writer.writerow([
            lead.name,
            lead.email,
            lead.source,
            lead.score,
            lead.status,
            lead.date_added.strftime('%Y-%m-%d')
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=leads.csv'
    response.headers['Content-type'] = 'text/csv'
    return response

@app.route('/logout')
def logout():
    try:
        supabase.auth.sign_out()
    except Exception as e:
        print(f"Error during logout: {str(e)}", file=sys.stderr)
    session.clear()
    return redirect(url_for('landing'))

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