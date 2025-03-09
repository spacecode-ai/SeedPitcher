"""LangGraph implementation for SeedPitcher."""

import os
from typing import Dict, Any, List, Annotated, TypedDict, Literal
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

import seed_pitcher.config as config


class AgentState(TypedDict):
    """State for the SeedPitcher agent."""

    action: str
    startup_info: Dict[str, str]
    current_profile: Dict[str, Any]
    investor_score: float
    investor_analysis: Dict[str, Any]
    message_draft: str
    history: List[Dict[str, Any]]
    urls_to_process: List[str]
    browser: Any
    query: str


def create_browser():
    """Create browser instance based on configuration."""
    if config.BROWSER_TYPE == "simular":
        try:
            from seed_pitcher.browsers.simular import SimularBrowser

            return SimularBrowser()
        except ImportError:
            print("Simular.ai browser not available, falling back to Playwright")
            from seed_pitcher.browsers.playwright import PlaywrightBrowser

            return PlaywrightBrowser()
    else:
        from seed_pitcher.browsers.playwright import PlaywrightBrowser

        return PlaywrightBrowser()


def create_llm():
    """Create LLM based on configuration."""
    # Prioritize Claude if ANTHROPIC_API_KEY is available
    if config.ANTHROPIC_API_KEY and (
        config.LLM_MODEL.startswith("claude") or config.LLM_MODEL == "auto"
    ):
        return ChatAnthropic(
            model="claude-3-7-sonnet-20250219", api_key=config.ANTHROPIC_API_KEY
        )
    # Fallback to OpenAI if specified or if Claude is specified but no API key is available
    elif config.LLM_MODEL.startswith("gpt") or not config.ANTHROPIC_API_KEY:
        return ChatOpenAI(
            model=config.LLM_MODEL if config.LLM_MODEL.startswith("gpt") else "gpt-4o",
            api_key=config.OPENAI_API_KEY,
        )
    elif config.LLM_MODEL.startswith("deepseek") and config.DEEPSEEK_API_KEY:
        # Would implement DeepSeek integration here if API key is available
        # For now, default to OpenAI
        return ChatOpenAI(model="gpt-4o", api_key=config.OPENAI_API_KEY)
    else:
        # Default fallback to OpenAI
        return ChatOpenAI(model="gpt-4o", api_key=config.OPENAI_API_KEY)


def initialize_state(elevator_pitch: str, pitch_deck_text: str) -> AgentState:
    """Initialize agent state."""
    return {
        "action": "initialize",
        "startup_info": {
            "elevator_pitch": elevator_pitch,
            "pitch_deck_text": pitch_deck_text,
        },
        "current_profile": {},
        "investor_score": 0.0,
        "investor_analysis": {},
        "message_draft": "",
        "history": [],
        "urls_to_process": [],
        "browser": create_browser(),
    }


def browse_connections(state: AgentState) -> AgentState:
    """Browse through LinkedIn connections."""
    from seed_pitcher.utils.linkedin import LinkedInHandler

    linkedin = LinkedInHandler(state["browser"])
    linkedin.go_to_connections_page()
    profiles = linkedin.extract_connections()

    state["urls_to_process"] = profiles
    state["action"] = "analyze_profile"
    return state


def search_profiles(state: AgentState) -> AgentState:
    """Search for specific profiles on LinkedIn."""
    from seed_pitcher.utils.linkedin import LinkedInHandler

    query = state.get("query")
    linkedin = LinkedInHandler(state["browser"])
    print(f'query is {query}')
    profiles = linkedin.search_profiles(query)

    state["urls_to_process"] = profiles
    state["action"] = "analyze_profile"
    return state


