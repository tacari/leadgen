from flask import Flask
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.debug = True  # Enable debug mode

@app.route('/')
def landing():
    """Landing page - temporary basic version"""
    return "Welcome to the Lead Generation Platform"

@app.route('/test')
def test():
    """Test endpoint to verify Flask is working"""
    return "Hello World! Flask is running."

if __name__ == '__main__':
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists('output'):
            os.makedirs('output')

        logger.info("Starting Flask application...")
        # Ensure the app is accessible externally
        app.run(host='0.0.0.0', port=3000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")