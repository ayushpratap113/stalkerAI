import asyncio
import logging
from typing import Optional
import argparse
from datetime import datetime

from researcher import generate_person_report
from utils.config import get_persona, PERSONAS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stalker_ai.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def run_stalker_ai(
    name: str,
    persona_name: str = "General",
    github_username: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    detailed: bool = True
) -> str:
    """
    Generate a comprehensive report about a person using the specified persona.
    
    Args:
        name: Name of the person to research
        persona_name: Name of the persona to use (e.g., "General", "Recruiter", "Investor", "Founder")
        github_username: Optional GitHub username to directly scrape
        linkedin_url: Optional LinkedIn URL to directly scrape
        detailed: Whether to generate a detailed report
        
    Returns:
        str: Markdown formatted report
    """
    start_time = datetime.now()
    logger.info(f"Starting research on {name} using {persona_name} persona")
    
    try:
        # Validate persona
        if persona_name not in PERSONAS:
            available_personas = ", ".join(PERSONAS.keys())
            return f"Error: Invalid persona '{persona_name}'. Available personas: {available_personas}"
        
        # Generate the report
        report = await generate_person_report(
            name=name,
            github_username=github_username,
            linkedin_url=linkedin_url,
            detailed=detailed,
            llm_enhanced=True,
            persona_name=persona_name
        )
        
        execution_time = datetime.now() - start_time
        logger.info(f"Research completed in {execution_time}")
        
        # Return the report
        return report
    
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        return f"# Error Generating Report\n\n{str(e)}"

def save_report(report: str, name: str, persona_name: str) -> str:
    """Save the report to a file and return the filename"""
    # Clean the name for the filename
    clean_name = "".join(c if c.isalnum() else "_" for c in name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{clean_name}_{persona_name}_{timestamp}.md"
    
    with open(filename, "w") as f:
        f.write(report)
    
    return filename

def main():
    parser = argparse.ArgumentParser(description="Generate a research report on a person")
    parser.add_argument("name", help="Name of the person to research")
    parser.add_argument("--persona", "-p", default="General", 
                      choices=list(PERSONAS.keys()),
                      help="Persona to use for the research (default: General)")
    parser.add_argument("--github", "-g", help="GitHub username")
    parser.add_argument("--linkedin", "-l", help="LinkedIn profile URL")
    parser.add_argument("--output", "-o", help="Output file (default: auto-generated)")
    parser.add_argument("--no-save", action="store_true", help="Don't save the report to a file")
    
    args = parser.parse_args()
    
    report = asyncio.run(run_stalker_ai(
        name=args.name,
        persona_name=args.persona,
        github_username=args.github,
        linkedin_url=args.linkedin
    ))
    
    # Print report to console
    print("\n" + "=" * 80)
    print(f"REPORT FOR {args.name} - {args.persona} PERSONA")
    print("=" * 80 + "\n")
    print(report)
    
    # Save report if requested
    if not args.no_save:
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            print(f"\nReport saved to {args.output}")
        else:
            filename = save_report(report, args.name, args.persona)
            print(f"\nReport saved to {filename}")

# Example usage
if __name__ == "__main__":
    main()