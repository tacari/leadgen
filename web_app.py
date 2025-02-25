from flask import Flask
import os
import logging

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
    """Basic landing page"""
    return "Hello World! Flask is running."

if __name__ == '__main__':
    try:
        logger.info("Starting Flask application on port 5000...")
        # ALWAYS serve the app on port 5000
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")