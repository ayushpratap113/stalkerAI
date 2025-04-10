# LinkedIn Scraper Documentation

## Overview
The LinkedIn Scraper is a tool that automates the extraction of profile information from LinkedIn using Playwright, a browser automation library. It's designed to navigate LinkedIn, handle authentication, and extract structured data from user profiles including personal details, work experience, and recent posts.

## Key Components

### 1. Core Architecture
- **LinkedInScraper Class**: The main class that handles all scraping functionality
- **Context Manager Pattern**: Uses Python's `__enter__` and `__exit__` methods to manage browser resources
- **Asynchronous Support**: Provides both synchronous and asynchronous interfaces for integration with different applications

### 2. Browser Management
- **Playwright Integration**: Uses Playwright's sync API to control a Chromium browser
- **Headless Mode**: Can run in headless (invisible) or headed (visible) mode
- **Resource Cleanup**: Properly closes browser contexts, pages, and Playwright instances to prevent memory leaks

### 3. Authentication Flow
- **Login Process**:
  1. Navigates to LinkedIn login page
  2. Fills in credentials (username/email and password)
  3. Submits the login form
  4. Verifies successful login using multiple detection methods:
     - Checking for specific home page elements
     - Monitoring URL changes
     - Detecting error messages

### 4. Data Extraction Techniques
- **Selector-Based Extraction**: Uses CSS selectors to find and extract text content
- **Multi-selector Approach**: Tries multiple selectors to accommodate LinkedIn's frequent UI changes
- **JavaScript Evaluation**: Executes custom JavaScript within the page context for complex extraction
- **Fallback Mechanisms**: Implements fallbacks when primary extraction methods fail

### 5. Profile Information Extraction
- **Basic Profile Data**:
  - Name: Extracted from heading elements
  - Headline: Professional headline/summary
- **Work Experience**:
  - Job titles
  - Company names
  - Employment dates
- **Recent Posts**:
  - Post content
  - Publication dates
  - Engagement metrics (likes, comments)
  - Media type detection (images, videos, articles, documents)

### 6. Error Handling and Resilience
- **Exception Handling**: Comprehensive try-except blocks around critical operations
- **Detailed Logging**: Records information, warnings, and errors for debugging
- **Graceful Degradation**: Returns partial data if some elements can't be extracted

### 7. Screenshot Management
- **Optional Screenshot Capture**: Can save screenshots at key points for debugging
- **Dedicated Images Directory**: Stores screenshots in an organized "images" folder
- **Timestamped Files**: Appends timestamps to screenshot filenames

### 8. Interface Options
- **Static Method Interface**: Simple `scrape()` method for one-off extractions
- **Async Method Interface**: `scrape_async()` for integration with asynchronous applications
- **Environment Variable Support**: Can read LinkedIn credentials from environment variables

## Authentication Strategy
1. The scraper navigates to LinkedIn's login page
2. Credentials are entered into the appropriate fields
3. Multi-factor detection of successful login:
   - Checks for home page elements
   - Monitors URL changes to detect redirects
   - Looks for specific authentication error messages

## Extraction Workflow
1. **Login**: Authenticate with LinkedIn credentials
2. **Profile Navigation**: Navigate to the target profile URL
3. **Wait for Content**: Allow dynamic content to load completely
4. **Extract Basic Information**: Name and headline
5. **Extract Work Experience**: 
   - Locate experience sections
   - Extract company, position, and date information for each role
6. **Extract Posts**:
   - Find and click to view all posts 
   - Extract post content, date, and engagement metrics
7. **Return to Profile**: Navigate back to the main profile page
8. **Process Data**: Structure all extracted information into a standardized format

## Challenges and Solutions
- **Dynamic UI**: LinkedIn frequently changes its UI; solved with multi-selector approach
- **Authentication Detection**: Using multiple methods to confirm login success
- **Content Visibility**: Adding custom waits after page loads to ensure content is visible
- **Page Structure Variations**: Using JavaScript evaluation for more flexible extraction
- **Detection Avoidance**: Implementing delays and user-agent spoofing to avoid bot detection

