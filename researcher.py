import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from utils.common import structure_profile_data, get_profile_summary
from scraper.github_scraper import GitHubScraper
from scraper.linkedin_scraper import LinkedInScraper
from retriever import MultiSourceRetriever

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_profile_report(profile_data: Dict[str, Any], detailed: bool = True, llm_enhanced: bool = False) -> str:
    """
    Generate a professional profile report in Markdown format from structured data.
    
    Args:
        profile_data: Structured profile data containing name, headline, work history, projects, skills
        detailed: Whether to generate a detailed report or a summary
        llm_enhanced: Whether to enhance the report with LLM-generated insights
        
    Returns:
        Markdown-formatted professional profile report
    """
    if not profile_data or not isinstance(profile_data, dict):
        return "# Error\nNo valid profile data available to generate report."
    
    # Initialize report sections
    sections = []
    
    # Add header with name and headline
    name = profile_data.get("name", "Unknown Person")
    sections.append(f"# Professional Profile: {name}")
    sections.append(f"*Generated on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*")
    sections.append("")  # Empty line
    
    # Add introduction section
    sections.append("## Introduction")
    if profile_data.get("headline"):
        sections.append(f"{profile_data['headline']}")
    
    sections.append("")  # Empty line
    
    # Add work experience section if available
    if profile_data.get("work_history"):
        sections.append("## Work Experience")
        for job in profile_data["work_history"]:
            job_title = job.get("title", "Role not specified")
            company = job.get("company", "Company not specified")
            date_range = job.get("date_range", "")
            
            job_entry = f"### {job_title} at {company}"
            sections.append(job_entry)
            
            if date_range:
                sections.append(f"*{date_range}*")
            
            # Add job description or responsibilities if available
            if job.get("description"):
                sections.append(f"\n{job['description']}")
            
            sections.append("")  # Empty line
    
    # Add projects section if available
    if profile_data.get("projects"):
        sections.append("## Projects")
        
        # Sort projects by stars if they have them
        sorted_projects = sorted(
            profile_data["projects"], 
            key=lambda x: x.get("stars", 0) or 0, 
            reverse=True
        )
        
        for project in sorted_projects:
            project_name = project.get("name", "Unnamed project")
            project_url = project.get("url", "")
            project_desc = project.get("description", "No description available.")
            project_lang = project.get("language", "Unknown language")
            project_stars = project.get("stars", 0)
            
            # Create project header with link if URL available
            if project_url:
                sections.append(f"### [{project_name}]({project_url})")
            else:
                sections.append(f"### {project_name}")
            
            # Add language and stars info
            sections.append(f"*{project_lang} | {project_stars} stars*")
            
            # Add description
            sections.append(f"\n{project_desc}")
            
            # Add topics/tags if available
            if project.get("topics") and len(project["topics"]) > 0:
                topics_str = ", ".join([f"`{topic}`" for topic in project["topics"]])
                sections.append(f"\n**Topics:** {topics_str}")
            
            sections.append("")  # Empty line
    
    # Add skills section if available
    if profile_data.get("skills"):
        sections.append("## Skills")
        
        # Group skills by category if available
        skills_by_category = {}
        for skill in profile_data["skills"]:
            category = skill.get("category", "Other")
            if category not in skills_by_category:
                skills_by_category[category] = []
            skills_by_category[category].append(skill.get("name", "Unnamed skill"))
        
        # Add skills by category
        for category, skills in skills_by_category.items():
            sections.append(f"### {category}")
            for skill in skills:
                sections.append(f"- {skill}")
            sections.append("")  # Empty line
    
    # Add sources section
    sections.append("## Sources")
    sources = profile_data.get("metadata", {}).get("sources", [])
    
    if not sources:
        sections.append("No source information available.")
    else:
        for source in sources:
            if source.lower() == "linkedin":
                sections.append("- LinkedIn profile data")
            elif source.lower() == "github":
                sections.append("- GitHub profile and repository data")
            else:
                sections.append(f"- {source}")
    
    # If LLM enhancement is requested, add an insights section
    if llm_enhanced and profile_data.get("name"):
        insights = generate_profile_insights(profile_data)
        if insights:
            sections.append("\n## Professional Insights")
            sections.append(insights)
    
    # Join all sections with double newlines for Markdown formatting
    return "\n\n".join(sections)

