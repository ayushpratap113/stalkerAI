import os
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from langchain_community.retrievers import ArxivRetriever
from langchain_community.retrievers import TavilySearchAPIRetriever
from langchain_core.documents import Document
from langchain.tools import Tool, BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun, CallbackManager, StdOutCallbackHandler
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.tracers import ConsoleCallbackHandler
from pydantic import Field
import logging
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Import scrapers
from scraper.github_scraper import GitHubScraper
from scraper.linkedin_scraper import LinkedInScraper

# Import configuration
from utils.config import (
    OPENAI_API_KEY, 
    TAVILY_API_KEY, 
    GITHUB_TOKEN,
    LINKEDIN_USERNAME,
    LINKEDIN_PASSWORD,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RATE_LIMIT_PAUSE
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a dedicated cost logger
cost_logger = logging.getLogger('cost_tracker')
cost_logger.setLevel(logging.INFO)

# Configure file handler for cost logs if needed
cost_file_handler = logging.FileHandler('api_costs.log')
cost_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
cost_logger.addHandler(cost_file_handler)

# Cost constants (current as of April 2025)
TAVILY_COST_PER_SEARCH = 0.01  # $0.01 per search
OPENAI_COSTS = {
    "gpt-4o-mini": {
        "input": 0.000005,  # $0.000005 per input token
        "output": 0.000015  # $0.000015 per output token
    },
    "gpt-4o": {
        "input": 0.00001,   # $0.00001 per input token
        "output": 0.00003   # $0.00003 per output token
    },
    "gpt-3.5-turbo": {
        "input": 0.0000015, # $0.0000015 per input token
        "output": 0.000002  # $0.000002 per output token
    }
}

class CostTrackingCallback(BaseCallbackHandler):
    """Callback handler for tracking API usage and estimating costs."""
    
    def __init__(self):
        """Initialize with counters for different API calls."""
        self.session_id = str(uuid.uuid4())[:8]  # Create a unique session ID
        cost_logger.info(f"Starting new cost tracking session: {self.session_id}")
        
        self.tavily_searches = 0
        self.openai_usage = {
            "total_tokens": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": None
        }
        self.arxiv_searches = 0
        self.github_api_calls = 0
        self.linkedin_scrapes = 0
        self.current_query = ""  # Store query for context
    
    def on_retriever_start(self, serialized: Dict[str, Any], query: str, **kwargs):
        """Track when a retriever is called."""
        self.current_query = query
        retriever_type = serialized.get("name", "")
        
        if "Tavily" in retriever_type:
            self.tavily_searches += 1
            cost_logger.info(
                f"COST: [SESSION:{self.session_id}] Tavily search API call - "
                f"${TAVILY_COST_PER_SEARCH:.4f} - Query: \"{query[:50]}...\""
            )
        elif "Arxiv" in retriever_type:
            self.arxiv_searches += 1
            cost_logger.info(
                f"COST: [SESSION:{self.session_id}] ArXiv search API call - "
                f"$0.00 (free) - Query: \"{query[:50]}...\""
            )
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """Track when the LLM is called."""
        self.openai_usage["model"] = serialized.get("name", "")
        model_name = serialized.get("name", "unknown")
        prompt_preview = prompts[0][:50] if prompts else "No prompt"
        
        cost_logger.info(
            f"COST: [SESSION:{self.session_id}] OpenAI LLM call started - "
            f"Model: {model_name} - Prompt: \"{prompt_preview}...\""
        )
    
    def on_llm_end(self, response, **kwargs):
        """Track token usage when LLM completes."""
        if hasattr(response, "llm_output") and response.llm_output is not None:
            llm_output = response.llm_output
            if isinstance(llm_output, dict) and "token_usage" in llm_output:
                usage = llm_output["token_usage"]
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                
                # Update counters
                self.openai_usage["prompt_tokens"] += prompt_tokens
                self.openai_usage["completion_tokens"] += completion_tokens
                self.openai_usage["total_tokens"] += total_tokens
                
                # Calculate cost
                model = self.openai_usage["model"] or "gpt-4o-mini"
                # Extract the base model name without version specifics
                for known_model in OPENAI_COSTS:
                    if known_model in model:
                        model = known_model
                        break
                
                model_costs = OPENAI_COSTS.get(model, OPENAI_COSTS["gpt-3.5-turbo"])
                prompt_cost = prompt_tokens * model_costs["input"]
                completion_cost = completion_tokens * model_costs["output"]
                total_cost = prompt_cost + completion_cost
                
                cost_logger.info(
                    f"COST: [SESSION:{self.session_id}] OpenAI LLM call completed - "
                    f"Model: {model} - Tokens: {prompt_tokens} in / {completion_tokens} out - "
                    f"Cost: ${total_cost:.6f}"
                )
    
    def log_tool_usage(self, tool_name: str, input_data: Any):
        """Track when a tool is called."""
        if "github" in tool_name.lower():
            self.github_api_calls += 1
            cost_logger.info(
                f"COST: [SESSION:{self.session_id}] GitHub API call - "
                f"$0.00 (free) - Input: \"{str(input_data)[:50]}...\""
            )
        elif "linkedin" in tool_name.lower():
            self.linkedin_scrapes += 1
            cost_logger.info(
                f"COST: [SESSION:{self.session_id}] LinkedIn scrape - "
                f"$0.00 (free but resource-intensive) - Input: \"{str(input_data)[:50]}...\""
            )
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Calculate and return cost summary."""
        tavily_cost = self.tavily_searches * TAVILY_COST_PER_SEARCH
        
        model = self.openai_usage["model"] or "gpt-4o-mini"
        # Extract the base model name without version specifics
        for known_model in OPENAI_COSTS:
            if known_model in model:
                model = known_model
                break
        
        model_costs = OPENAI_COSTS.get(model, OPENAI_COSTS["gpt-3.5-turbo"])
        openai_cost = (
            self.openai_usage["prompt_tokens"] * model_costs["input"] +
            self.openai_usage["completion_tokens"] * model_costs["output"]
        )
        
        total_cost = tavily_cost + openai_cost
        
        # Log the cost summary
        cost_logger.info(
            f"COST SUMMARY: [SESSION:{self.session_id}] "
            f"Total: ${total_cost:.6f} | "
            f"Tavily: ${tavily_cost:.6f} ({self.tavily_searches} searches) | "
            f"ArXiv: $0.00 ({self.arxiv_searches} searches) | "
            f"GitHub: $0.00 ({self.github_api_calls} API calls) | "
            f"LinkedIn: $0.00 ({self.linkedin_scrapes} scrapes) | "
            f"OpenAI: ${openai_cost:.6f} ({self.openai_usage['total_tokens']} tokens)"
        )
        
        return {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "query": self.current_query,
            "tavily": {
                "searches": self.tavily_searches,
                "cost": round(tavily_cost, 6)
            },
            "arxiv": {
                "searches": self.arxiv_searches,
                "cost": 0.0  # ArXiv is free
            },
            "github": {
                "api_calls": self.github_api_calls,
                "cost": 0.0  # GitHub API is free for public access
            },
            "linkedin": {
                "scrapes": self.linkedin_scrapes,
                "cost": 0.0  # LinkedIn scraping has no direct API cost
            },
            "openai": {
                "model": self.openai_usage["model"],
                "tokens": {
                    "prompt": self.openai_usage["prompt_tokens"],
                    "completion": self.openai_usage["completion_tokens"],
                    "total": self.openai_usage["total_tokens"]
                },
                "cost": round(openai_cost, 6)
            },
            "total_cost": round(total_cost, 6)
        }


# --- Tool Definitions ---

# Tavily Search Tool
tavily_retriever = TavilySearchAPIRetriever(k=5, api_key=TAVILY_API_KEY)
search_tavily = Tool(
    name="search_tavily",
    func=tavily_retriever.invoke,
    coroutine=tavily_retriever.ainvoke,
    description="Searches the web using Tavily for general information, news, or finding profile URLs. Input should be a search query."
)

# Arxiv Search Tool
arxiv_retriever = ArxivRetriever(load_max_docs=3)
search_arxiv = Tool(
    name="search_arxiv",
    func=arxiv_retriever.get_relevant_documents,
    description="Searches ArXiv for academic papers, preprints, and research articles. Useful for finding technical publications by a person. Input should be a search query (e.g., author name or topic)."
)


# GitHub Scraper Tool
class GitHubScraperTool(BaseTool):
    name: str = "scrape_github"
    description: str = "Scrapes a GitHub user's profile for repositories, languages, contributions, and profile details. Input should be the GitHub username."

    def _run(self, username: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> Dict[str, Any]:
        # Synchronous wrapper
        return asyncio.run(self._arun(username, run_manager=run_manager))

    async def _arun(self, username: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> Dict[str, Any]:
        logger.info(f"Attempting to scrape GitHub profile: {username}")
        try:
            # Track the GitHub API usage
            if run_manager and hasattr(run_manager, "handlers"):
                for handler in run_manager.handlers:
                    if isinstance(handler, CostTrackingCallback):
                        handler.log_tool_usage("scrape_github", username)
            
            result = GitHubScraper.scrape(username, GITHUB_TOKEN)
            
            # Add metadata to result
            result['_mcp_metadata'] = {
                'source': 'github_api',
                'timestamp': datetime.now().isoformat(),
                'confidence': 0.9 if result.get('success', False) else 0.5
            }
            
            logger.info(f"Successfully scraped GitHub profile for {username}")
            return result
        except Exception as e:
            logger.error(f"Error scraping GitHub profile {username}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to scrape GitHub profile {username}: {e}",
                "_mcp_metadata": {
                    'source': 'github_api',
                    'timestamp': datetime.now().isoformat(),
                    'confidence': 0.0
                }
            }


# LinkedIn Scraper Tool
class LinkedInScraperTool(BaseTool):
    name: str = "scrape_linkedin"
    description: str = "Scrapes a LinkedIn public profile URL for professional information like headline, work history, education, and skills. Input must be a valid LinkedIn profile URL."

    def _run(self, profile_url: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> Dict[str, Any]:
        return asyncio.run(self._arun(profile_url, run_manager=run_manager))

    async def _arun(self, profile_url: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> Dict[str, Any]:
        logger.info(f"Attempting to scrape LinkedIn profile: {profile_url}")
        
        # Track the LinkedIn scraper usage
        if run_manager and hasattr(run_manager, "handlers"):
            for handler in run_manager.handlers:
                if isinstance(handler, CostTrackingCallback):
                    handler.log_tool_usage("scrape_linkedin", profile_url)
        
        try:
            # Check if we have credentials
            if not LINKEDIN_USERNAME or not LINKEDIN_PASSWORD:
                return {
                    "success": False,
                    "error": "LinkedIn credentials not configured",
                    "_mcp_metadata": {
                        'source': 'linkedin_scraper',
                        'timestamp': datetime.now().isoformat(),
                        'confidence': 0.0
                    }
                }
            
            linkedin_credentials = {
                'username': LINKEDIN_USERNAME,
                'password': LINKEDIN_PASSWORD
            }
            
            # Use the async version of LinkedIn scraper
            result = await LinkedInScraper.scrape_async(profile_url, linkedin_credentials)
            
            # Add metadata to result
            result['_mcp_metadata'] = {
                'source': 'linkedin_scraper',
                'timestamp': datetime.now().isoformat(),
                'confidence': 0.8 if result.get('success', False) else 0.4
            }
            
            logger.info(f"Successfully scraped LinkedIn profile: {profile_url}")
            return result
        except Exception as e:
            logger.error(f"Error scraping LinkedIn profile {profile_url}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Failed to scrape LinkedIn profile {profile_url}: {e}",
                "_mcp_metadata": {
                    'source': 'linkedin_scraper',
                    'timestamp': datetime.now().isoformat(),
                    'confidence': 0.0
                }
            }


# Initialize tools
scrape_github_tool = GitHubScraperTool()
scrape_linkedin_tool = LinkedInScraperTool()


# --- Tool Management ---
def get_available_tools(persona_sources: List[str]) -> List[BaseTool]:
    """Returns a list of tools relevant to the persona's data sources."""
    tool_map = {
        "tavily": search_tavily,
        "arxiv": search_arxiv,
        "github": scrape_github_tool,
        "linkedin": scrape_linkedin_tool,
        # Add more tools as they are implemented
        # "stackoverflow": stackoverflow_tool,
        # "newsapi": newsapi_tool,
    }
    
    # Filter tools based on persona_sources, always include tavily as fallback
    available_tools = [tool_map[src] for src in persona_sources if src in tool_map]
    
    # If tavily isn't already included, add it as a fallback search tool
    if "tavily" not in persona_sources and "tavily" in tool_map:
        available_tools.append(tool_map["tavily"])
        
    return available_tools


class MultiSourceRetriever:
    """
    A retriever that combines results from multiple sources and exposes them as tools.
    """
    
    def __init__(self):
        """Initialize the MultiSourceRetriever."""
        # Create our cost tracking callback
        self.cost_tracker = CostTrackingCallback()
        
        # Log initialization
        logger.info("MultiSourceRetriever initialized")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get the cost summary for all operations."""
        return self.cost_tracker.get_cost_summary()
    
    def get_callback_manager(self) -> CallbackManager:
        """Get a callback manager with cost tracking."""
        return CallbackManager([self.cost_tracker, ConsoleCallbackHandler()])


# Example usage
if __name__ == "__main__":
    # Example of using the tools directly
    retriever = MultiSourceRetriever()
    
    async def test_tools():
        # Test GitHub tool
        github_result = await scrape_github_tool._arun("langchain-ai")
        print(f"\nGitHub Result for 'langchain-ai':")
        print(json.dumps(github_result, indent=2)[:500] + "...")
        
        # Test LinkedIn tool (replace with a real profile URL)
        linkedin_url = "https://www.linkedin.com/in/nityanandmathur/"
        linkedin_result = await scrape_linkedin_tool._arun(linkedin_url)
        print(f"\nLinkedIn Result for '{linkedin_url}':")
        print(json.dumps(linkedin_result, indent=2)[:500] + "...")
        
        # Test Tavily search
        tavily_docs = tavily_retriever.get_relevant_documents("LangChain AI framework")
        print(f"\nTavily Search Results for 'LangChain AI framework':")
        for i, doc in enumerate(tavily_docs[:2]):
            print(f"Result {i+1}: {doc.page_content[:100]}...")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
        
        # Print cost summary
        cost_summary = retriever.get_cost_summary()
        print("\nCost Summary:")
        print(json.dumps(cost_summary, indent=2))
    
    # Run the async test
    asyncio.run(test_tools())