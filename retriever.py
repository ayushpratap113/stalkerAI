import os
from typing import List, Dict, Any, Optional, Tuple
from langchain_community.retrievers import ArxivRetriever
from langchain_community.retrievers import TavilySearchAPIRetriever
from langchain_core.documents import Document
from langchain.prompts import PromptTemplate
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain_openai import ChatOpenAI
import logging
import json
import uuid
from datetime import datetime
from dotenv import load_dotenv
from langchain_core.callbacks import CallbackManager, StdOutCallbackHandler
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.tracers import ConsoleCallbackHandler

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create a dedicated cost logger
cost_logger = logging.getLogger('cost_tracker')
cost_logger.setLevel(logging.INFO)

# Configure file handler for cost logs if needed
# Uncomment these lines to save costs to a separate file
"""
cost_file_handler = logging.FileHandler('api_costs.log')
cost_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
cost_logger.addHandler(cost_file_handler)
"""

# Cost constants (current as of March 2025)
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
        cost_logger.info(f"COST SUMMARY: [SESSION:{self.session_id}] "
                        f"Total: ${total_cost:.6f} | "
                        f"Tavily: ${tavily_cost:.6f} ({self.tavily_searches} searches) | "
                        f"ArXiv: $0.00 ({self.arxiv_searches} searches) | "
                        f"OpenAI: ${openai_cost:.6f} ({self.openai_usage['total_tokens']} tokens)")
        
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

