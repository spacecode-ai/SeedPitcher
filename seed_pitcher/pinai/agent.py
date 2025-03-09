"""Pin AI integration for SeedPitcher.

This module implements the Pin AI agent functionality for SeedPitcher, enabling
users to interact with the SeedPitcher system through the Pin AI platform.
"""

import os
import re
import sys
import logging
import time
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from rich.console import Console

# Import Pin AI SDK
from pinai_agent_sdk import PINAIAgentSDK, AGENT_CATEGORY_SOCIAL

# Import from seed_pitcher
import seed_pitcher.config as config
from seed_pitcher.browsers import get_browser, start_browser_server
from seed_pitcher.agents.graph import create_agent_graph
from seed_pitcher.utils.pdf import extract_text_from_pdf

# Configure logging
logger = logging.getLogger("seed_pitcher.pinai")
console = Console()


def ensure_browser_server_running():
    """
    Check if the standalone browser server is running, and start it if it's not.
    
    This function checks for a running browser server using the PID file, and
    starts the server if it's not already running.
    
    Returns:
        bool: True if the server is running or was started successfully, False otherwise
    """
    logger.info("Checking if standalone browser server is running")
    console.print("[blue]Checking if standalone browser server is running...[/blue]")
    
    # Make sure Path is imported
    from pathlib import Path
    
    # Path to PID file
    pid_file = Path.home() / ".seed_pitcher" / "logs" / "browser_server.pid"
    
    # Check if server is already running
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            try:
                # Check if process is running
                os.kill(pid, 0)  # This doesn't actually kill the process, just checks if it exists
                logger.info(f"Browser server is already running with PID {pid}")
                console.print(f"[green]Using existing browser server with PID {pid}[/green]")
                
                # Try to connect to the server to verify it's working
                try:
                    import requests
                    port = 5500  # Default port
                    http_response = requests.get(f"http://localhost:{port}/health", timeout=2)
                    if http_response.status_code == 200:
                        # Server is running and accessible
                        logger.info("Successfully connected to browser server")
                        return True
                    else:
                        logger.warning(f"Browser server process is running but HTTP endpoint returned status {http_response.status_code}")
                except Exception as e:
                    logger.warning(f"Browser server process is running but couldn't connect to HTTP endpoint: {e}")
                    
                # If we got here, the process is running but the server isn't responding
                logger.warning("Stopping unresponsive browser server")
                try:
                    os.kill(pid, 15)  # SIGTERM
                    time.sleep(2)
                except:
                    pass
            except OSError:
                # Process is not running, remove PID file
                logger.warning("Browser server PID file exists but process is not running")
                pid_file.unlink()
        except Exception as e:
            logger.warning(f"Error checking browser server status: {e}")
            try:
                pid_file.unlink()
            except:
                pass
    
    # Server is not running, start it
    logger.info("Starting standalone browser server")
    console.print("[blue]Starting standalone browser server...[/blue]")
    
    # Check if playwright is installed
    try:
        import importlib.util
        if importlib.util.find_spec("playwright") is None:
            logger.warning("Playwright package not found. Please install with: pip install playwright")
            console.print("[yellow]⚠️ Playwright package not found. Please install with: pip install playwright[/yellow]")
            console.print("[yellow]Then install browsers with: playwright install[/yellow]")
            # We'll continue anyway, but the server won't work without playwright
    except ImportError:
        logger.warning("ImportLib not available, can't check for playwright installation")
        pass
    
    try:
        # Make sure required modules are imported
        import importlib.util
        import subprocess
        from pathlib import Path
        
        # Determine the path to the run_server.py script
        module_path = importlib.util.find_spec("seed_pitcher.browsers.run_server").origin
        
        # Create log directory if it doesn't exist
        log_dir = Path.home() / ".seed_pitcher" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Path to log file
        log_file = log_dir / "browser_server.log"
        
        # Start server in background
        with open(log_file, "a") as log_out:
            process = subprocess.Popen(
                [sys.executable, module_path, "--port", "5500"],
                stdout=log_out,
                stderr=log_out,
                start_new_session=True,  # Detach from parent process
            )
        
        # Write PID to file
        pid_file.write_text(str(process.pid))
        
        logger.info(f"Browser server started with PID {process.pid}")
        console.print(f"[green]Browser server started with PID {process.pid}[/green]")
        
        # Give the server a moment to start up
        time.sleep(3)
        
        # Check if the server is running and responding
        try:
            import requests
            port = 5500  # Default port
            response = requests.get(f"http://localhost:{port}/health", timeout=2)
            if response.status_code == 200:
                logger.info("Successfully verified browser server is running")
                console.print(f"[green]Browser server ready on port {port}[/green]")
                return True
            else:
                logger.warning(f"Browser server process started but HTTP endpoint returned status {response.status_code}")
                console.print(f"[yellow]Browser server process started but not responding properly[/yellow]")
                return False
        except Exception as e:
            logger.warning(f"Browser server process started but couldn't connect to HTTP endpoint: {e}")
            console.print(f"[yellow]Browser server process started but not responding: {e}[/yellow]")
            return False
    except Exception as e:
        logger.error(f"Error starting browser server: {e}")
        console.print(f"[red]Error starting browser server: {e}[/red]")
        return False

