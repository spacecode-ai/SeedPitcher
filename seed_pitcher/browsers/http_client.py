"""
HTTP Browser Client for SeedPitcher.

This module provides a client interface for the browser HTTP API,
allowing components like the Pin AI agent to control the browser indirectly,
which avoids the asyncio compatibility issues.
"""

import time
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger("seed_pitcher.browsers.http_client")

class HTTPBrowserClient:
    """Client for the Browser HTTP API."""

    def __init__(self, base_url="http://localhost:5500"):  # Updated default port to 5500
        """Initialize the HTTP browser client."""
        self.base_url = base_url
        self.session = requests.Session()
        logger.info(f"Initializing HTTP browser client with base URL: {base_url}")
        
        # Check if server is available
        try:
            logger.info("Performing health check on browser server...")
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Connected to browser server. Status: {data.get('status')}")
                logger.info(f"Browser server health data: {data}")
            else:
                logger.warning(f"Browser server returned unhealthy status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not connect to browser server: {str(e)}")
            logger.warning("Make sure the browser server is running")

    def navigate(self, url: str) -> bool:
        """Navigate to a URL."""
        try:
            response = self.session.post(
                f"{self.base_url}/navigate",
                json={"url": url},
                timeout=60  # Longer timeout for page navigation
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully navigated to {url}")
                return True
            else:
                logger.error(f"Failed to navigate to {url}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error navigating to {url}: {str(e)}")
            return False

    def get_page_source(self) -> str:
        """Get the current page source."""
        try:
            response = self.session.get(
                f"{self.base_url}/page_source",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("source", "")
            else:
                logger.error(f"Failed to get page source: {response.text}")
                return ""
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting page source: {str(e)}")
            return ""

    def find_element(self, selector: str, by: str = "css") -> Optional[Dict]:
        """Find an element on the page."""
        try:
            response = self.session.post(
                f"{self.base_url}/find_element",
                json={"selector": selector, "by": by},
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.info(f"Element not found with selector {selector}")
                return None
            else:
                logger.error(f"Failed to find element with selector {selector}: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error finding element with selector {selector}: {str(e)}")
            return None

    def find_elements(self, selector: str, by: str = "css") -> List[Dict]:
        """Find elements on the page."""
        try:
            response = self.session.post(
                f"{self.base_url}/find_elements",
                json={"selector": selector, "by": by},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("elements", [])
            elif response.status_code == 404:
                logger.info(f"No elements found with selector {selector}")
                return []
            else:
                logger.error(f"Failed to find elements with selector {selector}: {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error finding elements with selector {selector}: {str(e)}")
            return []

    def click(self, selector: str, by: str = "css") -> bool:
        """Click on an element identified by selector."""
        try:
            response = self.session.post(
                f"{self.base_url}/click",
                json={"selector": selector, "by": by},
                timeout=30  # Longer timeout for clicks that may trigger navigation
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully clicked element with selector {selector}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Could not click: Element not found with selector {selector}")
                return False
            else:
                logger.error(f"Failed to click element with selector {selector}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error clicking element with selector {selector}: {str(e)}")
            return False

    def type_text(self, selector: str, text: str, by: str = "css") -> bool:
        """Type text into an element identified by selector."""
        try:
            response = self.session.post(
                f"{self.base_url}/type_text",
                json={"selector": selector, "by": by, "text": text},
                timeout=20
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully typed text into element with selector {selector}")
                return True
            elif response.status_code == 404:
                logger.warning(f"Could not type text: Element not found with selector {selector}")
                return False
            else:
                logger.error(f"Failed to type text into element with selector {selector}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error typing text into element with selector {selector}: {str(e)}")
            return False

    def get_text(self, element: Dict) -> str:
        """Get text from an element result."""
        return element.get("text", "") if element else ""

    def get_attribute(self, element: Dict, attribute: str) -> str:
        """Get attribute from an element result."""
        return element.get("attribute_value", "") if element else ""

    def scroll(self, amount: int = 500) -> bool:
        """Scroll the page."""
        try:
            response = self.session.post(
                f"{self.base_url}/scroll",
                json={"amount": amount},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully scrolled page by {amount}")
                return True
            else:
                logger.error(f"Failed to scroll page: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error scrolling page: {str(e)}")
            return False

    def wait_for_element(self, selector: str, by: str = "css", timeout: int = 10000) -> bool:
        """Wait for an element to appear."""
        try:
            response = self.session.post(
                f"{self.base_url}/wait_for_element",
                json={"selector": selector, "by": by, "timeout": timeout},
                timeout=timeout/1000 + 5  # Add 5 seconds to the requested timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    logger.info(f"Element with selector {selector} appeared")
                    return True
                else:
                    logger.info(f"Element with selector {selector} did not appear within timeout")
                    return False
            else:
                logger.error(f"Failed to wait for element with selector {selector}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error waiting for element with selector {selector}: {str(e)}")
            return False

    def extract_linkedin_profile(self, url: str) -> Dict:
        """Extract information from a LinkedIn profile."""
        try:
            logger.info(f"Sending request to extract LinkedIn profile: {url}")
            logger.info(f"Using endpoint: {self.base_url}/linkedin_profile")
            
            response = self.session.post(
                f"{self.base_url}/linkedin_profile",
                json={"url": url},
                timeout=60  # Longer timeout for profile extraction
            )
            
            logger.info(f"LinkedIn profile extraction response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # Log important data from the response
                logger.info(f"Successfully extracted LinkedIn profile: {url}")
                
                # Log the critical investor data
                analysis = data.get('analysis', {})
                is_investor = analysis.get('is_investor', False)
                confidence = analysis.get('confidence', 0)
                keywords = analysis.get('investor_keywords_found', [])
                logger.info(f"EXTRACTED DATA - is_investor: {is_investor}, confidence: {confidence}, keywords: {keywords}")
                
                return data
            else:
                logger.error(f"Failed to extract LinkedIn profile {url}: {response.text}")
                return {"status": "error", "error": response.text}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error extracting LinkedIn profile {url}: {str(e)}")
            return {"status": "error", "error": str(e)}

    def close(self) -> bool:
        """Close the browser."""
        try:
            response = self.session.post(
                f"{self.base_url}/close",
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Successfully closed browser")
                return True
            else:
                logger.error(f"Failed to close browser: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error closing browser: {str(e)}")
            return False