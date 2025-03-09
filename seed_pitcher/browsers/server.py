"""
Browser server for SeedPitcher.

This module provides a simple HTTP API for browser automation, allowing
other components like the Pin AI agent to control the browser without direct integration.
"""

import os
import sys
import time
import json
import logging
import threading
import queue
from flask import Flask, request, jsonify
from seed_pitcher.browsers.playwright import PlaywrightBrowser
from seed_pitcher import config

# Create a queue for browser commands
browser_command_queue = queue.Queue()
browser_result_queue = queue.Queue()
browser_thread = None
browser_thread_running = False

# Configure logging
logger = logging.getLogger("seed_pitcher.browsers.server")

# Create Flask app
app = Flask(__name__)

# Global browser instance
browser = None

def browser_thread_function():
    """Thread function that handles all browser operations.
    
    This function runs in its own thread and handles all browser operations,
    ensuring they run in a consistent thread context.
    """
    global browser, browser_thread_running
    
    logger.info("Browser thread started")
    print("Browser thread started")
    
    # Initialize the browser
    browser = PlaywrightBrowser()
    
    # Check if browser is properly initialized
    if (browser and 
        hasattr(browser, 'browser') and browser.browser and
        hasattr(browser, 'context') and browser.context and
        hasattr(browser, 'page') and browser.page):
        
        logger.info("Browser initialized successfully in dedicated thread")
        print("Browser initialized successfully in dedicated thread")
        browser_thread_running = True
    else:
        logger.warning("Browser initialization incomplete in thread")
        print("Browser initialization incomplete in thread")
        browser_thread_running = False
        return
    
    # Process commands until told to stop
    while browser_thread_running:
        try:
            # Get command with a timeout to allow checking if thread should stop
            try:
                command = browser_command_queue.get(timeout=1.0)
            except queue.Empty:
                continue
                
            action = command.get('action')
            params = command.get('params', {})
            command_id = command.get('id')
            
            result = {'id': command_id, 'success': False, 'error': None, 'data': None}
            
            try:
                if action == 'navigate':
                    url = params.get('url')
                    browser.navigate(url)
                    result['success'] = True
                    
                elif action == 'find_element':
                    selector = params.get('selector')
                    by = params.get('by', 'css')
                    element = browser.find_element(selector, by)
                    result['success'] = element is not None
                    result['data'] = {'found': element is not None}
                    
                elif action == 'get_text':
                    selector = params.get('selector')
                    by = params.get('by', 'css')
                    element = browser.find_element(selector, by)
                    if element:
                        # Get the text content of the element
                        try:
                            text = element.inner_text()
                            result['success'] = True
                            result['data'] = {'text': text}
                        except Exception as text_err:
                            result['error'] = f"Error getting text: {str(text_err)}"
                    else:
                        result['error'] = f"Element not found for text extraction: {selector}"
                    
                elif action == 'wait_for_selector':
                    selector = params.get('selector')
                    timeout = params.get('timeout', 30000)
                    try:
                        # Use Playwright's built-in wait_for_selector method
                        browser.page.wait_for_selector(selector, timeout=timeout)
                        result['success'] = True
                    except Exception as wait_err:
                        result['error'] = f"Error waiting for selector: {str(wait_err)}"
                    
                elif action == 'close':
                    try:
                        browser.close()
                        result['success'] = True
                    except Exception as close_err:
                        if "Event loop is closed" in str(close_err) or "Playwright already stopped" in str(close_err):
                            # Browser is already being closed or stopped, which is fine
                            logger.info("Browser was already closing or closed")
                            result['success'] = True
                            result['data'] = {'message': 'Browser was already closed'}
                        else:
                            logger.error(f"Error closing browser: {str(close_err)}")
                            result['error'] = f"Error closing browser: {str(close_err)}"
                    # We need to exit the thread regardless of success or failure
                    browser_thread_running = False
                    
                elif action == 'get_page_source':
                    try:
                        content = browser.page.content()
                        result['success'] = True
                        result['data'] = {'content': content}
                    except Exception as source_err:
                        result['error'] = f"Error getting page source: {str(source_err)}"
                
                elif action == 'get_attribute':
                    selector = params.get('selector')
                    by = params.get('by', 'css')
                    attribute = params.get('attribute')
                    
                    if not attribute:
                        result['error'] = "Attribute name is required"
                    else:
                        try:
                            element = browser.find_element(selector, by)
                            if element:
                                # Get the attribute value of the element
                                attribute_value = element.get_attribute(attribute)
                                result['success'] = True
                                result['data'] = {'attribute_value': attribute_value}
                            else:
                                result['error'] = f"Element not found for attribute extraction: {selector}"
                        except Exception as attr_err:
                            result['error'] = f"Error getting attribute {attribute}: {str(attr_err)}"
                
                elif action == 'find_elements':
                    selector = params.get('selector')
                    by = params.get('by', 'css')
                    
                    try:
                        # Find multiple elements matching the selector
                        elements = browser.page.query_selector_all(selector)
                        elements_info = []
                        
                        # Store elements data for reference
                        for i, element in enumerate(elements):
                            elements_info.append({
                                'index': i,
                                'found': True
                            })
                            
                        result['success'] = True
                        result['data'] = {
                            'found': len(elements_info) > 0,
                            'elements': elements_info,
                            'count': len(elements_info)
                        }
                    except Exception as find_err:
                        result['error'] = f"Error finding elements with selector {selector}: {str(find_err)}"
                
                elif action == 'get_element_text':
                    selector = params.get('selector')
                    by = params.get('by', 'css')
                    index = params.get('index', 0)  # Default to first element if index not provided
                    
                    try:
                        # Get all elements matching the selector
                        elements = browser.page.query_selector_all(selector)
                        if elements and len(elements) > index:
                            # Get the specific element by index
                            element = elements[index]
                            # Get text content
                            try:
                                text = element.inner_text()
                                result['success'] = True
                                result['data'] = {'text': text}
                            except Exception as text_err:
                                result['error'] = f"Error getting text from element at index {index}: {str(text_err)}"
                        else:
                            result['error'] = f"Element at index {index} not found for selector {selector}"
                    except Exception as element_err:
                        result['error'] = f"Error accessing element at index {index}: {str(element_err)}"
                        
                # Add more actions as needed
                
            except Exception as action_err:
                result['error'] = str(action_err)
                
            # Put the result in the result queue
            browser_result_queue.put(result)
            
        except Exception as e:
            logger.error(f"Error in browser thread: {str(e)}")
            print(f"Error in browser thread: {str(e)}")
    
    logger.info("Browser thread stopping")
    print("Browser thread stopping")
    
    # Clean up
    try:
        if browser:
            browser.close()
    except Exception as e:
        logger.error(f"Error closing browser in thread: {str(e)}")
        print(f"Error closing browser in thread: {str(e)}")

