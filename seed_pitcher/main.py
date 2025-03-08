import os
import json
import logging
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich import print as rprint

# Import config module
from seed_pitcher import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("seed_pitcher.log")],
)
logger = logging.getLogger("seed_pitcher")

app = typer.Typer(name="seedpitcher")
console = Console()


@app.callback()
def callback():
    """
    SeedPitcher: An agentic system to assist with seed fundraising for early-stage startups.
    """
    pass


@app.command()
def run(
    pitch_deck: Optional[Path] = typer.Option(
        None, "--pitch-deck", "-p", help="Path to PDF pitch deck"
    ),
    linkedin_urls: Optional[List[str]] = typer.Option(
        None,
        "--linkedin-urls",
        "-l",
        help="List of specific LinkedIn profile URLs to analyze",
    ),
    threshold: float = typer.Option(
        0.5, "--threshold", "-t", help="Threshold score for investor relevance (0-1)"
    ),
    llm_model: str = typer.Option(
        "auto",
        "--llm-model",
        "-m",
        help="LLM model to use (auto, claude-3-7-sonnet, gpt-4o, deepseek-r1). Auto selects Claude if ANTHROPIC_API_KEY is available.",
    ),
):
    """
    Run the SeedPitcher agent to help with seed fundraising.
    """
    # Import here to avoid circular imports
    from seed_pitcher.agents.graph import create_agent_graph
    from seed_pitcher.utils.pdf import extract_text_from_pdf
    import seed_pitcher.config as config

    # Load or create config
    config_file = Path.home() / ".seed_pitcher" / "config.json"
    if config_file.exists():
        with open(config_file, "r") as f:
            user_config = json.load(f)
    else:
        user_config = {}
        config_file.parent.mkdir(exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(user_config, f)

    config.update_config(user_config)
    config.INVESTOR_THRESHOLD = threshold

    # Set the LLM model, with special handling for auto mode
    if llm_model.lower() == "auto":
        # In auto mode, use Claude if ANTHROPIC_API_KEY is available, otherwise use GPT-4o
        if config.ANTHROPIC_API_KEY:
            config.LLM_MODEL = "claude-3-7-sonnet-20250219"
            console.print(
                "[green]Using Claude 3.7 Sonnet (ANTHROPIC_API_KEY detected)[/green]"
            )
        else:
            config.LLM_MODEL = "gpt-4o"
            console.print(
                "[yellow]Using GPT-4o (ANTHROPIC_API_KEY not detected)[/yellow]"
            )
    else:
        # User explicitly specified a model
        config.LLM_MODEL = llm_model

        # Check if the API key is available for the requested model
        if llm_model.startswith("claude") and not config.ANTHROPIC_API_KEY:
            console.print(
                "[bold red]Warning: Claude model requested but ANTHROPIC_API_KEY not found. Will fallback to GPT-4o.[/bold red]"
            )
        elif llm_model.startswith("gpt") and not config.OPENAI_API_KEY:
            console.print(
                "[bold red]Warning: OpenAI model requested but OPENAI_API_KEY not found.[/bold red]"
            )

    # Get elevator pitch
    console.print("[bold green]Welcome to SeedPitcher![/bold green]")
    console.print("Let's get started with your startup details.\n")

    elevator_pitch = Prompt.ask(
        "[bold]Please provide your startup elevator pitch[/bold]\n"
        "This should be a concise description of your startup, problem, solution, and target market"
    )

    pitch_deck_text = ""
    if pitch_deck:
        with console.status(
            "[bold green]Extracting text from pitch deck...[/bold green]"
        ):
            pitch_deck_text = extract_text_from_pdf(pitch_deck)
        console.print("[green]✓[/green] Pitch deck processed successfully!")

    # Initialize the agent
    with console.status("[bold green]Initializing SeedPitcher agent...[/bold green]"):
        agent = create_agent_graph(elevator_pitch, pitch_deck_text)

    # Run the agent in interactive mode
    run_interactive_mode(agent, linkedin_urls)


def run_interactive_mode(agent, linkedin_urls=None):
    """Run the agent in interactive mode with the user."""
    console.print("\n[bold]SeedPitcher is ready![/bold]")

    # Import browser management and config
    from seed_pitcher.browsers import get_browser
    from seed_pitcher import config
    import logging

    logger = logging.getLogger("seed_pitcher")

    # Get the initial state from the graph
    if hasattr(agent, "initial_state"):
        initial_state = agent.initial_state
    else:
        # Fallback in case the graph doesn't have initial_state attribute
        initial_state = {
            "action": "initialize",
            "startup_info": {},
            "current_profile": {},
            "investor_score": 0.0,
            "investor_analysis": {},
            "message_draft": "",
            "history": [],
            "urls_to_process": [],
            "browser": None,
        }

    # Initialize browser once at the beginning to avoid multiple browser instances
    try:
        if initial_state["browser"] is None:
            logger.info("Initializing browser for LinkedIn profile analysis")
            initial_state["browser"] = get_browser()
            logger.info(f"Browser initialized successfully: {initial_state['browser']}")
    except Exception as e:
        logger.error(f"Error initializing browser: {str(e)}", exc_info=True)

    if linkedin_urls:
        logger.info(f"Processing {len(linkedin_urls)} provided LinkedIn profiles...")
        console.print(f"Processing {len(linkedin_urls)} provided LinkedIn profiles...")

        for url in linkedin_urls:
            # Start with a completely fresh state for each URL
            state = {
                "action": "analyze_profile",
                "startup_info": initial_state["startup_info"],
                "current_profile": {},
                "investor_score": 0.0,
                "investor_analysis": {},
                "message_draft": "",
                "history": initial_state.get(
                    "history", []
                ).copy(),  # Copy to avoid shared reference
                "urls_to_process": [],  # Clear previous URLs
                "browser": initial_state[
                    "browser"
                ],  # Use the already initialized browser
                "url": url,  # Directly set the URL to analyze
            }

            # Double-check browser is initialized
            if not state["browser"]:
                from seed_pitcher.browsers import get_browser

                state["browser"] = get_browser()
                logger.info(f"Initialized browser for processing")

            # Log the exact state being passed to the agent
            logger.info(f"Starting analysis of profile: {url}")
            logger.info(f"State keys being passed to agent: {list(state.keys())}")
            logger.info(f"URL in state: {state['url']}")

            # Run the agent with this state - use a specific recursion limit to avoid infinite loops
            try:
                from langchain_core.runnables.config import RunnableConfig

                # Create a config with a higher recursion limit
                config = RunnableConfig(configurable={"recursion_limit": 30})

                # Invoke with the config
                result = agent.invoke(state, config)

                logger.info(f"Analysis completed for URL: {url}")
                investor_found = bool(
                    result.get("investor_analysis")
                    and result.get("investor_analysis").get("is_investor")
                )
                logger.info(
                    f"Analysis result: action={result.get('action')}, found investor={investor_found}"
                )

                if investor_found:
                    logger.info(f"Investor score: {result.get('investor_score', 0)}")
                    if "message_draft" in result and result["message_draft"]:
                        logger.info("Message draft created successfully")
            except Exception as e:
                logger.error(
                    f"Error analyzing LinkedIn profile {url}: {str(e)}", exc_info=True
                )
    else:
        console.print("\nHow would you like to find investors?")
        console.print("1. Browse through your LinkedIn connections")
        console.print("2. Search for specific profiles on LinkedIn")
        console.print("3. Enter specific LinkedIn profile URLs\n")

        choice = Prompt.ask("Select an option", choices=["1", "2", "3"], default="1")

        if choice == "1":
            state = dict(initial_state)
            state["action"] = "browse_connections"
            agent.invoke(state)
        elif choice == "2":
            search_query = Prompt.ask("Enter your LinkedIn search query")
            state = dict(initial_state)
            state["action"] = "search_profiles"
            state["query"] = search_query
            agent.invoke(state)
        elif choice == "3":
            urls = []
            while True:
                url = Prompt.ask(
                    "Enter a LinkedIn profile URL (or press Enter to finish)"
                )
                if not url:
                    break
                urls.append(url)
            logger.info(f"Processing {len(urls)} LinkedIn URLs: {urls}")
            for i, url in enumerate(urls):
                logger.info(f"Processing URL {i + 1}/{len(urls)}: {url}")

                # Create a fresh state for each profile
                state = dict(initial_state)

                # Add the current URL to process and also to urls_to_process as a fallback
                state["action"] = "analyze_profile"
                state["url"] = url
                state["urls_to_process"] = [
                    url
                ]  # Add to urls_to_process for redundancy

                try:
                    logger.info(f"Invoking agent for URL: {url}")
                    result = agent.invoke(state)

                    # Log detailed information about the result
                    logger.info(f"Agent processing completed for URL: {url}")
                    if result.get("investor_score", 0) >= config.INVESTOR_THRESHOLD:
                        logger.info(
                            f"Investor {url} scored above threshold: {result.get('investor_score', 0)}"
                        )
                    else:
                        logger.info(
                            f"Investor {url} scored below threshold: {result.get('investor_score', 0)}"
                        )
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
                logger.info(f"Finished processing URL: {url}")


if __name__ == "__main__":
    app()
