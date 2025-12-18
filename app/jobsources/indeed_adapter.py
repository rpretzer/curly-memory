"""Indeed job source adapter with web scraping."""

import time
import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin
import random

import requests
from bs4 import BeautifulSoup

from app.jobsources.base import BaseJobSource, JobListing
from app.jobsources.utils import (
    retry_with_backoff, ProxyRotator, rotate_user_agent,
    ScrapeOpsAPI, HasDataAPI
)

logger = logging.getLogger(__name__)


class IndeedAdapter(BaseJobSource):
    """Indeed job search adapter."""
    
    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize Indeed adapter.
        
        Args:
            config: Configuration dictionary
            api_key: Indeed API key (if available, not used for scraping)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 3.0) if config else 3.0
        self.base_url = "https://www.indeed.com"
        self.session = requests.Session()
        
        # Third-party API support
        self.use_scrapeops = config.get("use_scrapeops", False) if config else False
        self.scrapeops_key = config.get("scrapeops_api_key") if config else None
        self.use_hasdata = config.get("use_hasdata", False) if config else False
        self.hasdata_key = config.get("hasdata_api_key") if config else None
        
        if self.use_scrapeops and self.scrapeops_key:
            self.scrapeops_api = ScrapeOpsAPI(self.scrapeops_key)
        else:
            self.scrapeops_api = None
        
        if self.use_hasdata and self.hasdata_key:
            self.hasdata_api = HasDataAPI(self.hasdata_key)
        else:
            self.hasdata_api = None
        
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
        Search Indeed jobs via web scraping.
        
        Args:
            query: Job title or search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results
            **kwargs: Additional parameters
            
        Returns:
            List of JobListing objects
        """
        logger.info(f"Searching Indeed for: {query} (location: {location}, remote: {remote})")
        
        # Try third-party APIs first if configured
        if self.scrapeops_api:
            try:
                logger.info("Using ScrapeOps API for Indeed search")
                return self._search_via_scrapeops(query, location, remote, max_results)
            except Exception as e:
                logger.warning(f"ScrapeOps API failed: {e}, falling back to scraping")
        
        if self.hasdata_api:
            try:
                logger.info("Using HasData API for Indeed search")
                return self._search_via_hasdata(query, location, remote, max_results)
            except Exception as e:
                logger.warning(f"HasData API failed: {e}, falling back to scraping")
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        try:
            jobs = []
            start = 0
            results_per_page = 10
            
            while len(jobs) < max_results and start < max_results:
                # Build search URL
                params = {
                    'q': query,
                    'start': start,
                }
                
                if location:
                    params['l'] = location
                
                if remote:
                    params['remotejob'] = '1'
                
                try:
                    # Rotate user agent occasionally
                    if random.random() < 0.3:
                        rotate_user_agent(self.session)
                    
                    # Use proxy if available
                    proxies = None
                    if self.proxy_rotator:
                        proxies = self.proxy_rotator.get_proxy()
                    
                    response = self._make_request_with_retry(
                        f"{self.base_url}/jobs",
                        params=params,
                        proxies=proxies
                    )
                    
                    # Check status before processing
                    if response.status_code == 403:
                        logger.warning("Got 403 from Indeed - rate limited or blocked")
                        break
                    
                    response.raise_for_status()
                    
                    # Check for CAPTCHA more carefully (only if we see specific patterns)
                    content_preview = response.text[:2000].lower()
                    if 'captcha' in content_preview and ('verify' in content_preview or 'robot' in content_preview):
                        logger.warning("CAPTCHA detected on Indeed")
                        break
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Try multiple selectors for Indeed's job cards
                    job_cards = (
                        soup.find_all('div', {'data-jk': True}) or
                        soup.find_all('div', class_='job_seen_beacon') or
                        soup.find_all('div', class_='slider_container') or
                        soup.find_all('td', {'data-jk': True})
                    )
                    
                    if not job_cards:
                        logger.warning("No job cards found on Indeed page - Indeed may have changed their HTML structure")
                        break
                    
                    for card in job_cards[:min(results_per_page, max_results - len(jobs))]:
                        try:
                            job = self._parse_job_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.warning(f"Error parsing job card: {e}")
                            continue
                    
                    # Check if there are more pages
                    if len(job_cards) < results_per_page:
                        break
                    
                    start += results_per_page
                    time.sleep(self.rate_limit_delay)  # Rate limit between pages
                    
                except requests.RequestException as e:
                    logger.error(f"Error fetching Indeed page: {e}")
                    break
            
            logger.info(f"Found {len(jobs)} jobs from Indeed")
            return jobs[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching Indeed: {e}", exc_info=True)
            # Don't use mock data - raise error to indicate real scraping failed
            raise Exception(f"Failed to scrape Indeed jobs: {str(e)}. Please check network connectivity, rate limits, or consider using a third-party API service.")
    
    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Indeed search results with multiple selector fallbacks."""
        try:
            # Extract job ID - try multiple attributes
            job_id = (
                card.get('data-jk', '') or
                card.get('data-jobkey', '') or
                card.get('id', '').replace('job_', '')
            )
            if not job_id:
                # Try finding a link with job ID
                link = card.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    match = re.search(r'jk=([^&]+)', href)
                    if match:
                        job_id = match.group(1)
            
            # Title - try multiple selectors
            title_elem = (
                card.find('h2', class_='jobTitle') or
                card.find('h2', {'data-testid': 'job-title'}) or
                card.find('h2') or
                card.find('a', class_='jcs-JobTitle') or
                card.find('span', class_='jobTitle')
            )
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
            
            # Company - try multiple selectors
            company_elem = (
                card.find('span', {'data-testid': 'company-name'}) or
                card.find('span', class_='companyName') or
                card.find('a', {'data-testid': 'company-name'}) or
                card.find('div', class_='company_location') or
                card.find('span', class_='company')
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location - try multiple selectors
            location_elem = (
                card.find('div', {'data-testid': 'text-location'}) or
                card.find('div', class_='companyLocation') or
                card.find('span', {'data-testid': 'job-location'}) or
                card.find('div', class_='location')
            )
            location = location_elem.get_text(strip=True) if location_elem else None
            
            # Description snippet - try multiple selectors
            snippet_elem = (
                card.find('div', class_='job-snippet') or
                card.find('div', {'data-testid': 'job-snippet'}) or
                card.find('span', class_='summary') or
                card.find('div', class_='summary')
            )
            description = snippet_elem.get_text(strip=True) if snippet_elem else None
            
            # Salary (if available) - try multiple selectors
            salary_elem = (
                card.find('span', class_='salary-snippet') or
                card.find('span', {'data-testid': 'attribute_snippet_testid'}) or
                card.find('div', class_='salaryText') or
                card.find('span', class_='salary')
            )
            salary_min, salary_max = self._parse_salary(salary_elem.get_text(strip=True) if salary_elem else None)
            
            # URL - try multiple selectors
            link_elem = (
                card.find('a', class_='jcs-JobTitle') or
                card.find('h2', class_='jobTitle').find('a') if card.find('h2', class_='jobTitle') else None or
                card.find('a', href=True)
            )
            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/'):
                    url = urljoin(self.base_url, href)
                elif href.startswith('http'):
                    url = href
                else:
                    url = f"{self.base_url}/viewjob?jk={job_id}"
            else:
                url = f"{self.base_url}/viewjob?jk={job_id}" if job_id else f"{self.base_url}/jobs"
            
            # Posting date - try multiple selectors
            date_elem = (
                card.find('span', {'data-testid': 'myJobsStateDate'}) or
                card.find('span', class_='date') or
                card.find('div', class_='date') or
                card.find('span', {'data-testid': 'job-date'})
            )
            posting_date = self._parse_date(date_elem.get_text(strip=True) if date_elem else None)
            
            # Extract keywords from title and description
            keywords = self.extract_keywords(f"{title} {description or ''}")
            
            return JobListing(
                title=title,
                company=company,
                location=location,
                description=description,
                raw_description=description,
                keywords=keywords,
                salary_min=salary_min,
                salary_max=salary_max,
                posting_date=posting_date,
                source="indeed",
                source_url=url,
                application_type="external",
                metadata={"job_id": job_id}
            )
        except Exception as e:
            logger.warning(f"Error parsing Indeed job card: {e}")
            return None
    
    def _parse_salary(self, salary_text: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        """Parse salary range from text."""
        if not salary_text:
            return None, None
        
        # Extract numbers (handle ranges like $100,000 - $150,000)
        numbers = re.findall(r'\$?([\d,]+)', salary_text.replace(',', ''))
        if len(numbers) >= 2:
            return int(numbers[0]), int(numbers[1])
        elif len(numbers) == 1:
            num = int(numbers[0])
            return num, num
        return None, None
    
    def _parse_date(self, date_text: Optional[str]) -> Optional[datetime]:
        """Parse posting date from text."""
        if not date_text:
            return datetime.utcnow()
        
        date_text = date_text.lower()
        now = datetime.utcnow()
        
        if 'just posted' in date_text or 'today' in date_text:
            return now
        elif 'yesterday' in date_text:
            return now - timedelta(days=1)
        elif 'day' in date_text:
            days = re.findall(r'(\d+)', date_text)
            if days:
                return now - timedelta(days=int(days[0]))
        elif 'week' in date_text:
            weeks = re.findall(r'(\d+)', date_text)
            if weeks:
                return now - timedelta(weeks=int(weeks[0]))
        elif 'month' in date_text:
            months = re.findall(r'(\d+)', date_text)
            if months:
                return now - timedelta(days=int(months[0]) * 30)
        
        return now
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def _make_request_with_retry(self, url: str, params: Dict, proxies: Optional[Dict] = None):
        """Make a request with retry logic."""
        response = self.session.get(
            url,
            params=params,
            timeout=15,
            allow_redirects=True,
            proxies=proxies
        )
        response.raise_for_status()
        return response
    
    def _search_via_scrapeops(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Search using ScrapeOps API."""
        raw_jobs = self.scrapeops_api.search_jobs(query, location, remote, max_results)
        jobs = []
        
        for raw_job in raw_jobs:
            try:
                job = self._normalize_scrapeops_job(raw_job)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error normalizing ScrapeOps job: {e}")
                continue
        
        return jobs
    
    def _search_via_hasdata(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Search using HasData API."""
        raw_jobs = self.hasdata_api.search_jobs(query, location, remote, max_results)
        jobs = []
        
        for raw_job in raw_jobs:
            try:
                job = self._normalize_hasdata_job(raw_job)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"Error normalizing HasData job: {e}")
                continue
        
        return jobs
    
    def _normalize_scrapeops_job(self, raw_job: Dict[str, Any]) -> Optional[JobListing]:
        """Normalize a job from ScrapeOps API."""
        try:
            return JobListing(
                title=raw_job.get('title', ''),
                company=raw_job.get('company', ''),
                location=raw_job.get('location'),
                description=raw_job.get('description') or raw_job.get('snippet'),
                raw_description=raw_job.get('description'),
                keywords=self.extract_keywords(raw_job.get('description', '')),
                salary_min=raw_job.get('salary_min'),
                salary_max=raw_job.get('salary_max'),
                posting_date=self._parse_date(raw_job.get('date')),
                source="indeed",
                source_url=raw_job.get('url', ''),
                application_type="external",
                metadata=raw_job
            )
        except Exception as e:
            logger.warning(f"Error normalizing ScrapeOps job: {e}")
            return None
    
    def _normalize_hasdata_job(self, raw_job: Dict[str, Any]) -> Optional[JobListing]:
        """Normalize a job from HasData API."""
        try:
            return JobListing(
                title=raw_job.get('job_title', ''),
                company=raw_job.get('company_name', ''),
                location=raw_job.get('location'),
                description=raw_job.get('job_description') or raw_job.get('summary'),
                raw_description=raw_job.get('job_description'),
                keywords=self.extract_keywords(raw_job.get('job_description', '')),
                salary_min=raw_job.get('salary_min'),
                salary_max=raw_job.get('salary_max'),
                posting_date=self._parse_date(raw_job.get('posted_date')),
                source="indeed",
                source_url=raw_job.get('job_url', ''),
                application_type="external",
                metadata=raw_job
            )
        except Exception as e:
            logger.warning(f"Error normalizing HasData job: {e}")
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
            "Insurance Innovations Co", "DataFin Tech", "Product Leaders Inc",
            "InsurTech Ventures", "Analytics Pro", "Insurance Data Co",
        ]
        
        mock_jobs = []
        for i in range(min(max_results, 4)):  # Generate 4 mock jobs
            company = mock_companies[i % len(mock_companies)]
            job = JobListing(
                title=f"{query} - {company}",
                company=company,
                location=location or "Remote, US" if remote else "New York, NY",
                description=f"We are looking for a talented {query} to drive product strategy. "
                          f"Experience in insurance or financial services is highly valued.",
                raw_description=f"Indeed job posting for {query} at {company}...",
                qualifications="3+ years PM experience, Insurance industry knowledge preferred, "
                             "Strong analytical skills",
                keywords=self.extract_keywords(f"{query} product management insurance analytics"),
                salary_min=100000 + (i * 15000),
                salary_max=160000 + (i * 25000),
                posting_date=datetime.utcnow() - timedelta(days=i),
                source="indeed",
                source_url=f"https://indeed.com/viewjob?jk={987654321 + i}",
                application_type="external",  # Indeed typically uses external applications
            )
            mock_jobs.append(job)
        
        return mock_jobs
