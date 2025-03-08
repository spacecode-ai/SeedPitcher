"""
Browser management module for SeedPitcher.
"""

from seed_pitcher.browsers.playwright import PlaywrightBrowser


def get_browser():
    """Get a browser instance.

    Returns:
        A browser instance for web automation.
    """
    return PlaywrightBrowser()
