"""Monster.com job source adapter with web scraping (includes Ohio Means Jobs support)."""

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
    retry_with_backoff, ProxyRotator, rotate_user_agent,
    ScrapeOpsAPI
)

logger = logging.getLogger(__name__)


class MonsterAdapter(BaseJobSource):
    """Monster.com job search adapter (supports Ohio Means Jobs)."""
    
    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize Monster adapter.
        
        Args:
            config: Configuration dictionary
            api_key: Monster API key (if available, not used for scraping)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 3.0) if config else 3.0
        # Support both monster.com and ohio means jobs
        self.use_ohio_means_jobs = config.get("use_ohio_means_jobs", False) if config else False
        if self.use_ohio_means_jobs:
            self.base_url = "https://www.ohiomeansjobs.com"
        else:
            self.base_url = "https://www.monster.com"
        self.session = requests.Session()
        self.use_playwright = config.get("use_playwright", False) if config else False
        
        # Third-party API support
        self.use_scrapeops = config.get("use_scrapeops", False) if config else False
        self.scrapeops_key = config.get("scrapeops_api_key") if config else None
        
        if self.use_scrapeops and self.scrapeops_key:
            self.scrapeops_api = ScrapeOpsAPI(self.scrapeops_key)
        else:
            self.scrapeops_api = None
        
        rotate_user_agent(self.session)
    
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[JobListing]:
        """
        Search Monster jobs via web scraping.
        
        Args:
            query: Job title or search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results
            **kwargs: Additional parameters
            
        Returns:
            List of JobListing objects
        """
        logger.info(f"=== STARTING MONSTER SEARCH ===")
        logger.info(f"Query: '{query}', Location: {location}, Remote: {remote}, Max Results: {max_results}")
        logger.info(f"Base URL: {self.base_url}")
        
        # Try ScrapeOps API first if enabled
        if self.scrapeops_api:
            try:
                logger.info("Using ScrapeOps API for Monster search")
                jobs = self._search_via_scrapeops(query, location, remote, max_results)
                if jobs:
                    logger.info(f"✓ Found {len(jobs)} jobs via ScrapeOps")
                    return jobs[:max_results]
            except Exception as e:
                logger.warning(f"ScrapeOps API failed: {e}, falling back to scraping")
        
        # Fallback to direct scraping
        if self.use_playwright:
            try:
                jobs = self._scrape_with_playwright(query, location, remote, max_results)
                if jobs:
                    logger.info(f"✓ Found {len(jobs)} jobs via Playwright")
                    return jobs[:max_results]
            except Exception as e:
                logger.warning(f"Playwright scraping failed: {e}, falling back to requests")
        
        # Direct scraping with requests
        return self._scrape_with_requests(query, location, remote, max_results)
    
    def _search_via_scrapeops(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Search using ScrapeOps API."""
        raw_response = self.scrapeops_api.search_jobs(query, location, remote, max_results)
        
        jobs = []
        
        # ScrapeOps returns HTML for Monster
        if raw_response and isinstance(raw_response, list) and len(raw_response) > 0:
            html_item = raw_response[0]
            if isinstance(html_item, dict) and html_item.get('scrapeops_html'):
                html_content = html_item.get('html_content', '')
                logger.info(f"Parsing ScrapeOps HTML response ({len(html_content)} chars)")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                job_cards = self._find_job_cards(soup)
                
                for card in job_cards[:max_results]:
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing Monster job card: {e}")
                        continue
        
        return jobs
    
    def _scrape_with_requests(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Scrape Monster jobs using requests and BeautifulSoup."""
        jobs = []
        start = 0
        results_per_page = 25
        max_pages = (max_results // results_per_page) + 1
        
        while len(jobs) < max_results and start // results_per_page < max_pages:
            page_num = (start // results_per_page) + 1
            logger.info(f"=== FETCHING MONSTER PAGE {page_num} ===")
            
            # Build search URL
            if self.use_ohio_means_jobs:
                # Ohio Means Jobs URL structure
                search_url = f"{self.base_url}/omj/jobsearch/search-results"
                params = {
                    'q': query,
                    'page': page_num,
                }
                if location:
                    params['where'] = location
            else:
                # Standard Monster.com URL structure
                search_url = f"{self.base_url}/jobs/search"
                params = {
                    'q': query,
                    'page': page_num,
                }
                if location:
                    params['where'] = location
            
            try:
                time.sleep(self.rate_limit_delay)
                response = self.session.get(search_url, params=params, timeout=30)
                response.raise_for_status()
                
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response size: {len(response.text)} characters")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = self._find_job_cards(soup)
                
                logger.info(f"Found {len(job_cards)} job cards on page {page_num}")
                
                for card in job_cards:
                    if len(jobs) >= max_results:
                        break
                    try:
                        job = self._parse_job_card(card)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing job card: {e}")
                        continue
                
                if len(job_cards) == 0:
                    logger.warning(f"No job cards found on page {page_num}, stopping pagination")
                    break
                
                start += results_per_page
                
            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}")
                break
        
        logger.info(f"=== MONSTER DIRECT SCRAPING COMPLETE ===")
        logger.info(f"Total jobs found: {len(jobs)}")
        logger.info(f"Requested max: {max_results}")
        return jobs[:max_results]
    
    def _scrape_with_playwright(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Scrape Monster jobs using Playwright."""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
            
            if not self._playwright:
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(headless=True)
            
            page = self._browser.new_page()
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            # Build search URL
            if self.use_ohio_means_jobs:
                search_url = f"{self.base_url}/omj/jobsearch/search-results"
                url_params = {'q': query}
                if location:
                    url_params['where'] = location
            else:
                search_url = f"{self.base_url}/jobs/search"
                url_params = {'q': query}
                if location:
                    url_params['where'] = location
            
            from urllib.parse import urlencode
            full_url = f"{search_url}?{urlencode(url_params)}"
            
            page.goto(full_url, wait_until='networkidle', timeout=30000)
            time.sleep(3)
            
            jobs = []
            scroll_attempts = 0
            max_scrolls = 10
            
            while len(jobs) < max_results and scroll_attempts < max_scrolls:
                # Find job cards
                job_cards = page.query_selector_all('div[data-testid*="job-card"], .job-card, .card-wrapper')
                
                for card in job_cards:
                    if len(jobs) >= max_results:
                        break
                    try:
                        # Parse card HTML
                        card_html = card.inner_html()
                        soup = BeautifulSoup(card_html, 'html.parser')
                        job = self._parse_job_card(soup)
                        if job:
                            jobs.append(job)
                    except Exception as e:
                        logger.warning(f"Error parsing Playwright job card: {e}")
                        continue
                
                if len(jobs) < max_results:
                    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    time.sleep(2)
                    scroll_attempts += 1
                else:
                    break
            
            page.close()
            return jobs[:max_results]
            
        except ImportError:
            raise Exception("Playwright not installed. Install with: pip install playwright && playwright install")
        except Exception as e:
            logger.error(f"Error in Playwright scraping: {e}", exc_info=True)
            raise
    
    def _find_job_cards(self, soup: BeautifulSoup) -> List:
        """Find job card elements in the HTML."""
        # Try multiple selectors for Monster job cards
        selectors = [
            'div[data-testid*="job-card"]',
            'div.card-wrapper',
            'div.job-card',
            'section[data-testid*="job-card"]',
            'article.card',
            'div[class*="job-card"]',
            'div[class*="JobCard"]',
        ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"Found {len(cards)} job cards using selector: {selector}")
                return cards
        
        logger.warning("No job cards found with any selector")
        return []
    
    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Monster."""
        try:
            # Convert to BeautifulSoup if it's not already
            if not isinstance(card, BeautifulSoup):
                if hasattr(card, 'inner_html'):
                    soup = BeautifulSoup(card.inner_html(), 'html.parser')
                else:
                    soup = BeautifulSoup(str(card), 'html.parser')
            else:
                soup = card
            
            # Title - try multiple selectors
            title = None
            title_selectors = [
                'h2 a', 'h3 a', 'h2', 'h3',
                'a[data-testid*="title"]',
                '.job-title a', '.job-title',
                '[class*="title"] a',
            ]
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.get_text(strip=True)
                    if title:
                        break
            
            if not title:
                return None
            
            # Company
            company = None
            company_selectors = [
                '[data-testid*="company"]',
                '.company-name',
                '[class*="company"]',
                'a[href*="/company/"]',
            ]
            for selector in company_selectors:
                elem = soup.select_one(selector)
                if elem:
                    company = elem.get_text(strip=True)
                    if company:
                        break
            
            # Location
            location = None
            location_selectors = [
                '[data-testid*="location"]',
                '.location',
                '[class*="location"]',
            ]
            for selector in location_selectors:
                elem = soup.select_one(selector)
                if elem:
                    location = elem.get_text(strip=True)
                    if location:
                        break
            
            # URL
            url = None
            link_elem = soup.select_one('a[href*="/job/"], a[href*="/jobs/"]')
            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    url = href
            
            # Description snippet
            description = None
            desc_selectors = [
                '[data-testid*="description"]',
                '.job-snippet',
                '[class*="snippet"]',
            ]
            for selector in desc_selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.get_text(strip=True)
                    if description:
                        break
            
            # Extract keywords
            keywords = self.extract_keywords(f"{title} {description or ''}")
            
            return JobListing(
                title=title,
                company=company or "Unknown Company",
                location=location,
                description=description,
                raw_description=description,
                keywords=keywords,
                posting_date=datetime.utcnow(),  # Monster doesn't always show dates easily
                source="monster" if not self.use_ohio_means_jobs else "ohio_means_jobs",
                source_url=url or f"{self.base_url}/jobs",
                application_type="external",
                metadata={}
            )
        except Exception as e:
            logger.warning(f"Error parsing Monster job card: {e}")
            return None


