"""Configuration management for SeedPitcher."""

import os
from pathlib import Path
from typing import Dict, Any

# Default configuration
INVESTOR_THRESHOLD = 0.5
LLM_MODEL = "claude"
BROWSER_TYPE = "playwright"
REMOTE_DEBUGGING_PORT = 9222

# API keys (to be loaded from environment or config)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# File paths
CONFIG_DIR = Path.home() / ".seed_pitcher"
CONFIG_FILE = CONFIG_DIR / "config.json"


def update_config(config_dict: Dict[str, Any]) -> None:
    """Update global configuration with values from config file."""
    global INVESTOR_THRESHOLD, LLM_MODEL, BROWSER_TYPE, REMOTE_DEBUGGING_PORT
    global OPENAI_API_KEY, ANTHROPIC_API_KEY, DEEPSEEK_API_KEY, TAVILY_API_KEY

    if "investor_threshold" in config_dict:
        INVESTOR_THRESHOLD = config_dict["investor_threshold"]

    if "llm_model" in config_dict:
        LLM_MODEL = config_dict["llm_model"]

    if "browser_type" in config_dict:
        BROWSER_TYPE = config_dict["browser_type"]

    if "remote_debugging_port" in config_dict:
        REMOTE_DEBUGGING_PORT = config_dict["remote_debugging_port"]

    # Load API keys from config if not in environment
    if "openai_api_key" in config_dict and not OPENAI_API_KEY:
        OPENAI_API_KEY = config_dict["openai_api_key"]

    if "anthropic_api_key" in config_dict and not ANTHROPIC_API_KEY:
        ANTHROPIC_API_KEY = config_dict["anthropic_api_key"]

    if "deepseek_api_key" in config_dict and not DEEPSEEK_API_KEY:
        DEEPSEEK_API_KEY = config_dict["deepseek_api_key"]

    if "tavily_api_key" in config_dict and not TAVILY_API_KEY:
        TAVILY_API_KEY = config_dict["tavily_api_key"]
