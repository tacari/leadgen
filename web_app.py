import os
import logging
import traceback
import json
import psutil
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from forms import LoginForm, RegisterForm
from models.user import User

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with explicit template and static paths
template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')
data_dir = os.path.abspath('data')

# Ensure all required directories exist
for directory in [template_dir, static_dir, data_dir]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

app = Flask(__name__,
           template_folder=template_dir,
           static_folder=static_dir)

# Configure Flask app
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', os.urandom(24)),
    SESSION_COOKIE_SECURE=False,  # Set to True in production
    SESSION_COOKIE_HTTPONLY=True,
    PERMANENT_SESSION_LIFETIME=3600,
    WTF_CSRF_ENABLED=True
)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        logger.debug(f"Loading user with ID: {user_id}")
        user = User.get(user_id)
        if user:
            logger.debug(f"User {user_id} loaded successfully")
        else:
            logger.warning(f"No user found with ID: {user_id}")
        return user
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

@app.route('/')
def landing():
    """Landing page with pricing packages"""
    try:
        logger.debug("Rendering landing page")
        return render_template('landing.html')
    except Exception as e:
        logger.error(f"Error rendering landing page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        logger.debug("Processing login request")
        if current_user.is_authenticated:
            logger.debug("User already authenticated, redirecting to dashboard")
            return redirect(url_for('dashboard'))

        form = LoginForm()
        if form.validate_on_submit():
            logger.debug(f"Login form submitted for email: {form.email.data}")
            user = User.get_by_email(form.email.data)
            if user and user.check_password(form.password.data):
                login_user(user)
                logger.info(f"User {user.id} logged in successfully")
                next_page = request.args.get('next')
                return redirect(next_page or url_for('dashboard'))
            logger.warning(f"Invalid login attempt for email: {form.email.data}")
            flash('Invalid email or password')
        elif request.method == 'POST':
            logger.warning("Login form validation failed")
            logger.debug(f"Form errors: {form.errors}")
        return render_template('login.html', form=form)
    except Exception as e:
        logger.error(f"Error in login route: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred during login')
        return redirect(url_for('landing'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        logger.debug("Processing registration request")
        if current_user.is_authenticated:
            logger.debug("User already authenticated, redirecting to dashboard")
            return redirect(url_for('dashboard'))

        form = RegisterForm()
        if form.validate_on_submit():
            logger.debug(f"Registration form submitted for email: {form.email.data}")
            user = User.create(
                email=form.email.data,
                password=form.password.data,
                name=form.name.data
            )
            if user:
                login_user(user)
                logger.info(f"User {user.id} registered and logged in successfully")
                return redirect(url_for('dashboard'))
            logger.warning(f"Registration failed - email already exists: {form.email.data}")
            flash('Email already registered')
        elif request.method == 'POST':
            logger.warning("Registration form validation failed")
            logger.debug(f"Form errors: {form.errors}")
        return render_template('register.html', form=form)
    except Exception as e:
        logger.error(f"Error in register route: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred during registration')
        return redirect(url_for('landing'))

@app.route('/logout')
@login_required
def logout():
    try:
        logger.debug("Processing logout request")
        logout_user()
        logger.info("User logged out successfully")
        return redirect(url_for('landing'))
    except Exception as e:
        logger.error(f"Error in logout route: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred during logout')
        return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    try:
        logger.debug("Loading dashboard for user")
        stats = {
            'dentist_count': 0,
            'saas_count': 0,
            'last_update': 'Never'
        }
        return render_template('dashboard.html', stats=stats)
    except Exception as e:
        logger.error(f"Error loading dashboard: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        flash('Error loading dashboard')
        return redirect(url_for('landing'))

@app.route('/health')
def health():
    """Health check endpoint"""
    return "ok"

@app.route('/test')
def test():
    """Test route to verify server is running"""
    return "Flask server is running!"

def kill_process_on_port(port):
    """Kill any process that is listening on the specified port"""
    try:
        logger.info(f"Checking for processes on port {port}")
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                # Skip processes that don't have network connections
                if not proc.info.get('connections'):
                    continue

                # Check each connection
                for conn in proc.info['connections']:
                    if hasattr(conn, 'laddr') and conn.laddr.port == port and conn.status == 'LISTEN':
                        logger.warning(f"Found process using port {port}: PID={proc.info['pid']}, Name={proc.info['name']}")
                        proc.kill()
                        logger.info(f"Killed process {proc.info['pid']}")
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        logger.info(f"No process found using port {port}")
        return False
    except Exception as e:
        logger.error(f"Error while checking/killing process on port {port}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

# Ensure data directory exists and is properly initialized before running the app
try:
    if not os.path.exists('data'):
        os.makedirs('data')
        logger.info("Created data directory")

    if not os.path.exists('data/users.json'):
        with open('data/users.json', 'w') as f:
            json.dump({}, f)
        logger.info("Initialized empty users.json file")
except Exception as e:
    logger.error(f"Error initializing data directory: {str(e)}")
    logger.error(f"Traceback: {traceback.format_exc()}")
    raise

if __name__ == '__main__':
    try:
        logger.info("Starting Flask application...")
        logger.debug("Current directory structure:")
        logger.debug(f"Template dir ({template_dir}): {os.listdir(template_dir) if os.path.exists(template_dir) else 'not found'}")
        logger.debug(f"Static dir ({static_dir}): {os.listdir(static_dir) if os.path.exists(static_dir) else 'not found'}")
        logger.debug(f"Data dir ({data_dir}): {os.listdir(data_dir) if os.path.exists(data_dir) else 'not found'}")

        # Kill any existing process on port 5000
        kill_process_on_port(5000)

        # ALWAYS serve the app on port 5000
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        exit(1)