"""Wellfound (formerly AngelList) job source adapter with web scraping."""

import time
import logging
import re
import random
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from app.jobsources.base import BaseJobSource, JobListing

logger = logging.getLogger(__name__)


class WellfoundAdapter(BaseJobSource):
    """Wellfound job search adapter."""
    
    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize Wellfound adapter.
        
        Args:
            config: Configuration dictionary
            api_key: Wellfound API key (not used for scraping)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 3.0) if config else 3.0
        self.base_url = "https://wellfound.com"  # Wellfound (formerly AngelList)
        self.session = requests.Session()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        self._set_random_user_agent()
    
    def _set_random_user_agent(self):
        """Set a random user agent."""
        import random
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[JobListing]:
        """
        Search Wellfound jobs via web scraping.
        
        Args:
            query: Job title or search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results
            **kwargs: Additional parameters
            
        Returns:
            List of JobListing objects
        """
        logger.info(f"Searching Wellfound for: {query} (location: {location}, remote: {remote})")
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        
        try:
            jobs = []
            page = 1
            results_per_page = 25
            
            while len(jobs) < max_results:
                # Build search URL - Wellfound uses /jobs endpoint with query params
                search_url = f"{self.base_url}/jobs"
                params = {}
                
                # Build query string
                query_parts = [query]
                if location:
                    query_parts.append(location)
                if remote:
                    query_parts.append("remote")
                
                # Wellfound uses URL path or query parameter for search
                # Try both approaches
                search_query = ' '.join(query_parts)
                params['role'] = query  # Role parameter
                
                if location:
                    params['location'] = location
                
                if remote:
                    params['remote'] = 'true'
                
                # Alternative: try /jobs/search endpoint
                # If first attempt fails, we'll try the alternative
                
                try:
                    # Rotate user agent occasionally
                    if random.random() < 0.3:
                        self._set_random_user_agent()
                    
                    response = self.session.get(
                        search_url,
                        params=params,
                        timeout=15,
                        allow_redirects=True
                    )
                    response.raise_for_status()
                    
                    # Check if we got blocked
                    if response.status_code == 403:
                        logger.warning("Wellfound returned 403 Forbidden - site may be blocking automated requests")
                        logger.warning("Consider using ScrapeOps or Playwright for Wellfound scraping")
                        raise Exception("Wellfound is blocking automated requests (403 Forbidden). Consider using ScrapeOps API or Playwright.")
                    
                    if 'captcha' in response.text.lower():
                        logger.warning("Possible CAPTCHA detected on Wellfound")
                        time.sleep(self.rate_limit_delay * 2)
                        continue
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find job listings - Wellfound uses various selectors
                    job_cards = (
                        soup.find_all('div', class_='job-listing') or
                        soup.find_all('div', {'data-testid': 'job-card'}) or
                        soup.find_all('article', class_='job-card')
                    )
                    
                    if not job_cards:
                        logger.warning("No job cards found on Wellfound page")
                        break
                    
                    for card in job_cards[:min(results_per_page, max_results - len(jobs))]:
                        try:
                            job = self._parse_job_card(card)
                            if job:
                                jobs.append(job)
                        except Exception as e:
                            logger.warning(f"Error parsing Wellfound job card: {e}")
                            continue
                    
                    # Check if there are more pages
                    if len(job_cards) < results_per_page:
                        break
                    
                    page += 1
                    time.sleep(self.rate_limit_delay)  # Rate limit between pages
                    
                except requests.RequestException as e:
                    logger.error(f"Error fetching Wellfound page: {e}")
                    break
            
            logger.info(f"Found {len(jobs)} jobs from Wellfound")
            return jobs[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching Wellfound: {e}", exc_info=True)
            # Don't use mock data - raise error to indicate real scraping failed
            raise Exception(f"Failed to scrape Wellfound jobs: {str(e)}. Please check network connectivity, rate limits, or website structure.")
    
    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Wellfound search results."""
        try:
            # Title
            title_elem = (
                card.find('h3') or
                card.find('a', class_='job-title') or
                card.find('div', class_='job-title')
            )
            title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
            
            # Company
            company_elem = (
                card.find('a', class_='startup-link') or
                card.find('div', class_='company-name') or
                card.find('span', class_='company')
            )
            company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
            
            # Location
            location_elem = (
                card.find('span', class_='location') or
                card.find('div', class_='job-location') or
                card.find('span', {'data-testid': 'location'})
            )
            location = location_elem.get_text(strip=True) if location_elem else None
            
            # Description
            desc_elem = (
                card.find('div', class_='job-description') or
                card.find('p', class_='description') or
                card.find('div', class_='snippet')
            )
            description = desc_elem.get_text(strip=True) if desc_elem else None
            
            # URL
            link_elem = card.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if href.startswith('/'):
                    url = urljoin(self.base_url, href)
                else:
                    url = href
            else:
                url = f"{self.base_url}/jobs"
            
            # Salary (if available)
            salary_elem = (
                card.find('span', class_='salary') or
                card.find('div', class_='compensation')
            )
            salary_min, salary_max = self._parse_salary(salary_elem.get_text(strip=True) if salary_elem else None)
            
            # Extract keywords
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
                posting_date=datetime.utcnow(),
                source="wellfound",
                source_url=url,
                application_type="external",
                metadata={}
            )
        except Exception as e:
            logger.warning(f"Error parsing Wellfound job card: {e}")
            return None
    
    def _parse_salary(self, salary_text: Optional[str]) -> tuple[Optional[int], Optional[int]]:
        """Parse salary range from text."""
        if not salary_text:
            return None, None
        
        # Extract numbers (handle ranges like $100k - $150k or $100,000 - $150,000)
        # Handle 'k' suffix
        salary_text = salary_text.lower().replace('k', '000')
        numbers = re.findall(r'\$?([\d,]+)', salary_text.replace(',', ''))
        
        if len(numbers) >= 2:
            return int(numbers[0]), int(numbers[1])
        elif len(numbers) == 1:
            num = int(numbers[0])
            return num, num
        return None, None
    
    def _generate_mock_jobs(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Generate mock job listings for testing."""
        mock_companies = [
            "StartupInsure", "FinTech Startup", "Data Startup Co",
            "AI Insurance Startup", "InsurTech Early Stage", "Product Startup",
        ]
        
        mock_jobs = []
        for i in range(min(max_results, 3)):  # Generate 3 mock jobs
            company = mock_companies[i % len(mock_companies)]
            job = JobListing(
                title=f"{query} - {company}",
                company=company,
                location=location or "Remote" if remote else "San Francisco, CA",
                description=f"Early-stage startup seeking a {query} to build our product team. "
                          f"We're revolutionizing insurance with data and AI.",
                raw_description=f"Wellfound job posting for {query} at {company}...",
                qualifications="2+ years product experience, Startup mindset, "
                             "Passion for insurance/fintech",
                keywords=self.extract_keywords(f"{query} startup product insurance fintech ai"),
                salary_min=90000 + (i * 10000),  # Startups may offer equity
                salary_max=140000 + (i * 20000),
                posting_date=datetime.utcnow() - timedelta(days=i * 2),
                source="wellfound",
                source_url=f"https://wellfound.com/startups/{company.lower().replace(' ', '-')}/jobs/{12345 + i}",
                application_type="external",  # Wellfound uses external applications
            )
            mock_jobs.append(job)
        
        return mock_jobs
