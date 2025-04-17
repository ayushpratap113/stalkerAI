from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from typing import List, Dict, Any
import logging

from utils.config import Persona, PLANNING_LLM_MODEL, OPENAI_API_KEY
from prompts import PLANNING_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

async def generate_research_plan(target_name: str, persona: Persona) -> List[str]:
    """
    Generates a list of search queries or research tasks based on the target name and persona.
    
    Args:
        target_name (str): The name of the person to research
        persona (Persona): The persona object containing research preferences
        
    Returns:
        List[str]: A list of research queries or tasks to execute
    """
    logger.info(f"Generating research plan for '{target_name}' with persona '{persona.name}'")

    try:
        llm = ChatOpenAI(model=PLANNING_LLM_MODEL, temperature=0.1, api_key=OPENAI_API_KEY)

        prompt = PromptTemplate(
            template=PLANNING_PROMPT_TEMPLATE,
            input_variables=["target_name", "persona_description", "data_sources", "query_keywords"]
        )

        chain = prompt | llm

        # Prepare input, joining lists into strings for the prompt
        data_sources_str = ", ".join(persona.data_sources)
        query_keywords_str = ", ".join(persona.query_keywords)

        response = await chain.ainvoke({
            "target_name": target_name,
            "persona_description": persona.description,
            "data_sources": data_sources_str,
            "query_keywords": query_keywords_str
        })

        # Assuming the LLM returns a newline-separated list of queries
        queries = [q.strip() for q in response.content.split('\n') if q.strip()]

        if not queries:
            logger.warning("LLM generated an empty research plan.")
            # Fallback: generate generic queries
            queries = [
                f"{target_name} LinkedIn profile",
                f"{target_name} GitHub profile",
                f"{target_name} recent work history",
                f"{target_name} notable projects or contributions"
            ]

        logger.info(f"Generated {len(queries)} research queries.")
        return queries

    except Exception as e:
        logger.error(f"Error generating research plan: {e}", exc_info=True)
        # Return a default set of queries as fallback
        return [
            f"Search for {target_name} online profile", 
            f"{target_name} professional background",
            f"{target_name} career highlights"
        ]