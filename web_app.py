from flask import Flask, render_template
import os
import logging
import traceback
import socket
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with explicit template and static paths
template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')

logger.info(f"Template directory: {template_dir}")
logger.info(f"Static directory: {static_dir}")

if not os.path.exists(template_dir):
    os.makedirs(template_dir)
    logger.info(f"Created template directory: {template_dir}")

if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    logger.info(f"Created static directory: {static_dir}")

app = Flask(__name__,
           template_folder=template_dir,
           static_folder=static_dir)

@app.route('/')
def landing():
    """Landing page with pricing packages"""
    try:
        logger.info("Attempting to render landing page")
        return render_template('landing.html')
    except Exception as e:
        logger.error(f"Error rendering landing page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return f"Error loading landing page: {str(e)}", 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return "ok"

if __name__ == '__main__':
    try:
        # Try to release the port if it's in a TIME_WAIT state
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', 5000))
            sock.close()
        except socket.error as e:
            logger.error(f"Port 5000 is not available: {e}")
            # Wait briefly to allow port to be released
            time.sleep(1)

        logger.info("Starting Flask application on port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        exit(1)