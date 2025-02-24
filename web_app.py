from flask import Flask, render_template, request, redirect, url_for, jsonify
from lead_manager import LeadManager
import os
from datetime import datetime

app = Flask(__name__)
lead_manager = LeadManager()

@app.route('/')
def landing():
    """Landing page"""
    return render_template('landing.html')

@app.route('/signup', methods=['POST'])
def signup():
    """Handle signup form submission"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        niche = request.form.get('niche')

        # For now, just redirect back to landing page
        # TODO: Implement proper signup handling
        return redirect(url_for('landing'))

@app.route('/leads/<lead_type>')
def view_leads(lead_type):
    """View leads of specific type"""
    if lead_type not in ['dentist', 'saas']:
        return 'Invalid lead type', 400

    leads = lead_manager.get_leads(lead_type)
    return render_template('leads.html', leads=leads, lead_type=lead_type)

@app.route('/download/<lead_type>')
def download_leads(lead_type):
    """Download leads as CSV"""
    if lead_type not in ['dentist', 'saas']:
        return 'Invalid lead type', 400

    filename = 'dentist_leads.csv' if lead_type == 'dentist' else 'saas_leads.csv'
    filepath = os.path.join('output', filename)

    if not os.path.exists(filepath):
        return 'No leads available', 404

    return send_file(filepath, as_attachment=True)

@app.route('/dashboard') #Added this to maintain the original dashboard functionality
def dashboard():
    """Main dashboard showing lead statistics"""
    dentist_leads = lead_manager.get_leads('dentist')
    saas_leads = lead_manager.get_leads('saas')

    stats = {
        'dentist_count': len(dentist_leads),
        'saas_count': len(saas_leads),
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    return render_template('dashboard.html', stats=stats)


if __name__ == '__main__':
    # Always serve the app on port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)