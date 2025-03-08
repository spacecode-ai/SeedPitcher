"""LinkedIn interaction utilities."""

import time
from typing import List, Dict, Any
from urllib.parse import urlparse, urlunparse


class LinkedInHandler:
    """Handler for LinkedIn operations."""

    def __init__(self, browser):
        """Initialize with a browser instance."""
        self.browser = browser
        self.base_url = "https://www.linkedin.com"

    def go_to_connections_page(self) -> None:
        """Navigate to the LinkedIn connections page."""
        connections_url = f"{self.base_url}/mynetwork/invite-connect/connections/"
        self.browser.navigate(connections_url)

        # Wait for the page to load
        time.sleep(3)

        # Check if we're logged in, connections page should have a specific element
        connections_header = self.browser.find_element("h1.t-18")
        if not connections_header or "Connections" not in self.browser.get_text(
            connections_header
        ):
            raise Exception(
                "Not logged in to LinkedIn or connections page couldn't load"
            )

    def extract_connections(self, max_pages: int = 5) -> List[str]:
        """Extract connection profiles from the connections page."""
        profile_urls = []

        for page in range(max_pages):
            # Find all connection elements
            connection_cards = self.browser.find_elements(".mn-connection-card")

            for card in connection_cards:
                try:
                    # Extract profile link
                    profile_link = self.browser.find_element(
                        ".mn-connection-card__link", card
                    )
                    href = self.browser.get_attribute(profile_link, "href")

                    # Normalize URL
                    parsed_url = urlparse(href)
                    clean_path = "/".join(
                        parsed_url.path.split("/")[:3]
                    )  # Keep only /in/username part
                    normalized_url = urlunparse(
                        (parsed_url.scheme, parsed_url.netloc, clean_path, "", "", "")
                    )

                    profile_urls.append(normalized_url)
                except:
                    continue

            # Scroll to load more
            self.browser.scroll(1000)
            time.sleep(2)

            # Check if "Show more" button exists and click it
            try:
                show_more = self.browser.find_element(
                    "button.scaffold-finite-scroll__load-button"
                )
                if show_more:
                    self.browser.click(show_more)
                    time.sleep(3)
                else:
                    # No more connections to load
                    break
            except:
                # No show more button, probably reached the end
                break

        return profile_urls

    def search_profiles(self, query: str, max_pages: int = 3) -> List[str]:
        """Search for profiles on LinkedIn."""
        # Encode query for URL
        from urllib.parse import quote

        encoded_query = quote(query)

        # Navigate to search results
        search_url = f"{self.base_url}/search/results/people/?keywords={encoded_query}"
        self.browser.navigate(search_url)
        time.sleep(3)

        profile_urls = []

        for page in range(max_pages):
            # Find all search result elements
            result_cards = self.browser.find_elements(
                ".reusable-search__result-container"
            )

            for card in result_cards:
                try:
                    # Extract profile link
                    profile_link = self.browser.find_element("a.app-aware-link", card)
                    href = self.browser.get_attribute(profile_link, "href")

                    # Extract only profile URLs
                    if "/in/" in href:
                        # Normalize URL
                        parsed_url = urlparse(href)
                        clean_path = "/".join(
                            parsed_url.path.split("/")[:3]
                        )  # Keep only /in/username part
                        normalized_url = urlunparse(
                            (
                                parsed_url.scheme,
                                parsed_url.netloc,
                                clean_path,
                                "",
                                "",
                                "",
                            )
                        )

                        profile_urls.append(normalized_url)
                except:
                    continue

            # Scroll to load more
            self.browser.scroll(1000)
            time.sleep(2)

            # Check if pagination exists and click next
            try:
                next_button = self.browser.find_element(
                    "button.artdeco-pagination__button--next"
                )
                if next_button:
                    self.browser.click(next_button)
                    time.sleep(3)
                else:
                    # No more pages
                    break
            except:
                # No pagination, probably only one page of results
                break

        return profile_urls

    def _safe_navigate(
        self, url: str, timeout: int = 60000, retry_count: int = 2
    ) -> bool:
        """Safely navigate to a URL with timeouts and retries."""
        import logging
        import time

        logger = logging.getLogger("seed_pitcher")

        logger.info(f"Navigating to {url} with {timeout}ms timeout")

        for attempt in range(retry_count + 1):
            try:
                # Increase the timeout for slow connections
                self.browser.page.set_default_navigation_timeout(timeout)

                # Navigate to the URL
                self.browser.navigate(url)

                # Wait for the page to load more completely
                wait_time = 3 + attempt * 2  # Increase wait time with each retry
                logger.info(
                    f"Navigation successful, waiting {wait_time}s for page to load"
                )
                time.sleep(wait_time)

                # Check if we were redirected to a login page
                current_url = self.browser.page.url
                login_indicators = ["login", "auth", "sign-in"]

                if any(
                    indicator in current_url.lower() for indicator in login_indicators
                ):
                    logger.error(f"Redirected to login page: {current_url}")
                    return False

                return True

            except Exception as e:
                logger.warning(
                    f"Navigation attempt {attempt + 1}/{retry_count + 1} failed: {str(e)}"
                )
                if attempt < retry_count:
                    # Increase timeout for next attempt
                    timeout += 30000  # Add 30s each retry
                    logger.info(f"Retrying with {timeout}ms timeout")
                    time.sleep(2)  # Wait before retry
                else:
                    logger.error(
                        f"All navigation attempts to {url} failed", exc_info=True
                    )
                    return False

        return False  # Should never reach here, but just in case

    def _safe_get_text(self, element) -> str:
        """Safely extract text from an element, handling JSHandle@node errors."""
        import logging

        logger = logging.getLogger("seed_pitcher")

        if element is None:
            return ""

        try:
            text = self.browser.get_text(element)
            if isinstance(text, str):
                return text.strip()
            logger.warning(f"Got non-string text object: {type(text)}")
            return ""
        except Exception as e:
            logger.warning(f"Error extracting text: {str(e)}")
            return ""

    def _safe_find_elements(self, selector, parent=None) -> list:
        """Safely find elements, handling JSHandle@node errors."""
        import logging

        logger = logging.getLogger("seed_pitcher")

        try:
            elements = []
            if parent is None:
                elements = self.browser.find_elements(selector)
            else:
                elements = self.browser.find_elements(selector, parent)

            # Filter out any non-element objects
            valid_elements = []
            for e in elements:
                if e is not None:
                    valid_elements.append(e)

            return valid_elements
        except Exception as e:
            logger.warning(f"Error finding elements with selector {selector}: {str(e)}")
            return []

    def extract_profile(self, url: str) -> Dict[str, Any]:
        """Extract information from a LinkedIn profile."""
        import logging

        logger = logging.getLogger("seed_pitcher")
        logger.info(f"Starting LinkedIn profile extraction for URL: {url}")

        # Use our safe navigation utility with retries and better error handling
        if not self._safe_navigate(url, timeout=60000, retry_count=2):
            logger.error(f"Failed to navigate to profile URL: {url}")
            return {
                "url": url,
                "error": "Failed to load profile due to navigation error or timeout",
            }

        logger.info("Page loaded successfully, proceeding with data extraction")

        profile_data = {
            "url": url,
            "name": "",
            "headline": "",
            "company": "",
            "location": "",
            "about": "",
            "experience": [],
            "education": [],
            "fund": "",
        }

        # Extract name - this is critical, exit with error if not found
        name_found = False
        try:
            # Try multiple selectors for the name
            name_selectors = [
                "h1.text-heading-xlarge",
                "h1.inline",
                "h1.text-heading-large",
            ]

            for selector in name_selectors:
                try:
                    name_element = self.browser.find_element(selector)
                    if name_element:
                        name = self._safe_get_text(name_element)
                        if name and len(name) > 0:
                            profile_data["name"] = name
                            logger.info(f"Extracted name: {profile_data['name']}")
                            name_found = True
                            break
                except Exception as e:
                    continue

            if not name_found:
                error_msg = "Could not extract profile name - LinkedIn profile data cannot be processed"
                logger.error(error_msg)
                return {"url": url, "error": error_msg}

        except Exception as e:
            error_msg = f"Error finding name element: {str(e)}"
            logger.error(error_msg)
            return {"url": url, "error": error_msg}

        try:
            headline_element = self.browser.find_element("div.text-body-medium")
            if headline_element:
                try:
                    profile_data["headline"] = self._safe_get_text(headline_element)
                    logger.info(f"Extracted headline: {profile_data['headline']}")
                except Exception as e:
                    logger.warning(f"Could not extract headline: {str(e)}")
            else:
                logger.warning("Headline element not found")
        except Exception as e:
            logger.warning(f"Error finding headline element: {str(e)}")

        try:
            location_element = self.browser.find_element(
                "span.text-body-small[aria-hidden='true']"
            )
            if location_element:
                try:
                    profile_data["location"] = self._safe_get_text(location_element)
                    logger.info(f"Extracted location: {profile_data['location']}")
                except Exception as e:
                    logger.warning(f"Could not extract location: {str(e)}")
            else:
                logger.warning("Location element not found")
        except Exception as e:
            logger.warning(f"Error finding location element: {str(e)}")

        # Extract about section with improved error handling
        try:
            about_element = self.browser.find_element(
                "div.display-flex.ph5.pv3 > div.pv-shared-text-with-see-more"
            )
            if about_element:
                try:
                    profile_data["about"] = self._safe_get_text(about_element)
                    logger.info(
                        f"Extracted about section, length: {len(profile_data['about'])}"
                    )
                except Exception as e:
                    logger.warning(f"Could not extract about text: {str(e)}")
            else:
                logger.warning("About element not found")
        except Exception as e:
            logger.warning(f"Error finding about element: {str(e)}")

        # Make sure we return a valid profile even with extraction errors
        if profile_data["name"]:
            logger.info(
                f"Successfully extracted basic profile for: {profile_data['name']}"
            )

            # If we couldn't extract any experience but we have a headline, use it to create a minimal experience
            if not profile_data["experience"] and profile_data["headline"]:
                headline = profile_data["headline"]
                logger.info(f"Creating minimal experience from headline: {headline}")

                # Parse headline to extract potential job title and company
                title_parts = []
                company = ""

                if " at " in headline:
                    parts = headline.split(" at ")
                    title_parts = [parts[0].strip()]
                    company = parts[1].strip()
                elif " @ " in headline:
                    parts = headline.split(" @ ")
                    title_parts = [parts[0].strip()]
                    company = parts[1].strip()
                else:
                    title_parts = [headline]

                # Add the experience from headline
                profile_data["experience"].append(
                    {
                        "title": title_parts[0] if title_parts else headline,
                        "company": company,
                    }
                )

                # Also set the company field if not already set
                if not profile_data["company"] and company:
                    profile_data["company"] = company

                    # Look for fund keywords in the company name
                    lower_company = company.lower()
                    if any(
                        keyword in lower_company
                        for keyword in ["capital", "ventures", "partners", "fund"]
                    ):
                        profile_data["fund"] = company
                        logger.info(f"Set fund to: {company}")

        # Extract experience (only first few) with improved error handling
        try:
            # Try multiple selectors for experience section - LinkedIn changes their selectors frequently
            experience_selectors = [
                "section#experience-section",
                "section.experience-section",
                "div.experience-section",
                "#experience",
            ]

            experience_section = None
            for selector in experience_selectors:
                try:
                    experience_section = self.browser.find_element(selector)
                    if experience_section:
                        logger.info(
                            f"Found experience section with selector: {selector}"
                        )
                        break
                except Exception as e:
                    logger.warning(
                        f"Error finding experience selector {selector}: {str(e)}"
                    )
                    continue

            if experience_section:
                # Try multiple selectors for experience items - using safe method
                item_selectors = [
                    "li.pv-entity__position-group-pager",
                    "li.pvs-list__item--line-separated",
                    "div.pvs-entity",
                ]

                experience_items = []
                for selector in item_selectors:
                    items = self._safe_find_elements(selector, experience_section)
                    if items:
                        experience_items = items
                        logger.info(
                            f"Found {len(items)} experience items with selector: {selector}"
                        )
                        break

                for i, item in enumerate(
                    experience_items[:3]
                ):  # Limit to first 3 experiences
                    try:
                        # Safe text extraction with fallbacks
                        title = ""
                        company = ""

                        # Try multiple selectors for title
                        title_selectors = [
                            "h3.t-16",
                            "span.t-16",
                            "span.mr1 span",
                            "span.mr1",
                        ]
                        for selector in title_selectors:
                            try:
                                title_element = self.browser.find_element(
                                    selector, item
                                )
                                if title_element:
                                    title = self._safe_get_text(title_element)
                                    if title:
                                        break
                            except:
                                continue

                        # Try multiple selectors for company
                        company_selectors = [
                            "p.pv-entity__secondary-title",
                            "span.t-14",
                            "span.t-normal",
                        ]
                        for selector in company_selectors:
                            try:
                                company_element = self.browser.find_element(
                                    selector, item
                                )
                                if company_element:
                                    company = self._safe_get_text(company_element)
                                    if company:
                                        break
                            except:
                                continue

                        if title or company:  # Only add if we found at least one field
                            experience = {"title": title, "company": company}

                            profile_data["experience"].append(experience)
                            logger.info(
                                f"Added experience {i + 1}: {title} at {company}"
                            )

                            # Set current company if not already set
                            if (
                                not profile_data["company"]
                                and company
                                and len(profile_data["experience"]) == 1
                            ):
                                profile_data["company"] = company
                                logger.info(f"Set current company to: {company}")

                                # Look for fund names in the company title
                                lower_company = company.lower()
                                if any(
                                    keyword in lower_company
                                    for keyword in [
                                        "capital",
                                        "ventures",
                                        "partners",
                                        "fund",
                                    ]
                                ):
                                    profile_data["fund"] = company
                                    logger.info(f"Set fund to: {company}")
                    except Exception as e:
                        logger.warning(
                            f"Error extracting experience item {i + 1}: {str(e)}"
                        )
                        continue
            else:
                logger.warning("Experience section not found")
        except Exception as e:
            logger.warning(f"Error finding experience section: {str(e)}")

        # Extract education (only first few) with improved error handling
        try:
            # Try multiple selectors for education section
            education_selectors = [
                "section#education-section",
                "section.education-section",
                "div.education-section",
                "#education",
            ]

            education_section = None
            for selector in education_selectors:
                try:
                    education_section = self.browser.find_element(selector)
                    if education_section:
                        logger.info(
                            f"Found education section with selector: {selector}"
                        )
                        break
                except Exception as e:
                    logger.warning(
                        f"Error finding education selector {selector}: {str(e)}"
                    )
                    continue

            if education_section:
                # Try multiple selectors for education items - using safe method
                item_selectors = [
                    "li.pv-education-entity",
                    "li.pvs-list__item--line-separated",
                    "div.pvs-entity",
                ]

                education_items = []
                for selector in item_selectors:
                    items = self._safe_find_elements(selector, education_section)
                    if items:
                        education_items = items
                        logger.info(
                            f"Found {len(items)} education items with selector: {selector}"
                        )
                        break

                for i, item in enumerate(
                    education_items[:2]
                ):  # Limit to first 2 educational experiences
                    try:
                        # Safe text extraction with fallbacks
                        school = ""
                        degree = ""

                        # Try multiple selectors for school
                        school_selectors = [
                            "h3.pv-entity__school-name",
                            "span.t-16",
                            "span.mr1 span",
                            "span.mr1",
                        ]
                        for selector in school_selectors:
                            try:
                                school_element = self.browser.find_element(
                                    selector, item
                                )
                                if school_element:
                                    school = self._safe_get_text(school_element)
                                    if school:
                                        break
                            except:
                                continue

                        # Try multiple selectors for degree
                        degree_selectors = [
                            "p.pv-entity__degree-name span.pv-entity__comma-item",
                            "span.t-14",
                            "span.t-normal",
                        ]
                        for selector in degree_selectors:
                            try:
                                degree_element = self.browser.find_element(
                                    selector, item
                                )
                                if degree_element:
                                    degree = self._safe_get_text(degree_element)
                                    if degree:
                                        break
                            except:
                                continue

                        if school or degree:  # Only add if we found at least one field
                            education = {"school": school, "degree": degree}

                            profile_data["education"].append(education)
                            logger.info(
                                f"Added education {i + 1}: {degree} at {school}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error extracting education item {i + 1}: {str(e)}"
                        )
                        continue
            else:
                logger.warning("Education section not found")
        except Exception as e:
            logger.warning(f"Error finding education section: {str(e)}")

        # Log the final profile data summary
        logger.info(
            f"Completed profile extraction for {profile_data.get('name', 'Unknown')}"
            + f" with {len(profile_data.get('experience', []))} experience items"
            + f" and {len(profile_data.get('education', []))} education items"
        )

        # Return the completed profile data
        return profile_data

    def get_previous_messages(self, profile_url: str) -> List[str]:
        """Check for previous message history with this contact."""
        try:
            # Navigate to the profile
            self.browser.navigate(profile_url)
            time.sleep(3)

            # Look for the message button
            message_selectors = [
                "button.message-anywhere-button",
                "button.pv-s-profile-actions--message",
                "button[aria-label='Message']",
                "a.message-anywhere-button",
                "a[data-control-name='message']",
            ]

            message_button = None
            for selector in message_selectors:
                try:
                    message_button = self.browser.find_element(selector)
                    if message_button:
                        break
                except Exception as e:
                    continue

            if not message_button:
                return []  # No message button found, can't check history

            # Click the message button to open the chat window
            self.browser.click(message_button)
            time.sleep(2)

            # Check if there are previous messages
            message_history_selectors = [
                ".msg-s-message-list__event",
                ".msg-s-message-list-content",
                ".msg-s-message-group__meta",
            ]

            # Look for message history
            messages = []
            for selector in message_history_selectors:
                try:
                    message_elements = self.browser.find_elements(selector)
                    if message_elements:
                        # Extract text from message elements
                        for element in message_elements:
                            msg_text = self._safe_get_text(element)
                            if msg_text:
                                messages.append(msg_text)
                except Exception as e:
                    continue

            # Close the message window
            try:
                close_button = self.browser.find_element(
                    "button.msg-overlay-bubble-header__control--close-btn"
                )
                if close_button:
                    self.browser.click(close_button)
            except:
                pass  # Can't close the window, not critical

            return messages

        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Failed to check previous messages: {str(e)}"
            )
            return []

    def send_message(self, profile_url: str, message: str) -> bool:
        """Send a message to a LinkedIn contact using Playwright."""
        import logging
        import time

        logger = logging.getLogger("seed_pitcher")

        try:
            # Use our new safe navigation utility instead of duplicating code
            if not self._safe_navigate(profile_url, timeout=60000, retry_count=2):
                logger.error(
                    f"Failed to navigate to profile for sending message: {profile_url}"
                )
                return False

            # Look for the message button
            message_selectors = [
                "button.message-anywhere-button",
                "button.pv-s-profile-actions--message",
                "button[aria-label='Message']",
                "a.message-anywhere-button",
                "a[data-control-name='message']",
            ]

            message_button = None
            for selector in message_selectors:
                try:
                    message_button = self.browser.find_element(selector)
                    if message_button:
                        logger.info(f"Found message button with selector: {selector}")
                        break
                except Exception as e:
                    continue

            if not message_button:
                logger.warning("Could not find message button on profile")
                return False

            # Click the message button to open the chat window
            logger.info("Clicking message button")
            try:
                self.browser.click(message_button)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to click message button: {str(e)}")
                # Try an alternative approach
                try:
                    self.browser.execute_script("arguments[0].click();", message_button)
                    time.sleep(2)
                except Exception as e2:
                    logger.error(
                        f"All methods to click message button failed: {str(e2)}"
                    )
                    return False

            # Look for message input field
            message_input_selectors = [
                "div.msg-form__contenteditable",
                "div[role='textbox']",
                "div.msg-form__msg-content-container",
            ]

            message_input = None
            for selector in message_input_selectors:
                try:
                    message_input = self.browser.find_element(selector)
                    if message_input:
                        logger.info(f"Found message input with selector: {selector}")
                        break
                except Exception as e:
                    continue

            if not message_input:
                logger.warning("Could not find message input field")
                return False

            # Type the message
            logger.info("Typing message")
            self.browser.fill(message_input, message)
            time.sleep(1)

            # Look for send button
            send_button_selectors = [
                "button.msg-form__send-button",
                "button[type='submit']",
                "button.artdeco-button--primary",
            ]

            send_button = None
            for selector in send_button_selectors:
                try:
                    send_button = self.browser.find_element(selector)
                    if send_button:
                        logger.info(f"Found send button with selector: {selector}")
                        break
                except Exception as e:
                    continue

            if not send_button:
                logger.warning("Could not find send button")
                return False

            # Click the send button
            logger.info("Clicking send button")
            try:
                self.browser.click(send_button)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to click send button: {str(e)}")
                # Try an alternative approach
                try:
                    self.browser.execute_script("arguments[0].click();", send_button)
                    time.sleep(2)
                except Exception as e2:
                    logger.error(f"All methods to click send button failed: {str(e2)}")
                    return False

            logger.info("Message sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            return False

    def _log_extraction_summary(self, url, profile_data):
        """Log a summary of the extracted profile data."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Profile extraction completed for: {url}")
        logger.info(
            f"Profile data: name='{profile_data['name']}', headline='{profile_data['headline']}', "
            + f"company='{profile_data['company']}', experiences={len(profile_data['experience'])}, "
            + f"education={len(profile_data['education'])}"
        )

        return profile_data
