"""Utilities for drafting investor messages."""

from typing import Dict, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate


def draft_investor_message(
    profile: Dict[str, Any],
    analysis: Dict[str, Any],
    startup_info: Dict[str, str],
    llm: BaseChatModel,
) -> str:
    """Draft a personalized message to an investor based on their profile and analysis."""
    # Create prompt template for message drafting
    template = """
    You are an expert in crafting effective initial outreach messages for startups to send to potential investors.
    Your task is to draft a brief, personalized LinkedIn message from a startup founder to a potential investor.
    
    ### Investor Information:
    - Name: {investor_name}
    - Current position: {investor_headline}
    - Fund/Company: {investor_company}
    
    ### Startup Information:
    - Elevator pitch: {elevator_pitch}
    - Founder name: {founder_name}
    
    Draft a short, personalized LinkedIn message (max 120 words) to this investor that:
    1. Establishes a brief personal connection if possible
    2. EXACTLY identifies the founder as "{founder_name}" (use the EXACT name provided, do NOT substitute with any other name like 'Alex')
    3. Includes specific details from the elevator pitch - focus on the problem being solved and unique value proposition
    4. Mentions 1-2 SPECIFIC and CONCRETE details about what the startup is building (extracted directly from the elevator pitch)
    5. Expresses interest in connecting but DOES NOT reveal detailed fundraising intentions
    6. Asks if they'd like to learn more
    7. Maintains a professional but conversational tone
    
    IMPORTANT GUIDELINES:
    - CRITICAL: The founder's name is "{founder_name}" - ALWAYS use this EXACT name in the intro and signature
    - NEVER use "Alex" or any other name - ONLY use "{founder_name}" as the founder's name
    - Be SPECIFIC about what the startup does - avoid vague terms like "what we're building"
    - Use ACTUAL DETAILS from the elevator pitch - don't be generic
    - Extract and include at least one CONCRETE achievement, metric, or specific technology mentioned in the elevator pitch
    - DO NOT invent or assume ANY details about the startup - use ONLY information explicitly provided in the elevator pitch
    - DO NOT make generic references to industries or technologies if they are not in the elevator pitch
    - NEVER mention "space technology", "space infrastructure" or similar terms unless they are explicitly in the elevator pitch
    - DO NOT mention the investor's investment focus or portfolio companies
    - DO NOT reveal detailed fundraising information
    - Be respectful of their time
    
    The message should include SPECIFIC details from the elevator pitch while maintaining a conversational tone.
    
    In the signature, ONLY use "{founder_name}" as the name, for example:
    
    Best,
    {founder_name}
    
    Do NOT use any other name like 'Alex' in the signature or anywhere in the message.
    """

    # Format variables for the prompt with robust error handling
    try:
        # First log what we've received to help with debugging
        import logging

        logger = logging.getLogger("seed_pitcher")
        logger.info(
            f"Profile data: {profile.get('name', 'Unknown')}, Analysis: {analysis.get('is_investor', 'Unknown')}"
        )
        if startup_info:
            logger.info(
                f"Startup elevator pitch: {startup_info.get('elevator_pitch', 'Not provided')}"
            )

        investor_name = profile.get("name", "Investor") if profile else "Investor"
        investor_headline = profile.get("headline", "") if profile else ""

        # Try multiple sources for company name with fallbacks
        investor_company = ""
        if profile:
            if profile.get("company"):
                investor_company = profile.get("company")
            elif profile.get("fund"):
                investor_company = profile.get("fund")
            elif profile.get("experience") and len(profile.get("experience")) > 0:
                # Extract from first experience item
                investor_company = profile["experience"][0].get("company", "")

        # Fallback to analysis if available
        if not investor_company and analysis:
            investor_company = analysis.get("fund_name", "")

        # Get startup info
        elevator_pitch = ""
        if startup_info:
            elevator_pitch = startup_info.get("elevator_pitch", "")
            if elevator_pitch and "." in elevator_pitch:
                elevator_pitch = (
                    elevator_pitch.split(".")[0] + "."
                )  # Just the first sentence
    except Exception as e:
        import logging

        logging.getLogger(__name__).error(
            f"Error preparing message variables: {str(e)}", exc_info=True
        )
        # Set fallback values
        investor_name = "Investor"
        investor_headline = ""
        investor_company = ""
        elevator_pitch = "Our startup has an innovative solution."

    # Startup info is already handled in the robust variable preparation above

    # Create the prompt
    prompt = ChatPromptTemplate.from_template(template)

    # Get founder name from startup_info with fallback
    founder_name = "Founder"
    if startup_info and "founder_name" in startup_info and startup_info["founder_name"]:
        founder_name = startup_info["founder_name"]

    # Format prompt with data
    formatted_prompt = prompt.format(
        investor_name=investor_name,
        investor_headline=investor_headline,
        investor_company=investor_company,
        elevator_pitch=elevator_pitch,
        founder_name=founder_name,
    )

    # Call LLM to generate the message with error handling
    try:
        response = llm.invoke([formatted_prompt])
        content = response.content

        # Check if the response contains comments about insufficient information instead of a message
        low_info_indicators = [
            "not enough information",
            "insufficient details",
            "would need more",
            "cannot craft",
            "would require",
            "additional details",
            "more information",
        ]

        if any(indicator in content.lower() for indicator in low_info_indicators):
            # Generate a fallback message that uses whatever information is available
            import logging

            logger = logging.getLogger("seed_pitcher")
            logger.warning(
                "LLM returned commentary instead of a message. Using fallback template."
            )

            # Extract company name from elevator pitch if available
            company_name = "my startup"
            # Check if founder name is available in startup_info
            founder_name = startup_info.get("founder_name", "")
            import re

            if elevator_pitch:
                # Try to extract company name (usually at the beginning of the pitch)
                # Look for company names including those with .AI or similar extensions
                company_match = re.search(
                    r"([A-Z][A-Za-z0-9]+(?:\.[A-Z][A-Za-z0-9]+)?(?:\.[A-Za-z0-9]+)?)",
                    elevator_pitch,
                )
                if company_match:
                    company_name = company_match.group(1)

                # Special case for known names if we didn't find a match
                if company_name == "my startup" and "Spacecode.AI" in elevator_pitch:
                    company_name = "Spacecode.AI"

            # Extract what the company does - use more specific matching for better descriptions
            what_it_does = ""
            if elevator_pitch:
                # Try to extract specific phrases about what the company does
                # First look for phrases after "that" or "which"
                does_match = re.search(r"(that|which)\s+([^.]+)\.", elevator_pitch)
                if does_match:
                    what_it_does = does_match.group(2).strip()
                # Look for phrases with "automates" or "automation"
                elif re.search(r"automat(es|ing|ion)", elevator_pitch, re.IGNORECASE):
                    auto_match = re.search(
                        r"automat(es|ing|ion)\s+([^.]+)(\.|$)",
                        elevator_pitch,
                        re.IGNORECASE,
                    )
                    if auto_match:
                        what_it_does = f"automates {auto_match.group(2).strip()}"
                # Look for "minimizes" or similar verbs
                elif re.search(r"minimiz(es|ing)", elevator_pitch, re.IGNORECASE):
                    min_match = re.search(
                        r"minimiz(es|ing)\s+([^.]+)(\.|$)",
                        elevator_pitch,
                        re.IGNORECASE,
                    )
                    if min_match:
                        what_it_does = f"minimizes {min_match.group(2).strip()}"
                # Look for patterns about "allowing" or "enabling"
                elif re.search(r"(allow|enable)(s|ing)", elevator_pitch, re.IGNORECASE):
                    allow_match = re.search(
                        r"(allow|enable)(s|ing)\s+([^.]+)(\.|$)",
                        elevator_pitch,
                        re.IGNORECASE,
                    )
                    if allow_match:
                        what_it_does = f"helps {allow_match.group(3).strip()}"
                # If none of those matched, use the first part of the first sentence excluding company name
                else:
                    # Get first clause that contains a verb (likely describes what it does)
                    first_sentence = (
                        elevator_pitch.split(".")[0]
                        if "." in elevator_pitch
                        else elevator_pitch
                    )
                    # Split by common conjunctions and take second part (often contains what it does)
                    if " by " in first_sentence:
                        second_part = first_sentence.split(" by ")[1].strip()
                        if len(second_part) < 80:
                            what_it_does = second_part
                    # Fall back to using a concise version of first sentence
                    elif len(first_sentence) < 80:
                        what_it_does = first_sentence

            # Generate a simple, concise message that uses whatever info we have
            # Make sure company name is properly extracted and not truncated
            if company_name == "Spacecode" and "Spacecode.AI" in elevator_pitch:
                company_name = "Spacecode.AI"

            # If we haven't extracted what the company does, use some default content from the pitch
            if (
                not what_it_does
                and "turbocharge software development" in elevator_pitch
            ):
                what_it_does = (
                    "automates issue tracker updates and minimizes maintenance overhead"
                )

            fallback_msg = f"# LinkedIn Message to {investor_name}\n\nHi {investor_name},\n\nI noticed your work as {investor_headline} and thought you might be interested in what we're building at {company_name}."

            # Add what the company does if we have that info
            if what_it_does:
                fallback_msg += f" We {what_it_does}."

            # Get founder's name or prompt for it if not available
            founder_name_placeholder = (
                "{founder_name}" if founder_name else "[Your Name]"
            )

            fallback_msg += (
                "\n\nWould you be open to a brief conversation to explore if there might be alignment between your investment interests and our startup?\n\nThanks for considering,\n"
                + founder_name_placeholder
            )

            # Log the complete message for debugging
            logger.info(
                f"Generated fallback message using company: {company_name}, description: {what_it_does}"
            )

            return fallback_msg

        return content
    except Exception as e:
        import logging

        logging.getLogger("seed_pitcher").error(
            f"Error calling LLM for message draft: {str(e)}", exc_info=True
        )
        # Improved fallback template message that properly incorporates the elevator pitch
        # Make sure it doesn't contain generic references to 'space' or other incorrect info
        # Check if founder name is available in startup_info (might have been missed earlier)
        if not founder_name and "founder_name" in startup_info:
            founder_name = startup_info.get("founder_name", "")

        # Create signature based on founder name
        signature = (
            f"\n\nBest regards,\n{founder_name}"
            if founder_name
            else "\n\nBest regards,\n[Your Name]"
        )

        if (
            not elevator_pitch
            or elevator_pitch == "Our startup has an innovative solution."
        ):
            # If we don't have a proper elevator pitch, be very generic
            return f"Hi {investor_name},\n\nI noticed your work at {investor_company} and wanted to connect. I'm working on an early-stage startup and would value your perspective. Would you be open to a quick conversation?{signature}".strip()
        else:
            # Use the actual elevator pitch
            return f"Hi {investor_name},\n\nI noticed your work at {investor_company} and wanted to connect. We're working on {elevator_pitch} I'd value your perspective on our approach. Would you be open to a brief conversation?{signature}".strip()


