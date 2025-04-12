# StalkerAI (I can see you)

![alt text](icsu.png)

## 🔍 Project Overview

StalkerAI is an advanced open-source tool designed to aggregate and analyze public information about individuals across multiple platforms. The system creates comprehensive professional profiles by scraping data from LinkedIn, GitHub, and other public sources, then structures this information into detailed reports.

## 🎯 Goals

- Create a unified system for ethical OSINT (Open Source Intelligence) gathering of publicly available professional information
- Automate the collection, analysis, and reporting of professional profiles
- Provide structured insights into a person's skills, work history, and projects
- Demonstrate responsible use of AI and web scraping technologies within legal and ethical boundaries

## 📊 Current Status

StalkerAI currently offers the following functionality:

- **Profile Scraping**: Automated collection of public profile data from:
  - LinkedIn profiles (work history, headline, posts)
  - GitHub profiles (repositories, skills, languages)
- **Data Processing**: Standardization and structuring of collected data
- **Report Generation**: Creation of comprehensive Markdown reports with:
  - Professional summary
  - Work experience history
  - Project portfolio with detailed metadata
  - Technical skill analysis
- **Basic Web Search**: Integration with search APIs for additional context

## 🔭 Future Development Plans

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
  - Compliance with regional privacy regulations

## 💻 Tech Stack

### Data Collection

- **LinkedIn Scraping**: Playwright (Python) for browser automation
- **GitHub Data**: GitHub REST API with Python requests
- **Web Search**: Integration with Tavily Search API
- **Academic Papers**: ArXiv API via LangChain

### Processing & Analysis

- **Data Structuring**: Custom Python utilities
- **LLM Integration**: OpenAI API (GPT-3.5/4o models) for text processing and insights
- **Cost Optimization**: Token usage tracking and model selection based on task complexity

### Report Generation

- **Document Creation**: Markdown formatting with custom templates
- **Enhanced Insights**: LLM-powered analysis of collected data

### Architecture

- **Modular Design**: Independent components for scraping, analysis, and reporting
- **Asynchronous Processing**: Python asyncio for parallel data collection
- **Error Handling**: Comprehensive logging and fallback mechanisms

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- API keys for:
  - OpenAI
  - Tavily Search
  - GitHub (optional, for higher rate limits)
- LinkedIn credentials (for profile scraping)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/stalkerAI.git
cd stalkerAI

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Usage

```python
# Example: Generate report for a person
from researcher import generate_person_report

# Generate a report with known usernames
report = generate_person_report(
    name="John Doe",
    github_username="johndoe",
    linkedin_url="https://linkedin.com/in/johndoe"
)

# Or let StalkerAI find information automatically
report = generate_person_report(name="John Doe")
```

## ⚠️ Ethical Considerations

StalkerAI is designed for legitimate professional research and is intended to be used responsibly:

- Only collect publicly available information
- Respect robots.txt and platform Terms of Service
- Use the tool for professional purposes (recruitment, professional networking)
- Do not use for harassment, stalking, or privacy violation

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

