import os
import sys
import psutil
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, current_user, login_user, logout_user, login_required

def terminate_port_process(port):
    """Terminate any process using the specified port"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Check if this is a Python process
            if 'python' in proc.info['name'].lower():
                # Get all connections for this process
                for conn in proc.connections():
                    if conn.laddr.port == port:
                        # Don't kill our own process
                        if proc.pid != os.getpid():
                            proc.terminate()
                            proc.wait()  # Wait for the process to terminate
                            print(f"Terminated process {proc.pid} using port {port}", file=sys.stderr)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    return User.get(user_id)

# Routes
@app.route('/')
def landing():
    return render_template('landing.html', current_user=current_user)

@app.route('/services')
def services():
    return render_template('services.html', current_user=current_user)

@app.route('/pricing', methods=['GET'])
def pricing():
    return render_template('pricing.html', current_user=current_user)

@app.route('/about')
def about():
    return render_template('about.html', current_user=current_user)

@app.route('/contact')
def contact():
    return render_template('contact.html', current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html', current_user=current_user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    from forms import RegisterForm
    form = RegisterForm()

    if form.validate_on_submit():
        from models.user import User
        user = User.create(
            email=form.email.data,
            password=form.password.data,
            name=form.username.data
        )
        if user:
            login_user(user)
            flash('Registration successful! Welcome to Leadzap.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Registration failed. Please try again.', 'error')

    return render_template('register.html', form=form, current_user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', current_user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing'))

if __name__ == '__main__':
    try:
        print("Checking for processes using port 5000...", file=sys.stderr)
        terminate_port_process(5000)
        print("Starting Flask server...", file=sys.stderr)
        # ALWAYS serve the app on port 5000
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Failed to start server: {str(e)}", file=sys.stderr)
        sys.exit(1)