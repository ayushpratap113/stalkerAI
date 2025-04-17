import os
import logging
import asyncio
from typing import Dict, Any, List, TypedDict, Annotated, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from utils.config import get_persona, Persona, REPORTING_LLM_MODEL, OPENAI_API_KEY
from agents.planning_agent import generate_research_plan
from retriever import get_available_tools, CostTrackingCallback
from prompts import REPORTING_PROMPT_TEMPLATE
from utils.common import structure_profile_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Graph State Definition ---
class ResearchState(TypedDict):
    target_name: str
    persona: Persona
    plan: Optional[List[str]]
    collected_data: List[Dict[str, Any]]
    report: Optional[str]
    error: Optional[str]
    sources_log: List[str]

# --- Graph Nodes ---

async def generate_plan_node(state: ResearchState) -> Dict[str, Any]:
    """Generates the research plan."""
    logger.info("--- Generating Research Plan ---")
    try:
        plan = await generate_research_plan(state['target_name'], state['persona'])
        return {"plan": plan, "error": None}
    except Exception as e:
        logger.error(f"Error in planning node: {e}", exc_info=True)
        return {"error": f"Planning failed: {e}"}

async def execute_research_node(state: ResearchState) -> Dict[str, Any]:
    """Executes the research plan using available tools."""
    logger.info("--- Executing Research ---")
    if state.get("error"):
        return {}  # Skip if prior error
    if not state.get("plan"):
        return {"error": "No research plan available."}

    plan = state["plan"]
    persona = state["persona"]
    tools = get_available_tools(persona.data_sources)
    tool_map = {tool.name: tool for tool in tools}
    logger.info(f"Available tools for execution: {[t.name for t in tools]}")

    tasks = []
    # Match tasks to tools
    for task_description in plan:
        # Basic logic: Try to find a tool name in the task description
        matched_tool_name = None
        tool_input = task_description  # Default input

        # Check for LinkedIn URLs
        if "linkedin.com/in/" in task_description.lower():
            matched_tool_name = "scrape_linkedin"
            # Try to extract LinkedIn URL
            words = task_description.split()
            for word in words:
                if "linkedin.com/in/" in word:
                    tool_input = word.strip(",.()\"'")
                    break
        
        # Check for GitHub username
        elif "github" in task_description.lower():
            matched_tool_name = "scrape_github"
            # Try to extract GitHub username
            words = task_description.split()
            for i, word in enumerate(words):
                if "github" in word.lower() and i < len(words) - 1:
                    potential_username = words[i + 1].strip(",.()\"'")
                    if "/" in potential_username:
                        # Extract username from URL
                        tool_input = potential_username.split("/")[-1]
                    else:
                        tool_input = potential_username
                    break
        
        # Check for academic search
        elif any(term in task_description.lower() for term in ["research", "paper", "publication", "academic", "arxiv"]):
            matched_tool_name = "search_arxiv"
            tool_input = f"{state['target_name']} {task_description}"
        
        # Default to web search
        else:
            matched_tool_name = "search_tavily"
            tool_input = f"{state['target_name']} {task_description}"

        if matched_tool_name and matched_tool_name in tool_map:
            logger.info(f"Mapping task '{task_description}' to tool '{matched_tool_name}' with input '{tool_input}'")
            tool_to_run = tool_map[matched_tool_name]
            
            # Create task
            if matched_tool_name == "search_tavily":
                tasks.append((matched_tool_name, tool_to_run.ainvoke(tool_input)))
            elif matched_tool_name == "search_arxiv":
                tasks.append((matched_tool_name, asyncio.create_task(
                    asyncio.to_thread(tool_to_run.func, tool_input)
                )))
            else:
                # For our custom tools with _arun method (GitHub, LinkedIn)
                tasks.append((matched_tool_name, tool_to_run.ainvoke(tool_input)))

    results = []
    sources_log = []
    
    if tasks:
        logger.info(f"Executing {len(tasks)} research tasks...")
        
        for tool_name, task in tasks:
            try:
                result = await task
                logger.info(f"Task with {tool_name} completed")
                
                # Add source tracking
                source_info = f"Source: {tool_name}"
                if tool_name == "search_tavily":
                    for i, doc in enumerate(result):
                        source_url = doc.metadata.get("source", "Unknown")
                        sources_log.append(f"[{len(sources_log)+1}] {source_url}")
                elif tool_name == "search_arxiv":
                    for i, doc in enumerate(result):
                        source_url = doc.metadata.get("Entry ID", "Unknown")
                        sources_log.append(f"[{len(sources_log)+1}] {source_url}")
                elif tool_name == "scrape_linkedin":
                    if "url" in result:
                        sources_log.append(f"[{len(sources_log)+1}] {result['url']}")
                    else:
                        sources_log.append(f"[{len(sources_log)+1}] LinkedIn profile")
                elif tool_name == "scrape_github":
                    if "html_url" in result:
                        sources_log.append(f"[{len(sources_log)+1}] {result['html_url']}")
                    else:
                        sources_log.append(f"[{len(sources_log)+1}] GitHub profile")
                
                results.append({"tool": tool_name, "result": result})
            except Exception as e:
                logger.error(f"Error executing task with {tool_name}: {e}")
                results.append({"tool": tool_name, "error": str(e)})
    else:
        logger.warning("No executable tasks derived from the plan.")
    
    # If we have GitHub and LinkedIn results, structure the data
    github_data = None
    linkedin_data = None
    
    for item in results:
        if item.get("tool") == "scrape_github" and "error" not in item:
            github_data = item.get("result")
        elif item.get("tool") == "scrape_linkedin" and "error" not in item:
            linkedin_data = item.get("result")
    
    # Structure the data if we have either GitHub or LinkedIn data
    if github_data or linkedin_data:
        structured_data = structure_profile_data(linkedin_data, github_data)
        
        # Add structured data to results
        results.append({
            "tool": "data_structuring",
            "result": structured_data
        })

    return {"collected_data": results, "sources_log": sources_log, "error": None}

