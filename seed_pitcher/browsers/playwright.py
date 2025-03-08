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
                self.browser = self.playwright.chromium.launch(headless=False)
                self.context = self.browser.new_context()
                self.page = self.context.new_page()
                print("Successfully launched new Chrome browser")

        except Exception as e:
            print(
                f"Failed to initialize browser: {str(e)}. "
                f"Make sure Chrome is running with remote debugging enabled on port {config.REMOTE_DEBUGGING_PORT}, "
                f"or that playwright can launch a new browser instance."
            )

    def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        if not self.page:
            print("Cannot navigate: browser not initialized")
            return

        try:
            self.page.goto(url)
            self.page.wait_for_load_state("networkidle")
        except Exception as e:
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

    def click(self, element: Any) -> None:
        """Click on an element."""
        if not element:
            print("Cannot click: element is None")
            return

        try:
            element.click()
            time.sleep(1)  # Wait for action to complete
        except Exception as e:
            print(f"Error clicking element: {str(e)}")

    def type_text(self, element: Any, text: str) -> None:
        """Type text into an element."""
        if not element:
            print("Cannot type text: element is None")
            return

        try:
            element.fill("")
            element.type(text)
        except Exception as e:
            print(f"Error typing text: {str(e)}")

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

    def close(self) -> None:
        """Close the browser."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"Error closing browser: {str(e)}")
