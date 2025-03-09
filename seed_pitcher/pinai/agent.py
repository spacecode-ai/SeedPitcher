"""Pin AI integration for SeedPitcher.

This module implements the Pin AI agent functionality for SeedPitcher, enabling
users to interact with the SeedPitcher system through the Pin AI platform.
"""

import os
import re
import logging
from typing import Dict, Any, Optional, Callable
from rich.console import Console

# Import Pin AI SDK
from pinai_agent_sdk import PINAIAgentSDK, AGENT_CATEGORY_SOCIAL

# Import from seed_pitcher
from seed_pitcher import config
from seed_pitcher.browsers import get_browser
from seed_pitcher.agents.graph import create_agent_graph
from seed_pitcher.utils.pdf import extract_text_from_pdf

# Configure logging
logger = logging.getLogger("seed_pitcher.pinai")
console = Console()


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
            user_sessions[session_id] = {
                "elevator_pitch": "",
                "pitch_deck_text": "",
                "founder_name": config.FOUNDER_NAME or "",
                "threshold": config.INVESTOR_THRESHOLD,
                "startup_info": {
                    "elevator_pitch": "",
                    "pitch_deck_text": "",
                    "founder_name": config.FOUNDER_NAME or "",
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

Would you like to set a relevance threshold for investors? This is a score from 0-1 that determines which investors are considered a good match for your startup.

The default is 0.5. You can say "use default" or provide a specific value like "0.7" or "0.3"."""
            client.send_message(content=response)
            return
        elif not session_data["onboarding_complete"]:
            # We have elevator pitch and founder name but need threshold confirmation
            if "default" in user_message.lower() or "0.5" in user_message:
                threshold = config.INVESTOR_THRESHOLD  # Use default
            else:
                # Try to extract a number
                threshold_match = re.search(r'0\.\d+', user_message)
                if threshold_match:
                    try:
                        threshold = float(threshold_match.group(0))
                        threshold = max(0.0, min(1.0, threshold))  # Ensure between 0 and 1
                    except:
                        threshold = config.INVESTOR_THRESHOLD
            
            # Update session data
            session_data["threshold"] = threshold
            
            logger.info(f"Set investor relevance threshold to: {threshold}")
            console.print(f"[green]Set investor relevance threshold to: {threshold}[/green]")
            
            # Initialize the agent now that we have the basic info
            with console.status("[bold green]Initializing SeedPitcher agent...[/bold green]"):
                if shared_agent is None:
                    shared_agent = create_agent_graph(elevator_pitch, pitch_deck_text)
                agent = shared_agent
                session_data["agent"] = agent
                session_data["onboarding_complete"] = True
            
            response = f"""Great! I've set your investor relevance threshold to {threshold}.
            
I'm now ready to help you with your fundraising. You can:

1. Send me LinkedIn URLs of potential investors to analyze (e.g., https://www.linkedin.com/in/investor-name/)
2. Ask for help or guidance on fundraising strategies
3. Type "help" any time for more information

What would you like to do first?"""
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
            
            # Initialize browser once for all URLs
            browser = None
            try:
                browser = get_browser()
            except Exception as e:
                error_msg = f"Error initializing browser: {str(e)}"
                logger.error(error_msg, exc_info=True)
                console.print(f"[red]{error_msg}[/red]")
                client.send_message(content=f"Sorry, I encountered an error initializing the browser: {error_msg}")
                return
            
            # Process each LinkedIn URL
            for url in linkedin_urls:
                # Create a state for processing this URL
                state = {
                    "action": "analyze_profile",
                    "startup_info": startup_info,
                    "current_profile": {},
                    "investor_score": 0.0,
                    "investor_analysis": {},
                    "message_draft": "",
                    "founder_name": founder_name,
                    "history": [],
                    "urls_to_process": [url],
                    "browser": browser,
                    "url": url,  # Direct URL to analyze
                }
                
                logger.info(f"Processing URL: {url}")
                console.print(f"[green]Processing URL: {url}[/green]")
                
                # Let user know we're working on it
                client.send_message(content=f"Analyzing {url}... This might take a minute or two. I'll get back to you soon!")
                
                # Process the URL with the agent
                try:
                    # Run the agent
                    if agent is None:
                        # Make sure we have an agent initialized
                        if shared_agent is None:
                            logger.info("Initializing agent on demand for LinkedIn analysis")
                            console.print("[yellow]Initializing agent on demand for LinkedIn analysis[/yellow]")
                            shared_agent = create_agent_graph(elevator_pitch, pitch_deck_text)
                        agent = shared_agent
                        session_data["agent"] = agent
                    
                    result = agent.invoke(state)
                    
                    # Make sure we're using the right threshold from the session
                    threshold = session_data["threshold"]
                    logger.info(f"Using threshold: {threshold}")
                    
                    if result.get("investor_score", 0) >= threshold:
                        # Investor is relevant
                        profile_name = result.get("current_profile", {}).get("name", "This investor")
                        score_info = f"{profile_name} scored {result.get('investor_score', 0):.2f}/1.0 (threshold: {threshold})"
                        
                        response += f"I've analyzed {url}\n\n{score_info}\n\n"
                        
                        # Include message draft if available
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
                        response += f"I've analyzed {url}\n\n{profile_name} scored {result.get('investor_score', 0):.2f}/1.0, which is below your threshold of {threshold}. This investor may not be the best fit for your startup.\n\n"
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
        # Clean up browser if it exists
        try:
            if 'browser' in locals() and browser:
                browser.close()
        except:
            pass