## Usage Examples
```python
# Basic usage with credentials
result = LinkedInScraper.scrape(
    "https://www.linkedin.com/in/username/", 
    credentials={'username': 'your_email', 'password': 'your_password'}
)

# Async usage in an event loop
profile_data = await LinkedInScraper.scrape_async(
    "https://www.linkedin.com/in/username/",
    save_screenshots=True  # Enable screenshots for debugging
)
```

# GitHub Scraper Documentation

## Overview
The GitHub Scraper is a tool designed to extract profile information and repository data from GitHub using the GitHub REST API. It provides a clean, reliable way to collect information about GitHub users, their repositories, programming languages, and other GitHub-specific data without requiring browser automation.

## Key Components

### 1. Core Architecture
- **GitHubScraper Class**: Central class handling all GitHub API interactions
- **API-based Approach**: Uses GitHub's REST API instead of browser automation
- **Rate-Limiting Awareness**: Handles GitHub's API rate limits appropriately

### 2. Authentication System
- **Token-based Authentication**: Uses GitHub Personal Access Tokens for higher rate limits
- **Anonymous Fallback**: Can operate without authentication with reduced rate limits
- **Environment Variable Integration**: Automatically reads tokens from environment variables

### 3. Request Management
- **Centralized Request Handling**: All API requests flow through a common method
- **Error Detection**: Identifies common API issues like rate limiting and authentication problems
- **Response Validation**: Ensures responses contain valid data before processing

### 4. Data Extraction Capabilities
- **User Profile Information**:
  - Basic details (name, bio, avatar URL)
  - Status counts (followers, following, public repos)
  - Contact information (company, blog, location)
- **Repository Data**:
  - Repository metadata (name, description, creation date)
  - Popularity metrics (stars, forks)
  - Technical details (primary language, topics)

### 5. Result Processing
- **Data Structuring**: Organizes raw API responses into a consistent format
- **Repository Sorting**: Orders repositories by popularity (stars, forks)
- **Language Analysis**: Provides distribution of programming languages across repositories

### 6. Error Handling and Resilience
- **Comprehensive Error Trapping**: Try-except blocks around all API interactions
- **Detailed Error Reporting**: Specific error messages for different failure modes
- **Partial Results**: Returns whatever data was successfully collected before errors

### 7. Interface Options
- **Simple Static Interface**: `scrape()` method for straightforward use
- **Detailed Component Access**: Individual methods for specific data needs
- **Pluggable Authentication**: Flexible token handling for different authentication scenarios

## Authentication Strategy
1. The scraper checks for a GitHub Personal Access Token:
   - First from the explicitly provided token parameter
   - Then from the `GITHUB_TOKEN` environment variable
2. If a token is found, it's added to request headers as `Authorization: token {TOKEN}`
3. If no token is available, requests are made without authentication (subject to stricter rate limits)

## API Interaction Workflow
1. **Initialize**: Set up headers and authentication
2. **Profile Retrieval**: Get user profile data from `/users/{username}` endpoint
3. **Repository Collection**: Fetch repositories from `/users/{username}/repos` endpoint
4. **Pagination Handling**: Iterate through all pages of repositories if more than 100 exist
5. **Data Processing**: Extract relevant fields and sort repositories
6. **Result Compilation**: Combine all data into a structured response format

## Challenges and Solutions
- **Rate Limiting**: Detects when rate limits are hit and provides reset time information
- **Pagination**: Handles large repository collections through proper pagination
- **Error Handling**: Gracefully handles network issues, authentication problems, and API changes
- **Data Consistency**: Handles missing fields or inconsistent data in the API responses
- **Limited API Coverage**: Notes when data (like contributions) requires additional HTML scraping

## Usage Examples
```python
# Basic usage
result = GitHubScraper.scrape("username")

# Usage with explicit token
github_token = "ghp_your_personal_access_token"
result = GitHubScraper.scrape("username", github_token)

# Advanced usage with direct instance
scraper = GitHubScraper(token)
profile = scraper.get_user_profile("username")
repositories = scraper.get_user_repositories("username")
language_stats = scraper.get_language_distribution(repositories)
```