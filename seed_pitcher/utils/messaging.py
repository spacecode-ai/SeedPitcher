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

    # Extract investor information
    investor_name = profile.get("name", "Investor") if profile else "Investor"
    investor_headline = profile.get("headline", "") if profile else ""

    # Determine investor company
    investor_company = ""
    if profile:
        if profile.get("company"):
            investor_company = profile.get("company")
        elif profile.get("fund"):
            investor_company = profile.get("fund")
        elif profile.get("experience") and len(profile.get("experience")) > 0:
            investor_company = profile["experience"][0].get("company", "")

    # Use fund_name from analysis if no company found
    if not investor_company and analysis:
        investor_company = analysis.get("fund_name", "")

    # Get elevator pitch
    elevator_pitch = startup_info.get("elevator_pitch", "") if startup_info else ""

    # Get founder name
    founder_name = startup_info.get("founder_name", "Founder") if startup_info else "Founder"

    # Create and format the prompt
    prompt = ChatPromptTemplate.from_template(template)
    formatted_prompt = prompt.format(
        investor_name=investor_name,
        investor_headline=investor_headline,
        investor_company=investor_company,
        elevator_pitch=elevator_pitch,
        founder_name=founder_name,
    )

    # Call LLM to generate the message - let errors propagate
    response = llm.invoke([formatted_prompt])
    return response.content


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
