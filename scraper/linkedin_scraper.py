import os
import logging
import time
import json
import asyncio
import concurrent.futures
import functools
from pathlib import Path
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LinkedInScraper:
    """
    A LinkedIn profile scraper using Playwright.
    """
    
    def __init__(self, headless: bool = True, slow_mo: int = 100, save_screenshots: bool = False):
        """
        Initialize the LinkedIn scraper.
        
        Args:
            headless: Whether to run the browser in headless mode.
            slow_mo: Slow down operations by this amount of milliseconds.
            save_screenshots: Whether to save debug screenshots.
        """
        self.headless = headless
        self.slow_mo = slow_mo
        self.page = None
        self.browser = None
        self.context = None
        self.save_screenshots = save_screenshots
        
        # Create images directory if it doesn't exist
        self.images_dir = Path(__file__).parent / "images"
        if self.save_screenshots and not self.images_dir.exists():
            self.images_dir.mkdir(parents=True)
            logger.info(f"Created images directory: {self.images_dir}")
        
    def __enter__(self):
        """
        Set up the Playwright browser when entering the context manager.
        """
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo
        )
        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
        )
        self.page = self.context.new_page()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Clean up resources when exiting the context manager.
        """
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
            
    def _save_screenshot(self, filename: str) -> None:
        """
        Save screenshot to images directory only if screenshots are enabled.
        
        Args:
            filename: Name for the screenshot file
        """
        if not self.save_screenshots:
            return
            
        try:
            timestamp = int(time.time())
            safe_filename = f"{filename}_{timestamp}.jpg"
            file_path = self.images_dir / safe_filename
            self.page.screenshot(path=str(file_path))
            logger.debug(f"Saved screenshot to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save screenshot {filename}: {str(e)}")
    
    def login(self, username: str, password: str) -> bool:
        """
        Log in to LinkedIn using the provided credentials.
        
        Args:
            username: LinkedIn username (email)
            password: LinkedIn password
            
        Returns:
            bool: True if login was successful, False otherwise
        """
        try:
            logger.info("Navigating to LinkedIn login page...")
            self.page.goto('https://www.linkedin.com/login')
            
            # Wait for the login page to load
            self.page.wait_for_selector('#username', timeout=30000)
            
            # Fill in login credentials
            self.page.fill('#username', username)
            self.page.fill('#password', password)
            
            # Click the login button
            logger.info("Attempting to log in...")
            self.page.click('button[type="submit"]')
            
            # Check if login was successful - use multiple methods
            logger.info("Waiting for login confirmation...")
            
            # Method 1: Wait for common selectors on the LinkedIn home page (updated)
            try:
                # Wait for any of these common selectors to appear
                self.page.wait_for_selector('div.feed-identity-module,div.feed-following-module,div.scaffold-layout__main,div.scaffold-layout,div.global-nav__me,div.authentication-outlet', 
                                             timeout=30000)
                logger.info("Login successful! (detected via home page elements)")
                return True
            except PlaywrightTimeoutError:
                logger.warning("Didn't find expected home page elements")
                
            # Method 2: Check URL change
            current_url = self.page.url
            if "feed" in current_url or "/in/" in current_url or "checkpoint" in current_url:
                logger.info(f"Login successful! (detected via URL change: {current_url})")
                return True
                
            # Method 3: Check for any error messages
            error_message = self.page.query_selector('div.alert.error,p.alert-content')
            if error_message:
                error_text = self.page.evaluate('(element) => element.textContent', error_message)
                logger.error(f"Login failed: {error_text}")
                return False
                
            # Additional debugging
            logger.info(f"Current page URL after login attempt: {self.page.url}")
            
            # Take a screenshot for debugging only if needed
            self._save_screenshot("login_debug")
            
            # If we've reached here, determine success based on URL
            if "login" not in self.page.url:
                logger.info("Login appears successful (login page no longer showing)")
                return True
                
            logger.error("Login may have failed - still on login page")
            return False
                
        except Exception as e:
            logger.error(f"Login failed with exception: {str(e)}")
            return False
    
    def _extract_text(self, selector: str, default: str = "Not available") -> str:
        """
        Helper method to extract text from a selector with a default value.
        """
        try:
            element = self.page.query_selector(selector)
            if element:
                text = self.page.evaluate('(element) => element.textContent.trim()', element)
                return text
            
            # Log for debugging which selector failed
            logger.debug(f"No element found for selector: {selector}")
            return default
        except Exception as e:
            logger.error(f"Failed to extract text from {selector}: {str(e)}")
            return default

    def _extract_experiences(self) -> List[Dict[str, str]]:
        """
        Extract work experience data from the profile.
        """
        experiences = []
        try:
            logger.info("Looking for experience sections...")
            
            # First, check if we need to click to expand experiences
            try:
                show_more = self.page.query_selector('button.pv-profile-section__see-more-inline')
                if show_more:
                    logger.info("Clicking 'Show more' button for experiences")
                    show_more.click()
                    self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.debug(f"No 'Show more' button found or couldn't click it: {e}")
            
            # Try multiple selectors for experience sections (newer LinkedIn UI)
            selectors = [
                # New LinkedIn UI (2023-2025)
                '#experience ~ .pvs-list__outer-container > ul > li',
                'section.experience-section li',
                'section[data-section="experience"] li',
                '.pvs-entity',
                '.artdeco-list__item',
                # Fallbacks for various LinkedIn UI versions
                '.pv-profile-section__list-item',
                '.pv-entity__position-group',
            ]
            
            # Try each selector until we find experience elements
            found_elements = []
            for selector in selectors:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    logger.info(f"Found {len(elements)} experience elements with selector: {selector}")
                    found_elements = elements
                    break
            
            if not found_elements:
                logger.warning("No experience elements found with any known selectors")
                return []
            
            for element in found_elements:
                try:
                    # Extract using JavaScript for better flexibility with different UI versions
                    experience_data = self.page.evaluate("""
                        (element) => {
                            // Common selectors for company name
                            const companySelectors = [
                                '.pv-entity__secondary-title', 
                                '.t-14.t-normal', 
                                '.pv-text-details__right-panel-item-text',
                                '.pv-entity__company-summary-info h3',
                                '[data-field="experience_company_name"]',
                                // Add newer LinkedIn selectors
                                '.pvs-entity__subtitle-text',
                                '.pvs-entity__secondary-title'
                            ];
                            
                            // Common selectors for job title
                            const titleSelectors = [
                                '.pv-entity__summary-info-margin-top h3', 
                                '.t-16.t-black.t-bold', 
                                '.pv-entity__summary-info h3',
                                '.pv-profile-section__card-item-v2 h3',
                                '[data-field="experience_title"]',
                                // Add newer LinkedIn selectors
                                '.pvs-entity__headline-text',
                                '.pvs-entity__primary-title'
                            ];
                            
                            // Common selectors for date range
                            const dateSelectors = [
                                '.pv-entity__date-range span:nth-child(2)',
                                '.pv-entity__date-range-v2 span:nth-child(2)',
                                '.t-14.t-normal.t-black--light',
                                '[data-field="date_range"] span',
                                // Add newer LinkedIn selectors
                                '.pvs-entity__caption-text',
                                '.pvs-entity__date-range'
                            ];
                            
                            // Helper function to find text using multiple selectors
                            const findText = (selectors) => {
                                for (const selector of selectors) {
                                    const el = element.querySelector(selector);
                                    if (el) {
                                        return el.textContent.trim();
                                    }
                                }
                                return null;
                            };
                            
                            // Extract the data
                            const company = findText(companySelectors) || 'Unknown Company';
                            const title = findText(titleSelectors) || 'Unknown Position';
                            const dateRange = findText(dateSelectors) || '';
                            
                            return { company, title, dateRange };
                        }
                    """, element)
                    
                    if experience_data:
                        experiences.append({
                            'company': experience_data.get('company', 'Unknown Company'),
                            'title': experience_data.get('title', 'Unknown Position'),
                            'date_range': experience_data.get('dateRange', '')
                        })
                                            
                except Exception as e:
                    logger.warning(f"Failed to extract experience details: {str(e)}")
            
            return experiences
                
        except Exception as e:
            logger.error(f"Failed to extract experiences: {str(e)}")
            return []

    
    def scrape_profile(self, profile_url: str, credentials: Dict[str, str]) -> Dict[str, Any]:
        """
        Scrape a LinkedIn profile using the provided credentials.
        
        Args:
            profile_url: URL of the LinkedIn profile to scrape
            credentials: Dictionary containing 'username' and 'password'
            
        Returns:
            Dictionary with the extracted profile data
        """
        result = {
            "success": False,
            "profile_url": profile_url,
            "name": None,
            "headline": None,
            "experiences": [],
            "posts": [],  # Added posts field
            "error": None
        }
        
        try:
            # Log in to LinkedIn
            login_success = self.login(credentials.get('username'), credentials.get('password'))
            if not login_success:
                result["error"] = "Failed to log in to LinkedIn"
                return result
            
            # Navigate to the profile - use less strict wait condition
            logger.info(f"Navigating to profile: {profile_url}")
            try:
                # Use 'load' instead of 'networkidle' and increase timeout
                self.page.goto(profile_url, wait_until="load", timeout=60000)
                
                # Add a manual wait to allow dynamic content to load
                logger.info("Waiting for profile content to stabilize...")
                self.page.wait_for_timeout(5000)
            except Exception as e:
                logger.error(f"Navigation error: {str(e)}")
                self._save_screenshot("navigation_error")
                result["error"] = f"Failed to navigate to profile: {str(e)}"
                return result
            
            # Check if we've been redirected to login or error page
            current_url = self.page.url
            if "login" in current_url or "authwall" in current_url:
                logger.error(f"Redirected to login page: {current_url}")
                result["error"] = "LinkedIn requires authentication - possible detection of automation"
                return result
                
            # Check if the profile is private or inaccessible
            if self.page.query_selector('div.profile-unavailable'):
                result["error"] = "Profile is private or unavailable"
                return result
            
            # Save screenshot of profile page if needed
            self._save_screenshot("profile_page")
            
            # Wait for any profile content to load
            logger.info("Looking for profile content...")
            selectors_to_try = [
                'h1.text-heading-xlarge',
                'h1.top-card-layout__title',
                'h1.pv-top-card--list li',
                '.pv-top-card-section__name',
                '.profile-info'
            ]
            
            found_element = False
            for selector in selectors_to_try:
                try:
                    if self.page.query_selector(selector):
                        logger.info(f"Found profile element with selector: {selector}")
                        found_element = True
                        break
                except:
                    continue
            
            if not found_element:
                logger.warning("Could not find any profile elements with known selectors")
                # Continue anyway as we might still be able to extract some data
            
            # Extract basic profile information with updated selectors
            name_selectors = 'h1.text-heading-xlarge, h1.top-card-layout__title, h1.pv-top-card--list li, .pv-top-card-section__name, .profile-info, .artdeco-entity-lockup__title, .text-heading-large'
            headline_selectors = 'div.text-body-medium, .pv-top-card-section__headline, .top-card-layout__headline, .ph5.pb5 .artdeco-entity-lockup__subtitle, .pvs-header__subtitle'
            
            result["name"] = self._extract_text(name_selectors)
            result["headline"] = self._extract_text(headline_selectors)
            
            # If we couldn't extract the name, try an alternative approach
            if result["name"] == "Not available":
                logger.warning("Could not extract profile name with regular selectors, trying JavaScript approach")
                try:
                    # Try to extract name using JavaScript
                    result["name"] = self.page.evaluate("""
                        () => {
                            // Try multiple ways to find the name
                            const nameElements = document.querySelectorAll('h1, .text-heading-xlarge, .artdeco-entity-lockup__title, .text-heading-large');
                            for (const el of nameElements) {
                                const text = el.textContent.trim();
                                if (text.length > 0 && text.length < 100) {  // Name should be reasonably short
                                    return text;
                                }
                            }
                            return "Not available";
                        }
                    """)
                    
                    logger.info(f"Extracted name via JavaScript: {result['name']}")
                except Exception as js_error:
                    logger.error(f"JavaScript name extraction failed: {str(js_error)}")
            
            # Extract work experience with our improved method
            logger.info("Extracting work experience...")
            result["experiences"] = self._extract_experiences()
            
            # Extract user's posts
            logger.info("Extracting recent posts...")
            result["posts"] = self._extract_posts()
            
            # If we got any data, consider it a partial success
            if result["name"] != "Not available" or result["headline"] != "Not available" or result["experiences"] or result["posts"]:
                result["success"] = True
                logger.info("Profile scraping completed with data extracted")
            else:
                result["error"] = "Could not extract any profile data"
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to scrape profile: {error_msg}")
            result["error"] = error_msg
        
        return result
    
    def _extract_posts(self) -> List[Dict[str, Any]]:
        """
        Extract recent posts from the user's profile.
        First attempts to find and click "Show all posts" button,
        then extracts posts' content, date, and engagement metrics.
        
        Returns:
            List of post dictionaries with content, date, and engagement data
        """
        posts = []
        try:
            logger.info("Looking for posts section...")
            
            # Try to find the posts section/articles section
            post_section_found = False
            
            # Try to find the "Show all posts" or "See all posts" button
            show_posts_selectors = [
                "a.artdeco-button:has-text('Show all posts')",
                "a.artdeco-button:has-text('See all posts')",
                "a.artdeco-button:has-text('Show all articles')",
                "a:has-text('Posts')",
                "a:has-text('Articles')",
                ".pv-recent-activity-section__all-posts-link",
                "a[href*='recent-activity/shares']"
            ]
            
            # Try each selector to find the "Show all posts" button
            show_posts_button = None
            for selector in show_posts_selectors:
                try:
                    button = self.page.query_selector(selector)
                    if button:
                        logger.info(f"Found show posts button with selector: {selector}")
                        show_posts_button = button
                        post_section_found = True
                        break
                except Exception as e:
                    continue
            
            # If we found the button, click it to see all posts
            if show_posts_button:
                logger.info("Clicking button to show all posts...")
                try:
                    # Get the URL from the button before clicking
                    posts_url = self.page.evaluate("(element) => element.href", show_posts_button)
                    
                    # Navigate to posts page
                    if posts_url:
                        self.page.goto(posts_url, wait_until="load", timeout=30000)
                        logger.info(f"Navigated to posts page: {posts_url}")
                        self.page.wait_for_timeout(3000)  # Wait for posts to load
                    else:
                        # Click the button if href extraction failed
                        show_posts_button.click()
                        logger.info("Clicked on show posts button")
                        self.page.wait_for_timeout(3000)  # Wait for posts to load
                    
                    # Save screenshot of posts page if needed
                    self._save_screenshot("posts_page") 
                    post_section_found = True
                except Exception as click_error:
                    logger.error(f"Failed to click show posts button: {str(click_error)}")
            
            if not post_section_found:
                logger.warning("Could not find posts section or show all posts button")
                return posts
                
            # Look for and extract individual posts
            post_selectors = [
                ".artdeco-card",
                ".feed-shared-update-v2",
                ".feed-shared-article",
                ".pv-post-entity",
                ".artdeco-list__item",
                ".occludable-update"
            ]
            
            # Try each selector to find posts
            post_elements = []
            for selector in post_selectors:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    logger.info(f"Found {len(elements)} posts with selector: {selector}")
                    post_elements = elements
                    break
            
            if not post_elements:
                logger.warning("No posts found with any known selectors")
                return posts
                
            # Process each post
            for i, element in enumerate(post_elements):
                try:
                    # Wait a moment for the post to be visible
                    self.page.wait_for_timeout(200)
                    
                    # Extract post data using JavaScript
                    post_data = self.page.evaluate("""
                        (element) => {
                            // Helper function to find text from multiple selectors
                            const findText = (selectors) => {
                                for (const selector of selectors) {
                                    const el = element.querySelector(selector);
                                    if (el) {
                                        return el.textContent.trim();
                                    }
                                }
                                return null;
                            };
                            
                            // Extract post content
                            const contentSelectors = [
                                '.feed-shared-update-v2__description',
                                '.feed-shared-text',
                                '.feed-shared-inline-show-more-text',
                                '.feed-shared-text-view',
                                '.artdeco-entity-lockup__caption',
                                '.share-update-card__update-text',
                                '.update-components-text'
                            ];
                            
                            // Extract post date
                            const dateSelectors = [
                                '.feed-shared-actor__sub-description',
                                '.feed-shared-time-ago',
                                '.artdeco-entity-lockup__caption',
                                '.share-update-card__update-info-text',
                                '.update-components-actor__sub-description',
                                'time',
                                '.feed-shared-actor__sub-description span[aria-hidden="true"]'
                            ];
                            
                            // Extract engagement metrics (likes, comments)
                            const likesSelectors = [
                                '.social-details-social-counts__reactions-count',
                                '.feed-shared-social-action-bar__reactions-count',
                                '.feed-social-aggregated-reaction-count',
                                '.social-details-social-counts__social-proof-text'
                            ];
                            
                            const commentsSelectors = [
                                '.feed-shared-social-counts__comments',
                                '.feed-shared-social-action-bar__comments-count',
                                '.social-details-social-counts__comments'
                            ];
                            
                            // Get the post content
                            const content = findText(contentSelectors) || "No content available";
                            
                            // Get post date
                            const date = findText(dateSelectors) || "No date available";
                            
                            // Get engagement metrics
                            const likes = findText(likesSelectors) || "0";
                            const comments = findText(commentsSelectors) || "0";
                            
                            // Get media content (if any)
                            const hasImage = !!element.querySelector('img.feed-shared-image__image');
                            const hasVideo = !!element.querySelector('.feed-shared-video');
                            const hasArticle = !!element.querySelector('.feed-shared-article');
                            const hasDocument = !!element.querySelector('.feed-shared-document');
                            
                            // Get link URL if shared article
                            let articleUrl = null;
                            const articleLink = element.querySelector('.feed-shared-article__meta-link');
                            if (articleLink) {
                                articleUrl = articleLink.href;
                            }
                            
                            return {
                                content,
                                date,
                                likes,
                                comments,
                                hasImage,
                                hasVideo,
                                hasArticle,
                                hasDocument,
                                articleUrl
                            };
                        }
                    """, element)
                    
                    if post_data:
                        # Add the post to our list
                        posts.append({
                            'content': post_data.get('content', "No content available"),
                            'date': post_data.get('date', "No date available"),
                            'likes': post_data.get('likes', "0"),
                            'comments': post_data.get('comments', "0"),
                            'has_image': post_data.get('hasImage', False),
                            'has_video': post_data.get('hasVideo', False),
                            'has_article': post_data.get('hasArticle', False),
                            'has_document': post_data.get('hasDocument', False),
                            'article_url': post_data.get('articleUrl')
                        })
                        
                        logger.info(f"Extracted post {i+1}: {posts[-1]['content'][:50]}...")
                    
                except Exception as post_error:
                    logger.warning(f"Failed to extract post #{i+1}: {str(post_error)}")
                    
            logger.info(f"Successfully extracted {len(posts)} posts")
            
            # Return to the profile page after extracting posts
            try:
                self.page.go_back()
                self.page.wait_for_timeout(2000)  # Wait for page to load
            except Exception as nav_error:
                logger.warning(f"Failed to navigate back to profile: {str(nav_error)}")
                
            return posts
                
        except Exception as e:
            logger.error(f"Failed to extract posts: {str(e)}")
            return posts
    
    @staticmethod
    def scrape(profile_url: str, credentials: Optional[Dict[str, str]] = None, save_screenshots: bool = False) -> Dict[str, Any]:
        """
        Static method to scrape a LinkedIn profile without manually managing the context.
        
        Args:
            profile_url: URL of the LinkedIn profile to scrape
            credentials: Dictionary containing 'username' and 'password'
            save_screenshots: Whether to save debug screenshots (default: False)
            
        Returns:
            Dictionary with the extracted profile data
        """
        if not credentials:
            # Try to get credentials from environment variables
            credentials = {
                'username': os.environ.get('LINKEDIN_USERNAME'),
                'password': os.environ.get('LINKEDIN_PASSWORD')
            }
            
        if not credentials.get('username') or not credentials.get('password'):
            return {
                "success": False,
                "error": "LinkedIn credentials not provided"
            }
            
        try:
            with LinkedInScraper(headless=True, slow_mo=500, save_screenshots=save_screenshots) as scraper:
                return scraper.scrape_profile(profile_url, credentials)
        except Exception as e:
            logger.error(f"Failed to initialize scraper: {str(e)}")
            return {
                "success": False,
                "error": f"Scraper initialization failed: {str(e)}"
            }
    
    @staticmethod
    async def scrape_async(profile_url: str, credentials: Optional[Dict[str, str]] = None, save_screenshots: bool = False) -> Dict[str, Any]:
        """
        Async-compatible method to scrape a LinkedIn profile without blocking the event loop.
        
        Args:
            profile_url: URL of the LinkedIn profile to scrape
            credentials: Dictionary containing 'username' and 'password'
            save_screenshots: Whether to save debug screenshots (default: False)
            
        Returns:
            Dictionary with the extracted profile data
        """
        logger.info(f"Running LinkedIn scraper asynchronously for: {profile_url}")
        
        # Run the synchronous scraper in a thread pool
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool, 
                functools.partial(LinkedInScraper.scrape, 
                                 profile_url=profile_url, 
                                 credentials=credentials,
                                 save_screenshots=save_screenshots)
            )
        
        return result
            
# Example usage
if __name__ == "__main__":
    # Example profile URL
    test_url = "https://www.linkedin.com/in/nityanandmathur/"
    
    load_dotenv()
    # Example credentials (replace with actual credentials or use environment variables)
    creds = {
        'username': os.environ.get('LINKEDIN_USERNAME'),
        'password': os.environ.get('LINKEDIN_PASSWORD')
    }
    
    if not creds['username'] or not creds['password']:
        print("Please set LINKEDIN_USERNAME and LINKEDIN_PASSWORD environment variables")
    else:
        print(f"Starting browser to scrape: {test_url}")
        result = LinkedInScraper.scrape(test_url, creds, save_screenshots=False)  # Set to False to disable screenshots
        print(json.dumps(result, indent=2))