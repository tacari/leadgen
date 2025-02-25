from flask import Flask, request, redirect, url_for
import os
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create and configure the Flask app
app = Flask(__name__)
app.debug = True

@app.route('/')
def landing():
    """Basic landing page test"""
    try:
        # First return a simple string to verify server is working
        return "Basic Flask server is working!"
    except Exception as e:
        logger.error(f"Error in landing page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"Error: {str(e)}", 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return "ok"

if __name__ == '__main__':
    try:
        logger.info("Starting Flask application on port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")