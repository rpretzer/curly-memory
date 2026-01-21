"""LinkedIn job source adapter with web scraping using Playwright."""

import time
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from app.jobsources.base import BaseJobSource, JobListing
from app.jobsources.utils import (
    retry_with_backoff, ApifyLinkedInAPI, MantiksLinkedInAPI, rotate_user_agent
)

logger = logging.getLogger(__name__)


class LinkedInAdapter(BaseJobSource):
    """LinkedIn job search adapter."""

    @staticmethod
    def _is_masked_content(title: str, company: str, description: Optional[str] = None) -> bool:
        """
        Check if job contains masked/placeholder content.

        Args:
            title: Job title
            company: Company name
            description: Job description

        Returns:
            True if content appears to be masked/placeholder
        """
        # Common masking patterns
        masked_patterns = [
            r'\*{3,}',  # Multiple asterisks (e.g., ****)
            r'x{3,}',   # Multiple x's (e.g., xxxx)
            r'_{3,}',   # Multiple underscores
            r'\[REDACTED\]',
            r'\[HIDDEN\]',
            r'Confidential',
        ]

        # Placeholder company names
        placeholder_companies = [
            'Unknown Company',
            'Company Name',
            'Placeholder',
            'N/A',
            '',
        ]

        # Check for masked patterns in title and company
        for pattern in masked_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                logger.debug(f"Masked content detected in title: {title}")
                return True
            if re.search(pattern, company, re.IGNORECASE):
                logger.debug(f"Masked content detected in company: {company}")
                return True
            if description and re.search(pattern, description[:500], re.IGNORECASE):  # Check first 500 chars
                logger.debug(f"Masked content detected in description")
                return True

        # Check for placeholder company names
        if company.strip() in placeholder_companies:
            logger.debug(f"Placeholder company detected: {company}")
            return True

        # Check for suspiciously short or missing critical fields
        if len(title.strip()) < 3:
            logger.debug(f"Title too short: {title}")
            return True

        if len(company.strip()) < 2:
            logger.debug(f"Company name too short: {company}")
            return True

        return False

    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize LinkedIn adapter.
        
        Args:
            config: Configuration dictionary
            api_key: LinkedIn API key (not used for scraping)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 2.0) if config else 2.0
        self.timeout = config.get("timeout_seconds", 60) if config else 60
        self.base_url = "https://www.linkedin.com"
        self.use_playwright = config.get("use_playwright", False) if config else False  # Disabled by default
        self._logged_in = False
        
        # LinkedIn credentials for authenticated access
        self.linkedin_email = config.get("linkedin_email", "")
        self.linkedin_password = config.get("linkedin_password", "")
        
        # Session for direct scraping
        self.session = requests.Session()
        rotate_user_agent(self.session)
        
        # Third-party API support
        self.use_apify = config.get("use_apify", False) if config else False
        self.apify_key = config.get("apify_api_key") if config else None
        self.use_mantiks = config.get("use_mantiks", False) if config else False
        self.mantiks_key = config.get("mantiks_api_key") if config else None
        
        if self.use_apify and self.apify_key:
            self.apify_api = ApifyLinkedInAPI(self.apify_key)
        else:
            self.apify_api = None
        
        if self.use_mantiks and self.mantiks_key:
            self.mantiks_api = MantiksLinkedInAPI(self.mantiks_key)
        else:
            self.mantiks_api = None
    
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[JobListing]:
        """
        Search LinkedIn jobs via web scraping with Playwright.
        
        Args:
            query: Job title or search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results
            **kwargs: Additional parameters
            
        Returns:
            List of JobListing objects
        """
        logger.info(f"Searching LinkedIn for: {query} (location: {location}, remote: {remote})")
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        # Try third-party APIs first if configured
        if self.mantiks_api:
            try:
                logger.info("Using Mantiks API for LinkedIn search")
                return self._search_via_mantiks(query, location, remote, max_results)
            except Exception as e:
                logger.warning(f"Mantiks API failed: {e}, falling back to direct scraping")
        
        if self.apify_api:
            try:
                logger.info("Using Apify API for LinkedIn search (free tier available)")
                return self._search_via_apify(query, location, remote, max_results)
            except Exception as e:
                logger.warning(f"Apify API failed: {e}, falling back to direct scraping")
        
        # Try direct scraping first (may fail due to auth requirements)
        direct_scraping_failed = False
        try:
            logger.info("Attempting direct LinkedIn scraping (free, no API key required)")
            return self._scrape_with_requests(query, location, remote, max_results)
        except Exception as e:
            logger.warning(f"Direct scraping failed: {e}, trying Playwright if enabled")
            direct_scraping_failed = True
            direct_error = str(e)
        
        # Try Playwright if direct scraping failed and Playwright is enabled
        if direct_scraping_failed and self.use_playwright:
            try:
                logger.info("Attempting LinkedIn scraping with Playwright")
                return self._scrape_with_playwright(query, location, remote, max_results)
            except Exception as e2:
                logger.error(f"Playwright scraping also failed: {e2}", exc_info=True)
                raise Exception(f"Failed to scrape LinkedIn jobs: Direct scraping failed ({direct_error}), Playwright also failed ({str(e2)}). LinkedIn may require authentication or login.")
        
        # If we get here, direct scraping failed and Playwright is not enabled
        if direct_scraping_failed:
            raise Exception(f"Failed to scrape LinkedIn jobs: {direct_error}. Enable Playwright in config (use_playwright: true) or use a third-party API (Apify, Mantiks).")
    
    def _login_linkedin(self, page) -> bool:
        """Login to LinkedIn if credentials are provided."""
        if not self.linkedin_email or not self.linkedin_password:
            logger.info("No LinkedIn credentials provided, skipping login")
            return False
        
        if self._logged_in:
            logger.info("Already logged into LinkedIn")
            return True
        
        try:
            logger.info("Logging into LinkedIn...")
            page.goto(f"{self.base_url}/login", wait_until='networkidle', timeout=30000)
            time.sleep(2)
            
            # Enter email
            email_input = page.query_selector('input[name="session_key"]')
            if email_input:
                email_input.fill(self.linkedin_email)
                time.sleep(1)
            
            # Enter password
            password_input = page.query_selector('input[name="session_password"]')
            if password_input:
                password_input.fill(self.linkedin_password)
                time.sleep(1)
            
            # Click sign in button
            sign_in_button = page.query_selector('button[type="submit"]')
            if sign_in_button:
                sign_in_button.click()
                time.sleep(5)  # Wait for login to complete
            
            # Check if login was successful (look for feed or jobs page)
            current_url = page.url
            if 'feed' in current_url or 'jobs' in current_url or 'login' not in current_url:
                self._logged_in = True
                logger.info("✓ Successfully logged into LinkedIn")
                return True
            else:
                logger.warning("Login may have failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Error logging into LinkedIn: {e}", exc_info=True)
            return False
    
    def get_hiring_connections(
        self,
        max_connections: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Crawl LinkedIn connections to identify who is hiring.
        
        Args:
            max_connections: Maximum number of connections to check
            
        Returns:
            List of dictionaries with connection info and hiring status
        """
        if not self.use_playwright:
            raise Exception("Playwright required for connection crawling. Enable use_playwright in config.")
        
        if not self.linkedin_email or not self.linkedin_password:
            raise Exception("LinkedIn credentials required for connection crawling. Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env or Profile")
        
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
            
            logger.info("=== STARTING LINKEDIN CONNECTION CRAWLING ===")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True) # Connections crawling can be headless
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                
                # Login first
                self._login_linkedin(page)
                
                if not self._logged_in:
                    browser.close()
                    raise Exception("Failed to login to LinkedIn")
            
            # Navigate to connections page
            logger.info("Navigating to LinkedIn connections...")
            connections_url = f"{self.base_url}/mynetwork/invite-connect/connections/"
            page.goto(connections_url, wait_until='networkidle', timeout=30000)
            time.sleep(3)
            
            hiring_connections = []
            connections_checked = 0
            scroll_attempts = 0
            max_scrolls = 20
            
            logger.info("Starting to scroll through connections...")
            
            while connections_checked < max_connections and scroll_attempts < max_scrolls:
                # Find connection cards
                # LinkedIn connections page uses various selectors
                connection_selectors = [
                    'li.reusable-search__result-container',
                    'div.entity-result',
                    'li.mn-connection-card',
                    'div.mn-connection-card',
                ]
                
                connection_cards = []
                for selector in connection_selectors:
                    found = page.query_selector_all(selector)
                    if found:
                        connection_cards = found
                        logger.info(f"Found {len(connection_cards)} connection cards using selector: {selector}")
                        break
                
                if not connection_cards:
                    logger.warning("No connection cards found, scrolling...")
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    scroll_attempts += 1
                    continue
                
                # Process each connection card
                for card in connection_cards:
                    if connections_checked >= max_connections:
                        break
                    
                    try:
                        connection_info = self._parse_connection_card(card, page)
                        if connection_info:
                            connections_checked += 1
                            
                            # Check if their company is hiring
                            if connection_info.get('company'):
                                hiring_status = self._check_company_hiring(page, connection_info['company'])
                                if hiring_status.get('is_hiring'):
                                    connection_info['hiring_info'] = hiring_status
                                    hiring_connections.append(connection_info)
                                    logger.info(f"Found hiring connection: {connection_info.get('name')} @ {connection_info.get('company')}")
                    except Exception as e:
                        logger.warning(f"Error processing connection card: {e}")
                        continue
                
                # Scroll to load more connections
                if connections_checked < max_connections:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    scroll_attempts += 1
                else:
                    break
            
            page.close()
            logger.info(f"=== CONNECTION CRAWLING COMPLETE ===")
            logger.info(f"Checked {connections_checked} connections, found {len(hiring_connections)} hiring")
            
            return hiring_connections
            
        except ImportError:
            raise Exception("Playwright not installed. Install with: pip install playwright && playwright install")
        except Exception as e:
            logger.error(f"Error in connection crawling: {e}", exc_info=True)
            raise Exception(f"Failed to crawl LinkedIn connections: {str(e)}")
    
    def _parse_connection_card(self, card, page) -> Optional[Dict[str, Any]]:
        """Parse a connection card to extract connection info."""
        try:
            # Extract name
            name = None
            name_selectors = [
                'span.entity-result__title-text a',
                'a.app-aware-link',
                'span.actor-name-with-distance',
            ]
            for selector in name_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        name = elem.inner_text().strip()
                        break
                except Exception:
                    continue
            
            # Extract company
            company = None
            company_selectors = [
                'div.entity-result__primary-subtitle',
                'span.entity-result__subtitle',
                '.t-14.t-black--light',
            ]
            for selector in company_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        company = elem.inner_text().strip()
                        break
                except Exception:
                    continue
            
            # Extract profile URL
            profile_url = None
            try:
                link = card.query_selector('a[href*="/in/"]')
                if link:
                    href = link.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            profile_url = f"{self.base_url}{href}"
                        elif href.startswith('http'):
                            profile_url = href
            except Exception:
                pass
            
            if name:
                return {
                    'name': name,
                    'company': company,
                    'profile_url': profile_url,
                }
            return None
        except Exception as e:
            logger.warning(f"Error parsing connection card: {e}")
            return None
    
    def _check_company_hiring(self, page, company_name: str) -> Dict[str, Any]:
        """Check if a company is currently hiring by searching for jobs."""
        try:
            # Search for jobs at this company using LinkedIn job search
            # Use URL encoding for company name
            from urllib.parse import quote
            encoded_company = quote(company_name)
            jobs_url = f"{self.base_url}/jobs/search/?keywords=&location=&f_C={encoded_company}"
            
            # Use the existing page but save current URL
            current_url = page.url
            
            # Navigate to company jobs page
            page.goto(jobs_url, wait_until='networkidle', timeout=15000)
            time.sleep(2)
            
            # Check for job listings
            job_count = 0
            try:
                job_elements = page.query_selector_all('div[data-job-id]')
                job_count = len(job_elements)
                # Also check for job count text (e.g., "123 jobs")
                job_count_text = page.query_selector('.jobs-search-results-list__text, .results-context-header__job-count')
                if job_count_text:
                    text = job_count_text.inner_text()
                    import re
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        job_count = max(job_count, int(numbers[0]))
            except Exception:
                pass
            
            # Go back to connections page
            page.goto(current_url, wait_until='networkidle', timeout=15000)
            time.sleep(1)
            
            return {
                'is_hiring': job_count > 0,
                'job_count': job_count,
            }
        except Exception as e:
            logger.debug(f"Error checking if {company_name} is hiring: {e}")
            return {'is_hiring': False, 'job_count': 0, 'error': str(e)}
    
    def _scrape_with_playwright(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Scrape LinkedIn jobs using Playwright."""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
            
            jobs = []
            with sync_playwright() as p:
                # Use headless=False to avoid detection and allow login
                browser = p.chromium.launch(headless=False)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                page = context.new_page()
                
                # Login if credentials are provided
                if self.linkedin_email and self.linkedin_password:
                    self._login_linkedin(page)
                
                # Build search URL
                search_url = f"{self.base_url}/jobs/search"
                params = {
                    'keywords': query,
                }
                
                if location:
                    params['location'] = location
                
                if remote:
                    params['f_WT'] = '2'  # Remote filter
                
                # Build URL with params
                param_str = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
                url = f"{search_url}?{param_str}"
                
                logger.info(f"Navigating to LinkedIn: {url}")
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)
                time.sleep(3)  # Wait for dynamic content (longer if logged in)
                
                scroll_attempts = 0
                seen_urls = set()  # Track URLs to avoid duplicates
                consecutive_no_new = 0  # Track consecutive rounds with no new jobs
                # Increase max scrolls significantly to fetch more results
                max_scrolls = max(30, max_results // 2)  # More aggressive scrolling
                max_consecutive_empty = 5  # Stop after 5 consecutive rounds with no new jobs
                
                logger.info(f"Starting job collection (target: {max_results} jobs, max scrolls: {max_scrolls})")
                
                while len(jobs) < max_results and scroll_attempts < max_scrolls and consecutive_no_new < max_consecutive_empty:
                    # Find job cards with multiple selector attempts
                    job_cards = []
                    selectors = [
                        'div[data-job-id]',
                        'div.job-card-container',
                        'li.jobs-search-results__list-item',
                        'div[data-entity-urn*="jobPosting"]',
                        'ul.jobs-search__results-list li',
                        'div.job-result-card',
                    ]
                    
                    for selector in selectors:
                        found = page.query_selector_all(selector)
                        if found:
                            job_cards = found
                            break
                    
                    if not job_cards:
                        page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                        time.sleep(2)
                        scroll_attempts += 1
                        consecutive_no_new += 1
                        continue
                    
                    # Parse each job card
                    parsed_this_round = 0
                    for card in job_cards:
                        if len(jobs) >= max_results:
                            break
                        
                        try:
                            job = self._parse_linkedin_card(card, page)
                            if job:
                                if job.source_url not in seen_urls:
                                    seen_urls.add(job.source_url)
                                    jobs.append(job)
                                    parsed_this_round += 1
                        except Exception:
                            continue
                    
                    # Check if we got new jobs this round
                    if parsed_this_round > 0:
                        consecutive_no_new = 0
                    else:
                        consecutive_no_new += 1
                    
                    # Scroll to load more jobs
                    if len(jobs) < max_results and consecutive_no_new < max_consecutive_empty:
                        page.evaluate('window.scrollTo({top: document.body.scrollHeight, behavior: "smooth"});')
                        time.sleep(2)
                        scroll_attempts += 1
                    else:
                        break
                
                browser.close()
            
            logger.info(f"Found {len(jobs)} jobs from LinkedIn")
            return jobs[:max_results]
            
        except ImportError:
            raise Exception("Playwright not installed. Required for LinkedIn scraping.")
        except Exception as e:
            logger.error(f"Error in Playwright scraping: {e}", exc_info=True)
            raise Exception(f"Failed to scrape LinkedIn with Playwright: {str(e)}")
    
    def _parse_linkedin_card(self, card, page) -> Optional[JobListing]:
        """Parse a job card from LinkedIn."""
        try:
            # Get job ID
            job_id = card.get_attribute('data-job-id') or ''
            
            # Title
            title_elem = card.query_selector('a.job-card-list__title')
            if not title_elem:
                title_elem = card.query_selector('h3 a')
            title = title_elem.inner_text().strip() if title_elem else "Unknown Title"
            
            # Company
            company_elem = card.query_selector('a.job-card-container__company-name')
            if not company_elem:
                company_elem = card.query_selector('h4 a')
            company = company_elem.inner_text().strip() if company_elem else "Unknown Company"
            
            # Location - try multiple selectors
            location = None
            location_selectors = [
                'li.job-card-container__metadata-item',
                '.job-card-container__metadata-item--bullet',
                'span.job-card-container__metadata-item',
                '.job-card-container__metadata-wrapper li',
            ]
            for selector in location_selectors:
                try:
                    location_elem = card.query_selector(selector)
                    if location_elem:
                        location = location_elem.inner_text().strip()
                        if location:
                            break
                except Exception:
                    continue
            
            # Description snippet
            snippet_elem = card.query_selector('p.job-card-container__description')
            description = snippet_elem.inner_text().strip() if snippet_elem else None
            
            # URL
            link_elem = card.query_selector('a.job-card-list__title')
            if not link_elem:
                link_elem = card.query_selector('h3 a')
            url = None
            if link_elem:
                href = link_elem.get_attribute('href') or ''
                if href.startswith('/'):
                    url = urljoin(self.base_url, href)
                else:
                    url = href
            
            if not url:
                url = f"{self.base_url}/jobs/view/{job_id}" if job_id else None
            
            # Check for Easy Apply
            easy_apply = card.query_selector('span.job-card-container__apply-method') is not None
            application_type = "easy_apply" if easy_apply else "external"
            
            # Extract keywords
            keywords = self.extract_keywords(f"{title} {description or ''}")

            # Check for masked content before creating job listing
            if self._is_masked_content(title, company, description):
                logger.debug(f"Rejecting job with masked content: {title} @ {company}")
                return None

            return JobListing(
                title=title,
                company=company,
                location=location,
                description=description,
                raw_description=description,
                keywords=keywords,
                posting_date=datetime.utcnow(),  # LinkedIn doesn't show dates easily
                source="linkedin",
                source_url=url or f"{self.base_url}/jobs",
                application_type=application_type,
                metadata={"job_id": job_id}
            )
        except Exception as e:
            logger.warning(f"Error parsing LinkedIn card: {e}")
            return None
    
    def _generate_mock_jobs(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Generate mock job listings for testing."""
        mock_companies = [
            "TechCorp Insurance", "InsureTech Solutions", "FinData Analytics",
            "AI Insurance Group", "DataDriven Inc", "ProductTech Ventures",
        ]
        
        mock_jobs = []
        for i in range(min(max_results, 5)):  # Generate 5 mock jobs
            company = mock_companies[i % len(mock_companies)]
            job = JobListing(
                title=f"{query} - {company}",
                company=company,
                location=location or "Remote, US" if remote else "San Francisco, CA",
                description=f"Seeking an experienced {query} to join our team. "
                          f"This role requires strong product management skills, "
                          f"experience with insurance/fintech products, and data analytics expertise.",
                raw_description=f"Full job description for {query} at {company}...",
                qualifications="5+ years product management, Insurance/FinTech experience, "
                             "Strong data analytics skills, MBA preferred",
                keywords=self.extract_keywords(f"{query} product management insurance fintech data analytics"),
                salary_min=120000 + (i * 20000),
                salary_max=180000 + (i * 30000),
                posting_date=datetime.utcnow(),
                source="linkedin",
                source_url=f"https://linkedin.com/jobs/view/{123456789 + i}",
                application_type="easy_apply" if i % 2 == 0 else "external",
            )
            mock_jobs.append(job)
        
        return mock_jobs
    
    def _search_via_mantiks(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Search using Mantiks API."""
        raw_jobs = self.mantiks_api.search_jobs(query, location, remote, max_results)
        jobs = []
        
        for raw_job in raw_jobs:
            try:
                job = self._normalize_mantiks_job(raw_job)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error normalizing Mantiks job: {e}")
                continue
        
        return jobs
    
    def _search_via_apify(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Search using Apify API."""
        raw_jobs = self.apify_api.search_jobs(query, location, remote, max_results)
        jobs = []
        
        for raw_job in raw_jobs:
            try:
                job = self._normalize_apify_job(raw_job)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error normalizing Apify job: {e}")
                continue
        
        return jobs
    
    def _normalize_mantiks_job(self, raw_job: Dict[str, Any]) -> Optional[JobListing]:
        """Normalize a job from Mantiks API."""
        try:
            title = raw_job.get('title', '')
            company = raw_job.get('company', '')
            description = raw_job.get('description') or raw_job.get('summary')

            # Check for masked content
            if self._is_masked_content(title, company, description):
                logger.debug(f"Rejecting Mantiks job with masked content: {title} @ {company}")
                return None

            return JobListing(
                title=title,
                company=company,
                location=raw_job.get('location'),
                description=description,
                raw_description=raw_job.get('description'),
                keywords=self.extract_keywords(raw_job.get('description', '')),
                salary_min=raw_job.get('salary_min'),
                salary_max=raw_job.get('salary_max'),
                posting_date=datetime.utcnow(),
                source="linkedin",
                source_url=raw_job.get('url', ''),
                application_type="easy_apply" if raw_job.get('easy_apply') else "external",
                metadata=raw_job
            )
        except Exception as e:
            logger.warning(f"Error normalizing Mantiks job: {e}")
            return None
    
    def _normalize_apify_job(self, raw_job: Dict[str, Any]) -> Optional[JobListing]:
        """Normalize a job from Apify API."""
        try:
            return JobListing(
                title=raw_job.get('title', ''),
                company=raw_job.get('company', ''),
                location=raw_job.get('location'),
                description=raw_job.get('description') or raw_job.get('jobDescription'),
                raw_description=raw_job.get('description'),
                keywords=self.extract_keywords(raw_job.get('description', '')),
                salary_min=raw_job.get('salary_min'),
                salary_max=raw_job.get('salary_max'),
                posting_date=datetime.utcnow(),
                source="linkedin",
                source_url=raw_job.get('url', ''),
                application_type="easy_apply" if raw_job.get('easyApply') else "external",
                metadata=raw_job
            )
        except Exception as e:
            logger.warning(f"Error normalizing Apify job: {e}")
            return None
    
    @retry_with_backoff(max_retries=2, initial_delay=3.0)
    def _scrape_with_requests(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Scrape LinkedIn jobs using requests (free, no API key required)."""
        try:
            # Build search URL - LinkedIn's public job search page
            search_url = f"{self.base_url}/jobs/search"
            params = {
                'keywords': query,
                'position': '1',
                'pageNum': '0',
            }
            
            if location:
                params['location'] = location
            
            if remote:
                params['f_WT'] = '2'  # Remote filter
            
            # Rotate user agent
            rotate_user_agent(self.session)
            
            response = self.session.get(
                search_url,
                params=params,
                timeout=15,
                allow_redirects=True
            )
            
            # Check if we got blocked or need login
            if response.status_code == 401 or 'login' in response.url.lower():
                logger.warning("LinkedIn requires authentication for this search")
                raise Exception("Authentication required")
            
            if response.status_code != 200:
                logger.warning(f"LinkedIn returned status {response.status_code}")
                raise Exception(f"HTTP {response.status_code}")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple selectors for LinkedIn job cards
            job_cards = (
                soup.find_all('div', {'data-job-id': True}) or
                soup.find_all('div', class_='job-search-card') or
                soup.find_all('li', class_='jobs-search-results__list-item') or
                soup.find_all('div', class_='base-card')
            )
            
            if not job_cards:
                # Check if we got a login page or error
                if 'signin' in response.url or 'authwall' in response.text.lower():
                    logger.warning("LinkedIn redirected to login page")
                    raise Exception("Authentication required")
                logger.warning("No job cards found - LinkedIn structure may have changed")
                raise Exception("No jobs found")
            
            jobs = []
            for card in job_cards[:max_results]:
                try:
                    job = self._parse_linkedin_card_requests(card)
                    if job:
                        jobs.append(job)
                except Exception as e:
                    if "Masked content detected" in str(e):
                        raise e
                    logger.debug(f"Error parsing card: {e}")
                    continue
            
            logger.info(f"Found {len(jobs)} jobs from LinkedIn direct scraping")
            return jobs
            
        except Exception as e:
            logger.warning(f"Direct LinkedIn scraping failed: {e}")
            raise
    
    def _parse_linkedin_card_requests(self, card) -> Optional[JobListing]:
        """Parse a job card from LinkedIn using requests/BeautifulSoup."""
        try:
            # Title - try multiple selectors
            title_elem = (
                card.find('a', class_='base-card__full-link') or
                card.find('h3', class_='base-search-card__title') or
                card.find('a', {'data-tracking-control-name': True}) or
                card.find('h3')
            )
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
            
            # Company
            company_elem = (
                card.find('h4', class_='base-search-card__subtitle') or
                card.find('a', class_='hidden-nested-link') or
                card.find('span', class_='job-search-card__subtitle-link')
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Check for masked content
            if self._is_masked_content(title, company, description):
                raise ValueError("Masked content detected - job rejected")
            
            # Location
            location_elem = (
                card.find('span', class_='job-search-card__location') or
                card.find('span', {'data-testid': 'job-location'})
            )
            location = location_elem.get_text(strip=True) if location_elem else None
            
            # Description snippet
            snippet_elem = card.find('p', class_='base-search-card__snippet')
            description = snippet_elem.get_text(strip=True) if snippet_elem else None
            
            # URL
            link_elem = (
                card.find('a', class_='base-card__full-link') or
                card.find('a', href=True)
            )
            url = None
            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    url = href
            
            # Job ID
            job_id = card.get('data-job-id', '') or card.get('data-job-id', '')
            
            # Check for Easy Apply
            easy_apply = card.find('span', string=lambda x: x and 'Easy Apply' in x) is not None
            application_type = "easy_apply" if easy_apply else "external"
            
            # Extract keywords
            keywords = self.extract_keywords(f"{title} {description or ''}")
            
            return JobListing(
                title=title,
                company=company,
                location=location,
                description=description,
                raw_description=description,
                keywords=keywords,
                posting_date=datetime.utcnow(),
                source="linkedin",
                source_url=url or f"{self.base_url}/jobs",
                application_type=application_type,
                metadata={"job_id": job_id}
            )
        except Exception as e:
            if "Masked content detected" in str(e):
                raise e
            logger.debug(f"Error parsing LinkedIn card: {e}")
            return None
