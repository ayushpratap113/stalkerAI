import os
from typing import List, Dict, Any, Optional
from langchain_community.retrievers import ArxivRetriever
from langchain_community.retrievers import TavilySearchAPIRetriever
from langchain_core.documents import Document
from langchain.prompts import PromptTemplate
from langchain.agents import initialize_agent, Tool
from langchain.agents import AgentType
from langchain_openai import ChatOpenAI
import logging
from dotenv import load_dotenv


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiSourceRetriever:
    """
    A retriever that combines results from multiple sources including 
    ArxivRetriever and TavilySearchAPIRetriever.
    """
    
    def __init__(self):
        """
        Initialize the MultiSourceRetriever using API keys from environment variables.
        """
        # # Check for required API keys
        # required_keys = ["TAVILY_API_KEY", "OPENAI_API_KEY"]
        # missing_keys = [key for key in required_keys if key not in os.environ]
            
        # if missing_keys:
        #     raise ValueError(f"Missing API keys: {', '.join(missing_keys)}. "
        #                     "Please set them in environment variables or pass them directly.")
        # if tavily_api_key:
        #     os.environ["TAVILY_API_KEY"] = tavily_api_key
        # elif "TAVILY_API_KEY" not in os.environ:
        #     logger.warning("TAVILY_API_KEY not found in environment variables")
        
        # Initialize retrievers
        try:
            self.arxiv_retriever = ArxivRetriever(load_max_docs=3)
            self.tavily_retriever = TavilySearchAPIRetriever(k=3)  # k specifies the number of results
            # Ensure the OpenAI API key is set
            if "OPENAI_API_KEY" not in os.environ:
                raise ValueError("OPENAI_API_KEY is not set. Please set it in your environment variables.")
            self.llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")
            
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
            
            # Initialize the agent
            self.agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                verbose=True
            )
            
            logger.info("MultiSourceRetriever initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize retrievers: {str(e)}")
            raise
    
    def _search_arxiv(self, query: str) -> List[Dict[str, str]]:
        """
        Search for academic papers on Arxiv.
        
        Args:
            query: The search query
            
        Returns:
            List of documents with title, URL and summary
        """
        try:
            results = self.arxiv_retriever.get_relevant_documents(query)
            if not results:
                logger.info(f"No results found on Arxiv for query: {query}")
                return []
            
            # Format results
            formatted_results = []
            for doc in results[:10]:  # Top 3 results
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
        """
        Search the web using Tavily API.
        
        Args:
            query: The search query
            
        Returns:
            List of documents with title, URL and content snippet
        """
        try:
            results = self.tavily_retriever.get_relevant_documents(query)
            if not results:
                logger.info(f"No results found on web for query: {query}")
                return []
            
            # Format results
            formatted_results = []
            for doc in results[:10]:  # Top 3 results
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
    
    def search(self, query: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Perform a comprehensive search using multiple sources.
        
        Args:
            query: The search query (e.g., a person's name)
            
        Returns:
            Dictionary containing search results from different sources
        """
        try:
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
            
            # Return combined results
            return {
                "agent_response": result,
                "arxiv_results": arxiv_results,
                "web_results": web_results
            }
        except Exception as e:
            logger.error(f"Error performing search: {str(e)}")
            return {
                "error": str(e),
                "arxiv_results": [],
                "web_results": []
            }

    def get_top_urls(self, query: str) -> List[str]:
        """
        Get only the top 3 URLs from the search results.
        
        Args:
            query: The search query (e.g., a person's name)
            
        Returns:
            List of top 3 URLs
        """
        try:
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
            
            # Return top 3 unique URLs
            unique_urls = list(dict.fromkeys(urls))
            return unique_urls[:3]
        except Exception as e:
            logger.error(f"Error getting top URLs: {str(e)}")
            return []

# Example usage
if __name__ == "__main__":
    
    # Make sure you have set TAVILY_API_KEY and OPENAI_API_KEY in your environment
    load_dotenv()
    retriever = MultiSourceRetriever()
    
    # Example search
    query = "Harshit Singh UMD"
    print(f"Searching for: {query}")
    
    # Get just the top URLs
    urls = retriever.get_top_urls(query)
    print("\nTop 10 URLs:")
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")
    
    # Get full search results
    results = retriever.search(query)
    print("\nFull search results:")
    print(results)