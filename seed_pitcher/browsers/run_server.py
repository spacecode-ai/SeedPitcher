#!/usr/bin/env python
"""
Standalone HTTP browser server for SeedPitcher.

This script starts the browser server as a standalone process, which can be run
independently from the main application. This allows the server to run in its own
process space, avoiding any conflicts with the main application's threads or asyncio.

Usage:
  python -m seed_pitcher.browsers.run_server [--port PORT]
"""

import os
import sys
import time
import logging
import argparse
from seed_pitcher.browsers.server import initialize_browser, app, browser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.expanduser("~/.seed_pitcher/logs/browser_server.log"))
    ]
)

logger = logging.getLogger("seed_pitcher.browsers.run_server")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Start the SeedPitcher browser server")
    parser.add_argument("--port", type=int, default=5500, help="Port to listen on (default: 5500)")
    parser.add_argument("--host", type=str, default="localhost", help="Host to bind to (default: localhost)")
    return parser.parse_args()

def main():
    """Main function to start the server."""
    args = parse_args()
    host = args.host
    port = args.port
    
    # Print startup banner
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + " SeedPitcher Browser Server ".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Process ID: {os.getpid()}")
    print(f"Python executable: {sys.executable}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print("*" * 80)
    
    # Create log directory if it doesn't exist
    os.makedirs(os.path.expanduser("~/.seed_pitcher/logs"), exist_ok=True)
    
    # Initialize browser with retries
    success = False
    for attempt in range(3):
        print(f"Initializing browser attempt {attempt + 1}/3...")
        try:
            if initialize_browser():
                success = True
                break
            else:
                print(f"Browser initialization failed on attempt {attempt + 1}")
                time.sleep(2)
        except Exception as e:
            print(f"Error initializing browser on attempt {attempt + 1}: {e}")
            time.sleep(2)
    
    if not success:
        print("Failed to initialize browser after multiple attempts.")
        print("The server will still start, but browser functionality may be limited.")
    
    # Start the server
    try:
        # Configure Flask for better stability
        app.config['PROPAGATE_EXCEPTIONS'] = False
        
        # Register error handlers
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception in Flask: {str(e)}")
            return {"error": str(e)}, 500
        
        # Start the server
        print(f"Starting browser server on {host}:{port}")
        logger.info(f"Starting browser server on {host}:{port}")
        app.run(host=host, port=port, debug=False, threaded=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        logger.error(f"Error starting server: {e}")
        try:
            if browser:
                browser.close()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()