def initialize_browser():
    """Initialize the browser instance in a dedicated thread.
    
    This function starts a dedicated thread for browser operations to avoid
    conflicts with Flask's threading model.
    """
    global browser_thread, browser_thread_running
    
    # Check if thread is already running
    if browser_thread and browser_thread.is_alive():
        logger.info("Browser thread already running")
        return True
    
    # Clean up any existing thread
    if browser_thread:
        try:
            browser_thread_running = False
            browser_thread.join(timeout=5.0)
        except Exception as e:
            logger.warning(f"Error stopping browser thread: {str(e)}")
    
    # Start a new browser thread
    try:
        logger.info("Starting browser thread")
        print("Starting browser thread")
        
        # Clear queues
        while not browser_command_queue.empty():
            browser_command_queue.get()
        while not browser_result_queue.empty():
            browser_result_queue.get()
        
        # Create and start thread
        browser_thread = threading.Thread(target=browser_thread_function)
        browser_thread.daemon = True  # Thread will exit when main thread exits
        browser_thread.start()
        
        # Wait for thread to initialize browser (with timeout)
        timeout = 30.0  # 30 seconds timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if browser_thread_running:
                logger.info("Browser thread started successfully")
                print("Browser thread started successfully")
                return True
            time.sleep(0.1)
        
        logger.error("Browser thread failed to start in time")
        print("Browser thread failed to start in time")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error starting browser thread: {str(e)}")
        print(f"Unexpected error starting browser thread: {str(e)}")
        return False

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    global browser
    
    # Check if browser exists
    if browser is None:
        return jsonify({
            "status": "unhealthy",
            "browser": "not initialized",
            "detail": "Browser instance does not exist"
        })
    
    # Check if browser is fully initialized
    browser_status = {}
    try:
        # Check browser object
        browser_status["has_browser_object"] = hasattr(browser, 'browser') and browser.browser is not None
        
        # Check context
        browser_status["has_context"] = hasattr(browser, 'context') and browser.context is not None
        
        # Check page
        browser_status["has_page"] = hasattr(browser, 'page') and browser.page is not None
        
        # Check if browser is connected
        if browser_status["has_browser_object"] and hasattr(browser.browser, 'is_connected'):
            browser_status["is_connected"] = browser.browser.is_connected()
        else:
            browser_status["is_connected"] = False
        
        # Overall status
        is_healthy = all([
            browser_status["has_browser_object"],
            browser_status["has_context"],
            browser_status["has_page"]
        ])
        
        return jsonify({
            "status": "healthy" if is_healthy else "unhealthy",
            "browser": "fully initialized" if is_healthy else "partially initialized",
            "detail": browser_status
        })
    except Exception as e:
        # If we get an error checking browser status, it's unhealthy
        return jsonify({
            "status": "unhealthy",
            "browser": "error checking status",
            "detail": str(e)
        })

