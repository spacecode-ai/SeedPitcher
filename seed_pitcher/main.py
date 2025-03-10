import os
import sys
import json
import logging
import subprocess
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

# Create a browser server command group
browser_server = typer.Typer(name="browser-server", help="Manage the browser server")
app.add_typer(browser_server)


@app.callback()
def callback():
    """
    SeedPitcher: An agentic system to assist with seed fundraising for early-stage startups.
    """
    pass


@browser_server.command("start")
def start_browser_server(
    port: int = typer.Option(5500, "--port", "-p", help="Port to listen on"),
    background: bool = typer.Option(True, "--background", "-b", help="Run in background"),
):
    """Start the browser server."""
    console.print("[bold blue]Starting browser server...[/bold blue]")
    
    # Determine the path to the run_server.py script
    try:
        import importlib.util
        module_path = importlib.util.find_spec("seed_pitcher.browsers.run_server").origin
    except (ImportError, AttributeError):
        # Fallback to manual path construction if module spec fails
        import os.path
        module_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   "seed_pitcher", "browsers", "run_server.py")
    
    # Create log directory if it doesn't exist
    log_dir = Path.home() / ".seed_pitcher" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Path to log file
    log_file = log_dir / "browser_server.log"
    
    # Path to PID file
    pid_file = log_dir / "browser_server.pid"
    
    # Check if server is already running
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            try:
                # Check if process is running
                os.kill(pid, 0)
                console.print(f"[yellow]Browser server is already running with PID {pid}[/yellow]")
                return
            except OSError:
                # Process is not running, remove PID file
                pid_file.unlink()
        except Exception as e:
            console.print(f"[yellow]Error checking server status: {e}[/yellow]")
            pid_file.unlink()
    
    # Start the server
    try:
        if background:
            # Start server in background
            with open(log_file, "a") as log_out:
                process = subprocess.Popen(
                    [sys.executable, module_path, "--port", str(port)],
                    stdout=log_out,
                    stderr=log_out,
                    start_new_session=True,  # Detach from parent process
                )
            
            # Write PID to file
            pid_file.write_text(str(process.pid))
            
            console.print(f"[green]Browser server started in background with PID {process.pid}[/green]")
            console.print(f"[blue]Log file: {log_file}[/blue]")
            console.print(f"[blue]Server running on http://localhost:{port}[/blue]")
            console.print(f"[blue]Use 'seedpitcher browser-server status' to check status[/blue]")
            console.print(f"[blue]Use 'seedpitcher browser-server stop' to stop the server[/blue]")
        else:
            # Start server in foreground
            console.print("[green]Starting browser server in foreground...[/green]")
            console.print("[yellow]Press Ctrl+C to stop[/yellow]")
            subprocess.run([sys.executable, module_path, "--port", str(port)])
    except Exception as e:
        console.print(f"[red]Error starting browser server: {e}[/red]")


@browser_server.command("stop")
def stop_browser_server():
    """Stop the browser server."""
    console.print("[bold blue]Stopping browser server...[/bold blue]")
    
    # Path to PID file
    pid_file = Path.home() / ".seed_pitcher" / "logs" / "browser_server.pid"
    
    # Check if server is running
    if not pid_file.exists():
        console.print("[yellow]Browser server is not running[/yellow]")
        return
    
    try:
        # Read PID from file
        pid = int(pid_file.read_text().strip())
        
        # Try to terminate the process
        try:
            console.print(f"[blue]Terminating browser server with PID {pid}...[/blue]")
            os.kill(pid, 15)  # SIGTERM
            
            # Wait for the process to terminate
            import time
            for _ in range(5):  # Wait up to 5 seconds
                time.sleep(1)
                try:
                    os.kill(pid, 0)  # Check if process is still running
                except OSError:
                    # Process is not running
                    console.print("[green]Browser server stopped successfully[/green]")
                    pid_file.unlink()
                    return
            
            # If we're here, the process didn't terminate gracefully
            console.print("[yellow]Process didn't terminate gracefully, force killing...[/yellow]")
            os.kill(pid, 9)  # SIGKILL
            console.print("[green]Browser server stopped forcefully[/green]")
        except OSError as e:
            if e.errno == 3:  # No such process
                console.print("[yellow]Browser server is not running (PID not found)[/yellow]")
            else:
                console.print(f"[red]Error stopping browser server: {e}[/red]")
                
        # Clean up PID file
        pid_file.unlink()
    except Exception as e:
        console.print(f"[red]Error stopping browser server: {e}[/red]")


