import os
import logging
import time
import json
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GitHubScraper:
    """
    A GitHub profile and repository scraper using the GitHub REST API.
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHub scraper.
        
        Args:
            token: GitHub personal access token for API authentication
        """
        self.token = token or os.environ.get('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'StalkerAI-GitHubScraper'
        }
        
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
            
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a request to the GitHub API with proper error handling.
        
        Args:
            endpoint: API endpoint to request
            
        Returns:
            Response JSON or error dictionary
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers)
            
            # Check for rate limiting
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers:
                if int(response.headers['X-RateLimit-Remaining']) == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    reset_datetime = datetime.fromtimestamp(reset_time)
                    return {
                        "error": "API rate limit exceeded",
                        "reset_time": reset_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    }
            
            # Check for other errors
            if response.status_code != 200:
                return {
                    "error": f"API request failed with status code {response.status_code}",
                    "message": response.json().get('message', 'No message provided')
                }
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
        
        except json.JSONDecodeError:
            logger.error("Failed to decode response as JSON")
            return {"error": "Failed to decode response as JSON"}
    
    def get_user_profile(self, username: str) -> Dict[str, Any]:
        """
        Get a user's GitHub profile information.
        
        Args:
            username: GitHub username
            
        Returns:
            User profile data or error dictionary
        """
        logger.info(f"Fetching GitHub profile for: {username}")
        return self._make_request(f"users/{username}")
    
    def get_user_repositories(self, username: str) -> List[Dict[str, Any]]:
        """
        Get a user's GitHub repositories.
        
        Args:
            username: GitHub username
            
        Returns:
            List of repositories or error dictionary
        """
        logger.info(f"Fetching repositories for: {username}")
        
        # Get all repositories (paginated results)
        repositories = []
        page = 1
        per_page = 100
        
        while True:
            endpoint = f"users/{username}/repos?page={page}&per_page={per_page}&sort=updated"
            response = self._make_request(endpoint)
            
            # Check for errors
            if isinstance(response, dict) and "error" in response:
                return response
            
            # No more repositories or empty list
            if not response:
                break
                
            repositories.extend(response)
            
            # Check if we got fewer repositories than requested (last page)
            if len(response) < per_page:
                break
                
            page += 1
            
        return repositories
    
    def scrape_profile(self, username: str) -> Dict[str, Any]:
        """
        Scrape a GitHub profile and repositories.
        
        Args:
            username: GitHub username to scrape
            
        Returns:
            Dictionary with extracted profile data
        """
        result = {
            "success": False,
            "profile_url": f"https://github.com/{username}",
            "username": username,
            "name": None,
            "bio": None,
            "repositories": [],
            "error": None
        }
        
        try:
            # Get user profile
            profile = self.get_user_profile(username)
            
            # Check for errors
            if "error" in profile:
                result["error"] = profile["error"]
                return result
            
            # Extract basic profile information
            result["name"] = profile.get("name")
            result["bio"] = profile.get("bio")
            result["avatar_url"] = profile.get("avatar_url")
            result["followers"] = profile.get("followers")
            result["following"] = profile.get("following")
            result["public_repos"] = profile.get("public_repos")
            result["company"] = profile.get("company")
            result["blog"] = profile.get("blog")
            result["location"] = profile.get("location")
            result["created_at"] = profile.get("created_at")
            
            # Get repositories
            repos = self.get_user_repositories(username)
            
            # Check for errors
            if isinstance(repos, dict) and "error" in repos:
                result["error"] = repos["error"]
                return result
            
            # Extract repository information
            for repo in repos:
                repo_info = {
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "language": repo.get("language"),
                    "url": repo.get("html_url"),
                    "created_at": repo.get("created_at"),
                    "updated_at": repo.get("updated_at"),
                    "topics": repo.get("topics", [])
                }
                result["repositories"].append(repo_info)
            
            # Sort repositories by stars (most popular first)
            result["repositories"] = sorted(
                result["repositories"], 
                key=lambda x: (x["stars"] or 0, x["forks"] or 0), 
                reverse=True
            )
            
            # If we got this far, the scraping was successful
            result["success"] = True
            logger.info(f"Successfully scraped GitHub profile for: {username}")
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to scrape GitHub profile: {error_msg}")
            result["error"] = error_msg
        
        return result
    
    @staticmethod
    def scrape(username: str, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Static method to scrape a GitHub profile without manually managing the context.
        
        Args:
            username: GitHub username to scrape
            token: GitHub API token (optional)
            
        Returns:
            Dictionary with extracted profile data
        """
        try:
            scraper = GitHubScraper(token)
            return scraper.scrape_profile(username)
        except Exception as e:
            logger.error(f"Failed to initialize GitHub scraper: {str(e)}")
            return {
                "success": False,
                "error": f"Scraper initialization failed: {str(e)}"
            }
    
    def get_user_contributions(self, username: str) -> Dict[str, Any]:
        """
        Get contributions data for a GitHub user.
        Note: This requires scraping as GitHub API doesn't provide this directly.
        
        Args:
            username: GitHub username
            
        Returns:
            Contributions data or error dictionary
        """
        # This requires HTML parsing, so for now we'll return a placeholder
        # In a real implementation, you would use a library like BeautifulSoup to parse the contributions graph
        logger.info(f"GitHub API doesn't provide contributions data directly for: {username}")
        return {
            "note": "GitHub API doesn't provide contribution data directly. Would require HTML scraping.",
            "contribution_url": f"https://github.com/users/{username}/contributions"
        }
    
    def get_language_distribution(self, repositories: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Calculate distribution of programming languages across repositories.
        
        Args:
            repositories: List of repository dictionaries
            
        Returns:
            Dictionary mapping languages to counts
        """
        language_counts = {}
        
        for repo in repositories:
            language = repo.get("language")
            if language:
                language_counts[language] = language_counts.get(language, 0) + 1
        
        return language_counts

# Example usage
if __name__ == "__main__":
    # Example GitHub username
    test_username = "octocat"
    
    # Get token from environment (or pass directly)
    github_token = os.environ.get('GITHUB_TOKEN')
    
    # Run the scraper
    result = GitHubScraper.scrape(test_username, github_token)
    
    # Print summarized results
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Name: {result['name']}")
        print(f"Bio: {result['bio']}")
        print(f"Repositories: {len(result['repositories'])}")
        for i, repo in enumerate(result['repositories'][:5], 1):
            print(f"{i}. {repo['name']} - ⭐ {repo['stars']} - {repo['language'] or 'No language'}")
        if len(result['repositories']) > 5:
            print(f"... and {len(result['repositories']) - 5} more repositories")
    else:
        print(f"Error: {result['error']}")