@app.route('/navigate', methods=['POST'])
def navigate():
    """Navigate to a URL."""
    global browser
    
    # Check if browser is initialized, if not try to initialize it
    browser_ready = False
    if not browser:
        logger.info("Browser not initialized, attempting initialization")
        if not initialize_browser():
            logger.error("Failed to initialize browser for navigation")
            return jsonify({"error": "Failed to initialize browser"}), 500
    
    # Double check browser is fully initialized
    if not (hasattr(browser, 'browser') and browser.browser and 
            hasattr(browser, 'page') and browser.page):
        logger.error("Browser not fully initialized for navigation")
        # Try to reinitialize
        if not initialize_browser():
            return jsonify({"error": "Browser not fully initialized"}), 500
    
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    try:
        logger.info(f"Navigating to {url}")
        
        # Try navigation with retries
        for attempt in range(3):
            try:
                if hasattr(browser, 'navigate'):
                    browser.navigate(url)
                    logger.info(f"Successfully navigated to {url}")
                    return jsonify({"status": "success", "url": url})
                elif hasattr(browser, 'page') and browser.page:
                    # Try direct page navigation as fallback
                    browser.page.goto(url, timeout=30000)
                    logger.info(f"Successfully navigated to {url} using direct page navigation")
                    return jsonify({"status": "success", "url": url})
                else:
                    logger.error("Browser has no navigate method or page object")
                    break
            except Exception as nav_e:
                logger.warning(f"Navigation attempt {attempt+1} failed: {str(nav_e)}")
                time.sleep(1)
                
                # On last attempt, try to recover the browser
                if attempt == 2:
                    logger.warning("Final navigation attempt failed, trying to reinitialize browser")
                    # Try to reinitialize the browser
                    try:
                        if browser:
                            browser.close()
                        initialize_browser()
                        
                        # One last try after reinitialization
                        if browser and hasattr(browser, 'navigate'):
                            browser.navigate(url)
                            logger.info(f"Successfully navigated to {url} after browser reinitialization")
                            return jsonify({"status": "success", "url": url})
                    except Exception as reinit_e:
                        logger.error(f"Browser reinitialization failed: {str(reinit_e)}")
        
        # If we got here, all navigation attempts failed
        logger.error(f"All navigation attempts to {url} failed")
        return jsonify({"error": "Failed to navigate after multiple attempts"}), 500
    except Exception as e:
        logger.error(f"Unexpected error navigating to {url}: {str(e)}")
        # Try to reinitialize the browser for future requests
        try:
            if browser:
                browser.close()
            initialize_browser()
        except Exception as cleanup_e:
            logger.error(f"Error during browser cleanup: {str(cleanup_e)}")
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500