def analyze_profile(state: AgentState) -> AgentState:
    """Analyze a LinkedIn profile."""
    import logging

    logger = logging.getLogger("seed_pitcher")
    logger.info("Starting analyze_profile function")

    from seed_pitcher.utils.linkedin import LinkedInHandler
    from seed_pitcher.utils.investor import analyze_investor_profile, score_investor
    from seed_pitcher.utils.web_search import search_investor_info

    # Detailed state inspection for debugging
    logger.info(f"State keys available: {list(state.keys())}")
    for key in ["url", "action", "current_profile"]:
        if key in state:
            logger.info(f"State[{key}] = {state[key]}")

    # Try several ways to get the URL
    url = None

    # Method 1: Direct URL in state
    if "url" in state and state["url"]:
        url = state["url"]
        logger.info(f"Found URL directly in state: {url}")

    # Fallback to urls_to_process if available
    if not url and state["urls_to_process"]:
        url = state["urls_to_process"].pop(0)
        logger.info(f"No direct URL provided, using URL from queue: {url}")

    if not url:
        logger.info("No URL available for analysis, ending process")
        state["action"] = "end"
        return state

    logger.info(f"Initializing LinkedIn handler with browser: {state['browser']}")
    try:
        linkedin = LinkedInHandler(state["browser"])
        logger.info(f"Starting profile extraction for: {url}")
        profile_data = linkedin.extract_profile(url)

        # Check if extraction failed (profile_data is None or has an error)
        if profile_data is None:
            logger.error(f"Profile extraction failed: returned None")
            # Move to the next URL if available, otherwise end
            if state["urls_to_process"]:
                state["action"] = "analyze_profile"
            else:
                state["action"] = "end"
            return state

        # Check if there was an error in profile extraction
        if isinstance(profile_data, dict) and "error" in profile_data:
            logger.error(f"Profile extraction failed: {profile_data['error']}")
            # Move to the next URL if available, otherwise end
            if state["urls_to_process"]:
                state["action"] = "analyze_profile"
            else:
                state["action"] = "end"
            return state

        logger.info(
            f"Profile extracted successfully: {profile_data.get('name', 'Unknown')}"
        )
        state["current_profile"] = profile_data
    except Exception as e:
        logger.error(f"Error extracting profile data: {str(e)}", exc_info=True)
        # If there's an error, try to continue with next profile
        if state["urls_to_process"]:
            state["action"] = "analyze_profile"
        else:
            state["action"] = "end"
        return state

    # Analyze if the profile is an investor
    logger.info("Creating LLM for investor analysis")
    try:
        llm = create_llm()
        logger.info("Starting investor profile analysis")
        analysis = analyze_investor_profile(profile_data, llm)
        logger.info(
            f"Investor analysis complete: is_investor={analysis.get('is_investor', False)}"
        )
        state["investor_analysis"] = analysis
    except Exception as e:
        logger.error(f"Error in investor analysis: {str(e)}", exc_info=True)
        # If there's an error, try to continue with next profile
        if state["urls_to_process"]:
            state["action"] = "analyze_profile"
        else:
            state["action"] = "end"
        return state

    # If they appear to be an investor, search for more info
    if analysis.get("is_investor", False):
        logger.info(
            f"Profile is an investor, searching for additional web info for: {profile_data['name']}"
        )
        try:
            investor_info = search_investor_info(
                profile_data["name"],
                profile_data.get("company", ""),
                profile_data.get("fund", ""),
            )
            logger.info("Web search for investor info completed")
            state["investor_analysis"]["web_info"] = investor_info

            # Score the investor
            logger.info("Scoring investor relevance")
            score = score_investor(
                analysis, investor_info, state["startup_info"]["elevator_pitch"]
            )
            logger.info(
                f"Investor score: {score}, threshold: {config.INVESTOR_THRESHOLD}"
            )
            state["investor_score"] = score

            if score >= config.INVESTOR_THRESHOLD:
                logger.info(
                    f"Investor score {score} meets threshold {config.INVESTOR_THRESHOLD}, offering message draft"
                )
                state["action"] = "offer_message_draft"
            else:
                logger.info(
                    f"Investor score {score} below threshold {config.INVESTOR_THRESHOLD}, skipping"
                )
                # Move to next profile
                if state["urls_to_process"]:
                    logger.info("More URLs in queue, continuing to next profile")
                    state["action"] = "analyze_profile"
                else:
                    logger.info("No more URLs to process, ending")
                    state["action"] = "end"
        except Exception as e:
            logger.error(f"Error in web search or scoring: {str(e)}", exc_info=True)
            if state["urls_to_process"]:
                state["action"] = "analyze_profile"
            else:
                state["action"] = "end"
    else:
        logger.info("Profile is not an investor, skipping")
        # Not an investor, move to next profile
        if state["urls_to_process"]:
            logger.info("More URLs in queue, continuing to next profile")
            state["action"] = "analyze_profile"
        else:
            logger.info("No more URLs to process, ending")
            state["action"] = "end"

    # Add to history
    logger.info("Adding profile analysis to history")
    try:
        state["history"].append(
            {
                "profile": profile_data,
                "analysis": analysis,
                "score": state.get("investor_score", 0),
            }
        )
        logger.info("Successfully added to history")
    except Exception as e:
        logger.error(f"Error adding to history: {str(e)}", exc_info=True)

    # Critical: Clear URL from state to prevent infinite recursion
    if "url" in state:
        logger.info("Clearing URL from state to avoid recursion")
        state.pop("url")

    logger.info(f"Analyze profile completed. Next action: {state['action']}")
    return state