def start_pinai_agent(
    api_key: Optional[str] = None,
    agent_id: Optional[int] = None,
    register_only: bool = False,
) -> None:
    """
    Start SeedPitcher as a Pin AI agent.
    
    Args:
        api_key: Pin AI API key (optional if set via environment)
        agent_id: Existing Pin AI agent ID to use (if None, a new one will be registered)
        register_only: If True, only register the agent and exit
    """
    # Ensure the browser server is running
    browser_server_available = ensure_browser_server_running()
    
    if not browser_server_available:
        logger.warning("Browser server not available. Some features may be limited.")
        console.print("[yellow]⚠️ Warning: Browser server not available. Some features may be limited.[/yellow]")
    # Set API key from environment if not provided
    if api_key:
        os.environ["PINAI_API_KEY"] = api_key
    
    # Get API key from environment
    pinai_api_key = os.environ.get("PINAI_API_KEY")
    if not pinai_api_key:
        console.print("[red]Error: Pin AI API key not provided. Please provide it with --pinai-key or set the PINAI_API_KEY environment variable.[/red]")
        return
    
    # Initialize Pin AI SDK client
    console.print("[bold green]Initializing Pin AI agent...[/bold green]")
    client = PINAIAgentSDK(api_key=pinai_api_key)
    
    # Check for existing agents or register a new one if needed
    if not agent_id:
        # List existing agents first to find the SeedPitcher agent
        try:
            console.print("[bold green]Looking for existing SeedPitcher agent...[/bold green]")
            agents = client.list_agents()
            
            # Look for an agent with the name "SeedPitcher"
            existing_agent = None
            for agent in agents:
                if agent.get("name") == "SeedPitcher":
                    existing_agent = agent
                    break
            
            if existing_agent:
                agent_id = existing_agent.get("id")
                console.print(f"[green]Found existing SeedPitcher agent with ID: {agent_id}[/green]")
            else:
                # No existing SeedPitcher agent found, register a new one
                console.print("[bold green]Registering new SeedPitcher agent with Pin AI...[/bold green]")
                agent_info = client.register_agent(
                    name="SeedPitcher",
                    description="SeedPitcher helps startups with seed fundraising by analyzing investor profiles, scoring their relevance, and drafting personalized outreach messages.",
                    category=AGENT_CATEGORY_SOCIAL
                )
                agent_id = agent_info.get("id")
                console.print(f"[green]Agent registered with ID: {agent_id}[/green]")
        except Exception as e:
            logger.error(f"Error finding or registering agent: {str(e)}", exc_info=True)
            console.print(f"[red]Error: {str(e)}[/red]")
            console.print("[yellow]Please provide your agent ID explicitly using the --agent-id parameter.[/yellow]")
            return
        
        # Exit if only registering the agent
        if register_only:
            console.print("[bold green]Agent registration complete. Use this ID to start the agent in the future:[/bold green]")
            console.print(f"[bold green]Agent ID: {agent_id}[/bold green]")
            return
    
    # Dictionary to store user session data
    user_sessions = {}
    
    # Initialize shared analysis agent
    shared_agent = None
    
    console.print("[bold green]Pin AI agent ready. Waiting for users to connect...[/bold green]")
    
    # Create callback function to handle messages
    def handle_message(message: Dict[str, Any]) -> None:
        """
        Process incoming messages from Pin AI and respond
        
        Args:
            message: Message object with content from user
        """
        nonlocal user_sessions, shared_agent
        
        session_id = message.get("session_id")
        if not session_id:
            logger.error("Message missing session_id, cannot respond")
            return
        
        # Initialize session data if this is a new session
        if session_id not in user_sessions:
            # Make sure we're using config directly here to avoid variable scope issues
            import seed_pitcher.config as sp_config
            user_sessions[session_id] = {
                "elevator_pitch": "",
                "pitch_deck_text": "",
                "founder_name": sp_config.FOUNDER_NAME or "",
                "threshold": sp_config.INVESTOR_THRESHOLD,
                "startup_info": {
                    "elevator_pitch": "",
                    "pitch_deck_text": "",
                    "founder_name": sp_config.FOUNDER_NAME or "",
                },
                "agent": None,
                "onboarding_complete": False,
            }
            logger.info(f"New session created: {session_id}")
            console.print(f"[green]New user session started: {session_id}[/green]")
            
            # Send welcome message
            welcome_message = """Welcome to SeedPitcher! I'm here to help you find relevant investors for your startup and draft personalized outreach messages.

To get started, please provide a brief elevator pitch for your startup. This should include your:
• Problem you're solving
• Your solution
• Target market
• Current stage (pre-seed, seed, etc.)
• What makes your startup unique"""
            client.send_message(content=welcome_message)
            return
        
        # Get session data
        session_data = user_sessions[session_id]
        elevator_pitch = session_data["elevator_pitch"]
        pitch_deck_text = session_data["pitch_deck_text"]
        founder_name = session_data["founder_name"] 
        threshold = session_data["threshold"]
        startup_info = session_data["startup_info"]
        agent = session_data["agent"]
        onboarding_complete = session_data["onboarding_complete"]
        
        # Debug current state
        logger.info(f"Current state - elevator_pitch: {bool(elevator_pitch)}, founder_name: {bool(founder_name)}, threshold set: {threshold != config.INVESTOR_THRESHOLD}, agent initialized: {agent is not None}")
        console.print(f"[yellow]DEBUG - Current state - elevator_pitch: {bool(elevator_pitch)}, founder_name: {bool(founder_name)}, threshold set: {threshold != config.INVESTOR_THRESHOLD}, agent initialized: {agent is not None}[/yellow]")
        
        session_id = message.get("session_id")
        if not session_id:
            logger.error("Message missing session_id, cannot respond")
            return
        
        # Get user message
        user_message = message.get("content", "")
        logger.info(f"Received message: {user_message}")
        console.print(f"[blue]Received: {user_message}[/blue]")
        
        # Get persona info
        try:
            persona_info = client.get_persona(session_id)
            logger.info(f"User: {persona_info.get('username', 'Unknown user')}")
            console.print(f"[green]User: {persona_info.get('username', 'Unknown user')}[/green]")
        except Exception as e:
            logger.warning(f"Could not get user info: {e}")
            console.print(f"[yellow]Could not get user info: {e}[/yellow]")
        
        # Check for onboarding status
        if not elevator_pitch:
            # We need to get elevator pitch first
            if "pitch" in user_message.lower() or len(user_message) > 50:
                # User might be providing elevator pitch
                elevator_pitch = user_message
                startup_info["elevator_pitch"] = elevator_pitch
                
                # Update session data
                session_data["elevator_pitch"] = elevator_pitch
                session_data["startup_info"]["elevator_pitch"] = elevator_pitch
                
                logger.info(f"Collected elevator pitch: {elevator_pitch}")
                console.print(f"[green]Collected elevator pitch from user[/green]")
                
                response = """Thank you for sharing your startup pitch! I'll use this to help identify relevant investors.

Now, could you tell me your name as it should appear in outreach messages?"""
                client.send_message(content=response)
                return
            else:
                # Ask for elevator pitch
                response = """Welcome to SeedPitcher! To help you find relevant investors, I need to know about your startup.

Please provide a brief elevator pitch for your startup. This should include your:
• Problem you're solving
• Your solution
• Target market
• Current stage (pre-seed, seed, etc.)
• What makes your startup unique"""
                client.send_message(content=response)
                return
        elif not founder_name:
            # We have elevator pitch but need founder name
            founder_name = user_message.strip()
            startup_info["founder_name"] = founder_name
            config.FOUNDER_NAME = founder_name
            
            # Update session data
            session_data["founder_name"] = founder_name
            session_data["startup_info"]["founder_name"] = founder_name
            
            logger.info(f"Collected founder name: {founder_name}")
            console.print(f"[green]Collected founder name: {founder_name}[/green]")
            
            response = f"""Thanks, {founder_name}! I'll use your name in outreach messages.

I'm now ready to analyze investor profiles. You can:
1. Send me LinkedIn URLs of potential investors
2. Type "help" for more information
3. You can also customize settings like "set threshold to 0.7" if you want to adjust the investor relevance threshold (default is 0.5)"""

            # Set onboarding as complete since we now have the required information
            session_data["onboarding_complete"] = True
            
            # Initialize the agent now that we have the basic info
            with console.status("[bold green]Initializing SeedPitcher agent...[/bold green]"):
                if shared_agent is None:
                    local_elevator_pitch = elevator_pitch
                    local_pitch_deck_text = pitch_deck_text
                    shared_agent = create_agent_graph(local_elevator_pitch, local_pitch_deck_text)
                agent = shared_agent
                session_data["agent"] = agent
            client.send_message(content=response)
            return
        
        # Check for LinkedIn URL in the message
        linkedin_urls = re.findall(r'(https?://(?:www\.)?linkedin\.com/\S+)', user_message)
        
        # Debug log for URL detection
        logger.info(f"LinkedIn URLs found in message: {linkedin_urls}")
        console.print(f"[yellow]LinkedIn URLs found in message: {linkedin_urls}[/yellow]")
        
        response = ""
        
        if linkedin_urls:
            # Process LinkedIn URLs
            logger.info(f"Found {len(linkedin_urls)} LinkedIn URLs in message")
            console.print(f"[green]Found {len(linkedin_urls)} LinkedIn URLs in message[/green]")
            
            # Initialize browser_working here to ensure it's always defined
            browser_working = False
            
            # The Pin AI SDK uses threading which conflicts with Playwright's synchronous API
            # We'll use the HTTP client to communicate with the browser server
            logger.info("Using HTTP client to connect to browser server")
            console.print("[blue]Connecting to browser server for LinkedIn profile analysis...[/blue]")
            
            # Standard port for the browser server
            browser_server_port = 5500
            
            # Initialize HTTP client for browser
            from seed_pitcher.browsers.http_client import HTTPBrowserClient
            
            # Initialize the client to connect to our browser server
            browser = None
            
            # Try to connect to the server with retries
            for attempt in range(3):
                try:
                    logger.info(f"Connecting to browser server attempt {attempt+1}/3")
                    
                    # Import the HTTP client
                    try:
                        from seed_pitcher.browsers.http_client import HTTPBrowserClient
                    except ImportError as imp_err:
                        logger.error(f"Failed to import HTTPBrowserClient: {imp_err}")
                        console.print(f"[red]Failed to import HTTPBrowserClient: {imp_err}[/red]")
                        break
                        
                    # Create a fresh client on each attempt
                    # Explicitly use the correct port and add additional logging
                    logger.info(f"Creating HTTPBrowserClient with URL: http://localhost:{browser_server_port}")
                    browser = HTTPBrowserClient(base_url=f"http://localhost:{browser_server_port}")
                    
                    # Test the connection with a short timeout
                    try:
                        logger.info(f"Testing connection to browser server at {browser.base_url}/health")
                        http_response = browser.session.get(f"{browser.base_url}/health", timeout=10)  # Increased timeout
                        
                        if http_response.status_code == 200:
                            logger.info(f"Successfully connected to browser server on attempt {attempt+1}")
                            console.print(f"[green]Successfully connected to browser server[/green]")
                            break
                        else:
                            logger.warning(f"Browser server returned status {http_response.status_code} on attempt {attempt+1}")
                            # Wait before retry
                            time.sleep(2)
                    except Exception as req_err:
                        logger.warning(f"Request to browser server failed: {req_err}")
                        # Wait before retry
                        time.sleep(2)
                except Exception as conn_err:
                    logger.warning(f"Connection to browser server failed on attempt {attempt+1}: {conn_err}")
                    # Wait before retry
                    time.sleep(2)
                    
                # If we failed 3 times, set browser to None
                if attempt == 2:
                    browser = None
                    logger.warning("All connection attempts to browser server failed")
                    console.print("[yellow]All connection attempts to browser server failed, falling back to browser-free mode[/yellow]")
            
            # Check if the browser client was created successfully
            if browser is not None:
                # Check if we can connect to the browser server and if browser is properly initialized
                browser_available = False
                try:
                    # Try a health check with short timeout
                    http_response = browser.session.get(f"{browser.base_url}/health", timeout=5)
                    
                    if http_response.status_code == 200:
                        # Check if browser is actually initialized and working
                        health_data = http_response.json()
                        logger.info(f"Browser server health check result: {health_data}")
                        
                        # If the health check indicates the browser is initialized and healthy
                        if health_data.get("status") == "healthy":
                            browser_available = True
                            logger.info(f"Successfully connected to browser server on port {browser_server_port}")
                            console.print(f"[green]Successfully connected to browser server on port {browser_server_port}[/green]")
                        else:
                            # Browser server is running but browser is not healthy
                            logger.warning(f"Browser server is running but browser is not healthy: {health_data}")
                            console.print(f"[yellow]Browser server is running but browser is not healthy: {health_data.get('browser', 'unknown status')}[/yellow]")
                            
                            # Try to reinitialize browser by going to a test URL
                            try:
                                # Test navigation to a simple URL
                                test_response = browser.session.post(
                                    f"{browser.base_url}/navigate", 
                                    json={"url": "https://www.google.com"},
                                    timeout=10
                                )
                                
                                if test_response.status_code == 200:
                                    logger.info("Successfully initialized browser with test navigation")
                                    console.print("[green]Successfully initialized browser with test navigation[/green]")
                                    browser_available = True
                                else:
                                    logger.warning(f"Test navigation failed: {test_response.status_code}")
                            except Exception as test_err:
                                logger.warning(f"Test navigation failed: {test_err}")
                    else:
                        logger.error(f"Browser server returned unhealthy status: {http_response.status_code}")
                        console.print(f"[yellow]Browser server returned unhealthy status: {http_response.status_code}[/yellow]")
                except Exception as e:
                    logger.error(f"Failed to connect to browser server: {e}")
                    console.print(f"[yellow]Failed to connect to browser server: {e}[/yellow]")
            else:
                logger.warning("Browser client not created, using browser-free mode")
                browser_available = False
                
            # If browser is not available, fall back to browser-free mode
            if not browser_available:
                console.print("[yellow]⚠️ Browser server not accessible or not healthy. Will use browser-free mode.[/yellow]")
                browser = None
            
            # Process each LinkedIn URL
            for url in linkedin_urls:
                # Create a state for processing this URL
                state = {
                    "action": "analyze_profile",
                    "startup_info": {
                        "elevator_pitch": elevator_pitch,
                        "pitch_deck_text": pitch_deck_text,
                        "founder_name": founder_name
                    },
                    "current_profile": {
                        "url": url,
                        "name": "LinkedIn Profile",  # Will be populated from browser or user input
                    },
                    "investor_score": 0.0,
                    "investor_analysis": {
                        "is_investor": False,
                        "confidence": 0.0,
                        "reasoning": "Analysis pending"
                    },
                    "message_draft": "",
                    "history": [],
                    "urls_to_process": [url],  # Store URL in urls_to_process array
                    "browser": browser,  # Use our async-compatible browser
                    "url": url,  # Directly set URL for analysis
                    "founder_name": founder_name  # Add this separately as the CLI does
                }
                
                # Make sure config INVESTOR_THRESHOLD is explicitly set
                import seed_pitcher.config as sp_config
                logger.info(f"Using INVESTOR_THRESHOLD: {sp_config.INVESTOR_THRESHOLD}")
                
                # We're using a browser-free approach, so no browser initialization needed
                logger.info("Using browser-free approach for LinkedIn profile analysis")
                
                logger.info(f"Processing URL: {url}")
                console.print(f"[green]Processing URL: {url}[/green]")
                
                # Let user know we're working on it
                progress_msg = f"Analyzing {url}... This might take a minute or two. I'll get back to you soon!"
                client.send_message(content=progress_msg)
                
                # Only use browser-free mode if no browser is available
                if browser is None:
                    logger.info("Using browser-free mode for LinkedIn profile analysis")
                    browser_working = False
                else:
                    logger.info("Using browser-connected mode for LinkedIn profile analysis")
                    # Keep existing browser_working state based on actual connection status
                
                # If this appears to be the first time they're sending this URL, prompt for info
                first_time_url = True
                for recent_msg in session_data.get("recent_messages", []):
                    if url in recent_msg:
                        first_time_url = False
                        break
                
                # Store this URL in recent messages
                if "recent_messages" not in session_data:
                    session_data["recent_messages"] = []
                session_data["recent_messages"].append(user_message)
                if len(session_data["recent_messages"]) > 5:
                    session_data["recent_messages"].pop(0)  # Keep only last 5 messages
                
                if first_time_url:
                    if browser_available and browser:
                        # Try to use the browser to analyze the profile
                        client.send_message(content=f"""I'll help you analyze this LinkedIn profile ({url}).
                        
I'm accessing and analyzing this profile automatically. This may take a moment...""")
                        
                        try:
                            # Use the dedicated LinkedIn profile extraction endpoint
                            logger.info(f"Using HTTP client to extract LinkedIn profile: {url}")
                            
                            # Set a reasonable timeout for profile extraction
                            profile_data = None
                            # Initialize the result dictionary here to avoid the 'result not defined' error
                            result = {}
                            # Ensure browser_working is always defined
                            browser_working = browser is not None
                            
                            extraction_timeout = threading.Timer(20.0, lambda: client.send_message(content="Still analyzing the profile. This may take a bit longer..."))
                            try:
                                extraction_timeout.start()
                                profile_data = browser.extract_linkedin_profile(url)
                            finally:
                                extraction_timeout.cancel()
                            
                            if profile_data and profile_data.get("status") == "success":
                                logger.info("Successfully extracted LinkedIn profile data")
                                # Log the complete profile data for debugging
                                logger.info(f"COMPLETE LINKEDIN PROFILE DATA: {profile_data}")
                                
                                profile_info = profile_data.get("profile", {})
                                analysis = profile_data.get("analysis", {})
                                
                                # Log detailed analysis information
                                logger.info(f"LinkedIn analysis data: {analysis}")
                                
                                # Extract basic profile information
                                if "name" in profile_info:
                                    state["current_profile"]["name"] = profile_info["name"]
                                    logger.info(f"Found profile name: {profile_info['name']}")
                                
                                # Extract whether this person is an investor
                                is_investor = analysis.get("is_investor", False)
                                confidence = analysis.get("confidence", 0.5)
                                logger.info(f"Raw LinkedIn data - is_investor: {is_investor}, confidence: {confidence}")
                                investor_keywords = analysis.get("investor_keywords_found", [])
                                
                                logger.info(f"LinkedIn analysis results: is_investor={is_investor}, confidence={confidence}")
                                logger.info(f"Investor keywords found: {investor_keywords}")
                                
                                # Directly set investor score based on LinkedIn analysis
                                # This is critical to ensure investor scoring works correctly
                                if is_investor and confidence > 0:
                                    # Calculate initial score from confidence
                                    base_score = confidence
                                    # Add bonus for investor keywords
                                    keyword_bonus = min(0.2, len(investor_keywords) * 0.05)
                                    investor_score = min(0.95, base_score + keyword_bonus)
                                    
                                    # Update the result with the score
                                    result["investor_score"] = investor_score
                                    logger.info(f"CRITICAL: Setting initial investor_score from LinkedIn data: {investor_score}")
                                
                                # Update state with extracted information
                                state["investor_analysis"] = {
                                    "is_investor": is_investor,
                                    "confidence": confidence,
                                    "investor_keywords": investor_keywords,
                                    "reasoning": "Based on automatic LinkedIn profile analysis"
                                }
                                
                                # Add any extracted roles or focus areas
                                if "investment_roles" in profile_info:
                                    state["investor_analysis"]["roles"] = profile_info["investment_roles"]
                                    
                                # Add experiences to the state
                                if "experience" in profile_info:
                                    state["current_profile"]["experience"] = profile_info["experience"]
                                
                                # Add headline to the state
                                if "headline" in profile_info:
                                    state["current_profile"]["headline"] = profile_info["headline"]
                                
                                logger.info(f"Profile analysis: is_investor={is_investor}, confidence={confidence}")
                                
                                # Proceed with analysis
                                client.send_message(content=f"""I've analyzed the LinkedIn profile for {profile_info.get('name', 'this person')}.
                                
Based on their profile information, I've determined the following:
- {'They appear to be an investor' if is_investor else 'They do not appear to be an investor'} 
- {'Their current headline: ' + profile_info.get('headline', 'Not available') if 'headline' in profile_info else ''}

Now I'll evaluate if they're a good match for your startup...""")
                                
                                # Continue processing with this URL since we have the data
                            else:
                                # Failed to extract, fall back to asking the user for info
                                error = profile_data.get("error", "Unknown error") if profile_data else "No data returned"
                                logger.warning(f"Failed to extract LinkedIn profile data: {error}")
                                client.send_message(content=f"""I had some trouble analyzing the full LinkedIn profile automatically.

Could you help me by providing some information about this person:

1. Their name
2. Their current job title and company  
3. Whether they appear to be an investor (VC, angel, etc.)
4. Any investment focus areas mentioned in their profile
5. Any stage preferences they have

This will help me determine if they're a good match for your startup.""")
                                # Wait for user input
                                continue
                        except Exception as e:
                            logger.error(f"Error in LinkedIn profile extraction: {str(e)}")
                            client.send_message(content=f"""I encountered an error while analyzing the LinkedIn profile.

Could you help me by providing some information about this person:

1. Their name
2. Their current job title and company
3. Whether they appear to be an investor (VC, angel, etc.)
4. Any investment focus areas mentioned in their profile
5. Any stage preferences they have

This will help me determine if they're a good match for your startup.""")
                            # Wait for user input
                            continue
                    else:
                        # No browser available - fall back to asking for information
                        logger.info(f"No browser available, asking user for profile information for {url}")
                        client.send_message(content=f"""I'll help you analyze this LinkedIn profile ({url}).

Since I can't access the profile directly, I need some basic information about this person:

1. Their name
2. Their current job title and company
3. Whether they appear to be an investor (VC, angel investor, etc.)
4. Any investment focus areas mentioned in their profile (e.g., fintech, healthcare, SaaS)
5. Any stage preferences mentioned (e.g., seed, early-stage, Series A)

This will help me analyze if they're a good match for your startup.""")
                        # We need to wait for user input, so don't process this URL yet
                        continue
                
                # Process the URL with the agent
                try:
                    # Run the agent
                    if agent is None:
                        # Make sure we have an agent initialized
                        if shared_agent is None:
                            logger.info("Initializing agent on demand for LinkedIn analysis")
                            console.print("[yellow]Initializing agent on demand for LinkedIn analysis[/yellow]")
                            # Use local variables to avoid scope issues
                            local_elevator_pitch = elevator_pitch
                            local_pitch_deck_text = pitch_deck_text
                            shared_agent = create_agent_graph(local_elevator_pitch, local_pitch_deck_text)
                        agent = shared_agent
                        session_data["agent"] = agent
                    
                    # Log agent input state for debugging
                    logger.info(f"Agent input state: action={state['action']}, elevator_pitch={bool(state['startup_info']['elevator_pitch'])}")
                    logger.info(f"State keys: {list(state.keys())}")
                    
                    try:
                        # Log detailed state information as in the CLI
                        logger.info(f"Starting analysis of profile: {url}")
                        logger.info(f"State keys being passed to agent: {list(state.keys())}")
                        # Check if url is in state, otherwise get from urls_to_process
                        profile_url = state.get('url', url)
                        logger.info(f"Profile URL: {profile_url}")
                        logger.info(f"Elevator pitch: {state['startup_info']['elevator_pitch'][:50]}...")
                        
                        # ========== IMPORTANT ==========
                        # Since we're in browser-free mode, we need to handle the investor analysis ourselves
                        # and bypass the agent's built-in LinkedIn handling completely
                        
                        # Create a default result structure, similar to what the agent would return
                        logger.info("In browser-free mode, creating default result structure")
                        
                        # Extract info about the investor from user message, if available
                        result = {
                            "action": "offer_message_draft",
                            "startup_info": state["startup_info"],
                            "current_profile": {
                                "url": url,
                                "name": "LinkedIn Profile",  # Will be updated from user input
                            },
                            "investor_score": 0.0,
                            "investor_analysis": {
                                "is_investor": False,
                                "confidence": 0.0,
                                "reasoning": "Based on user input in browser-free mode"
                            },
                            "message_draft": "",
                            "history": [],
                            "founder_name": founder_name
                        }
                        
                        # Log the result for debugging
                        logger.info(f"Agent result keys: {list(result.keys())}")
                        logger.info(f"Investor score from result: {result.get('investor_score', 0)}")
                        logger.info(f"Result action: {result.get('action', 'unknown')}")
                        
                        # Detailed logging of investor analysis
                        investor_analysis = result.get("investor_analysis", {})
                        logger.info(f"INVESTOR ANALYSIS: {investor_analysis}")
                        
                        # Now extract info from user message to populate our result directly
                        # Extract profile name if provided by user
                        name_match = re.search(r'(?:name is|name:|called)\s+([A-Z][a-zA-Z\s\-\']+)', user_message, re.IGNORECASE)
                        if name_match:
                            profile_name = name_match.group(1).strip()
                            if profile_name:
                                result["current_profile"]["name"] = profile_name
                                logger.info(f"Extracted profile name from user input: {profile_name}")
                        
                        # Extract company/title if provided
                        company_match = re.search(r'(?:work(?:s|ing)? (?:at|for)|company is|company:|with)\s+([A-Za-z0-9\s\-\'\&\.]+)', user_message, re.IGNORECASE)
                        if company_match:
                            company = company_match.group(1).strip()
                            if company:
                                result["current_profile"]["company"] = company
                                logger.info(f"Extracted company from user input: {company}")
                        
                        # Check if user indicated this is an investor
                        positive_investor_indicators = [
                            "yes", "they're an investor", "they are an investor", "is an investor",
                            "venture capitalist", "vc", "angel investor", "fund", "capital", "investor",
                            "invests in", "investment", "partner at"
                        ]
                        negative_investor_indicators = [
                            "no", "not an investor", "doesn't appear", "doesn't seem", "isn't", "is not"
                        ]
                        
                        is_investor = False
                        confidence = 0.0
                        
                        # Check if user explicitly indicated investor status
                        if any(indicator in user_message.lower() for indicator in positive_investor_indicators):
                            is_investor = True
                            # Higher confidence if they explicitly said yes or used multiple investor terms
                            confidence = 0.7 + (0.1 * sum(1 for ind in positive_investor_indicators if ind in user_message.lower()))
                            confidence = min(confidence, 0.9)  # Cap at 0.9
                            
                            logger.info(f"User indicated this is an investor with confidence {confidence}")
                        elif any(indicator in user_message.lower() for indicator in negative_investor_indicators):
                            is_investor = False
                            logger.info("User indicated this is NOT an investor")
                        
                        # Extract investment focus if provided
                        focus_areas = []
                        focus_keywords = [
                            "fintech", "finance", "financial", "health", "healthcare", "biotech", "saas", 
                            "enterprise", "consumer", "retail", "ecommerce", "ai", "ml", "artificial intelligence",
                            "machine learning", "deep tech", "climate", "cleantech", "education", "edtech",
                            "crypto", "blockchain", "web3", "marketplaces", "b2b", "b2c", "software"
                        ]
                        
                        for keyword in focus_keywords:
                            if keyword in user_message.lower():
                                focus_areas.append(keyword)
                                
                        if focus_areas:
                            logger.info(f"Extracted investment focus areas: {focus_areas}")
                        
                        # Extract stage preferences if provided
                        stages = []
                        stage_keywords = ["seed", "pre-seed", "early stage", "early-stage", "series a", "growth", "late stage", "late-stage"]
                        
                        for keyword in stage_keywords:
                            if keyword in user_message.lower():
                                stages.append(keyword)
                                
                        if stages:
                            logger.info(f"Extracted stage preferences: {stages}")
                        
                        # Update investor analysis
                        if is_investor:
                            investor_analysis["is_investor"] = True
                            investor_analysis["confidence"] = confidence
                            investor_analysis["reasoning"] = "Based on user provided information"
                            investor_analysis["investment_focus"] = focus_areas
                            
                            # Create web_info with the extracted information
                            web_info = {
                                "recent_investments": [],  # No specific investments known
                                "investment_stages": stages,
                                "investment_sectors": focus_areas,
                                "startup_sectors": []  # Will be derived from elevator pitch
                            }
                            
                            investor_analysis["web_info"] = web_info
                            
                            # Set a reasonable score based on available information
                            investor_score = confidence * 0.7  # Base score on confidence
                            
                            # Boost score if focus areas are relevant to startup
                            elevator_pitch = state["startup_info"]["elevator_pitch"]
                            if focus_areas and elevator_pitch:
                                relevant_focus = sum(1 for focus in focus_areas if focus.lower() in elevator_pitch.lower())
                                if relevant_focus > 0:
                                    investor_score += min(0.3, relevant_focus * 0.1)
                            
                            result["investor_score"] = investor_score
                            result["investor_analysis"] = investor_analysis
                            
                            logger.info(f"Set investor score to {investor_score} based on user input")
                        else:
                            # Not an investor according to user
                            investor_analysis["is_investor"] = False
                            investor_analysis["confidence"] = 0.8  # High confidence in user's assessment
                            investor_analysis["reasoning"] = "User indicated this is not an investor"
                            result["investor_score"] = 0.0
                            result["investor_analysis"] = investor_analysis
                            
                            logger.info("Set as non-investor based on user input")
                        
                        # Detailed logging of investor analysis
                        investor_analysis = result.get("investor_analysis", {})
                        logger.info(f"INVESTOR ANALYSIS: {investor_analysis}")
                        
                        # Debug is_investor flag specifically
                        is_investor = investor_analysis.get("is_investor", False)
                        logger.info(f"Is investor: {is_investor} (type: {type(is_investor)})")
                        
                        # If is_investor is True but there's no web_info, try to add it
                        if is_investor and "web_info" not in investor_analysis:
                            logger.info("Investor is True but web_info missing, trying to add it")
                            try:
                                # Use web search to get additional info
                                from seed_pitcher.utils.web_search import search_investor_info
                                profile_name = result.get("current_profile", {}).get("name", "")
                                company = result.get("current_profile", {}).get("company", "")
                                fund = result.get("current_profile", {}).get("fund", "")
                                
                                if profile_name:
                                    web_info = search_investor_info(profile_name, company, fund)
                                    investor_analysis["web_info"] = web_info
                                    logger.info(f"Added web_info to investor_analysis: {web_info}")
                            except Exception as web_err:
                                logger.error(f"Error adding web_info: {web_err}", exc_info=True)
                        
                        # Debug confidence score
                        confidence = investor_analysis.get("confidence", 0.0)
                        logger.info(f"Investor confidence: {confidence} (type: {type(confidence)})")
                        
                        # Debug web_info
                        web_info = investor_analysis.get("web_info", {})
                        logger.info(f"Web info: {web_info}")
                        
                        # Debug recent investments
                        recent_investments = web_info.get("recent_investments", [])
                        logger.info(f"Recent investments: {recent_investments}")
                        
                        # Run the scoring function directly to debug
                        from seed_pitcher.utils.investor import score_investor
                        elevator_pitch = state["startup_info"]["elevator_pitch"]
                        try:
                            debug_score = score_investor(investor_analysis, web_info, elevator_pitch)
                            logger.info(f"DEBUG DIRECT SCORE: {debug_score}")
                        except Exception as score_err:
                            logger.error(f"Error in direct scoring: {score_err}", exc_info=True)
                    except Exception as e:
                        logger.error(f"Error invoking agent: {str(e)}", exc_info=True)
                        console.print(f"[red]Error invoking agent: {str(e)}[/red]")
                        client.send_message(content=f"I encountered an error analyzing this profile: {str(e)}")
                        continue
                    
                    # Make sure we're using the right threshold from the session
                    threshold = session_data["threshold"]
                    logger.info(f"Using threshold: {threshold}")
                    
                    # Calculate the investor score based on confidence and profile data
                    investor_score = result.get("investor_score", 0)
                    logger.info(f"Initial investor_score: {investor_score}")
                    
                    # Extract key information for scoring
                    is_investor = investor_analysis.get("is_investor", False)
                    confidence = investor_analysis.get("confidence", 0)
                    investor_keywords = investor_analysis.get("investor_keywords", [])
                    logger.info(f"Profile analysis: is_investor={is_investor}, confidence={confidence}, keywords={investor_keywords}")
                    
                    # Calculate score using confidence value regardless of is_investor
                    # We'll use the confidence directly even if is_investor is False
                    # This is important because sometimes the model has high confidence but sets is_investor incorrectly
                    
                    # If we have confidence data, use it directly as the base of our score
                    if confidence > 0:
                        logger.info(f"Using confidence value {confidence} for base score calculation")
                        base_score = confidence
                        logger.info(f"Using direct confidence value {confidence} for investor score")
                        
                        # Additional bonus for having investor keywords
                        keyword_bonus = min(0.2, len(investor_keywords) * 0.05)
                        investor_score = min(0.95, base_score + keyword_bonus)
                        logger.info(f"Added keyword bonus of {keyword_bonus} based on {len(investor_keywords)} keywords")
                        result["investor_score"] = investor_score
                    
                    # Override is_investor if confidence is high enough
                    if confidence >= 0.5 and not is_investor:
                        logger.info(f"High confidence ({confidence}) detected despite is_investor=False. Treating as investor.")
                        is_investor = True
                        investor_analysis["is_investor"] = True
                    
                    # If confidence data is missing but is_investor is True, try direct scoring
                    if is_investor and confidence <= 0 and investor_score == 0:
                        logger.info("No confidence score but is_investor is True - trying direct scoring")
                        try:
                            # Try to score directly
                            from seed_pitcher.utils.investor import score_investor
                            web_info = investor_analysis.get("web_info", {})
                            elevator_pitch = state["startup_info"]["elevator_pitch"]
                            direct_score = score_investor(investor_analysis, web_info, elevator_pitch)
                            logger.info(f"Direct scoring result: {direct_score}")
                            
                            # Update the score in the result
                            investor_score = direct_score
                            result["investor_score"] = direct_score
                            logger.info(f"Updated investor_score to {direct_score}")
                        except Exception as score_err:
                            logger.error(f"Error in direct scoring: {score_err}", exc_info=True)
                            
                            # If scoring fails but it's an investor, use a default score
                            investor_score = 0.6
                            result["investor_score"] = investor_score
                            logger.info(f"Scoring failed but is_investor is True, using default score of {investor_score}")
                    
                    # If browser is not working, give a small boost to the score since we're working with limited information
                    if not browser_working and investor_score > 0:
                        original_score = investor_score
                        investor_score = max(investor_score, 0.6)
                        result["investor_score"] = investor_score
                        logger.info(f"Browser not working, boosted score from {original_score} to {investor_score}")
                    # Log the DEBUG DIRECT SCORE for debugging
                    logger.info(f"DEBUG DIRECT SCORE: {investor_score}")
                    
                    # Final investor score log
                    logger.info(f"Final investor score: {investor_score}")
                    
                    if investor_score >= threshold:
                        # Investor is relevant
                        profile_name = result.get("current_profile", {}).get("name", "This investor")
                        score_info = f"{profile_name} scored {investor_score:.2f}/1.0 (threshold: {threshold})"
                        
                        # Add note about browser limitations if applicable
                        if not browser_working:
                            browser_note = "\n\n**Note**: I wasn't able to access this LinkedIn profile directly due to browser connection issues. This analysis is based on limited information."
                        else:
                            browser_note = ""
                        
                        # Get URL from current_profile if available, otherwise use the original URL
                        profile_url = result.get("current_profile", {}).get("url", url)
                        response += f"I've analyzed {profile_url}\n\n{score_info}{browser_note}\n\n"
                        
                        # Include message draft if available, or generate a simple one for browser-free mode
                        if "message_draft" in result and result["message_draft"]:
                            # Process the message draft to include founder name
                            message_content = result["message_draft"]
                            
                            # Replace placeholders with founder name
                            if "[Founder's Name]" in message_content:
                                message_content = message_content.replace("[Founder's Name]", founder_name)
                            if "[Your Name]" in message_content:
                                message_content = message_content.replace("[Your Name]", founder_name)
                            if "{founder_name}" in message_content:
                                message_content = message_content.replace("{founder_name}", founder_name)
                            
                            response += f"Here's a suggested outreach message:\n\n```\n{message_content}\n```\n\n"
                        elif not browser_working and investor_score >= threshold:
                            # Generate a basic message for browser-free mode
                            investor_name = result.get("current_profile", {}).get("name", "")
                            if not investor_name:
                                investor_name = "there"
                                
                            company = result.get("current_profile", {}).get("company", "")
                            company_mention = f" at {company}" if company else ""
                            
                            # Get focus areas if available
                            focus_areas = investor_analysis.get("investment_focus", [])
                            focus_mention = ""
                            if focus_areas:
                                focus_mention = f" I noticed your interest in {', '.join(focus_areas[:2])}, "
                            
                            # Create message
                            message_content = f"""Hi {investor_name},

I'm {founder_name}, founder of a startup in the {elevator_pitch[:50].split()[0]} space.{focus_mention} and I thought my startup might be of interest to you.

Our company {elevator_pitch[:200]}...

Would you be open to connecting for a brief conversation about our work? I'd love to hear your thoughts and see if there might be alignment.

Best regards,
{founder_name}"""
                            
                            response += f"Here's a suggested outreach message:\n\n```\n{message_content}\n```\n\n"
                            
                        # Include analysis highlights
                        if "investor_analysis" in result and result["investor_analysis"]:
                            analysis = result["investor_analysis"]
                            highlights = []
                            
                            if "investment_focus" in analysis:
                                highlights.append(f"Investment focus: {analysis['investment_focus']}")
                            if "stage_preference" in analysis:
                                highlights.append(f"Preferred stages: {analysis['stage_preference']}")
                            if "deal_size" in analysis:
                                highlights.append(f"Typical deal size: {analysis['deal_size']}")
                            
                            if highlights:
                                response += "Analysis highlights:\n"
                                for highlight in highlights:
                                    response += f"- {highlight}\n"
                                response += "\n"
                    else:
                        # Investor is not relevant
                        profile_name = result.get("current_profile", {}).get("name", "This profile")
                        
                        # Add note about browser limitations if applicable
                        if not browser_working:
                            browser_note = "\n\n**Note**: I wasn't able to access this LinkedIn profile directly due to browser connection issues. This analysis is based on limited information."
                        else:
                            browser_note = ""
                        
                        # Get URL from current_profile if available, otherwise use the original URL
                        profile_url = result.get("current_profile", {}).get("url", url)
                        response += f"I've analyzed {profile_url}\n\n{profile_name} scored {investor_score:.2f}/1.0, which is below your threshold of {threshold}. This investor may not be the best fit for your startup.{browser_note}\n\n"
                except Exception as e:
                    error_msg = f"Error processing profile: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    console.print(f"[red]{error_msg}[/red]")
                    response += f"Sorry, I encountered an error analyzing {url}: {error_msg}\n\n"
            
            # Clean up browser
            try:
                if browser:
                    browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
        # Handle pitch deck upload intent
        elif "pitch deck" in user_message.lower() and ("upload" in user_message.lower() or "share" in user_message.lower() or "send" in user_message.lower()):
            response = """I'd love to analyze your pitch deck, but currently I can only accept LinkedIn URLs to analyze.

For now, you can upload your pitch deck to a file sharing service like Google Drive or Dropbox and share the key points with me in text form. I'll use that information to help you find relevant investors."""
        # Handle setting threshold
        elif "threshold" in user_message.lower() and any(x in user_message.lower() for x in ["set", "change", "update"]):
            # Try to extract a number
            threshold_match = re.search(r'0\.\d+', user_message)
            if threshold_match:
                try:
                    new_threshold = float(threshold_match.group(0))
                    new_threshold = max(0.0, min(1.0, new_threshold))  # Ensure between 0 and 1
                    threshold = new_threshold
                    # Update session data
                    session_data["threshold"] = threshold
                    
                    # Update global config so the agent will use the right threshold
                    import seed_pitcher.config as sp_config
                    sp_config.INVESTOR_THRESHOLD = threshold
                    logger.info(f"Updated global config INVESTOR_THRESHOLD to {sp_config.INVESTOR_THRESHOLD}")
                    
                    logger.info(f"Updated investor relevance threshold to: {threshold}")
                    console.print(f"[green]Updated investor relevance threshold to: {threshold}[/green]")
                    response = f"I've updated your investor relevance threshold to {threshold}. I'll use this for future investor analyses."
                except:
                    response = "I couldn't understand that threshold value. Please provide a number between 0 and 1, like 0.7."
            else:
                response = f"Your current investor relevance threshold is {threshold}. To change it, please provide a number between 0 and 1, like 'Set threshold to 0.7'."
        # Handle updating founder name
        elif ("name" in user_message.lower() or "founder" in user_message.lower()) and any(x in user_message.lower() for x in ["change", "update", "set"]):
            # Extract name (assume anything after "to" or after "name is")
            name_match = re.search(r'(?:to|is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', user_message)
            if name_match:
                founder_name = name_match.group(1).strip()
                startup_info["founder_name"] = founder_name
                config.FOUNDER_NAME = founder_name
                
                # Update session data
                session_data["founder_name"] = founder_name
                session_data["startup_info"]["founder_name"] = founder_name
                logger.info(f"Updated founder name to: {founder_name}")
                console.print(f"[green]Updated founder name to: {founder_name}[/green]")
                response = f"I've updated your name to {founder_name}. I'll use this in all future outreach messages."
            else:
                response = f"Your current name is set to {founder_name}. To change it, please say something like 'Change my name to John Smith'."
        # Handle updating elevator pitch
        elif "pitch" in user_message.lower() and any(x in user_message.lower() for x in ["update", "change", "new"]):
            if len(user_message) > 30:
                # Assume the entire message is the new pitch
                elevator_pitch = user_message
                startup_info["elevator_pitch"] = elevator_pitch
                
                # Update session data
                session_data["elevator_pitch"] = elevator_pitch
                session_data["startup_info"]["elevator_pitch"] = elevator_pitch
                logger.info(f"Updated elevator pitch: {elevator_pitch}")
                console.print(f"[green]Updated elevator pitch[/green]")
                
                # Reinitialize the agent with the new pitch
                with console.status("[bold green]Reinitializing SeedPitcher agent...[/bold green]"):
                    shared_agent = create_agent_graph(elevator_pitch, pitch_deck_text)
                    agent = shared_agent
                    session_data["agent"] = agent
                
                response = "Thanks for the updated pitch! I'll use this information to better analyze potential investors for your startup."
            else:
                response = """To update your elevator pitch, please provide a detailed description of your startup.

Include information about:
• The problem you're solving
• Your solution
• Target market
• Current stage
• What makes your startup unique"""
        # Handle help or other general queries
        elif "help" in user_message.lower() or user_message.strip() == "?":
            response = f"""SeedPitcher helps with your seed fundraising efforts!

To use SeedPitcher:
1. Send me LinkedIn profile URLs of potential investors to analyze
2. I'll score their relevance and draft personalized outreach messages
3. I'll help you understand which investors are most likely to be interested in your startup

Current settings:
• Founder name: {founder_name}
• Relevance threshold: {threshold}

Example: Send a message like 'Can you analyze this investor? https://www.linkedin.com/in/investor-profile/'"""
        elif "about" in user_message.lower() or "who are you" in user_message.lower():
            response = f"""I'm SeedPitcher, an AI agent designed to help early-stage startups with fundraising efforts.

I can analyze investor LinkedIn profiles, assess their relevance to your startup ({elevator_pitch}), and draft personalized outreach messages.

Send me LinkedIn profile URLs to get started!"""
        else:
            response = f"""I'm SeedPitcher, your fundraising assistant! I can help analyze potential investors and draft personalized messages.

To use me, simply send LinkedIn profile URLs of potential investors you'd like me to analyze. 

Current settings:
• Founder name: {founder_name}
• Relevance threshold: {threshold}

For example: https://www.linkedin.com/in/investor-name/"""
        
        # Send response
        logger.info(f"Sending response to user: {response[:100]}...")
        console.print(f"[green]Sending response to user (first 100 chars): {response[:100]}...[/green]")
        
        # If response is empty for some reason, send a fallback
        if not response.strip():
            fallback_response = """I'm here to help analyze potential investors. Please send me a LinkedIn URL to analyze, or ask for help if you need guidance.

For example: https://www.linkedin.com/in/investor-name/"""
            client.send_message(content=fallback_response)
        else:
            client.send_message(content=response)
    
    # Start the agent
    console.print(f"[bold green]Starting SeedPitcher agent with Pin AI (Agent ID: {agent_id})[/bold green]")
    console.print("Press Ctrl+C to stop the agent")
    
    try:
        client.start_and_run(
            on_message_callback=handle_message,
            agent_id=agent_id
        )
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        console.print("[yellow]Agent stopped by user[/yellow]")
    except Exception as e:
        logger.error(f"Error running agent: {str(e)}", exc_info=True)
        console.print(f"[red]Error running agent: {str(e)}[/red]")
    finally:
        # Cleanup resources
        console.print("[bold green]Shutting down agent...[/bold green]")
        logger.info("Pin AI agent shutting down")
        
        # Note: We don't shut down the browser server since it's now managed independently
        # and might be used by other processes. The user can stop it using the command:
        # seedpitcher browser-server stop