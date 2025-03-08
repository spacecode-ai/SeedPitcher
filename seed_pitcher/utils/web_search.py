"""Web search utilities for finding investor information."""

from typing import Dict, Any, List
import json
import seed_pitcher.config as config


def search_investor_info(
    name: str, company: str = "", fund: str = ""
) -> Dict[str, Any]:
    """Search for investor information on the web."""
    try:
        # Use Tavily if API key is available
        if config.TAVILY_API_KEY:
            return search_with_tavily(name, company, fund)
        else:
            # Fall back to LLM-based search simulation
            return simulate_search_results(name, company, fund)
    except Exception as e:
        print(f"Error during web search: {str(e)}")
        return {
            "recent_investments": [],
            "investment_stages": [],
            "investment_sectors": [],
            "startup_sectors": [],
            "error": str(e),
        }


def search_with_tavily(name: str, company: str = "", fund: str = "") -> Dict[str, Any]:
    """Search for investor information using Tavily API."""
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=config.TAVILY_API_KEY)

        # Create search queries
        queries = [
            f"{name} {fund if fund else company} recent investments",
            f"{fund if fund else company} portfolio companies",
            f"{name} investor profile angel vc",
        ]

        all_results = []
        for query in queries:
            search_result = client.search(query=query, search_depth="advanced")
            all_results.extend(search_result.get("results", []))

        # Process results to extract structured information
        investor_info = process_search_results(all_results, name, company, fund)
        return investor_info

    except ImportError:
        print("Tavily package not installed, falling back to simulated search")
        return simulate_search_results(name, company, fund)


def process_search_results(
    results: List[Dict[str, Any]], name: str, company: str, fund: str
) -> Dict[str, Any]:
    """Process search results to extract structured information."""
    # Combine all text into a corpus
    corpus = ""
    for result in results:
        corpus += result.get("content", "") + "\n"

    # Use the configured LLM to extract structured information
    from seed_pitcher.agents.graph import create_llm
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser

    llm = create_llm()

    template = """
    You are an expert in analyzing information about investors. I will provide you with text from web search 
    results about an investor, and I need you to extract key information about them.
    
    Investor name: {name}
    Company/Fund: {company_or_fund}
    
    Web search results: 
    {corpus}
    
    Based on these search results, extract the following information in JSON format:
    - recent_investments: A list of the investor's most recent investments (company names)
    - investment_stages: A list of investment stages they focus on (e.g., "Seed", "Series A", etc.)
    - investment_sectors: A list of sectors/industries they invest in
    - fund_size: The size of their fund, if mentioned
    - investment_range: The typical investment amount range, if mentioned
    
    If the information isn't available in the search results, use empty lists or empty strings.
    """

    prompt = ChatPromptTemplate.from_template(template)

    company_or_fund = fund if fund else company

    formatted_prompt = prompt.format(
        name=name,
        company_or_fund=company_or_fund,
        corpus=corpus[:10000],  # Limit corpus size to avoid token limits
    )

    response = llm.invoke([formatted_prompt])

    try:
        parser = JsonOutputParser()
        extracted_info = parser.parse(response.content)
    except Exception:
        # If parsing fails, return empty structure
        extracted_info = {
            "recent_investments": [],
            "investment_stages": [],
            "investment_sectors": [],
            "fund_size": "",
            "investment_range": "",
        }

    return extracted_info


def simulate_search_results(
    name: str, company: str = "", fund: str = ""
) -> Dict[str, Any]:
    """Simulate search results when actual search is not available."""
    # Placeholder implementation that returns simulated data
    # In a real implementation, this would be replaced with actual web search

    # Sample data structures
    tech_sectors = [
        "SaaS",
        "AI",
        "Machine Learning",
        "Fintech",
        "Healthtech",
        "E-commerce",
    ]
    non_tech_sectors = ["Retail", "Healthcare", "Finance", "Education", "Manufacturing"]
    stages = ["Pre-seed", "Seed", "Series A", "Series B", "Growth"]

    # Generate simulated data based on input
    import random
    import hashlib

    # Create a deterministic but seemingly random output based on input
    seed = hashlib.md5((name + company + fund).encode()).hexdigest()
    random.seed(seed)

    # Decide if this is a tech investor or broader focus
    is_tech_focused = random.random() < config.INVESTOR_THRESHOLD  # 70% chance of tech focus

    # Select relevant sectors
    if is_tech_focused:
        sector_pool = tech_sectors
    else:
        sector_pool = tech_sectors + non_tech_sectors

    num_sectors = random.randint(1, 4)
    investment_sectors = random.sample(sector_pool, min(num_sectors, len(sector_pool)))

    # Select stages
    num_stages = random.randint(1, 3)
    investment_stages = random.sample(stages, min(num_stages, len(stages)))
    if "Fund" in fund or "Capital" in fund or "Ventures" in fund:
        # Real funds typically have more concentrated stage focus
        investment_stages = investment_stages[:1]

    # Generate some realistic-sounding company names for recent investments
    company_prefixes = [
        "Acme",
        "Nova",
        "Quantum",
        "Apex",
        "Zenith",
        "Flux",
        "Helix",
        "Echo",
    ]
    company_suffixes = [
        "AI",
        "Tech",
        "Labs",
        "Systems",
        "Networks",
        "Health",
        "Finance",
        "Robotics",
    ]

    num_investments = random.randint(0, 6)
    recent_investments = []
    for _ in range(num_investments):
        company_name = random.choice(company_prefixes) + random.choice(company_suffixes)
        recent_investments.append(company_name)

    return {
        "recent_investments": recent_investments,
        "investment_stages": investment_stages,
        "investment_sectors": investment_sectors,
        "fund_size": f"${random.randint(1, 500)}M" if random.random() < 0.5 else "",
        "investment_range": f"${random.randint(50, 500)}K - ${random.randint(1, 10)}M"
        if random.random() < 0.5
        else "",
        "is_simulated": True,  # Flag to indicate this is simulated data
    }
