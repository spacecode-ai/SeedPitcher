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

                        # Display the message draft to the user
                        console.print(
                            "\n[bold green]===== Message Draft =====[/bold green]"
                        )
                        console.print(result["message_draft"])
                        console.print(
                            "[bold green]=======================[/bold green]\n"
                        )

                        # Ask for confirmation or edits
                        action = Prompt.ask(
                            "[bold]Would you like to[/bold]",
                            choices=["send", "edit", "skip"],
                            default="edit",
                        )

                        if action == "edit":
                            # Allow the user to edit the message
                            console.print("[yellow]Edit the message below:[/yellow]")
                            edited_message = Prompt.ask(
                                "Message", default=result["message_draft"]
                            )
                            result["message_draft"] = edited_message
                            console.print("[green]Message updated![/green]")

                            # Ask again after editing
                            action = Prompt.ask(
                                "[bold]Would you like to[/bold]",
                                choices=["send", "skip"],
                                default="send",
                            )

                        if action == "send":
                            # Use the LinkedIn handler to automatically send the message
                            console.print(
                                "[bold blue]Sending message via LinkedIn...[/bold blue]"
                            )

                            # Check for previous messages first
                            from seed_pitcher.utils.linkedin import LinkedInHandler
                            from seed_pitcher.browsers import get_browser

                            # Ensure browser is initialized
                            if not state.get("browser"):
                                logger.info("Initializing browser for messaging")
                                state["browser"] = get_browser()

                            linkedin_handler = LinkedInHandler(state["browser"])

                            # Get previous messages with this investor (if any)
                            previous_messages = linkedin_handler.get_previous_messages(
                                url
                            )
                            if previous_messages:
                                console.print(
                                    f"[yellow]Found {len(previous_messages)} previous message(s) with this contact[/yellow]"
                                )

                                # Log previous messages for context
                                logger.info(
                                    f"Previous messages with {url}: {previous_messages}"
                                )

                                # Confirm before sending another message
                                confirm = Prompt.ask(
                                    "[bold]You have previous messages with this contact. Still send new message?[/bold]",
                                    choices=["yes", "no"],
                                    default="yes",
                                )

                                if confirm.lower() != "yes":
                                    console.print(
                                        "[yellow]Message sending canceled[/yellow]"
                                    )
                                    continue

                            # Ask for the founder's name to replace placeholder if needed
                            message_content = result["message_draft"]

                            if "[Founder's Name]" in message_content:
                                # Get founder name if not already in state
                                if not state.get("founder_name"):
                                    state["founder_name"] = Prompt.ask(
                                        "[bold]Please enter your name as it should appear in the message[/bold]",
                                        default="Founder",
                                    )

                                # Replace placeholder with actual name
                                message_content = message_content.replace(
                                    "[Founder's Name]", state["founder_name"]
                                )
                                console.print(
                                    f"[blue]Updated message with your name: {state['founder_name']}[/blue]"
                                )

                            # Display final message for confirmation
                            console.print("\n[bold]Final message to be sent:[/bold]\n")
                            console.print(f"[green]{message_content}[/green]\n")

                            confirm_send = Prompt.ask(
                                "[bold]Send this message?[/bold]",
                                choices=["yes", "no"],
                                default="yes",
                            )

                            if confirm_send.lower() != "yes":
                                console.print(
                                    "[yellow]Message sending canceled[/yellow]"
                                )
                                continue

                            # Send the message automatically
                            with console.status(
                                "[bold green]Sending message...[/bold green]"
                            ) as status:
                                success = linkedin_handler.send_message(
                                    url, message_content
                                )

                            if success:
                                console.print(
                                    "[green]✓ Message sent successfully![/green]"
                                )
                                # Update history to reflect that message was sent
                                result["message_sent"] = True
                            else:
                                console.print(
                                    "[red]✗ Failed to send message automatically[/red]"
                                )

                                # Fallback to manual sending if automated attempt fails
                                console.print(
                                    "[yellow]Falling back to manual sending...[/yellow]"
                                )

                                # Copy message to clipboard for easy pasting
                                try:
                                    import pyperclip

                                    pyperclip.copy(result["message_draft"])
                                    console.print(
                                        "[green]✓ Message copied to clipboard[/green]"
                                    )
                                except ImportError:
                                    console.print(
                                        "[yellow]Could not copy to clipboard - pyperclip package not installed[/yellow]"
                                    )

                                console.print(
                                    "\n[bold]Instructions for manual sending:[/bold]"
                                )
                                console.print(
                                    "1. Navigate to the LinkedIn profile in your browser"
                                )
                                console.print(
                                    "2. Click the 'Message' button on their profile"
                                )
                                console.print(
                                    "3. Paste the message in the text box (Ctrl+V / Cmd+V)"
                                )
                                console.print("4. Review and click 'Send' when ready\n")

                                proceed = Prompt.ask(
                                    "Press Enter when you've sent the message or type 'skip' to skip",
                                    default="",
                                )
                                if proceed.lower() != "skip":
                                    console.print(
                                        "[green]✓ Message sent successfully![/green]"
                                    )
                                    # Update history to reflect that message was sent
                                    result["message_sent"] = True
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

                        # Display message draft if available
                        if "message_draft" in result and result["message_draft"]:
                            console.print(
                                "\n[bold green]===== Message Draft =====[/bold green]"
                            )
                            console.print(result["message_draft"])
                            console.print(
                                "[bold green]=======================[/bold green]\n"
                            )

                            # Ask for confirmation or edits
                            action = Prompt.ask(
                                "[bold]Would you like to[/bold]",
                                choices=["send", "edit", "skip"],
                                default="edit",
                            )

                            if action == "edit":
                                # Allow the user to edit the message
                                console.print(
                                    "[yellow]Edit the message below:[/yellow]"
                                )
                                edited_message = Prompt.ask(
                                    "Message", default=result["message_draft"]
                                )
                                result["message_draft"] = edited_message
                                console.print("[green]Message updated![/green]")

                                # Ask again after editing
                                action = Prompt.ask(
                                    "[bold]Would you like to[/bold]",
                                    choices=["send", "skip"],
                                    default="send",
                                )

                            if action == "send":
                                # Use the LinkedIn handler to automatically send the message
                                console.print(
                                    "[bold blue]Sending message via LinkedIn...[/bold blue]"
                                )

                                # Check for previous messages first
                                from seed_pitcher.utils.linkedin import LinkedInHandler
                                from seed_pitcher.browsers import get_browser

                                # Ensure browser is initialized
                                if not state.get("browser"):
                                    logger.info("Initializing browser for messaging")
                                    state["browser"] = get_browser()

                                linkedin_handler = LinkedInHandler(state["browser"])

                                # Get previous messages with this investor (if any)
                                previous_messages = (
                                    linkedin_handler.get_previous_messages(url)
                                )
                                if previous_messages:
                                    console.print(
                                        f"[yellow]Found {len(previous_messages)} previous message(s) with this contact[/yellow]"
                                    )

                                    # Log previous messages for context
                                    logger.info(
                                        f"Previous messages with {url}: {previous_messages}"
                                    )

                                    # Confirm before sending another message
                                    confirm = Prompt.ask(
                                        "[bold]You have previous messages with this contact. Still send new message?[/bold]",
                                        choices=["yes", "no"],
                                        default="yes",
                                    )

                                    if confirm.lower() != "yes":
                                        console.print(
                                            "[yellow]Message sending canceled[/yellow]"
                                        )
                                        continue

                                # Send the message automatically
                                with console.status(
                                    "[bold green]Sending message...[/bold green]"
                                ) as status:
                                    success = linkedin_handler.send_message(
                                        url, result["message_draft"]
                                    )

                                if success:
                                    console.print(
                                        "[green]✓ Message sent successfully![/green]"
                                    )
                                    # Update history to reflect that message was sent
                                    result["message_sent"] = True
                                else:
                                    console.print(
                                        "[red]✗ Failed to send message automatically[/red]"
                                    )

                                    # Fallback to manual sending if automated attempt fails
                                    console.print(
                                        "[yellow]Falling back to manual sending...[/yellow]"
                                    )

                                    # Copy message to clipboard for easy pasting
                                    try:
                                        import pyperclip

                                        pyperclip.copy(result["message_draft"])
                                        console.print(
                                            "[green]✓ Message copied to clipboard[/green]"
                                        )
                                    except ImportError:
                                        console.print(
                                            "[yellow]Could not copy to clipboard - pyperclip package not installed[/yellow]"
                                        )

                                    console.print(
                                        "\n[bold]Instructions for manual sending:[/bold]"
                                    )
                                    console.print(
                                        "1. Navigate to the LinkedIn profile in your browser"
                                    )
                                    console.print(
                                        "2. Click the 'Message' button on their profile"
                                    )
                                    console.print(
                                        "3. Paste the message in the text box (Ctrl+V / Cmd+V)"
                                    )
                                    console.print(
                                        "4. Review and click 'Send' when ready\n"
                                    )

                                    proceed = Prompt.ask(
                                        "Press Enter when you've sent the message or type 'skip' to skip",
                                        default="",
                                    )
                                    if proceed.lower() != "skip":
                                        console.print(
                                            "[green]✓ Message sent successfully![/green]"
                                        )
                                        # Update history to reflect that message was sent
                                        result["message_sent"] = True
                    else:
                        logger.info(
                            f"Investor {url} scored below threshold: {result.get('investor_score', 0)}"
                        )
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
                logger.info(f"Finished processing URL: {url}")


if __name__ == "__main__":
    app()
