import os
import sys
import json
import csv
from datetime import datetime
from io import StringIO
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request, make_response
from flask_login import LoginManager, current_user, login_user, logout_user, login_required, UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from models.user import db

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

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the Flask app
db.init_app(app)
migrate = Migrate(app, db)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

class UpdateEmailForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Update Email')

@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    print(f"Loading user with ID: {user_id}", file=sys.stderr)
    user = User.get(user_id)
    print(f"User loaded: {user is not None}", file=sys.stderr)
    return user

@app.route('/')
def landing():
    return render_template('landing.html', current_user=current_user)

@app.route('/services')
def services():
    return render_template('services.html', current_user=current_user)

@app.route('/about')
def about():
    return render_template('about.html', current_user=current_user)

@app.route('/contact')
def contact():
    return render_template('contact.html', current_user=current_user)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    print(f"Login form submitted: {form.is_submitted()}", file=sys.stderr)
    print(f"Login form validated: {form.validate()}", file=sys.stderr)
    if form.validate_on_submit():
        print(f"Attempting login with email: {form.email.data}", file=sys.stderr)
        from models.user import User
        user = User.get_by_email(form.email.data)
        print(f"User found: {user is not None}", file=sys.stderr)
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next', url_for('dashboard'))
            flash('Welcome back!', 'success')
            return redirect(next_page)
        flash('Invalid email or password', 'error')
        print("Login failed: Invalid credentials", file=sys.stderr)
    return render_template('login.html', form=form, current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    from forms import RegisterForm
    form = RegisterForm()

    print(f"Register form submitted: {form.is_submitted()}", file=sys.stderr)
    print(f"Register form validated: {form.validate()}", file=sys.stderr)
    if form.errors:
        print(f"Form validation errors: {form.errors}", file=sys.stderr)

    if form.validate_on_submit():
        print(f"Attempting to create user with email: {form.email.data}", file=sys.stderr)
        try:
            from models.user import User
            user = User.create(
                email=form.email.data,
                password=form.password.data,
                name=form.username.data
            )
            print(f"User creation result: {user is not None}", file=sys.stderr)
            if user:
                login_user(user)
                flash('Registration successful! Welcome to Leadzap.', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Registration failed. Email may already be registered.', 'error')
                print("Registration failed: Email exists", file=sys.stderr)
        except Exception as e:
            flash('Registration failed. Please try again.', 'error')
            print(f"Registration error: {str(e)}", file=sys.stderr)

    return render_template('register.html', form=form, current_user=current_user)

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    from models.lead import Lead
    from models.user_package import UserPackage

    form = UpdateEmailForm(email=current_user.email)
    if form.validate_on_submit():
        current_user.email = form.email.data
        # Save email update
        try:
            with open('data/users.json', 'r') as f:
                users = json.load(f)
                users[str(current_user.id)]['email'] = form.email.data
            with open('data/users.json', 'w') as f:
                json.dump(users, f, indent=4)
            flash('Email updated successfully')
        except Exception as e:
            flash('Failed to update email')
            print(f"Error updating email: {str(e)}", file=sys.stderr)


    # Get user's leads
    leads = Lead.get_by_user_id(current_user.id)

    # Get user's subscription
    subscription = UserPackage.get_by_user_id(current_user.id)

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
        form=form,
        current_user=current_user
    )

@app.route('/download_leads')
@login_required
def download_leads():
    from models.lead import Lead
    leads = Lead.get_by_user_id(current_user.id)

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
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    try:
        # Create required JSON files if they don't exist
        for file_path in ['data/users.json', 'data/leads.json', 'data/user_packages.json']:
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