class MultiSourceRetriever:
    """
    A retriever that combines results from multiple sources including 
    ArxivRetriever and TavilySearchAPIRetriever.
    """
    
    def __init__(self):
        """Initialize the MultiSourceRetriever using API keys from environment variables."""
        # Create our cost tracking callback
        self.cost_tracker = CostTrackingCallback()
        callback_manager = CallbackManager([self.cost_tracker, ConsoleCallbackHandler()])
        
        # Initialize retrievers
        try:
            self.arxiv_retriever = ArxivRetriever(load_max_docs=3)
            self.tavily_retriever = TavilySearchAPIRetriever(k=3)  # k specifies the number of results
            
            # Ensure the OpenAI API key is set
            if "OPENAI_API_KEY" not in os.environ:
                raise ValueError("OPENAI_API_KEY is not set. Please set it in your environment variables.")
            
            # Initialize LLM with callback manager for cost tracking
            self.llm = ChatOpenAI(
                temperature=0, 
                model="gpt-4o-mini",
                callbacks=[self.cost_tracker]
            )
            
            # Create tools for the agent to use
            self.tools = [
                Tool(
                    name="ArxivSearch",
                    func=self._search_arxiv,
                    description="Search for academic papers on Arxiv related to the query"
                ),
                Tool(
                    name="WebSearch",
                    func=self._search_web,
                    description="Search the web for information about a person or topic"
                )
            ]
            
            # Initialize the agent with callbacks
            self.agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True,
                callbacks=[self.cost_tracker]
            )
            
            logger.info("MultiSourceRetriever initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize retrievers: {str(e)}")
            raise
    
    def _search_arxiv(self, query: str) -> List[Dict[str, str]]:
        """Search for academic papers on Arxiv."""
        try:
            # Manually track Arxiv search since it doesn't support callbacks
            self.cost_tracker.arxiv_searches += 1
            cost_logger.info(
                f"COST: [SESSION:{self.cost_tracker.session_id}] ArXiv search API call - "
                f"$0.00 (free) - Query: \"{query[:50]}...\""
            )
            
            results = self.arxiv_retriever.get_relevant_documents(query)
            if not results:
                logger.info(f"No results found on Arxiv for query: {query}")
                return []
            
            # Format results
            formatted_results = []
            for doc in results[:10]:
                metadata = doc.metadata
                formatted_results.append({
                    "title": metadata.get("Title", "No title"),
                    "url": metadata.get("Entry ID", "No URL"),
                    "summary": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Error in Arxiv search: {str(e)}")
            return []
    
    def _search_web(self, query: str) -> List[Dict[str, str]]:
        """Search the web using Tavily API."""
        try:
            # Manually track Tavily search since it may not trigger callback
            self.cost_tracker.tavily_searches += 1
            cost_logger.info(
                f"COST: [SESSION:{self.cost_tracker.session_id}] Tavily search API call - "
                f"${TAVILY_COST_PER_SEARCH:.4f} - Query: \"{query[:50]}...\""
            )
            
            results = self.tavily_retriever.get_relevant_documents(query)
            if not results:
                logger.info(f"No results found on web for query: {query}")
                return []
            
            # Format results
            formatted_results = []
            for doc in results[:10]:
                metadata = doc.metadata
                formatted_results.append({
                    "title": metadata.get("title", "No title"),
                    "url": metadata.get("source", "No URL"),
                    "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            return formatted_results
        except Exception as e:
            logger.error(f"Error in web search: {str(e)}")
            return []
    
    def search(self, query: str, return_costs: bool = False) -> Dict[str, Any]:
        """Perform a comprehensive search using multiple sources."""
        try:
            # Reset the cost tracker for this search
            self.cost_tracker = CostTrackingCallback()
            logger.info(f"Starting search with cost tracking session {self.cost_tracker.session_id}")
            
            # Create the prompt for the agent
            prompt = f"""
            I need to find information about: {query}
            First, search for academic publications by or about this person on Arxiv.
            Then, search the web for general information about this person.
            Provide the top 10 most relevant results from each source.
            """
            
            # Run the agent
            result = self.agent.run(prompt)
            
            # Since the agent response might be in various formats, we'll also 
            # explicitly get results from each source
            arxiv_results = self._search_arxiv(query)
            web_results = self._search_web(query)
            
            # Get cost summary
            cost_summary = self.cost_tracker.get_cost_summary()
            
            # Log overall cost for this search operation
            logger.info(
                f"Search completed [session:{self.cost_tracker.session_id}] - "
                f"Total cost: ${cost_summary['total_cost']}"
            )
            
            # Prepare response
            response = {
                "agent_response": result,
                "arxiv_results": arxiv_results,
                "web_results": web_results
            }
            
            # Include cost information if requested
            if return_costs:
                response["costs"] = cost_summary
                
            return response
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            response = {
                "error": str(e),
                "arxiv_results": [],
                "web_results": []
            }
            
            if return_costs:
                response["costs"] = self.cost_tracker.get_cost_summary()
                
            return response
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get the cost summary for all operations."""
        cost_summary = self.cost_tracker.get_cost_summary()
        logger.info(f"Current cost summary - Total: ${cost_summary['total_cost']}")
        return cost_summary
    
    def get_top_urls(self, query: str, return_costs: bool = False) -> Dict[str, Any]:
        """Get only the top 3 URLs from the search results."""
        try:
            # Reset the cost tracker for this search
            self.cost_tracker = CostTrackingCallback()
            logger.info(f"Starting URL retrieval with cost tracking session {self.cost_tracker.session_id}")
            
            # Search web first as it's likely more relevant for person queries
            web_results = self._search_web(query)
            arxiv_results = self._search_arxiv(query)
            
            urls = []
            
            # Add web URLs
            for result in web_results:
                if "url" in result and result["url"]:
                    urls.append(result["url"])
            
            # Add arxiv URLs
            for result in arxiv_results:
                if "url" in result and result["url"]:
                    urls.append(result["url"])
            
            # Get unique URLs
            unique_urls = list(dict.fromkeys(urls))[:3]
            
            # Get cost summary
            cost_summary = self.cost_tracker.get_cost_summary()
            
            # Log overall cost for this URL retrieval operation
            logger.info(
                f"URL retrieval completed [session:{self.cost_tracker.session_id}] - "
                f"Found {len(unique_urls)} URLs - Total cost: ${cost_summary['total_cost']}"
            )
            
            response = {
                "urls": unique_urls
            }
            
            if return_costs:
                response["costs"] = cost_summary
                
            return response
                
        except Exception as e:
            logger.error(f"Error getting top URLs: {str(e)}")
            response = {
                "urls": [],
                "error": str(e)
            }
            
            if return_costs:
                response["costs"] = self.cost_tracker.get_cost_summary()
                
            return response

# Example usage
if __name__ == "__main__":
    retriever = MultiSourceRetriever()
    
    # Example search
    query = "Geoffrey Hinton neural networks"
    print(f"Searching for: {query}")
    
    # Get just the top URLs with cost tracking
    url_results = retriever.get_top_urls(query, return_costs=True)
    print("\nTop 3 URLs:")
    for i, url in enumerate(url_results["urls"], 1):
        print(f"{i}. {url}")
    
    # Print cost summary for the URL retrieval
    if "costs" in url_results:
        print("\nCost Summary for URL Retrieval:")
        print(json.dumps(url_results["costs"], indent=2))
    
    # Get full search results with cost tracking
    search_results = retriever.search(query, return_costs=True)
    
    # Print cost summary for the full search
    if "costs" in search_results:
        print("\nCost Summary for Full Search:")
        print(json.dumps(search_results["costs"], indent=2))
    
    print("\nSearch Results Summary:")
    print(f"Agent response length: {len(search_results.get('agent_response', ''))}")
    print(f"Arxiv results: {len(search_results.get('arxiv_results', []))}")
    print(f"Web results: {len(search_results.get('web_results', []))}")