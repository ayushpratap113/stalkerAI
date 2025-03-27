# **Using GPT-Researcher for a Personal Profile Researcher Tool**

* ---

* ## **GPT-Researcher’s Architecture** 

* The repo uses a multi-agent system (planner \+ executor) with **LangGraph** for orchestration. Here’s what matters for your use case:  
* ---

* ### **🔹 Research Planner Agent**

* **Code:** `planner.py` → Generates search queries based on the user’s question.

* #### **✅ Your Adaptation:**

* Modify planner prompts to focus on personal data queries, e.g.,

```py
PERSON_PROFILE_PROMPT = """
You are a research planner. Generate Google search queries to find ONLINE PROFILES and PUBLIC DATA about {name}.
Include LinkedIn, GitHub, personal websites, and news mentions.
Queries:
1. "{name} LinkedIn site:linkedin.com"
2. "{name} GitHub site:github.com"
...
"""
```

### **🔹 Research Execution Agent**

**Code:** `execute.py` → Runs searches via **Tavily AI** (or other APIs), scrapes results, filters/summarizes.

#### **✅ Your Adaptation:**

* Replace **Tavily** with **Google Search API** (or SERP providers like **BrightData**) for more aggressive crawling.

* Use `selenium` / `playwright` in `researcher.py` for scraping dynamic sites (like LinkedIn public profiles).

* Add data extraction templates for parsing personal info (e.g., regex for education/employment history).

---

### **🔹 Report Generation**

**Code:** `writer.py` → Synthesizes scraped data into a structured report.

#### **✅ Your Adaptation:**

* Customize prompts to output profiles in a person-centric format (e.g., "Summary," "Career Timeline," "Skills").

* Use `src/masters/prompts.py` to define sections like “Education,” “Work Experience,” “Online Presence.”

---

### **🔹 LangGraph Integration**

**Code:** `retriever.py` → Agents for recursive refinement.

#### **✅ Your Adaptation:**

* Add agents for **cross-verification** (e.g., compare LinkedIn data with personal websites).

---

## **Components to Build for Your Tool**

---

### **🔸 Targeted Search Queries**

Modify the planner to generate queries like:

* `{name} LinkedIn site:linkedin.com`

* `{name} GitHub site:github.com`

* `CV/resume of {name} filetype:pdf`

---

### **🔸 Person-Specific Scrapers**

**Code:** Add scripts in `researcher/scrapers/` (e.g., `linkedin_scraper.py`) with logic to parse:

* Public LinkedIn profiles (job titles, education).

* GitHub contributions (languages, repositories).

* Personal websites (bio, achievements).

```py
from playwright.sync_api import sync_playwright  

def scrape_linkedin_public_profile(url):  
    with sync_playwright() as p:  
        browser = p.chromium.launch()  
        page = browser.new_page()  
        page.goto(url)  
        name = page.query_selector("h1.top-card-layout__title").text_content()  
        # Extract other fields...  
        browser.close()  
        return {"name": name, ...}  
```

### **🔸 Customize Report Writing**

Modify `writer.py`:

```py
PERSON_REPORT_TEMPLATE = """
Generate a report about {name} using the following data:
- Education: {education}
- Work Experience: {work}
Output in markdown with sections: Summary, Career, Education, Online Presence.
"""
```

### **🔸 Chatbot Integration**

**Code:** Add a conversational interface (in `app/`) that:

* Uses the report as context for **RAG** (Retrieval-Augmented Generation).

* Integrates with an LLM (e.g., **GPT-4o**, **Claude 3**) to answer questions like:

  * *“What frameworks has this person used recently?”* → Query GitHub/Stack Overflow data.

* **Reasoning Model:**  
  Use a smaller, cost-effective model (or prompt-engineered chain-of-thought agent) to reason over the scraped data. This agent helps piece together fragmented data logically.  
* **Generator Model:**  
  Use a larger, more robust model (e.g., GPT-4) to produce a high-quality final report, ensuring natural language flow and completeness.

---

## **Legal Safeguards**

* **Robots.txt Checker:** Use `scrapy.robotstxt` in `researcher/` to block unethical scraping.

* **Rate Limiting:** Use proxies/IP rotation in `researcher/config.py` for public sites.

## **Minimal Viable Implementation (Step-by-Step)**

1. **Fork the Repo**

`git clone https://github.com/assafelovic/gpt-researcher`    
`cd gpt-researcher`  

2. **Modify the Planner Prompt**  
    Edit `planner.py`.

3. **Add Person-Centric Scrapers**  
    Create `researcher/scrapers/person_scraper.py`.

4. **Test Locally**

`from gptr.main import GVTR`    
`report = GVTR().run("Research Alice Smith's professional background")`    
`print(report)`  

---

## **Key Files & Components for Your Use Case**

* `gpt_researcher/master/prompts.py`: Customize system prompts for biographical details.

* `gpt_researcher/master/researcher.py`: Modify `ResearchAgent` class for person-specific sources.

* `gpt_researcher/master/retriever.py`: Handles data chunking/summarization.

* `gpt_researcher/master/scraper/crawler.py`: Asynchronous scraping logic.

* `gpt_researcher/master/agents/`: Use `PlanningAgent` for structured searches.

---

## **Sample Workflow Using the Library**

```py
from gpt_researcher import GPTResearcher

# Step 1: Initialize researcher with a focused query
researcher = GPTResearcher(
    query="Find all professional and educational details for John Doe, including LinkedIn and GitHub activity",
    report_type="detailed",  # Customize to "biographical_report"
    config_path="path/to/config.yaml"  # Restrict sources to LinkedIn, GitHub, etc.
)

# Step 2: Run asynchronous research (crawler scrapes, retriever chunks data)
await researcher.conduct_research()

# Step 3: Generate structured report
report = await researcher.write_report()
```

---

## **Addressing Context Length**

* The `retriever.py` splits scraped data into **embeddings-chunks**.

* Use a **big LLM** as generator (e.g., GPT-4-turbo) and a **smaller LLM** for reasoning (e.g., GPT-3.5).

---

## **Legal Note on LinkedIn Scraping**

* Use **LinkedIn API** where possible.

* Direct scraping violates Terms of Service.

* Use `is_allowed_domain` in `gpt_researcher/scraper/crawler.py` to whitelist permissible sources.

---

## **Next Steps**

* **Set Up Research Pipeline:** Clone the repo and test default workflows on public figures.

* **Customize Prompts:** Modify `prompts.py` for biographical keywords.

* **Integrate UI:** Use **Streamlit** or **Gradio** for a frontend where users input names and get PDF reports.

* **Start small** (single-source testing) before scaling.

