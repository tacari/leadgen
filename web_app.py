import os
import sys
import psutil
from flask import Flask, render_template

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

@app.route('/')
def landing():
    return "Flask server is running!"


if __name__ == '__main__':
    try:
        print("Checking for processes using port 5000...", file=sys.stderr)
        terminate_port_process(5000)
        print("Starting Flask server...", file=sys.stderr)
        # Start with minimal configuration
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Failed to start server: {str(e)}", file=sys.stderr)
        sys.exit(1)