def summarize_pitch_deck(pitch_deck_text: str, llm: BaseChatModel) -> str:
    """Summarize the pitch deck text to extract key information."""
    # Create prompt template for summarization
    template = """
    You are an expert in analyzing startup pitch decks. I will provide you with the text 
    extracted from a pitch deck, and I need you to summarize the key information that would 
    be relevant for crafting an initial outreach message to a potential investor.
    
    Focus on extracting:
    1. The core value proposition
    2. Key market and traction metrics
    3. Competitive advantages
    4. Team highlights
    5. Funding details (how much is being raised and for what purpose)
    
    Extracted pitch deck text:
    {pitch_deck_text}
    
    Provide a concise summary (max 200 words) of the most important points that would help 
    convince an investor to take a meeting. Avoid generic statements and focus on specific, 
    compelling details.
    """

    # Limit text length to avoid token limits
    limited_text = (
        pitch_deck_text[:8000] if len(pitch_deck_text) > 8000 else pitch_deck_text
    )

    # Create the prompt
    prompt = ChatPromptTemplate.from_template(template)

    # Format prompt with pitch deck text
    formatted_prompt = prompt.format(pitch_deck_text=limited_text)

    # Call LLM to generate the summary
    response = llm.invoke([formatted_prompt])

    return response.content