async def generate_report_node(state: ResearchState) -> Dict[str, Any]:
    """Generates the final report using LLM."""
    logger.info("--- Generating Report ---")
    if state.get("error"):
        return {}
    if not state.get("collected_data"):
        return {"error": "No data collected to generate report."}

    collected_data = state["collected_data"]
    persona = state["persona"]
    target_name = state["target_name"]
    sources_log = state.get("sources_log", [])

    # Basic summarization/formatting of collected data
    summary = ""
    structured_data = None
    
    # Try to find structured profile data first
    for item in collected_data:
        if item.get("tool") == "data_structuring":
            structured_data = item.get("result")
            summary += f"Structured Profile Data:\n{str(structured_data)}\n\n"
    
    # Add results from each tool
    for item in collected_data:
        tool_name = item.get("tool", "unknown")
        
        # Skip the structured data since we've already added it
        if tool_name == "data_structuring":
            continue
        
        if "error" in item:
            summary += f"{tool_name} Error: {item['error']}\n\n"
        elif "result" in item:
            result = item["result"]
            
            if isinstance(result, list) and len(result) > 0:
                # Handle document lists from retrievers
                if hasattr(result[0], "page_content"):  # LangChain Document objects
                    summary += f"{tool_name} Results:\n"
                    for i, doc in enumerate(result[:5]):  # Limit to 5 documents
                        summary += f"  - Document {i+1}: {doc.page_content[:300]}...\n"
                        summary += f"    Source: {doc.metadata.get('source', 'Unknown')}\n\n"
                else:
                    # Regular list results
                    summary += f"{tool_name} Results:\n"
                    for i, item in enumerate(result[:5]):  # Limit to 5 items
                        if isinstance(item, dict):
                            summary += f"  - Item {i+1}: {str(item)[:300]}...\n\n"
                        else:
                            summary += f"  - Item {i+1}: {str(item)[:300]}...\n\n"
            elif isinstance(result, dict):
                # Handle dictionary results, like those from scrapers
                summary += f"{tool_name} Result:\n"
                
                # For GitHub results
                if tool_name == "scrape_github":
                    if "name" in result:
                        summary += f"  Name: {result.get('name')}\n"
                    if "bio" in result:
                        summary += f"  Bio: {result.get('bio')}\n"
                    if "repositories" in result:
                        summary += f"  Repositories: {len(result.get('repositories', []))} repos found\n"
                        for i, repo in enumerate(result.get('repositories', [])[:3]):  # Show top 3 repos
                            summary += f"    - {repo.get('name')}: {repo.get('description', 'No description')} ({repo.get('language', 'Unknown language')}, {repo.get('stars', 0)} stars)\n"
                    summary += "\n"
                
                # For LinkedIn results
                elif tool_name == "scrape_linkedin":
                    if "name" in result:
                        summary += f"  Name: {result.get('name')}\n"
                    if "headline" in result:
                        summary += f"  Headline: {result.get('headline')}\n"
                    if "experiences" in result:
                        summary += f"  Experiences: {len(result.get('experiences', []))} positions found\n"
                        for i, exp in enumerate(result.get('experiences', [])[:3]):  # Show top 3 experiences
                            summary += f"    - {exp.get('title', 'Role')} at {exp.get('company', 'Company')} ({exp.get('date_range', 'Date unknown')})\n"
                    summary += "\n"
                else:
                    # Generic dictionary handling
                    for key, value in list(result.items())[:5]:  # Limit to first 5 keys
                        if key.startswith('_'):  # Skip metadata fields
                            continue
                        summary += f"  {key}: {str(value)[:100]}...\n"
                    summary += "\n"
            else:
                # Handle string or other result types
                summary += f"{tool_name} Result: {str(result)[:500]}...\n\n"

    # Prepare for LLM report generation
    report_sections_str = ", ".join(persona.report_sections)
    sources_list_str = "\n".join(sources_log)

    try:
        # Attach CostTrackingCallback to the LLM call
        cost_callback = CostTrackingCallback()
        llm = ChatOpenAI(
            model=REPORTING_LLM_MODEL,
            temperature=0.3,
            api_key=OPENAI_API_KEY,
            callbacks=[cost_callback]  # Attach callback
        )

        prompt = PromptTemplate(
            template=REPORTING_PROMPT_TEMPLATE,
            input_variables=["target_name", "persona_name", "report_sections", "research_summary", "sources_list"]
        )
        chain = prompt | llm

        response = await chain.ainvoke({
            "target_name": target_name,
            "persona_name": persona.name,
            "report_sections": report_sections_str,
            "research_summary": summary,
            "sources_list": sources_list_str
        })

        report = response.content
        logger.info("Report generated successfully.")
        return {"report": report, "error": None}

    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return {"error": f"Report generation failed: {e}"}