@browser_server.command("status")
def browser_server_status():
    """Check the status of the browser server."""
    console.print("[bold blue]Checking browser server status...[/bold blue]")
    
    # Path to PID file
    pid_file = Path.home() / ".seed_pitcher" / "logs" / "browser_server.pid"
    
    # Check if server is running
    if not pid_file.exists():
        console.print("[yellow]Browser server is not running[/yellow]")
        return
    
    try:
        # Read PID from file
        pid = int(pid_file.read_text().strip())
        
        # Check if process is running
        try:
            os.kill(pid, 0)  # This doesn't actually kill the process, just checks if it exists
            
            # Now check the HTTP health endpoint
            try:
                import requests
                port = 5500  # Default port
                
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                if response.status_code == 200:
                    health_data = response.json()
                    browser_status = health_data.get("browser", "unknown")
                    console.print(f"[green]Browser server is running with PID {pid}[/green]")
                    console.print(f"[blue]Server URL: http://localhost:{port}[/blue]")
                    console.print(f"[blue]Browser status: {browser_status}[/blue]")
                    console.print(f"[blue]Health status: {health_data.get('status', 'unknown')}[/blue]")
                else:
                    console.print(f"[yellow]Browser server process is running with PID {pid}, but HTTP endpoint returned status {response.status_code}[/yellow]")
            except Exception as e:
                console.print(f"[yellow]Browser server process is running with PID {pid}, but couldn't connect to HTTP endpoint: {e}[/yellow]")
        except OSError:
            console.print("[yellow]Browser server is not running (stale PID file)[/yellow]")
            pid_file.unlink()
    except Exception as e:
        console.print(f"[red]Error checking browser server status: {e}[/red]")


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
    founder_name: Optional[str] = typer.Option(
        None,
        "--founder-name",
        "-f",
        help="Your name as the founder (to be used in messages)",
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

    # Set founder name if provided via command line
    if founder_name:
        config.FOUNDER_NAME = founder_name
        console.print(f"[green]Founder name set to: {founder_name}[/green]")

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
            "founder_name": config.FOUNDER_NAME,  # Initialize with the config value
        }

    # Prompt for founder name if not provided via command line
    if not initial_state.get("founder_name"):
        initial_state["founder_name"] = Prompt.ask(
            "[bold]Please enter your name as it should appear in outreach messages[/bold]",
            default="Founder",
        )
        console.print(
            f"[blue]Founder name set to: {initial_state['founder_name']}[/blue]"
        )

        # Also update the config for persistence
        config.FOUNDER_NAME = initial_state["founder_name"]

        # Save to config file for future use
        config_file = Path.home() / ".seed_pitcher" / "config.json"
        if config_file.exists():
            with open(config_file, "r") as f:
                user_config = json.load(f)
        else:
            user_config = {}
            config_file.parent.mkdir(exist_ok=True)

        user_config["founder_name"] = initial_state["founder_name"]
        with open(config_file, "w") as f:
            json.dump(user_config, f)

    # Add founder name to startup_info as well for message drafting
    if "startup_info" in initial_state and initial_state["founder_name"]:
        if initial_state["startup_info"] is None:
            initial_state["startup_info"] = {}
        initial_state["startup_info"]["founder_name"] = initial_state["founder_name"]

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
                "founder_name": initial_state.get(
                    "founder_name", ""
                ),  # Carry over founder name
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

                            # Handle founder name in message content
                            message_content = result["message_draft"]
                            console.print(
                                "[blue]Personalizing message with your name...[/blue]"
                            )

                            # The founder name should already be in the state from our earlier modifications
                            # But just in case, we'll check and set a fallback if needed
                            if not state.get("founder_name"):
                                # This should rarely happen since we ask at startup now
                                state["founder_name"] = config.FOUNDER_NAME or "Founder"

                            # Add founder name to startup_info for future use
                            if "startup_info" in state and state["founder_name"]:
                                state["startup_info"]["founder_name"] = state[
                                    "founder_name"
                                ]

                            # Handle all possible placeholder formats
                            if "[Founder's Name]" in message_content:
                                message_content = message_content.replace(
                                    "[Founder's Name]", state["founder_name"]
                                )
                            if "[Your Name]" in message_content:
                                message_content = message_content.replace(
                                    "[Your Name]", state["founder_name"]
                                )
                            if "{founder_name}" in message_content:
                                message_content = message_content.replace(
                                    "{founder_name}", state["founder_name"]
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
            print(f"search query is {search_query}")
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
                            # Process the message to include founder name before displaying
                            message_content = result["message_draft"]

                            # Ensure founder name is set in batch mode
                            if not state.get("founder_name"):
                                state["founder_name"] = config.FOUNDER_NAME or "Founder"

                            # Replace name placeholders with founder name
                            if "[Founder's Name]" in message_content:
                                message_content = message_content.replace(
                                    "[Founder's Name]", state["founder_name"]
                                )
                            if "[Your Name]" in message_content:
                                message_content = message_content.replace(
                                    "[Your Name]", state["founder_name"]
                                )
                            if "{founder_name}" in message_content:
                                message_content = message_content.replace(
                                    "{founder_name}", state["founder_name"]
                                )

                            # Update the message draft with personalized content
                            result["message_draft"] = message_content

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


@app.command()
def pinai(
    api_key: Optional[str] = typer.Option(
        None, "--pinai-key", help="Pin AI API key (can also be set via environment variable PINAI_API_KEY)"
    ),
    agent_id: Optional[int] = typer.Option(
        None, "--agent-id", help="Existing Pin AI agent ID to use. If not provided, a new agent will be registered."
    ),
    register_only: bool = typer.Option(
        False, "--register-only", help="Only register the agent and display its ID, then exit."
    ),
):
    """
    Start SeedPitcher as a Pin AI agent.
    
    This mode connects SeedPitcher to the Pin AI platform, allowing users
    to interact with it through the Pin AI interface. All startup information
    will be gathered through the chat interface.
    """
    from seed_pitcher.pinai import start_pinai_agent
    
    # Set defaults for auto model selection
    if config.ANTHROPIC_API_KEY:
        llm_model = "claude-3-7-sonnet"
        console.print("Using Claude 3.7 Sonnet (ANTHROPIC_API_KEY detected)")
    elif config.OPENAI_API_KEY:
        llm_model = "gpt-4o"
        console.print("Using GPT-4o (OPENAI_API_KEY detected)")
    else:
        llm_model = "deepseek-r1"
        console.print("Using DeepSeek Coder API (no API keys detected)")
            
    config.LLM_MODEL = llm_model
    
    # Start the Pin AI agent
    try:
        start_pinai_agent(
            api_key=api_key,
            agent_id=agent_id,
            register_only=register_only
        )
    except KeyboardInterrupt:
        console.print("[yellow]Agent stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running agent: {str(e)}[/red]")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
