import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

load_dotenv()

# --- API Keys & Configuration ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

# --- LLM Configuration ---
PLANNING_LLM_MODEL = "gpt-4o-mini"
REPORTING_LLM_MODEL = "gpt-4o"
VERIFICATION_LLM_MODEL = "gpt-4o-mini"

# --- Persona Definitions ---

class Persona(BaseModel):
    name: str
    description: str
    data_sources: List[str] = Field(default_factory=list)
    report_sections: List[str] = Field(default_factory=list)
    query_keywords: List[str] = Field(default_factory=list)

PERSONAS: Dict[str, Persona] = {
    "General": Persona(
        name="General",
        description="Provides a broad overview of a person's public professional and technical footprint.",
        data_sources=["linkedin", "github", "tavily", "arxiv"],
        report_sections=["Profile Overview", "Public Footprint", "Career Insights", "Technical Contributions", "Skills"],
        query_keywords=["profile", "contributions", "work history", "projects"]
    ),
    "Recruiter": Persona(
        name="Recruiter",
        description="Focuses on professional history, skills, technical contributions, and certifications for hiring purposes.",
        data_sources=["linkedin", "github", "stackoverflow", "tavily"],
        report_sections=["Professional Summary", "Key Skills", "Employment History", "Project Portfolio", "Technical Contributions", "Certifications & Courses", "Social Media Footprint"],
        query_keywords=["resume", "cv", "skills", "experience", "certifications", "github profile", "linkedin profile"]
    ),
    "Investor": Persona(
        name="Investor",
        description="Investigates financial performance, market impact, innovation track record, and funding history.",
        data_sources=["tavily", "linkedin", "newsapi"],
        report_sections=["Executive Summary", "Financial Performance", "Market Impact", "Innovation Track Record", "Past Funding Rounds", "Industry Recognition", "Media Mentions"],
        query_keywords=["investment history", "funding rounds", "financials", "market position", "company performance", "news articles about"]
    ),
    "Founder": Persona(
        name="Founder",
        description="Highlights entrepreneurial ventures, startup history, product development, innovation, and networking.",
        data_sources=["linkedin", "github", "tavily", "newsapi", "arxiv"],
        report_sections=["Entrepreneurial Ventures", "Startup History", "Product Development", "Innovation Milestones", "Networking & Partnerships", "Media Mentions", "Technical Contributions"],
        query_keywords=["startup founder", "entrepreneur", "product launch", "patent history", "venture capital", "company founded by"]
    ),
}

def get_persona(persona_name: str) -> Optional[Persona]:
    """
    Get a persona configuration by name.
    
    Args:
        persona_name: Name of the persona to retrieve
        
    Returns:
        Persona object if found, None otherwise
    """
    return PERSONAS.get(persona_name)

# --- Rate Limits & Timeouts ---
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RATE_LIMIT_PAUSE = 2  # seconds between API calls