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
    You are an expert in crafting effective fundraising messages for startups to send to potential investors.
    Your task is to draft a personalized LinkedIn message from a startup founder to a potential investor.
    
    ### Investor Information:
    - Name: {investor_name}
    - Current position: {investor_headline}
    - Fund/Company: {investor_company}
    - Investment focus: {investment_focus}
    - Recent investments: {recent_investments}
    
    ### Startup Information:
    - Elevator pitch: {elevator_pitch}
    - Additional details from pitch deck: {pitch_deck_summary}
    
    Draft a personalized, concise LinkedIn message (max 300 words) to this investor that:
    1. Establishes a personal connection if possible
    2. Briefly introduces the startup and its value proposition
    3. Explains why this specific investor would be interested (based on their investment focus)
    4. Mentions recent investments they've made only if relevant
    5. Requests a brief call or meeting to discuss further
    6. Maintains a professional but conversational tone
    7. Avoids generic phrases that could apply to any investor
    
    IMPORTANT GUIDELINES:
    - Keep it brief and to the point
    - Personalize for this specific investor
    - Focus on value proposition, not just features
    - Don't oversell or use hyperbole
    - Be respectful of their time
    - Don't attach any files or suggest sharing documents yet
    
    The message should feel like it was written specifically for this investor, not a template.
    """

    # Format variables for the prompt
    investor_name = profile.get("name", "")
    investor_headline = profile.get("headline", "")
    investor_company = profile.get("company", "") or analysis.get("fund_name", "")
    investment_focus = ", ".join(analysis.get("investment_focus", []))

    # Format recent investments
    recent_investments = ", ".join(
        analysis.get("web_info", {}).get("recent_investments", [])[:3]
    )

    # Get startup info
    elevator_pitch = startup_info.get("elevator_pitch", "")

    # Create a summary of the pitch deck if available
    pitch_deck_text = startup_info.get("pitch_deck_text", "")
    pitch_deck_summary = (
        summarize_pitch_deck(pitch_deck_text, llm) if pitch_deck_text else ""
    )

    # Create the prompt
    prompt = ChatPromptTemplate.from_template(template)

    # Format prompt with data
    formatted_prompt = prompt.format(
        investor_name=investor_name,
        investor_headline=investor_headline,
        investor_company=investor_company,
        investment_focus=investment_focus,
        recent_investments=recent_investments,
        elevator_pitch=elevator_pitch,
        pitch_deck_summary=pitch_deck_summary,
    )

    # Call LLM to generate the message
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