def offer_message_draft(state: AgentState) -> AgentState:
    """Offer to draft a message to the investor."""
    import logging

    logger = logging.getLogger("seed_pitcher")
    logger.info("Starting offer_message_draft function")

    from seed_pitcher.utils.messaging import draft_investor_message

    try:
        logger.info("Creating LLM for message drafting")
        llm = create_llm()
        logger.info(
            f"Starting to draft message for profile: {state['current_profile'].get('name', 'Unknown')}"
        )

        message = draft_investor_message(
            state["current_profile"],
            state["investor_analysis"],
            state["startup_info"],
            llm,
        )
        logger.info("Message draft created successfully")
        state["message_draft"] = message
    except Exception as e:
        logger.error(f"Error creating message draft: {str(e)}", exc_info=True)
        # Fall back to a generic message if drafting fails
        state["message_draft"] = "[Message drafting failed. Please try again.]"
        logger.info("Set fallback message due to error")

    # Add to history
    try:
        logger.info("Attempting to add message to history")
        if state["history"]:  # Check if history list is not empty
            logger.info("History exists, updating last entry")
            state["history"][-1]["message_draft"] = message
        else:
            # If history is empty, create a new entry
            logger.info("History is empty, creating new entry")
            state["history"].append({"message_draft": message})
        logger.info("Successfully updated history with message draft")
    except Exception as e:
        logger.error(
            f"Error updating history with message draft: {str(e)}", exc_info=True
        )

    # Move to next profile
    if state["urls_to_process"]:
        logger.info("More URLs in queue, continuing to next profile")
        state["action"] = "analyze_profile"
    else:
        logger.info("No more URLs to process, ending")
        state["action"] = "end"

    logger.info(f"offer_message_draft completed. Next action: {state['action']}")
    return state


def router(
    state: AgentState,
) -> Literal[
    "browse_connections",
    "search_profiles",
    "analyze_profile",
    "offer_message_draft",
    END,
]:
    """Route to the appropriate action based on state."""
    import logging

    logger = logging.getLogger("seed_pitcher")

    # Log state details for debugging
    logger.info(f"Router called with state keys: {list(state.keys())}")
    action = state["action"]
    logger.info(f"Router action: {action}")

    if action == "initialize":
        # Default starting action when no specific URLs are provided
        return "browse_connections"
    elif action == "browse_connections":
        return "browse_connections"
    elif action == "search_profiles":
        return "search_profiles"
    elif action == "analyze_profile":
        return "analyze_profile"
    elif action == "offer_message_draft":
        return "offer_message_draft"
    elif action == "end":
        return END  # Use END constant instead of string
    else:
        return END  # Use END constant instead of string


def create_agent_graph(elevator_pitch: str, pitch_deck_text: str = ""):
    """Create the LangGraph agent for SeedPitcher."""
    # Define the state graph with our AgentState type
    workflow = StateGraph(AgentState)

    # Add all nodes first
    workflow.add_node("entry_point", lambda state: state)
    workflow.add_node("browse_connections", browse_connections)
    workflow.add_node("search_profiles", search_profiles)
    workflow.add_node("analyze_profile", analyze_profile)
    workflow.add_node("offer_message_draft", offer_message_draft)

    # Set entry point (must match a node name defined above)
    workflow.set_entry_point("entry_point")

    # Add conditional edges from entry point
    workflow.add_conditional_edges(
        "entry_point",
        lambda state: state["action"] == "initialize"
        and "browse_connections"
        or state["action"] == "browse_connections"
        and "browse_connections"
        or state["action"] == "search_profiles"
        and "search_profiles"
        or state["action"] == "analyze_profile"
        and "analyze_profile"
        or state["action"] == "offer_message_draft"
        and "offer_message_draft"
        or END,
    )

    # Add edges between action nodes
    # Replace direct edges with conditional edges that respect the action state
    # From browse_connections
    workflow.add_conditional_edges("browse_connections", router)

    # From search_profiles
    workflow.add_conditional_edges("search_profiles", router)

    # From analyze_profile - route based on action state
    workflow.add_conditional_edges("analyze_profile", router)

    # From offer_message_draft - route based on action state
    workflow.add_conditional_edges("offer_message_draft", router)

    # Compile the graph first without initial state
    graph = workflow.compile()

    # Initialize state with startup info
    # We'll store this to be used by main.py instead of trying to set it here
    initial_state = initialize_state(elevator_pitch, pitch_deck_text)

    # Store the initial state as an attribute on the graph for convenience
    graph.initial_state = initial_state

    # Return the compiled graph
    return graph