def generate_profile_insights(profile_data: Dict[str, Any]) -> str:
    """
    Generate insights about the professional profile using an LLM.
    
    Args:
        profile_data: Structured profile data
        
    Returns:
        LLM-generated insights as a string
    """
    try:
        # Create a summary of the profile for the LLM
        profile_summary = get_profile_summary(profile_data)
        
        # Define the prompt template
        insights_prompt = PromptTemplate(
            input_variables=["profile_summary"],
            template="""
            Below is a summary of a professional's profile:
            
            {profile_summary}
            
            Based solely on the information above, provide 3-5 insights about this professional's:
            1. Technical expertise and specialization
            2. Career progression and growth
            3. Professional strengths based on projects and experience
            
            Format your response in Markdown with bullet points.
            Do NOT make up additional details or assumptions beyond what is provided.
            """
        )
        
        # Create LLM instance
        llm = ChatOpenAI(temperature=0.2, model_name="gpt-3.5-turbo")
        
        # Generate insights
        insights = llm.predict(insights_prompt.format(profile_summary=profile_summary))
        return insights.strip()
        
    except Exception as e:
        logger.error(f"Failed to generate profile insights: {str(e)}")
        return ""

async def research_person(name: str, github_username: Optional[str] = None, linkedin_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Research a person using multiple sources and generate structured profile data.
    
    Args:
        name: The person's name to research
        github_username: Optional GitHub username if known
        linkedin_url: Optional LinkedIn profile URL if known
        
    Returns:
        Structured profile data dictionary
    """
    logger.info(f"Researching person: {name}")
    
    linkedin_data = None
    github_data = None
    
    # Use MultiSourceRetriever to find information if github/linkedin not provided
    if not github_username or not linkedin_url:
        retriever = MultiSourceRetriever()
        search_results = retriever.search(name)
        
        # Extract potential GitHub or LinkedIn URLs from search results
        web_results = search_results.get("web_results", [])
        for result in web_results:
            url = result.get("url", "")
            if "github.com/" in url and not github_username:
                # Extract username from GitHub URL
                parts = url.strip("/").split("/")
                if len(parts) > 3:  # https://github.com/username
                    github_username = parts[3]
                    logger.info(f"Extracted GitHub username: {github_username}")
            
            if "linkedin.com/in/" in url and not linkedin_url:
                linkedin_url = url
                logger.info(f"Found LinkedIn URL: {linkedin_url}")
    
    # Scrape GitHub profile if username is available
    if github_username:
        logger.info(f"Scraping GitHub profile for: {github_username}")
        github_token = os.environ.get("GITHUB_TOKEN")
        github_data = GitHubScraper.scrape(github_username, github_token)
    
    # Scrape LinkedIn profile if URL is available
    if linkedin_url:
        logger.info(f"Scraping LinkedIn profile: {linkedin_url}")
        linkedin_credentials = {
            'username': os.environ.get('LINKEDIN_USERNAME'),
            'password': os.environ.get('LINKEDIN_PASSWORD')
        }
        if linkedin_credentials['username'] and linkedin_credentials['password']:
            linkedin_data = LinkedInScraper.scrape(linkedin_url, linkedin_credentials)
    
    # Structure the collected data
    structured_data = structure_profile_data(linkedin_data, github_data)
    
    # If name wasn't found from scrapers, add it from the input
    if not structured_data.get("name"):
        structured_data["name"] = name
    
    return structured_data

async def generate_person_report(name: str, github_username: Optional[str] = None, linkedin_url: Optional[str] = None, 
                                detailed: bool = True, llm_enhanced: bool = True) -> str:
    """
    Research a person and generate a comprehensive profile report.
    
    Args:
        name: The person's name to research
        github_username: Optional GitHub username if known
        linkedin_url: Optional LinkedIn profile URL if known
        detailed: Whether to generate a detailed report
        llm_enhanced: Whether to enhance the report with LLM insights
        
    Returns:
        Markdown-formatted professional profile report
    """
    # Research the person
    profile_data = await research_person(name, github_username, linkedin_url)
    
    # Generate the report
    report = generate_profile_report(profile_data, detailed, llm_enhanced)
    
    return report

# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Example: Generate report for a GitHub user
        report = await generate_person_report(
            name="Nityanand Mathur", 
            
        )
        
        print(report)
        
        # Save to file
        with open("profile_report.md", "w") as f:
            f.write(report)
            print("Report saved to profile_report.md")
    
    asyncio.run(main())