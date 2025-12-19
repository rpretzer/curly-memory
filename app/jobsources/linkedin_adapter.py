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
    
    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize LinkedIn adapter.
        
        Args:
            config: Configuration dictionary
            api_key: LinkedIn API key (not used for scraping)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 4.0) if config else 4.0
        self.base_url = "https://www.linkedin.com"
        self.use_playwright = config.get("use_playwright", False) if config else False  # Disabled by default
        self._playwright = None
        self._browser = None
        
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
            
            if not self._playwright:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(headless=True)
            
            page = self._browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
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
            page.goto(url, wait_until='networkidle', timeout=30000)
            time.sleep(2)  # Wait for dynamic content
            
            jobs = []
            scroll_attempts = 0
            # Increase max scrolls to fetch more results (scroll more aggressively)
            max_scrolls = max(5, max_results // 5)  # Allow more scrolling
            
            while len(jobs) < max_results and scroll_attempts < max_scrolls:
                # Find job cards
                job_cards = page.query_selector_all('div[data-job-id]')
                
                for card in job_cards:
                    if len(jobs) >= max_results:
                        break
                    
                    try:
                        job = self._parse_linkedin_card(card, page)
                        if job and job not in jobs:  # Avoid duplicates
                            jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing LinkedIn job card: {e}")
                        continue
                
                # Scroll to load more
                if len(jobs) < max_results:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    scroll_attempts += 1
                else:
                    break
            
            page.close()
            logger.info(f"Found {len(jobs)} jobs from LinkedIn")
            return jobs[:max_results]
            
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install")
            raise Exception("Playwright not installed. Required for LinkedIn scraping. Install with: pip install playwright && playwright install chromium")
        except Exception as e:
            logger.error(f"Error in Playwright scraping: {e}", exc_info=True)
            raise Exception(f"Failed to scrape LinkedIn with Playwright: {str(e)}. Check Playwright installation and LinkedIn login requirements.")
    
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
            
            # Location
            location_elem = card.query_selector('li.job-card-container__metadata-item')
            location = location_elem.inner_text().strip() if location_elem else None
            
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
            return JobListing(
                title=raw_job.get('title', ''),
                company=raw_job.get('company', ''),
                location=raw_job.get('location'),
                description=raw_job.get('description') or raw_job.get('summary'),
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
            logger.debug(f"Error parsing LinkedIn card: {e}")
            return None
