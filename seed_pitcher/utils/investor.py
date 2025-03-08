"""Investor analysis and scoring utilities."""

from typing import Dict, Any, List
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser


def analyze_investor_profile(
    profile_data: Dict[str, Any], llm: BaseChatModel
) -> Dict[str, Any]:
    """Analyze LinkedIn profile to determine if it's an investor."""
    # Create prompt template
    template = """
    You are an expert in analyzing LinkedIn profiles to identify investors.
    
    Please analyze the following LinkedIn profile information and determine if this person is likely an investor 
    (e.g. venture capitalist, angel investor, investment manager, etc.).
    
    Profile data:
    Name: {name}
    Headline: {headline}
    Current company: {company}
    Location: {location}
    About: {about}
    
    Experience:
    {experience}
    
    Education:
    {education}
    
    Fund name (if any): {fund}
    
    Respond with a JSON object containing the following fields:
    - is_investor: boolean indicating if this person is likely an investor
    - investor_type: string (e.g. "VC", "Angel", "LP", etc.) if is_investor is true
    - confidence: number between 0 and 1 indicating your confidence
    - fund_name: string with the fund name if available
    - investment_focus: list of strings representing investment focus areas (markets, industries, etc.)
    - reasoning: string explaining your analysis
    """

    # Format experience and education for the prompt
    experience_str = ""
    for exp in profile_data.get("experience", []):
        experience_str += f"- {exp.get('title', '')} at {exp.get('company', '')}\n"

    education_str = ""
    for edu in profile_data.get("education", []):
        education_str += f"- {edu.get('degree', '')} at {edu.get('school', '')}\n"

    # Create prompt
    prompt = ChatPromptTemplate.from_template(template)

    # Format prompt with profile data
    formatted_prompt = prompt.format(
        name=profile_data.get("name", ""),
        headline=profile_data.get("headline", ""),
        company=profile_data.get("company", ""),
        location=profile_data.get("location", ""),
        about=profile_data.get("about", ""),
        experience=experience_str,
        education=education_str,
        fund=profile_data.get("fund", ""),
    )

    # Call LLM to analyze the profile
    response = llm.invoke([formatted_prompt])

    # Parse the response
    try:
        parser = JsonOutputParser()
        analysis = parser.parse(response.content)
        return analysis
    except Exception as e:
        # If parsing fails, return a basic analysis
        return {
            "is_investor": False,
            "investor_type": "",
            "confidence": 0.0,
            "fund_name": "",
            "investment_focus": [],
            "reasoning": f"Error parsing response: {str(e)}",
        }


def score_investor(
    analysis: Dict[str, Any], web_info: Dict[str, Any], startup_pitch: str
) -> float:
    """Score an investor based on analysis, web info, and startup pitch."""
    # Base score from investor analysis
    if not analysis.get("is_investor", False):
        return 0.0

    score = analysis.get("confidence", 0.0) * 0.5  # 50% weight from investor confidence

    # Additional scoring from web information
    recent_investments = web_info.get("recent_investments", [])

    # More recent investments = higher score
    num_investments = len(recent_investments)
    if num_investments >= 5:
        score += 0.2  # 20% weight for having 5+ recent investments
    elif num_investments >= 3:
        score += 0.15  # 15% weight for having 3-4 recent investments
    elif num_investments >= 1:
        score += 0.1  # 10% weight for having 1-2 recent investments

    # Check investment stage match
    investment_stages = web_info.get("investment_stages", [])
    if (
        "seed" in " ".join(investment_stages).lower()
        or "early" in " ".join(investment_stages).lower()
    ):
        score += 0.15  # 15% weight for early/seed stage focus

    # Check industry/sector match
    investment_sectors = web_info.get("investment_sectors", [])
    startup_sectors = web_info.get("startup_sectors", [])  # Extracted from pitch

    # Calculate sector overlap
    overlap = set(investment_sectors).intersection(set(startup_sectors))
    if len(overlap) > 0:
        sector_match_score = min(
            len(overlap) / max(len(investment_sectors), 1), 0.15
        )  # Up to 15% weight
        score += sector_match_score

    return min(score, 1.0)  # Cap score at 1.0
