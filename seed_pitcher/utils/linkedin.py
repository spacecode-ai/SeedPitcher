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

    def extract_profile(self, url: str) -> Dict[str, Any]:
        """Extract information from a LinkedIn profile."""
        import logging

        logger = logging.getLogger("seed_pitcher")
        logger.info(f"Starting LinkedIn profile extraction for URL: {url}")

        try:
            logger.info(f"Navigating to URL: {url}")
            self.browser.navigate(url)
            logger.info("Waiting for page to load")
            time.sleep(5)  # Increased wait time to allow page to load fully
            logger.info("Page loaded, proceeding with data extraction")
        except Exception as e:
            logger.error(
                f"Error navigating to LinkedIn profile: {str(e)}", exc_info=True
            )
            return {"url": url, "name": "Unknown", "error": str(e)}

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
                        name = self.browser.get_text(name_element)
                        if name and len(name.strip()) > 0:
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
                    profile_data["headline"] = (
                        self.browser.get_text(headline_element) or ""
                    )
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
                    profile_data["location"] = (
                        self.browser.get_text(location_element) or ""
                    )
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
                    profile_data["about"] = self.browser.get_text(about_element) or ""
                    logger.info(
                        f"Extracted about section, length: {len(profile_data['about'])}"
                    )
                except Exception as e:
                    logger.warning(f"Could not extract about text: {str(e)}")
            else:
                logger.warning("About element not found")
        except Exception as e:
            logger.warning(f"Error finding about element: {str(e)}")

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
                except:
                    continue

            if experience_section:
                # Try multiple selectors for experience items
                item_selectors = [
                    "li.pv-entity__position-group-pager",
                    "li.pvs-list__item--line-separated",
                    "div.pvs-entity",
                ]

                experience_items = []
                for selector in item_selectors:
                    try:
                        items = self.browser.find_elements(selector, experience_section)
                        if items:
                            experience_items = items
                            logger.info(
                                f"Found {len(items)} experience items with selector: {selector}"
                            )
                            break
                    except:
                        continue

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
                                    title = self.browser.get_text(title_element) or ""
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
                                    company = (
                                        self.browser.get_text(company_element) or ""
                                    )
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
                except:
                    continue

            if education_section:
                # Try multiple selectors for education items
                item_selectors = [
                    "li.pv-education-entity",
                    "li.pvs-list__item--line-separated",
                    "div.pvs-entity",
                ]

                education_items = []
                for selector in item_selectors:
                    try:
                        items = self.browser.find_elements(selector, education_section)
                        if items:
                            education_items = items
                            logger.info(
                                f"Found {len(items)} education items with selector: {selector}"
                            )
                            break
                    except:
                        continue

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
                                    school = self.browser.get_text(school_element) or ""
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
                                    degree = self.browser.get_text(degree_element) or ""
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
        logger.info(f"Profile extraction completed for: {url}")
        logger.info(
            f"Profile data: name='{profile_data['name']}', headline='{profile_data['headline']}', "
            + f"company='{profile_data['company']}', experiences={len(profile_data['experience'])}, "
            + f"education={len(profile_data['education'])}"
        )

        return profile_data