@app.route('/page_source', methods=['GET'])
def page_source():
    """Get the current page source using thread-safe approach."""
    global browser, browser_command_queue, browser_result_queue
    if not browser_thread_running:
        return jsonify({"error": "Browser thread not running"}), 500
    
    try:
        logger.info("Getting page source via browser thread")
        
        # Generate a unique command ID
        command_id = f"page_source_{int(time.time()*1000)}"
        
        # Send command to browser thread
        browser_command_queue.put({
            'id': command_id,
            'action': 'get_page_source',
            'params': {}
        })
        
        # Wait for result with timeout
        result = None
        wait_start = time.time()
        while time.time() - wait_start < 10.0:  # 10 second timeout
            try:
                result = browser_result_queue.get(timeout=0.5)
                if result.get('id') == command_id:
                    break
                # Put back results that aren't ours
                browser_result_queue.put(result)
            except queue.Empty:
                continue
        
        if not result:
            return jsonify({"error": "Timeout waiting for page source"}), 500
            
        if not result.get('success'):
            return jsonify({"error": result.get('error', "Unknown error getting page source")}), 500
            
        return jsonify({"status": "success", "source": result.get('data', {}).get('content', '')})
    except Exception as e:
        logger.error(f"Error in page_source endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/find_element', methods=['POST'])
def find_element():
    """Find an element on the page and return its text using thread-safe approach."""
    global browser_command_queue, browser_result_queue
    if not browser_thread_running:
        return jsonify({"error": "Browser thread not running"}), 500
    
    data = request.json
    selector = data.get('selector')
    by = data.get('by', 'css')
    get_attribute = data.get('attribute')
    
    if not selector:
        return jsonify({"error": "Selector is required"}), 400
    
    try:
        logger.info(f"Finding element with selector {selector} by {by} via browser thread")
        
        # Generate a unique command ID
        command_id = f"find_element_{int(time.time()*1000)}"
        
        # Send find_element command to browser thread
        browser_command_queue.put({
            'id': command_id,
            'action': 'find_element',
            'params': {'selector': selector, 'by': by}
        })
        
        # Wait for result with timeout
        result = None
        wait_start = time.time()
        while time.time() - wait_start < 10.0:  # 10 second timeout
            try:
                result = browser_result_queue.get(timeout=0.5)
                if result.get('id') == command_id:
                    break
                # Put back results that aren't ours
                browser_result_queue.put(result)
            except queue.Empty:
                continue
        
        if not result:
            return jsonify({"error": "Timeout waiting for find_element operation"}), 500
            
        if not result.get('success'):
            error_message = result.get('error', "Unknown error finding element")
            return jsonify({"status": "not_found", "message": error_message}), 404
        
        api_result = {"status": "success", "found": result.get('data', {}).get('found', False)}
        
        # If element was found and we need an attribute or text
        if api_result["found"]:
            if get_attribute:
                # Send another command to get the attribute
                attr_command_id = f"{command_id}_attr_{get_attribute}"
                browser_command_queue.put({
                    'id': attr_command_id,
                    'action': 'get_attribute',
                    'params': {'selector': selector, 'by': by, 'attribute': get_attribute}
                })
                
                # Wait for attribute result
                attr_result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        attr_result = browser_result_queue.get(timeout=0.5)
                        if attr_result.get('id') == attr_command_id:
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(attr_result)
                    except queue.Empty:
                        continue
                
                if attr_result and attr_result.get('success'):
                    api_result["attribute_value"] = attr_result.get('data', {}).get('attribute_value', '')
            else:
                # Send another command to get the text
                text_command_id = f"{command_id}_text"
                browser_command_queue.put({
                    'id': text_command_id,
                    'action': 'get_text',
                    'params': {'selector': selector, 'by': by}
                })
                
                # Wait for text result
                text_result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        text_result = browser_result_queue.get(timeout=0.5)
                        if text_result.get('id') == text_command_id:
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(text_result)
                    except queue.Empty:
                        continue
                
                if text_result and text_result.get('success'):
                    api_result["text"] = text_result.get('data', {}).get('text', '')
        
        return jsonify(api_result)
    except Exception as e:
        logger.error(f"Error finding element {selector}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/find_elements', methods=['POST'])
def find_elements():
    """Find elements on the page and return their text."""
    global browser
    if not browser:
        return jsonify({"error": "Browser not initialized"}), 500
    
    data = request.json
    selector = data.get('selector')
    by = data.get('by', 'css')
    get_attribute = data.get('attribute')
    
    if not selector:
        return jsonify({"error": "Selector is required"}), 400
    
    try:
        logger.info(f"Finding elements with selector {selector} by {by}")
        elements = browser.find_elements(selector, by)
        
        if not elements:
            return jsonify({"status": "not_found", "message": f"No elements found with selector {selector}"}), 404
        
        results = []
        for element in elements:
            if get_attribute:
                value = browser.get_attribute(element, get_attribute)
                results.append({"attribute_value": value})
            else:
                text = browser.get_text(element)
                results.append({"text": text})
                
        return jsonify({"status": "success", "elements": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Error finding elements {selector}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/click', methods=['POST'])
def click_element():
    """Click on an element."""
    global browser
    if not browser:
        return jsonify({"error": "Browser not initialized"}), 500
    
    data = request.json
    selector = data.get('selector')
    by = data.get('by', 'css')
    
    if not selector:
        return jsonify({"error": "Selector is required"}), 400
    
    try:
        logger.info(f"Clicking element with selector {selector} by {by}")
        element = browser.find_element(selector, by)
        
        if not element:
            return jsonify({"status": "not_found", "message": f"Element not found with selector {selector}"}), 404
        
        browser.click(element)
        return jsonify({"status": "success", "message": f"Clicked element with selector {selector}"})
    except Exception as e:
        logger.error(f"Error clicking element {selector}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/type_text', methods=['POST'])
def type_text():
    """Type text into an element."""
    global browser
    if not browser:
        return jsonify({"error": "Browser not initialized"}), 500
    
    data = request.json
    selector = data.get('selector')
    by = data.get('by', 'css')
    text = data.get('text')
    
    if not selector:
        return jsonify({"error": "Selector is required"}), 400
    if text is None:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        logger.info(f"Typing text into element with selector {selector} by {by}")
        element = browser.find_element(selector, by)
        
        if not element:
            return jsonify({"status": "not_found", "message": f"Element not found with selector {selector}"}), 404
        
        browser.type_text(element, text)
        return jsonify({"status": "success", "message": f"Typed text into element with selector {selector}"})
    except Exception as e:
        logger.error(f"Error typing text into element {selector}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/scroll', methods=['POST'])
def scroll():
    """Scroll the page."""
    global browser
    if not browser:
        return jsonify({"error": "Browser not initialized"}), 500
    
    data = request.json
    amount = data.get('amount', 500)
    
    try:
        logger.info(f"Scrolling page by {amount}")
        browser.scroll(amount)
        return jsonify({"status": "success", "message": f"Scrolled page by {amount}"})
    except Exception as e:
        logger.error(f"Error scrolling page: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/wait_for_element', methods=['POST'])
def wait_for_element():
    """Wait for an element to appear."""
    global browser
    if not browser:
        return jsonify({"error": "Browser not initialized"}), 500
    
    data = request.json
    selector = data.get('selector')
    by = data.get('by', 'css')
    timeout = data.get('timeout', 10000)
    
    if not selector:
        return jsonify({"error": "Selector is required"}), 400
    
    try:
        logger.info(f"Waiting for element with selector {selector} by {by} with timeout {timeout}")
        element = browser.wait_for_element(selector, by, timeout)
        
        if not element:
            return jsonify({"status": "timeout", "message": f"Element with selector {selector} did not appear within timeout"})
        
        return jsonify({"status": "success", "message": f"Element with selector {selector} appeared"})
    except Exception as e:
        logger.error(f"Error waiting for element {selector}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/extract_linkedin_profile', methods=['GET', 'POST'])
@app.route('/linkedin_profile', methods=['GET', 'POST'])  # Add backwards compatibility with old endpoint
def extract_linkedin_profile():
    """Extract information from a LinkedIn profile."""
    global browser_thread_running
    
    # Make sure the browser thread is running
    if not initialize_browser():
        logger.error("Failed to initialize browser thread for LinkedIn profile extraction")
        return jsonify({"error": "Failed to initialize browser thread"}), 500
    
    # Get URL from either GET or POST request
    if request.method == 'GET':
        url = request.args.get('url')
    else:  # POST
        data = request.json or {}
        url = data.get('url')
    
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    try:
        logger.info(f"Extracting LinkedIn profile from {url}")
        print(f"Extracting LinkedIn profile from {url}")
        
        profile_info = {}
        
        # Create a unique command ID
        command_id = f"linkedin_{int(time.time())}"
        
        # Send navigate command to browser thread
        logger.info(f"Navigating to {url}")
        print(f"Navigating to {url}")
        
        # Try navigation with retries
        navigation_successful = False
        for attempt in range(3):
            try:
                # Queue the navigate command
                browser_command_queue.put({
                    'id': f"{command_id}_nav_{attempt}",
                    'action': 'navigate',
                    'params': {'url': url}
                })
                
                # Wait for result with timeout
                result = None
                wait_start = time.time()
                while time.time() - wait_start < 10.0:  # 10 second timeout
                    try:
                        result = browser_result_queue.get(timeout=0.5)
                        if result.get('id') == f"{command_id}_nav_{attempt}":
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(result)
                    except queue.Empty:
                        continue
                
                if not result or not result.get('success'):
                    error = result.get('error') if result else "Timeout waiting for navigation"
                    logger.warning(f"Navigation failed (attempt {attempt+1}): {error}")
                    time.sleep(2)  # Wait before retry
                    continue
                
                # Wait for page to load with increasing time based on retry count
                wait_time = 3 + (attempt * 2)
                logger.info(f"Waiting {wait_time}s for page to load (attempt {attempt+1})") 
                time.sleep(wait_time)
                
                navigation_successful = True
                break
            except Exception as nav_err:
                logger.error(f"Navigation failed (attempt {attempt+1}): {str(nav_err)}")
                time.sleep(1)
                
        if not navigation_successful:
            logger.error("Failed to navigate to LinkedIn profile after multiple attempts")
            return jsonify({
                "status": "error",
                "error": "Failed to navigate to LinkedIn profile after multiple attempts"
            }), 500
        
        # Extract basic profile information using thread-safe approach
        profile_info = {}
        
        # Get name
        try:
            # Primary selector for name
            name_selectors = ["h1.text-heading-xlarge", "h1.inline.t-24", "h1.top-card-layout__title", "h1.pv-top-card-section__name"]
            
            for selector in name_selectors:
                # Send find element command to browser thread
                browser_command_queue.put({
                    'id': f"{command_id}_name_{selector}",
                    'action': 'find_element',
                    'params': {'selector': selector, 'by': 'css'}
                })
                
                # Wait for result with timeout
                result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        result = browser_result_queue.get(timeout=0.5)
                        if result.get('id') == f"{command_id}_name_{selector}":
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(result)
                    except queue.Empty:
                        continue
                
                if result and result.get('success') and result.get('data', {}).get('found'):
                    # Found element, now get text
                    browser_command_queue.put({
                        'id': f"{command_id}_name_text_{selector}",
                        'action': 'get_text',
                        'params': {'selector': selector, 'by': 'css'}
                    })
                    
                    # Wait for text result
                    text_result = None
                    wait_start = time.time()
                    while time.time() - wait_start < 5.0:  # 5 second timeout
                        try:
                            text_result = browser_result_queue.get(timeout=0.5)
                            if text_result.get('id') == f"{command_id}_name_text_{selector}":
                                break
                            # Put back results that aren't ours
                            browser_result_queue.put(text_result)
                        except queue.Empty:
                            continue
                    
                    if text_result and text_result.get('success') and text_result.get('data', {}).get('text'):
                        profile_info["name"] = text_result['data']['text']
                        break
                    
        except Exception as e:
            logger.warning(f"Could not extract name: {str(e)}")
        
        # Get headline/title using thread-safe approach
        try:
            # Multiple possible selectors for headline
            title_selectors = [
                "div.text-body-medium", 
                "h2.top-card-layout__headline", 
                "div.pv-top-card-section__headline",
                "div.text-body-large"
            ]
            
            for selector in title_selectors:
                # Send find element command to browser thread
                browser_command_queue.put({
                    'id': f"{command_id}_title_{selector}",
                    'action': 'find_element',
                    'params': {'selector': selector, 'by': 'css'}
                })
                
                # Wait for result with timeout
                result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        result = browser_result_queue.get(timeout=0.5)
                        if result.get('id') == f"{command_id}_title_{selector}":
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(result)
                    except queue.Empty:
                        continue
                
                if result and result.get('success') and result.get('data', {}).get('found'):
                    # Found element, now get text
                    browser_command_queue.put({
                        'id': f"{command_id}_title_text_{selector}",
                        'action': 'get_text',
                        'params': {'selector': selector, 'by': 'css'}
                    })
                    
                    # Wait for text result
                    text_result = None
                    wait_start = time.time()
                    while time.time() - wait_start < 5.0:  # 5 second timeout
                        try:
                            text_result = browser_result_queue.get(timeout=0.5)
                            if text_result.get('id') == f"{command_id}_title_text_{selector}":
                                break
                            # Put back results that aren't ours
                            browser_result_queue.put(text_result)
                        except queue.Empty:
                            continue
                    
                    if text_result and text_result.get('success') and text_result.get('data', {}).get('text'):
                        profile_info["headline"] = text_result['data']['text']
                        break
        except Exception as e:
            logger.warning(f"Could not extract title: {str(e)}")
        
        # Get about section using thread-safe approach
        try:
            # Try multiple possible selectors for about section
            about_selectors = [
                "div.display-flex.ph5.pv3 > div.inline-show-more-text", 
                "div.pv-about__summary-text", 
                "section.summary div.pv-shared-text-with-see-more",
                "section.pv-about-section div.inline-show-more-text"
            ]
            
            for selector in about_selectors:
                # Send find element command to browser thread
                browser_command_queue.put({
                    'id': f"{command_id}_about_{selector}",
                    'action': 'find_element',
                    'params': {'selector': selector, 'by': 'css'}
                })
                
                # Wait for result with timeout
                result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        result = browser_result_queue.get(timeout=0.5)
                        if result.get('id') == f"{command_id}_about_{selector}":
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(result)
                    except queue.Empty:
                        continue
                
                if result and result.get('success') and result.get('data', {}).get('found'):
                    # Found element, now get text
                    browser_command_queue.put({
                        'id': f"{command_id}_about_text_{selector}",
                        'action': 'get_text',
                        'params': {'selector': selector, 'by': 'css'}
                    })
                    
                    # Wait for text result
                    text_result = None
                    wait_start = time.time()
                    while time.time() - wait_start < 5.0:  # 5 second timeout
                        try:
                            text_result = browser_result_queue.get(timeout=0.5)
                            if text_result.get('id') == f"{command_id}_about_text_{selector}":
                                break
                            # Put back results that aren't ours
                            browser_result_queue.put(text_result)
                        except queue.Empty:
                            continue
                    
                    if text_result and text_result.get('success') and text_result.get('data', {}).get('text'):
                        profile_info["about"] = text_result['data']['text']
                        break
        except Exception as e:
            logger.warning(f"Could not extract about: {str(e)}")
        
        # Get experience using thread-safe approach
        try:
            # Try multiple possible selectors for experience
            experience_selectors = [
                "section#experience-section li", 
                "section.experience-section li",
                "section.pv-profile-section.experience-section ul.pv-profile-section__section-info li", 
                "div#experience ul li.artdeco-list__item",
                "main section:nth-child(5) ul li"
            ]
            
            experience = []
            for selector in experience_selectors:
                # First check if the selector exists and has elements
                browser_command_queue.put({
                    'id': f"{command_id}_experience_find_{selector}",
                    'action': 'find_elements',
                    'params': {'selector': selector, 'by': 'css'}
                })
                
                # Wait for result with timeout
                find_result = None
                wait_start = time.time()
                while time.time() - wait_start < 5.0:  # 5 second timeout
                    try:
                        find_result = browser_result_queue.get(timeout=0.5)
                        if find_result.get('id') == f"{command_id}_experience_find_{selector}":
                            break
                        # Put back results that aren't ours
                        browser_result_queue.put(find_result)
                    except queue.Empty:
                        continue
                
                if find_result and find_result.get('success') and find_result.get('data', {}).get('elements', []):
                    elements_count = len(find_result['data']['elements'])
                    if elements_count > 0:
                        # Get text for each experience element (up to 5)
                        for i in range(min(5, elements_count)):
                            # Request text for this specific element
                            browser_command_queue.put({
                                'id': f"{command_id}_experience_text_{selector}_{i}",
                                'action': 'get_element_text',
                                'params': {'selector': selector, 'by': 'css', 'index': i}
                            })
                            
                            # Wait for text result
                            text_result = None
                            wait_start = time.time()
                            while time.time() - wait_start < 5.0:  # 5 second timeout
                                try:
                                    text_result = browser_result_queue.get(timeout=0.5)
                                    if text_result.get('id') == f"{command_id}_experience_text_{selector}_{i}":
                                        break
                                    # Put back results that aren't ours
                                    browser_result_queue.put(text_result)
                                except queue.Empty:
                                    continue
                            
                            if text_result and text_result.get('success'):
                                experience_text = text_result.get('data', {}).get('text', '')
                                if experience_text and len(experience_text) > 10:  # Ensure it's substantial content
                                    experience.append(experience_text)
                        
                        if experience:
                            break  # Stop trying selectors if we got some experience
            
            if experience:
                profile_info["experience"] = experience
        except Exception as e:
            logger.warning(f"Could not extract experience: {str(e)}")
        
        # Analyze if this looks like an investor
        is_investor = False
        investor_confidence = 0.0
        investment_roles = set()
        investor_keywords = ["investor", "venture capital", "vc ", "angel ", "investment", "investing", 
                            "fund", "capital", "partner at", "seed", "early stage", "managing director",
                            "general partner", "principal", "partner ", "portfolio"]
        
        # Strong investor role indicators (higher confidence)
        strong_indicators = ["venture capital", "vc ", "angel investor", "general partner", "seed investor"]
        
        logger.info(f"LinkedIn profile analysis for {url}")
        
        # Initialize confidence counters
        keyword_matches = 0
        strong_matches = 0
        sections_with_matches = 0

        # Check title/headline 
        if "headline" in profile_info:
            headline = profile_info["headline"].lower()
            headline_matches = [keyword for keyword in investor_keywords if keyword in headline]
            headline_strong_matches = [keyword for keyword in strong_indicators if keyword in headline]
            
            if headline_matches:
                logger.info(f"Found investor keywords in headline: {headline_matches}")
                keyword_matches += len(headline_matches)
                strong_matches += len(headline_strong_matches)
                sections_with_matches += 1
                is_investor = True
                
                # Extract investment roles
                for keyword in headline_matches:
                    investment_roles.add(keyword.strip())
        else:
            logger.info("No headline found in profile")

        # Check experience
        if "experience" in profile_info:
            logger.info(f"Analyzing {len(profile_info['experience'])} experience entries")
            experience_has_match = False
            
            for exp in profile_info["experience"]:
                exp_lower = exp.lower()
                exp_matches = [keyword for keyword in investor_keywords if keyword in exp_lower]
                exp_strong_matches = [keyword for keyword in strong_indicators if keyword in exp_lower]
                
                if exp_matches:
                    logger.info(f"Found investor keywords in experience: {exp_matches}")
                    keyword_matches += len(exp_matches)
                    strong_matches += len(exp_strong_matches)
                    experience_has_match = True
                    is_investor = True
                    
                    # Extract investment roles
                    for keyword in exp_matches:
                        investment_roles.add(keyword.strip())
            
            if experience_has_match:
                sections_with_matches += 1
        else:
            logger.info("No experience entries found in profile")
                    
        # Check about section
        if "about" in profile_info:
            about_lower = profile_info["about"].lower()
            about_matches = [keyword for keyword in investor_keywords if keyword in about_lower]
            about_strong_matches = [keyword for keyword in strong_indicators if keyword in about_lower]
            
            if about_matches:
                logger.info(f"Found investor keywords in about section: {about_matches}")
                keyword_matches += len(about_matches)
                strong_matches += len(about_strong_matches)
                sections_with_matches += 1
                is_investor = True
                
                # Extract investment roles
                for keyword in about_matches:
                    investment_roles.add(keyword.strip())
        else:
            logger.info("No about section found in profile")
            
        # Calculate confidence based on matches
        if is_investor:
            # Base confidence on number of matches and sections with matches
            base_confidence = min(0.7, (keyword_matches * 0.1) + (sections_with_matches * 0.2))
            # Bonus for strong indicators
            strong_bonus = min(0.3, strong_matches * 0.15)
            investor_confidence = min(0.95, base_confidence + strong_bonus)
            
            logger.info(f"Investor confidence calculation: {investor_confidence:.2f} (keyword matches: {keyword_matches}, "+
                      f"sections with matches: {sections_with_matches}, strong matches: {strong_matches})")
        else:
            investor_confidence = 0.0
            logger.info("No investor indicators found in profile")
                        
        # Add investment roles to profile info
        if investment_roles:
            profile_info["investment_roles"] = list(investment_roles)
        
        # Add to result
        profile_info["is_investor"] = is_investor
        profile_info["url"] = url
        
        # Use calculated confidence instead of hardcoded values
        return jsonify({
            "status": "success", 
            "profile": profile_info,
            "analysis": {
                "is_investor": is_investor,
                "confidence": investor_confidence,  # Use our calculated confidence value
                "url": url,
                "investor_keywords_found": list(investment_roles) if investment_roles else []
            }
        })
    except Exception as e:
        logger.error(f"Error extracting LinkedIn profile {url}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/close', methods=['POST'])
def close_browser():
    """Close the browser using thread-safe approach."""
    global browser_command_queue, browser_result_queue, browser_thread_running
    
    if not browser_thread_running:
        return jsonify({"status": "success", "message": "Browser already closed"})
    
    try:
        logger.info("Closing browser via browser thread")
        
        # Generate a unique command ID
        command_id = f"close_{int(time.time()*1000)}"
        
        # Send close command to browser thread
        browser_command_queue.put({
            'id': command_id,
            'action': 'close',
            'params': {}
        })
        
        # Wait for result with timeout
        result = None
        wait_start = time.time()
        while time.time() - wait_start < 10.0:  # 10 second timeout
            try:
                result = browser_result_queue.get(timeout=0.5)
                if result.get('id') == command_id:
                    break
                # Put back results that aren't ours
                browser_result_queue.put(result)
            except queue.Empty:
                # If browser thread has stopped running, break out of the loop
                if not browser_thread_running:
                    break
                continue
        
        return jsonify({"status": "success", "message": "Browser close command sent"})
    except Exception as e:
        logger.error(f"Error in close_browser endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

def start_server(host='localhost', port=5000):
    """Start the browser server."""
    global browser
    
    try:
        # Set Flask to production mode
        import os
        os.environ['FLASK_ENV'] = 'production'
        
        # Only initialize if browser is not already initialized
        if browser is None or not (hasattr(browser, 'browser') and browser.browser and 
                                  hasattr(browser, 'page') and browser.page):
            # Initialize browser at startup with retries
            success = False
            for attempt in range(3):
                print(f"Initializing browser attempt {attempt+1}/3...")
                if initialize_browser():
                    success = True
                    break
                time.sleep(2)
            
            if not success:
                logger.error("Failed to initialize browser after multiple attempts. Starting server anyway.")
                print("WARNING: Failed to initialize browser after multiple attempts. Starting server anyway.")
        else:
            logger.info("Browser already initialized, skipping initialization")
            print("Browser already initialized, skipping initialization")
            success = True
        
        # Configure Flask for better stability
        app.config['PROPAGATE_EXCEPTIONS'] = False
        
        # Register error handlers
        @app.errorhandler(Exception)
        def handle_exception(e):
            logger.error(f"Unhandled exception in Flask: {str(e)}")
            return jsonify({"error": str(e)}), 500
            
        # Start the server
        logger.info(f"Starting browser server on {host}:{port}")
        print(f"Starting browser server on {host}:{port}")
        app.run(host=host, port=port, debug=False, threaded=True)
    except Exception as e:
        logger.error(f"Error starting browser server: {str(e)}")
        print(f"Error starting browser server: {str(e)}")
        if browser:
            try:
                browser.close()
            except:
                pass

def start_server_thread(host='localhost', port=5000):
    """Start the browser server in a separate thread."""
    server_thread = threading.Thread(target=start_server, args=(host, port))
    server_thread.daemon = True
    server_thread.start()
    logger.info(f"Browser server thread started on {host}:{port}")
    return server_thread

def main(host='localhost', port=5000):
    """
    Main function to start the browser server when run as script.
    
    Args:
        host: Host address to bind to (default: localhost)
        port: Port to listen on (default: 5000)
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Print startup banner to make it clear in logs
    print("*" * 80)
    print("*" + " " * 78 + "*")
    print("*" + " SeedPitcher Browser Server Starting ".center(78) + "*")
    print("*" + " " * 78 + "*")
    print("*" * 80)
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Process ID: {os.getpid()}")
    print(f"Python executable: {sys.executable}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print("*" * 80)
    
    # Initialize the browser immediately to verify it works
    print("Initializing browser...")
    success = initialize_browser()
    if success:
        print("Browser initialized successfully!")
    else:
        print("ERROR: Failed to initialize browser!")
        return False
    
    # Start the server
    try:
        print(f"Starting browser server on {host}:{port}...")
        start_server(host=host, port=port)
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Error running server: {e}")
        return False
    finally:
        print("Browser server shutting down")
        # Clean up browser if it exists
        global browser
        if browser:
            try:
                browser.close()
                print("Browser closed successfully")
            except Exception as e:
                print(f"Error closing browser: {e}")
    
    return True

if __name__ == '__main__':
    import sys
    main()