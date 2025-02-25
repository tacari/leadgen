import os
import logging
import traceback
from flask import Flask, render_template

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with explicit template and static paths
template_dir = os.path.abspath('templates')
static_dir = os.path.abspath('static')

app = Flask(__name__,
           template_folder=template_dir,
           static_folder=static_dir)

# Configure Flask app
app.config['SECRET_KEY'] = os.urandom(24)

@app.route('/')
def landing():
    """Landing page"""
    try:
        logger.debug("Rendering landing page")
        return render_template('landing.html')
    except Exception as e:
        logger.error(f"Error rendering landing page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

@app.route('/services')
def services():
    """Services page route"""
    try:
        logger.debug("Rendering services page")
        return render_template('services.html')
    except Exception as e:
        logger.error(f"Error rendering services page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

@app.route('/pricing')
def pricing():
    """Pricing page route"""
    try:
        logger.debug("Rendering pricing page")
        return render_template('pricing.html')
    except Exception as e:
        logger.error(f"Error rendering pricing page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

@app.route('/about')
def about():
    """About page route"""
    try:
        logger.debug("Rendering about page")
        return render_template('about.html')
    except Exception as e:
        logger.error(f"Error rendering about page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

@app.route('/contact')
def contact():
    """Contact page route"""
    try:
        logger.debug("Rendering contact page")
        return render_template('contact.html')
    except Exception as e:
        logger.error(f"Error rendering contact page: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500


if __name__ == '__main__':
    try:
        logger.info("Starting Flask application...")
        logger.debug("Current directory structure:")
        logger.debug(f"Template dir ({template_dir}): {os.listdir(template_dir) if os.path.exists(template_dir) else 'not found'}")
        logger.debug(f"Static dir ({static_dir}): {os.listdir(static_dir) if os.path.exists(static_dir) else 'not found'}")

        try:
            # ALWAYS serve the app on port 5000
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
        except Exception as run_error:
            logger.error(f"Error starting the Flask server: {str(run_error)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")
            raise
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        exit(1)