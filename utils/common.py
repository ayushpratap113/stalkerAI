import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

def structure_profile_data(
    linkedin_data: Optional[Dict[str, Any]] = None, 
    github_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Structure raw data from LinkedIn and GitHub scrapers into a standardized format.
    
    Args:
        linkedin_data: Raw data from LinkedIn scraper
        github_data: Raw data from GitHub scraper
        
    Returns:
        Structured profile data as a dictionary
    """
    structured_data = {
        "name": None,
        "headline": None,
        "work_history": [],
        "projects": [],
        "skills": [],
        "metadata": {
            "sources": [],
            "last_updated": datetime.now().isoformat(),
            "success": False
        }
    }
    
    try:
        # Process LinkedIn data if available
        if linkedin_data and isinstance(linkedin_data, dict):
            if linkedin_data.get("success", False):
                structured_data["metadata"]["sources"].append("linkedin")
                structured_data["metadata"]["success"] = True
                
                # Extract name
                if not structured_data["name"] and linkedin_data.get("name"):
                    structured_data["name"] = linkedin_data["name"]
                
                # Extract headline
                structured_data["headline"] = linkedin_data.get("headline")
                
                # Extract work history
                if linkedin_data.get("experiences"):
                    for experience in linkedin_data["experiences"]:
                        job_entry = {
                            "title": experience.get("title", "Unknown Position"),
                            "company": experience.get("company", "Unknown Company"),
                            "date_range": experience.get("date_range", ""),
                            "source": "linkedin"
                        }
                        structured_data["work_history"].append(job_entry)
                
                # Note: LinkedIn skills aren't currently extracted in the scraper
                # This is a placeholder for when that functionality is added
                if linkedin_data.get("skills"):
                    structured_data["skills"] = linkedin_data["skills"]
            else:
                logger.warning("LinkedIn data indicates unsuccessful scrape")
        
        # Process GitHub data if available
        if github_data and isinstance(github_data, dict):
            if github_data.get("success", False):
                structured_data["metadata"]["sources"].append("github")
                structured_data["metadata"]["success"] = True
                
                # Extract name if not already set or if GitHub has a name but LinkedIn doesn't
                if not structured_data["name"] and github_data.get("name"):
                    structured_data["name"] = github_data["name"]
                    
                # If no headline from LinkedIn, use GitHub bio as headline
                if not structured_data["headline"] and github_data.get("bio"):
                    structured_data["headline"] = github_data["bio"]
                
                # Extract repositories as projects
                if github_data.get("repositories"):
                    for repo in github_data["repositories"]:
                        project_entry = {
                            "name": repo.get("name", "Unnamed Repository"),
                            "description": repo.get("description", ""),
                            "stars": repo.get("stars", 0),
                            "language": repo.get("language", "Unknown"),
                            "url": repo.get("url", ""),
                            "topics": repo.get("topics", []),
                            "source": "github"
                        }
                        structured_data["projects"].append(project_entry)
                        
                # Extract language skills from repositories
                languages = set()
                for repo in github_data.get("repositories", []):
                    if repo.get("language") and repo["language"] not in ("None", "Unknown", None):
                        languages.add(repo["language"])
                
                # Add programming languages as skills if they don't exist already
                for lang in languages:
                    skill_entry = {
                        "name": lang,
                        "category": "Programming Language",
                        "source": "github"
                    }
                    structured_data["skills"].append(skill_entry)
            else:
                logger.warning("GitHub data indicates unsuccessful scrape")
                
        # Overall success is true if at least one source was successful
        structured_data["metadata"]["success"] = len(structured_data["metadata"]["sources"]) > 0
        
        if not structured_data["metadata"]["success"]:
            error_messages = []
            if linkedin_data and linkedin_data.get("error"):
                error_messages.append(f"LinkedIn error: {linkedin_data['error']}")
            if github_data and github_data.get("error"):
                error_messages.append(f"GitHub error: {github_data['error']}")
                
            structured_data["metadata"]["errors"] = error_messages
            logger.error(f"Failed to structure profile data: {', '.join(error_messages)}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error structuring profile data: {error_msg}")
        structured_data["metadata"]["success"] = False
        structured_data["metadata"]["errors"] = [error_msg]
    
    return structured_data

def enrich_structured_data(structured_data: Dict[str, Any], additional_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich structured profile data with additional information from other sources.
    
    Args:
        structured_data: Previously structured profile data
        additional_data: Additional data to enrich the profile with
        
    Returns:
        Enriched profile data as a dictionary
    """
    try:
        if not structured_data or not isinstance(structured_data, dict):
            logger.error("Invalid structured data provided for enrichment")
            return structured_data
            
        # Add the source to metadata
        if additional_data.get("source"):
            if "sources" not in structured_data["metadata"]:
                structured_data["metadata"]["sources"] = []
            if additional_data["source"] not in structured_data["metadata"]["sources"]:
                structured_data["metadata"]["sources"].append(additional_data["source"])
        
        # Merge or add new fields as needed
        # This is where we could integrate data from other sources beyond LinkedIn and GitHub
        
        # Update last_updated timestamp
        structured_data["metadata"]["last_updated"] = datetime.now().isoformat()
        
        return structured_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error enriching profile data: {error_msg}")
        return structured_data

def get_profile_summary(structured_data: Dict[str, Any], max_projects: int = 5, max_work_history: int = 3) -> str:
    """
    Generate a human-readable summary of the structured profile data.
    Useful for providing context to LLM agents or for displaying in CLI.
    
    Args:
        structured_data: Structured profile data
        max_projects: Maximum number of projects to include in summary
        max_work_history: Maximum number of work history items to include
        
    Returns:
        Human-readable summary string
    """
    if not structured_data or not isinstance(structured_data, dict):
        return "No valid profile data available."
        
    summary_parts = []
    
    # Name and headline
    if structured_data.get("name"):
        summary_parts.append(f"# {structured_data['name']}")
    
    if structured_data.get("headline"):
        summary_parts.append(f"{structured_data['headline']}")
    
    summary_parts.append("")  # Empty line
    
    # Work history
    if structured_data.get("work_history"):
        summary_parts.append("## Work Experience")
        for i, job in enumerate(structured_data["work_history"][:max_work_history]):
            job_desc = f"- {job.get('title', 'Role')} at {job.get('company', 'Company')}"
            if job.get("date_range"):
                job_desc += f" ({job['date_range']})"
            summary_parts.append(job_desc)
        
        if len(structured_data["work_history"]) > max_work_history:
            summary_parts.append(f"- ... and {len(structured_data['work_history']) - max_work_history} more positions")
        
        summary_parts.append("")  # Empty line
    
    # Projects
    if structured_data.get("projects"):
        summary_parts.append("## Notable Projects")
        for i, project in enumerate(structured_data["projects"][:max_projects]):
            proj_desc = f"- {project.get('name', 'Unnamed')} - {project.get('language', 'Unknown language')}"
            if project.get("stars"):
                proj_desc += f" (⭐ {project['stars']})"
            if project.get("description") and len(project["description"]) > 0:
                desc = project["description"]
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                proj_desc += f": {desc}"
            summary_parts.append(proj_desc)
        
        if len(structured_data["projects"]) > max_projects:
            summary_parts.append(f"- ... and {len(structured_data['projects']) - max_projects} more projects")
        
        summary_parts.append("")  # Empty line
    
    # Skills
    if structured_data.get("skills"):
        summary_parts.append("## Skills")
        skill_names = [skill.get("name", "Unnamed skill") for skill in structured_data["skills"]]
        summary_parts.append(", ".join(skill_names))
        
    return "\n".join(summary_parts)