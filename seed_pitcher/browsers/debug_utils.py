"""Debug utilities for browser interaction."""

from typing import List, Dict, Any, Optional
import json

def print_all_links(browser, selector: str = "a", attrs_to_print: List[str] = None) -> None:
    """
    Print all link elements and their attributes found on the current page.
    
    Args:
        browser: Browser instance
        selector: CSS selector to find elements (default: all links)
        attrs_to_print: List of attributes to print for each element (default: href, id, class, text)
    """
    if attrs_to_print is None:
        attrs_to_print = ["href", "id", "class"]
    
    elements = browser.find_elements(selector)
    print(f"Found {len(elements)} elements matching selector '{selector}'")
    
    for i, element in enumerate(elements):
        print(f"\n--- Element {i+1} ---")
        
        # Print requested attributes
        for attr in attrs_to_print:
            value = browser.get_attribute(element, attr)
            if value:
                print(f"{attr}: {value}")
        
        # Also print text content
        text = browser.get_text(element)
        if text and text.strip():
            # Truncate very long text
            if len(text) > 100:
                text = text[:97] + "..."
            print(f"text: {text}")

def find_elements_containing_url_pattern(browser, pattern: str, selector: str = "a") -> List[Dict[str, Any]]:
    """
    Find all elements containing a specific URL pattern and return their details.
    
    Args:
        browser: Browser instance
        pattern: URL pattern to search for (e.g., "/in/")
        selector: CSS selector to find elements (default: all links)
        
    Returns:
        List of dictionaries containing element details
    """
    results = []
    elements = browser.find_elements(selector)
    
    print(f"Searching {len(elements)} elements for pattern '{pattern}'...")
    
    for i, element in enumerate(elements):
        href = browser.get_attribute(element, "href") or ""
        if pattern in href:
            # Collect details about this element
            element_info = {
                "index": i,
                "href": href,
                "text": browser.get_text(element),
                "id": browser.get_attribute(element, "id"),
                "class": browser.get_attribute(element, "class"),
            }
            results.append(element_info)
    
    print(f"Found {len(results)} elements containing pattern '{pattern}'")
    return results

def examine_linkedin_search_results(browser) -> None:
    """
    Specifically analyze LinkedIn search results page to find profile links.
    
    Args:
        browser: Browser instance
    """
    print("\n=== LinkedIn Search Results Analysis ===\n")
    
    # First check for search result containers
    containers = browser.find_elements(".reusable-search__result-container")
    print(f"Found {len(containers)} search result containers")
    
    # Find all profile links 
    profile_links = find_elements_containing_url_pattern(browser, "/in/")
    
    # Print the first 5 links in detail
    for i, link in enumerate(profile_links[:5]):
        print(f"\nProfile Link {i+1}:")
        print(json.dumps(link, indent=2))
    
    if len(profile_links) > 5:
        print(f"\n...and {len(profile_links) - 5} more profile links")
    
    # Try to identify any search-specific elements
    print("\nChecking for search navigation elements:")
    pagination = browser.find_elements(".artdeco-pagination")
    if pagination:
        print("- Found pagination controls")
        
    next_button = browser.find_element("button.artdeco-pagination__button--next")
    if next_button:
        print("- Found 'Next' button")
    
    # Check if we're on a proper search results page
    search_header = browser.find_element(".search-results__cluster-title")
    if search_header:
        print(f"- Found search header: {browser.get_text(search_header)}")
