import requests
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_investor_scoring')

# Test the LinkedIn profile extraction and scoring
def test_scoring():
    base_url = "http://localhost:5500"
    
    # Test LinkedIn profile URL
    linkedin_url = "https://www.linkedin.com/in/christian-neumann-44a7a5195/"
    
    # Step 1: Extract LinkedIn profile
    logger.info(f"Extracting LinkedIn profile from {linkedin_url}")
    extract_response = requests.post(f"{base_url}/linkedin_profile", json={"url": linkedin_url})
    
    if extract_response.status_code == 200:
        profile_data = extract_response.json()
        logger.info(f"Profile extraction successful: {json.dumps(profile_data, indent=2)}")
        
        # Check if the profile has been identified as an investor
        is_investor = profile_data['analysis'].get('is_investor', False)
        confidence = profile_data['analysis'].get('confidence', 0)
        keywords = profile_data['analysis'].get('investor_keywords_found', [])
        
        logger.info(f"Investor detection: {is_investor} (confidence: {confidence})")
        logger.info(f"Investor keywords found: {keywords}")
        
        # Now with the agent scoring formula directly here
        if is_investor:
            # Base score from confidence
            base_score = confidence
            logger.info(f"Using direct confidence value {confidence} for investor score")
            
            # Additional bonus for having investor keywords
            keyword_bonus = min(0.2, len(keywords) * 0.05)
            investor_score = min(0.95, base_score + keyword_bonus)
            logger.info(f"Added keyword bonus of {keyword_bonus} based on {len(keywords)} keywords")
            logger.info(f"Final calculated investor score: {investor_score}")
        else:
            logger.info("Not identified as an investor, score would be 0")
            
    else:
        logger.error(f"Failed to extract profile: {extract_response.status_code}")
    
    # Step 3: Close the browser when done
    logger.info("Closing browser")
    close_response = requests.post(f"{base_url}/close")
    logger.info(f"Browser close response: {close_response.status_code}")

if __name__ == "__main__":
    test_scoring()
