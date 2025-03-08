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

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/seed-pitcher.git
cd seed-pitcher

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

## Usage

```bash
# Basic usage
seed-pitcher run

# With a pitch deck
seed-pitcher run --pitch-deck /path/to/your/pitch_deck.pdf

# With specific LinkedIn profile URLs
seed-pitcher run --linkedin-urls https://linkedin.com/in/profile1 https://linkedin.com/in/profile2

# Set scoring threshold
seed-pitcher run --threshold 0.8

# Choose LLM model
seed-pitcher run --llm-model claude-3-7
```

## Configuration

SeedPitcher will create a configuration file at `~/.seed_pitcher/config.json`. You can edit this file to configure:

- API keys
- Browser preferences
- Remote debugging port (if using Playwright)
- Default investor scoring threshold

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
