"""Integration with simular.ai browser."""

import time
from typing import List, Dict, Any, Optional


class SimularBrowser:
    """Wrapper for the simular.ai browser."""

    def __init__(self):
        """Initialize the simular.ai browser."""
        try:
            from simular import Simular

            self.browser = Simular()
            self.driver = self.browser.driver
        except ImportError:
            raise ImportError(
                "The simular package is not installed. "
                "Please install it with: pip install pysimular"
            )

    def navigate(self, url: str) -> None:
        """Navigate to a URL."""
        self.driver.get(url)
        time.sleep(2)  # Wait for page to load

    def get_page_source(self) -> str:
        """Get the current page source."""
        return self.driver.page_source

    def find_element(self, selector: str, by: str = "css") -> Any:
        """Find an element on the page."""
        if by == "css":
            return self.driver.find_element_by_css_selector(selector)
        elif by == "xpath":
            return self.driver.find_element_by_xpath(selector)
        else:
            raise ValueError(f"Unsupported selector type: {by}")

    def find_elements(self, selector: str, by: str = "css") -> List[Any]:
        """Find elements on the page."""
        if by == "css":
            return self.driver.find_elements_by_css_selector(selector)
        elif by == "xpath":
            return self.driver.find_elements_by_xpath(selector)
        else:
            raise ValueError(f"Unsupported selector type: {by}")

    def click(self, element: Any) -> None:
        """Click on an element."""
        element.click()
        time.sleep(1)  # Wait for action to complete

    def type_text(self, element: Any, text: str) -> None:
        """Type text into an element."""
        element.clear()
        element.send_keys(text)

    def get_text(self, element: Any) -> str:
        """Get text from an element."""
        return element.text

    def get_attribute(self, element: Any, attribute: str) -> str:
        """Get attribute from an element."""
        return element.get_attribute(attribute)

    def scroll(self, amount: int = 500) -> None:
        """Scroll the page."""
        self.driver.execute_script(f"window.scrollBy(0, {amount})")
        time.sleep(0.5)

    def wait_for_element(
        self, selector: str, by: str = "css", timeout: int = 10
    ) -> Optional[Any]:
        """Wait for an element to appear."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC

        by_method = By.CSS_SELECTOR if by == "css" else By.XPATH

        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_method, selector))
            )
            return element
        except:
            return None

    def close(self) -> None:
        """Close the browser."""
        self.driver.quit()
