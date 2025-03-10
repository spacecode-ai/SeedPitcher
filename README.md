# SeedPitcher

An agentic system to assist with seed fundraising for early-stage startups. SeedPitcher helps founders identify potential investors from their LinkedIn connections and draft personalized outreach messages.

## Features

- Interactive CLI interface
- Built with LangGraph for a robust agent workflow system
- Extracts information from pitch decks to enrich your outreach
- Uses browser automation to analyze LinkedIn profiles
- Supports either simular.ai browser (preferred) or connects to your existing Chrome browser
- Identifies investors among your LinkedIn connections
- Searches for web information about potential investors
- Analyzes investor fit based on investment history, stages, and sectors
- Drafts personalized outreach messages
- Never sends messages automatically - you always have the final say
- Supports integration with Pin AI platform for chat-based interaction

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/seedpitcher.git
cd seedpitcher

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate

# Install the package
pip install -e .
```

## Requirements

- Python 3.10+
- LinkedIn account (you must be logged in to LinkedIn in your browser)
- API keys for LLMs (OpenAI, Anthropic, or DeepSeek)
- Optional: simular.ai browser (if not available, will fall back to Playwright)
- Optional: Pin AI API key (for Pin AI platform integration)

## Usage

```bash
# Basic usage
seedpitcher run

# With a pitch deck
seedpitcher run --pitch-deck /path/to/your/pitch_deck.pdf

# With specific LinkedIn profile URLs
seedpitcher run --linkedin-urls https://linkedin.com/in/profile1 https://linkedin.com/in/profile2

# Set scoring threshold
seedpitcher run --threshold 0.8

# Choose LLM model
seedpitcher run --llm-model claude-3-7

seedpitcher run --founder-name "Your Name"

### Using Pin AI Integration

SeedPitcher can be deployed as an agent on the Pin AI platform, allowing users to interact with it through chat:

```bash
# Register a new agent on the Pin AI platform
seedpitcher pinai --pinai-key "your-pinai-api-key" --pitch-deck /path/to/your/pitch_deck.pdf --founder-name "Your Name" --register-only

# Start an existing agent (using previously registered agent-id)
seedpitcher pinai --pinai-key "your-pinai-api-key" --pitch-deck /path/to/your/pitch_deck.pdf --agent-id 123

# Start with alternative model
seedpitcher pinai --llm-model gpt-4o --pitch-deck /path/to/your/pitch_deck.pdf
```

Once running as a Pin AI agent, users can interact with SeedPitcher by sending LinkedIn URLs to be analyzed through the Pin AI chat interface.

## Configuration

SeedPitcher will create a configuration file at `~/.seed_pitcher/config.json`. You can edit this file to configure:

- API keys (OpenAI, Anthropic, DeepSeek, Pin AI)
- Browser preferences
- Remote debugging port (if using Playwright)
- Default investor scoring threshold
- Founder name for personalized messages

## Browser Setup

### Using simular.ai (recommended):

Install the simular.ai package:

```bash
pip install pysimular
```

### Using Playwright with your existing Chrome browser:

Start Chrome with remote debugging enabled:

```bash
# On macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# On Windows
start chrome --remote-debugging-port=9222

# On Linux
google-chrome --remote-debugging-port=9222
```

Then set the browser type in the configuration:

```json
{
  "browser_type": "playwright",
  "remote_debugging_port": 9222
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
