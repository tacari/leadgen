import os
from flask import Flask, render_template

# Create Flask app with explicit template and static paths
template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')

app = Flask(__name__,
           template_folder=template_dir,
           static_folder=static_dir)

app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    # ALWAYS serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)