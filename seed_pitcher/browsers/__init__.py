"""
Browser management module for SeedPitcher.
"""

import logging
import threading
import os
from typing import Optional
from seed_pitcher.browsers.playwright import PlaywrightBrowser

# Set up logger
logger = logging.getLogger("seed_pitcher.browsers")

# Import HTTP client
try:
    from seed_pitcher.browsers.http_client import HTTPBrowserClient
except ImportError:
    # Handle the case where the HTTP client isn't available yet
    logger.warning("HTTP browser client not available, will use direct browser access")
    HTTPBrowserClient = None

# Global browser server thread
_server_thread = None
_server_port = 5050

def start_browser_server(port: int = 5050) -> bool:
    """Start the browser server on a specified port.
    
    Args:
        port: Port number to use for the browser server
        
    Returns:
        True if server started successfully, False otherwise
    """
    global _server_thread, _server_port
    
    # Check if auto-start is disabled by environment variable
    if os.environ.get("SEED_PITCHER_NO_AUTO_SERVER", "").lower() in ("1", "true", "yes"):
        logger.info("Browser server auto-start disabled by environment variable")
        return False
    
    if _server_thread is not None and _server_thread.is_alive():
        logger.info(f"Browser server already running on port {_server_port}")
        return True
    
    try:
        from seed_pitcher.browsers.server import start_server_thread
        logger.info(f"Starting browser server on port {port}")
        _server_thread = start_server_thread(host='localhost', port=port)
        _server_port = port
        
        # Small delay to allow server to start
        import time
        time.sleep(2)
        
        logger.info("Browser server started")
        return True
    except Exception as e:
        logger.error(f"Failed to start browser server: {e}")
        return False

def get_browser(use_http_client: bool = False, http_port: Optional[int] = None) -> object:
    """Get a browser instance.

    Args:
        use_http_client: If True, use the HTTP client to connect to a browser server.
                         This is ideal for environments with threading or asyncio conflicts.
        http_port: Port to use for HTTP browser server. If not provided, uses default port.

    Returns:
        A browser instance for web automation.
    """
    if use_http_client:
        # Use HTTP client to connect to browser server
        port = http_port or _server_port
        
        # Start server if needed
        if not (_server_thread and _server_thread.is_alive()):
            success = start_browser_server(port)
            if not success:
                logger.error("Could not start browser server, falling back to direct browser access")
                return PlaywrightBrowser()
        
        logger.info(f"Using HTTP browser client on port {port}")
        return HTTPBrowserClient(base_url=f"http://localhost:{port}")
    else:
        # Use direct browser access
        logger.info("Using direct browser access (PlaywrightBrowser)")
        return PlaywrightBrowser()
