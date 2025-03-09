"""Integration with Playwright for browser automation."""

import time
from typing import List, Dict, Any, Optional
import seed_pitcher.config as config


class PlaywrightBrowser:
    """Wrapper for Playwright browser."""

    def __init__(self):
        """Initialize the Playwright browser connection."""
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        try:
            # First check if playwright is installed
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                print(
                    "The playwright package is not installed. Please install it with: pip install playwright"
                )
                return

            # Start playwright and attempt to connect
            self.playwright = sync_playwright().start()

            # Try to connect to an existing Chrome instance
            try:
                print(
                    f"Attempting to connect to Chrome on port {config.REMOTE_DEBUGGING_PORT}..."
                )
                self.browser = self.playwright.chromium.connect_over_cdp(
                    f"http://localhost:{config.REMOTE_DEBUGGING_PORT}"
                )
                if len(self.browser.contexts) > 0:
                    self.context = self.browser.contexts[0]
                    if len(self.context.pages) > 0:
                        self.page = self.context.pages[0]
                    else:
                        print("No pages found in browser context, creating new page")
                        self.page = self.context.new_page()
                else:
                    print("No browser contexts found, creating new context and page")
                    self.context = self.browser.new_context()
                    self.page = self.context.new_page()

                print("Successfully connected to Chrome browser")
            except Exception as e:
                # If connection fails, launch a new browser instance
                print(f"Could not connect to existing Chrome instance: {str(e)}")
                print("Launching new browser instance...")

                # Configure browser for better visibility and performance
                browser_args = [
                    "--start-maximized",  # Start with window maximized
                    "--disable-extensions",  # Disable extensions for stability
                    "--disable-popup-blocking",  # Allow popups (like message windows)
                    "--window-size=1920,1080",  # Set a large window size
                    "--disable-infobars",  # Remove info bars that might interfere with clicks
                ]

                self.browser = self.playwright.chromium.launch(
                    headless=False,
                    slow_mo=50,  # Reduced slow_mo for better responsiveness
                    args=browser_args,
                )

                # Create a context with specific viewport size
                self.context = self.browser.new_context(
                    viewport={"width": 1920, "height": 1080}
                )

                self.page = self.context.new_page()

                # Configure longer timeouts for all operations
                self.page.set_default_timeout(60000)  # 60 seconds timeout

                print("Successfully launched new Chrome browser")

        except Exception as e:
            print(
                f"Failed to initialize browser: {str(e)}. "
                f"Make sure Chrome is running with remote debugging enabled on port {config.REMOTE_DEBUGGING_PORT}, "
                f"or that playwright can launch a new browser instance."
            )

    def navigate(self, url: str, timeout: int = 3000, wait_until: str = "domcontentloaded") -> None:
        """Navigate to a URL.
        
        Args:
            url: The URL to navigate to
            timeout: Maximum navigation time in milliseconds
            wait_until: Navigation condition to wait for, options are:
                - 'domcontentloaded' - wait until DOMContentLoaded event
                - 'load' - wait until load event
                - 'networkidle' - wait until there are no network connections for 500ms
        """
        if not self.page:
            print("Cannot navigate: browser not initialized")
            return

        try:
            # First navigate with the specified wait_until condition
            self.page.goto(url, timeout=timeout, wait_until=wait_until)
            
        except Exception as e:
            pass
            print(f"Error navigating to {url}: {str(e)}")

    def get_page_source(self) -> str:
        """Get the current page source."""
        if not self.page:
            print("Cannot get page source: browser not initialized")
            return ""

        try:
            return self.page.content()
        except Exception as e:
            print(f"Error getting page source: {str(e)}")
            return ""

    def find_element(self, selector: str, by: str = "css") -> Any:
        """Find an element on the page."""
        if not self.page:
            print("Cannot find element: browser not initialized")
            return None

        try:
            if by == "css":
                return self.page.query_selector(selector)
            elif by == "xpath":
                return self.page.query_selector(f"xpath={selector}")
            else:
                print(f"Unsupported selector type: {by}")
                return None
        except Exception as e:
            print(f"Error finding element {selector}: {str(e)}")
            return None

    def find_elements(self, selector: str, by: str = "css") -> List[Any]:
        """Find elements on the page."""
        if not self.page:
            print("Cannot find elements: browser not initialized")
            return []
        # Don't try to print all elements here as it will affect the normal functionality
        # Instead use print_all_elements() method when needed

        try:
            if by == "css":
                return self.page.query_selector_all(selector)
            elif by == "xpath":
                return self.page.query_selector_all(f"xpath={selector}")
            else:
                print(f"Unsupported selector type: {by}")
                return []
        except Exception as e:
            print(f"Error finding elements {selector}: {str(e)}")
            return []
            
    def print_all_elements(self, max_elements: int = 100, include_attrs: bool = True) -> None:
        """Print all elements on the page with their details.
        
        Args:
            max_elements: Maximum number of elements to print
            include_attrs: Whether to include element attributes
        """
        if not self.page:
            print("Cannot print elements: browser not initialized")
            return
            
        try:
            # Execute JavaScript to get all elements and their details
            elements_info = self.page.evaluate("""
                () => {
                    const results = [];
                    const allElements = document.querySelectorAll('*');
                    
                    // Limit to avoid overwhelming output
                    const maxElements = Math.min(allElements.length, arguments[0]);
                    
                    for (let i = 0; i < maxElements; i++) {
                        const el = allElements[i];
                        const tagName = el.tagName.toLowerCase();
                        
                        // Skip some non-visible or less useful elements
                        if (['script', 'style', 'meta', 'link', 'head'].includes(tagName)) {
                            continue;
                        }
                        
                        // Build selector parts
                        let idSelector = el.id ? `#${el.id}` : '';
                        
                        let classSelector = '';
                        if (el.classList && el.classList.length > 0) {
                            classSelector = Array.from(el.classList)
                                .map(c => `.${c}`)
                                .join('');
                        }
                        
                        // Basic info
                        const info = {
                            tagName,
                            id: el.id || '',
                            classes: el.className || '',
                            textContent: (el.textContent || '').trim().substring(0, 50),
                            selector: `${tagName}${idSelector}${classSelector}`,
                            href: el.href || '',
                            src: el.src || '',
                        };
                        
                        // Include all attributes if requested
                        if (arguments[1]) {
                            info.attributes = {};
                            for (const attr of el.attributes) {
                                info.attributes[attr.name] = attr.value;
                            }
                        }
                        
                        results.push(info);
                    }
                    
                    return results;
                }
            """, max_elements, include_attrs)
            
            # Print the results
            print(f"\nFound {len(elements_info)} elements (limited to {max_elements}):\n")
            
            for i, info in enumerate(elements_info):
                print(f"Element {i+1}: <{info['tagName']}>")
                print(f"  Selector: {info['selector']}")
                
                if info['textContent']:
                    print(f"  Text: {info['textContent']}")
                    
                if info['href']:
                    print(f"  Href: {info['href']}")
                
                if include_attrs and 'attributes' in info:
                    attr_str = ", ".join([f"{k}='{v}'" for k, v in info['attributes'].items()])
                    print(f"  Attributes: {attr_str}")
                    
                print("")
                
        except Exception as e:
            print(f"Error printing elements: {str(e)}")
            
    def print_selector_matches(self, selector: str, limit: int = 10) -> None:
        """Print elements that match a specific selector.
        
        Args:
            selector: CSS or XPath selector to match
            limit: Maximum number of matching elements to print
        """
        if not self.page:
            print("Cannot find matches: browser not initialized")
            return
            
        try:
            # Determine if this is an XPath selector
            is_xpath = selector.startswith("xpath=") or selector.startswith("/")
            
            if is_xpath:
                if not selector.startswith("xpath="):
                    selector = f"xpath={selector}"
                    
            # Get elements
            elements = self.page.query_selector_all(selector)
            
            print(f"\nFound {len(elements)} elements matching '{selector}'")
            
            # Limit number of elements to display
            elements = elements[:limit]
            
            for i, element in enumerate(elements):
                # Get basic element info
                tag_name = element.evaluate("el => el.tagName.toLowerCase()")
                inner_text = element.inner_text()
                inner_text = inner_text[:50] + "..." if inner_text and len(inner_text) > 50 else inner_text
                
                # Get attributes
                attrs = element.evaluate("""
                    el => {
                        const result = {};
                        for (const attr of el.attributes) {
                            result[attr.name] = attr.value;
                        }
                        return result;
                    }
                """)
                
                # Print element information
                print(f"\nMatch {i+1}: <{tag_name}>")
                if inner_text:
                    print(f"  Text: {inner_text}")
                    
                # Print href attribute if it exists
                if 'href' in attrs:
                    print(f"  Href: {attrs['href']}")
                    
                # Print a few key attributes
                for attr in ['id', 'class', 'name', 'aria-label']:
                    if attr in attrs and attrs[attr]:
                        print(f"  {attr}: {attrs[attr]}")
        except Exception as e:
            print(f"Error printing selector matches: {str(e)}")

    def click(self, element: Any) -> None:
        """Click on an element with retry logic and better error handling."""
        import logging

        logger = logging.getLogger("seed_pitcher")

        if not element:
            logger.error("Cannot click: element is None")
            return

        # Try multiple click methods in sequence to ensure success
        for attempt in range(3):  # Try 3 times with different methods
            try:
                # Ensure browser window is active
                self.page.bring_to_front()

                # Scroll element into view before clicking
                self.page.evaluate(
                    "(element) => { element.scrollIntoView({behavior: 'smooth', block: 'center'}); }",
                    element,
                )

                # Wait for element to be stable
                time.sleep(1)

                if attempt == 0:
                    # First try: standard click with longer timeout
                    logger.info("Trying standard click")
                    self.page.set_default_timeout(60000)  # 60 seconds timeout
                    element.click(timeout=60000, force=False)
                elif attempt == 1:
                    # Second try: force click which bypasses some checks
                    logger.info("Trying force click")
                    element.click(force=True, timeout=60000)
                else:
                    # Third try: JavaScript click
                    logger.info("Trying JavaScript click")
                    self.page.evaluate("(element) => { element.click(); }", element)

                # If we get here, click was successful
                logger.info("Click successful")
                time.sleep(2)  # Wait longer for action to complete
                return

            except Exception as e:
                logger.warning(f"Click attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2)  # Wait before retrying

        # All attempts failed
        logger.error("All click methods failed")

        # Last resort: try dispatch click event directly
        try:
            logger.info("Trying dispatch event as last resort")
            self.page.evaluate(
                """
                (element) => {
                    const clickEvent = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        buttons: 1
                    });
                    element.dispatchEvent(clickEvent);
                }
                """,
                element,
            )
            time.sleep(2)
            logger.info("Dispatch event completed")
        except Exception as e:
            logger.error(f"Final click attempt also failed: {str(e)}")

    def type_text(self, element: Any, text: str) -> None:
        """Type text into an element with better error handling and multiple attempts."""
        import logging

        logger = logging.getLogger("seed_pitcher")

        if not element:
            logger.error("Cannot type text: element is None")
            return

        for attempt in range(3):  # Try 3 times with different methods
            try:
                if attempt == 0:
                    # First try: clear and type
                    logger.info("Trying standard fill and type method")
                    element.fill("")  # Clear existing text
                    time.sleep(0.5)  # Brief pause between clearing and typing
                    element.type(
                        text, delay=5
                    )  # Type with slight delay between keypresses
                elif attempt == 1:
                    # Second try: focus and type
                    logger.info("Trying focus and type method")
                    element.focus()
                    time.sleep(0.5)
                    element.press("Control+A")  # Select all text
                    element.press("Delete")  # Delete selected text
                    time.sleep(0.5)
                    element.type(text, delay=10)  # Type with more delay
                else:
                    # Third try: JavaScript approach
                    logger.info("Trying JavaScript approach")
                    # Use JavaScript to set the value and trigger input events
                    self.page.evaluate(
                        """
                        (element, text) => {
                            element.focus();
                            element.innerHTML = '';
                            element.textContent = text;
                            
                            // Trigger input event to activate any listeners
                            element.dispatchEvent(new Event('input', { bubbles: true }));
                            element.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                        """,
                        element,
                        text,
                    )

                # If we get here, typing was successful
                logger.info("Text input successful")
                return

            except Exception as e:
                logger.warning(f"Type attempt {attempt + 1} failed: {str(e)}")
                time.sleep(1)  # Wait before retrying

        # All attempts failed
        logger.error("All typing methods failed")

    def get_text(self, element: Any) -> str:
        """Get text from an element."""
        if not element:
            print("Cannot get text: element is None")
            return ""

        try:
            return element.inner_text()
        except Exception as e:
            print(f"Error getting text: {str(e)}")
            return ""

    def get_attribute(self, element: Any, attribute: str) -> str:
        """Get attribute from an element."""
        if not element:
            print(f"Cannot get attribute {attribute}: element is None")
            return ""

        try:
            return element.get_attribute(attribute) or ""
        except Exception as e:
            print(f"Error getting attribute {attribute}: {str(e)}")
            return ""

    def scroll(self, amount: int = 500) -> None:
        """Scroll the page."""
        if not self.page:
            print("Cannot scroll: browser not initialized")
            return

        try:
            self.page.evaluate(f"window.scrollBy(0, {amount})")
            time.sleep(0.5)
        except Exception as e:
            print(f"Error scrolling page: {str(e)}")

    def wait_for_element(
        self, selector: str, by: str = "css", timeout: int = 10000
    ) -> Optional[Any]:
        """Wait for an element to appear."""
        if not self.page:
            print("Cannot wait for element: browser not initialized")
            return None

        try:
            if by == "css":
                return self.page.wait_for_selector(selector, timeout=timeout)
            elif by == "xpath":
                return self.page.wait_for_selector(f"xpath={selector}", timeout=timeout)
            else:
                print(f"Unsupported selector type: {by}")
                return None
        except Exception as e:
            print(f"Error waiting for element {selector}: {str(e)}")
            return None

    def execute_script(self, script: str, element: Any = None) -> Any:
        """Execute JavaScript in the browser with better error handling."""
        import logging

        logger = logging.getLogger("seed_pitcher")

        if not self.page:
            logger.error("Cannot execute script: browser not initialized")
            return None

        try:
            # Ensure the page is active before executing script
            self.page.bring_to_front()

            # Different execution paths based on whether an element is provided
            if element:
                logger.info("Executing script with element")
                return self.page.evaluate(script, element)
            else:
                logger.info("Executing script without element")
                return self.page.evaluate(script)

        except Exception as e:
            logger.error(f"Error executing script: {str(e)}")

            # Try an alternative method if the first one fails
            try:
                logger.info("Trying alternative script execution method")

                # For element-based scripts that failed, try with a different approach
                if element:
                    # Create a script that works with element selectors instead
                    result = self.page.evaluate(
                        """
                        (script) => {
                            // Execute the script in the global context
                            return eval(script);
                        }
                        """,
                        script.replace("arguments[0]", "document.activeElement"),
                    )
                    return result
                else:
                    # Just try to evaluate it directly as a string
                    return self.page.evaluate(f"() => {{ {script} }}")

            except Exception as e2:
                logger.error(f"Alternative script execution also failed: {str(e2)}")
                return None

    def close(self) -> None:
        """Close the browser."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"Error closing browser: {str(e)}")