# --- Build the Graph ---
workflow = StateGraph(ResearchState)

workflow.add_node("generate_plan", generate_plan_node)
workflow.add_node("execute_research", execute_research_node)
workflow.add_node("generate_report", generate_report_node)

workflow.set_entry_point("generate_plan")
workflow.add_edge("generate_plan", "execute_research")
workflow.add_edge("execute_research", "generate_report")
workflow.add_edge("generate_report", END)

# Compile the graph
app = workflow.compile()

# --- Main Runner Function ---
async def run_research(target_name: str, persona_name: str = "General") -> Dict[str, Any]:
    """Runs the full research process for a target and persona."""
    persona = get_persona(persona_name)
    if not persona:
        return {"error": f"Persona '{persona_name}' not found."}

    initial_state: ResearchState = {
        "target_name": target_name,
        "persona": persona,
        "plan": None,
        "collected_data": [],
        "report": None,
        "error": None,
        "sources_log": []
    }

    logger.info(f"Starting research for '{target_name}' using persona '{persona_name}'")
    final_state = await app.ainvoke(initial_state)
    logger.info(f"Research finished for '{target_name}'. Final state error: {final_state.get('error')}")

    # Return relevant parts of the final state
    return {
        "report": final_state.get("report"),
        "sources": final_state.get("sources_log"),
        "error": final_state.get("error"),
    }

async def generate_person_report(name: str, github_username: Optional[str] = None, 
                              linkedin_url: Optional[str] = None, 
                              detailed: bool = True, 
                              llm_enhanced: bool = True,
                              persona_name: str = "General") -> str:
    """
    Generate a comprehensive report about a person using the specified persona.
    
    Args:
        name: Name of the person to research
        github_username: Optional GitHub username to scrape
        linkedin_url: Optional LinkedIn URL to scrape
        detailed: Whether to generate a detailed report
        llm_enhanced: Whether to use LLM for enhancing the report
        persona_name: Name of the persona to use (e.g., "General", "Recruiter", "Investor", "Founder")
        
    Returns:
        str: Markdown formatted report
    """
    logger.info(f"Generating report for {name} with persona {persona_name}")
    
    # Run the research with specified persona
    result = await run_research(name, persona_name)
    
    if result.get("error"):
        return f"# Error Generating Report for {name}\n\n{result['error']}"
    
    if not result.get("report"):
        return f"# No Report Generated for {name}\n\nNo data could be collected or processed."
    
    return result["report"]

# --- Example Usage (for testing) ---
if __name__ == "__main__":
    async def main():
        target = "Andrew Ng"  # Replace with a real person for testing
        persona = "Recruiter"
        result = await run_research(target, persona)

        if result.get("error"):
            print(f"\n--- Research Failed ---")
            print(f"Error: {result['error']}")
        elif result.get("report"):
            print(f"\n--- Research Report ({persona} Persona) ---")
            print(result["report"])
            print("\n--- Sources ---")
            if result.get("sources"):
                for src in result["sources"]:
                    print(src)
        else:
            print("\n--- Research Completed (No Report Generated?) ---")

    asyncio.run(main())