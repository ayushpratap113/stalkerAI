# StalkerAI (I can see you)

![alt text](icsu.png)

## 🔍 Project Overview

StalkerAI is an advanced open-source tool designed to aggregate and analyze public information about individuals across multiple platforms. Using a **persona-driven, multi-agent system built with Langgraph**, it creates comprehensive professional profiles by scraping data from LinkedIn, GitHub, and other public sources, then structures this information into detailed reports tailored to specific user needs (e.g., Recruiter, Investor, Founder).

## 🎯 Goals

- Create a unified system for ethical OSINT (Open Source Intelligence) gathering of publicly available professional information
- Automate the collection, analysis, and reporting of professional profiles **based on different user personas**.
- Provide structured insights into a person's skills, work history, and projects **relevant to the chosen persona**.
- Demonstrate responsible use of AI and web scraping technologies within legal and ethical boundaries

## 📊 Current Status

StalkerAI currently offers the following functionality:

- **Persona-Driven Research Planning**: Generates targeted research plans based on selected personas (General, Recruiter, Investor, Founder).
- **Multi-Source Data Collection**: Automated collection of public profile data from:
  - LinkedIn profiles (work history, headline, posts)
  - GitHub profiles (repositories, skills, languages)
  - Web Search via Tavily
  - Academic Papers via ArXiv
- **Structured Data Processing**: Standardization and structuring of collected data.
- **Persona-Tailored Report Generation**: Creation of comprehensive Markdown reports with sections relevant to the chosen persona.
- **Asynchronous Execution**: Utilizes Langgraph and asyncio for efficient, concurrent data gathering and processing.

<!-- ## 🔭 Future Development Plans

- **Enhanced Data Sources**:
  - Add support for Twitter/X, research publications, personal websites
  - Implement academic paper analysis via ArXiv
- **Advanced Analysis**:
  - Sentiment analysis of public posts and communications
  - Network analysis to map professional connections
  - Skills/expertise verification through project contribution analysis
- **Improved User Experience**:
  - Web interface with visualization capabilities
  - Dockerized deployment for easy usage
  - API access for integration with other tools
- **Ethical Guardrails**:
  - Privacy-preserving mechanisms and data retention policies
  - Configurable depth of information gathering
  - Compliance with regional privacy regulations -->

## 💻 Tech Stack

### Data Collection

- **LinkedIn Scraping**: Playwright (Python) for browser automation
- **GitHub Data**: GitHub REST API with Python requests
- **Web Search**: Integration with Tavily Search API
- **Academic Papers**: ArXiv API via LangChain

### Processing & Analysis

- **Data Structuring**: Custom Python utilities
- **LLM Integration**: OpenAI API (GPT-4o models) for planning, reporting, and analysis.
- **Workflow Orchestration**: Langchain & Langgraph for defining and running the multi-agent research process.
- **Cost Optimization**: Token usage tracking and model selection based on task complexity.

### Report Generation

- **Document Creation**: Markdown formatting with custom templates
- **Enhanced Insights**: LLM-powered analysis of collected data

### Architecture

- **Modular Design**: Independent components for planning, scraping, analysis, and reporting.
- **Agent-Based System**: Uses distinct agents (Planning, Execution, Reporting) orchestrated by Langgraph.
- **Asynchronous Processing**: Python asyncio for parallel data collection and agent execution.
- **Error Handling**: Comprehensive logging and fallback mechanisms

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- API keys for:
  - OpenAI
  - Tavily Search
  - GitHub (optional, for higher rate limits)
  - NewsAPI (optional, for Investor/Founder personas)
- LinkedIn credentials (for profile scraping)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/ayushpratap113/stalkerAI
cd stalkerAI

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env
# Edit .env and add your API keys and LinkedIn credentials
```

### Usage

#### Python Script

```python
# Example: Generate report for a person using a specific persona
import asyncio
from researcher import run_research # Updated function name

async def main():
    report_data = await run_research(
        target_name="Andrew Ng",
        persona_name="Recruiter" # Specify the desired persona
    )
    if report_data.get("report"):
        print(report_data["report"])
    else:
        print(f"Error: {report_data.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
```

#### CLI Usage

```bash
# Run StalkerAI from the command line, specifying the persona
python main.py "Person Name" --persona [General|Recruiter|Investor|Founder]

# Example:
python main.py "Elon Musk" --persona Investor
```

## ⚠️ Ethical Considerations

StalkerAI is designed for legitimate professional research and is intended to be used responsibly:

- Only collect publicly available information
- Respect robots.txt and platform Terms of Service
- Use the tool for professional purposes (recruitment, professional networking)
- Do not use for harassment, stalking, or privacy violation



