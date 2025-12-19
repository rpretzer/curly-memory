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
        self.use_playwright = config.get("use_playwright", False) if config else False
        self._playwright = None
        self._browser = None
        
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
        logger.info(f"=== STARTING INDEED SEARCH ===")
        logger.info(f"Query: '{query}', Location: {location}, Remote: {remote}, Max Results: {max_results}")
        
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
            
            # Allow fetching more pages, but add safety limit to prevent infinite loops
            max_pages = max(10, (max_results // results_per_page) + 2)  # Allow extra pages
            page_count = 0
            while len(jobs) < max_results and page_count < max_pages:
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
                    
                    search_url = f"{self.base_url}/jobs"
                    logger.info(f"=== FETCHING INDEED PAGE {page_count + 1} ===")
                    logger.info(f"URL: {search_url}")
                    logger.info(f"Params: {params}")
                    logger.info(f"Start offset: {start}, Results per page: {results_per_page}")
                    
                    response = self._make_request_with_retry(
                        search_url,
                        params=params,
                        proxies=proxies
                    )
                    
                    logger.info(f"Response status: {response.status_code}")
                    logger.info(f"Response size: {len(response.text)} characters")
                    logger.info(f"Final URL: {response.url}")
                    
                    # Check status before processing
                    if response.status_code == 403:
                        logger.error("=== 403 FORBIDDEN - Rate limited or blocked ===")
                        logger.error(f"Response preview: {response.text[:500]}")
                        break
                    
                    response.raise_for_status()
                    
                    # Check for CAPTCHA more carefully (only if we see specific patterns)
                    content_preview = response.text[:2000].lower()
                    if 'captcha' in content_preview and ('verify' in content_preview or 'robot' in content_preview):
                        logger.warning("CAPTCHA detected on Indeed")
                        break
                    
                    logger.info("Parsing HTML with BeautifulSoup...")
                    soup = BeautifulSoup(response.content, 'html.parser')
                    logger.info(f"HTML parsed. Looking for job cards...")
                    
                    # Try multiple selectors for Indeed's job cards (try each until we find results)
                    job_cards = []
                    selectors = [
                        ('div', {'data-jk': True}),
                        ('div', {'class': 'job_seen_beacon'}),
                        ('div', {'class': 'slider_container'}),
                        ('td', {'data-jk': True}),
                        ('div', {'class': 'job_seen_beacon'}),
                        ('a', {'data-jk': True}),
                        ('div', {'id': lambda x: x and 'job_' in x}),
                    ]
                    
                    logger.info(f"Trying {len(selectors)} different selectors...")
                    for idx, (tag, attrs) in enumerate(selectors, 1):
                        found = soup.find_all(tag, attrs)
                        logger.info(f"Selector {idx}/{len(selectors)}: {tag} with {attrs} -> Found {len(found)} elements")
                        if found:
                            job_cards = found
                            logger.info(f"✓ SUCCESS: Found {len(job_cards)} job cards using selector: {tag} with {attrs}")
                            break
                    
                    if not job_cards:
                        # Try a more generic approach - look for links containing /viewjob
                        job_links = soup.find_all('a', href=re.compile(r'/viewjob|jk='))
                        if job_links:
                            logger.info(f"Found {len(job_links)} job links using generic approach")
                            # Create minimal card objects from links - wrap them in a div-like structure
                            job_cards = job_links[:max_results]
                            # We'll need special parsing for these
                        else:
                            logger.warning(f"No job cards found on Indeed page (start={start}). Page length: {len(response.text)} chars")
                            # Save HTML sample for debugging
                            if start == 0:  # Only save for first page
                                try:
                                    # Save a sample of the HTML
                                    html_sample_path = "indeed_html_sample.html"
                                    with open(html_sample_path, 'w', encoding='utf-8') as f:
                                        f.write(response.text[:50000])  # First 50k chars
                                    logger.error(f"Saved HTML sample to {html_sample_path} for inspection")
                                    
                                    # Try to find ANY divs with job-related classes/ids
                                    all_divs = soup.find_all('div')
                                    logger.info(f"Total divs on page: {len(all_divs)}")
                                    
                                    # Look for divs with job-related attributes
                                    job_related_divs = []
                                    for div in all_divs[:100]:  # Check first 100 divs
                                        attrs = div.attrs
                                        if any(key in str(attrs).lower() for key in ['job', 'result', 'card', 'listing', 'position']):
                                            job_related_divs.append((div.name, attrs, div.get_text()[:50]))
                                    
                                    if job_related_divs:
                                        logger.info(f"Found {len(job_related_divs)} potentially job-related divs:")
                                        for name, attrs, text in job_related_divs[:10]:
                                            logger.info(f"  {name} with {attrs}: {text}...")
                                    
                                    # Look for any links with job IDs
                                    all_links = soup.find_all('a', href=True)
                                    viewjob_links = [a for a in all_links if '/viewjob' in a.get('href', '') or 'jk=' in a.get('href', '')]
                                    logger.info(f"Found {len(viewjob_links)} links with /viewjob or jk= in href")
                                    if viewjob_links:
                                        logger.info(f"Sample link: {viewjob_links[0].get('href')}")
                                        # Try to find parent elements
                                        for link in viewjob_links[:5]:
                                            parent = link.parent
                                            if parent:
                                                logger.info(f"Link parent: {parent.name} with classes: {parent.get('class', [])}")
                                    
                                except Exception as e:
                                    logger.error(f"Error saving HTML sample: {e}")
                                
                                logger.error(f"Indeed page structure may have changed. Response status: {response.status_code}, URL: {response.url}")
                            break
                    
                    cards_to_process = min(results_per_page, max_results - len(jobs))
                    logger.info(f"=== PARSING JOB CARDS ===")
                    logger.info(f"Total cards found: {len(job_cards)}")
                    logger.info(f"Cards to process: {cards_to_process}")
                    logger.info(f"Already have {len(jobs)} jobs, need {max_results - len(jobs)} more")
                    
                    parsed_count = 0
                    failed_count = 0
                    for idx, card in enumerate(job_cards[:cards_to_process], 1):
                        try:
                            logger.debug(f"Parsing card {idx}/{cards_to_process}...")
                            job = self._parse_job_card(card)
                            if job:
                                jobs.append(job)
                                parsed_count += 1
                                logger.debug(f"✓ Card {idx}: Successfully parsed '{job.title}' at {job.company}")
                            else:
                                failed_count += 1
                                logger.warning(f"✗ Card {idx}: Parsed but returned None")
                        except Exception as e:
                            failed_count += 1
                            logger.warning(f"✗ Card {idx}: Error parsing job card: {e}", exc_info=True)
                            continue
                    
                    logger.info(f"=== PARSING SUMMARY ===")
                    logger.info(f"Successfully parsed: {parsed_count}/{cards_to_process}")
                    logger.info(f"Failed/None: {failed_count}/{cards_to_process}")
                    logger.info(f"Total jobs collected so far: {len(jobs)}/{max_results}")
                    
                    # Check if there are more pages
                    if len(job_cards) < results_per_page:
                        break
                    
                    start += results_per_page
                    page_count += 1
                    time.sleep(self.rate_limit_delay)  # Rate limit between pages
                    
                except requests.RequestException as e:
                    logger.error(f"Error fetching Indeed page: {e}")
                    break
            
            logger.info(f"=== INDEED DIRECT SCRAPING COMPLETE ===")
            logger.info(f"Total jobs found: {len(jobs)}")
            logger.info(f"Requested max: {max_results}")
            logger.info(f"Pages fetched: {page_count}")
            
            # If we got 0 jobs and Playwright is enabled, try Playwright as fallback
            if len(jobs) == 0 and self.use_playwright:
                logger.warning("Direct scraping found 0 jobs, trying Playwright fallback...")
                try:
                    playwright_jobs = self._scrape_with_playwright(query, location, remote, max_results)
                    logger.info(f"Playwright found {len(playwright_jobs)} jobs")
                    return playwright_jobs[:max_results]
                except Exception as e:
                    logger.error(f"Playwright fallback also failed: {e}", exc_info=True)
                    logger.warning("Returning 0 jobs - both direct scraping and Playwright failed")
            
            logger.info(f"Returning {min(len(jobs), max_results)} jobs")
            return jobs[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching Indeed: {e}", exc_info=True)
            # Don't use mock data - raise error to indicate real scraping failed
            raise Exception(f"Failed to scrape Indeed jobs: {str(e)}. Please check network connectivity, rate limits, or consider using a third-party API service.")
    
    def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parse a job card from Indeed search results with multiple selector fallbacks."""
        try:
            # If card is a link element (from fallback parsing), handle it differently
            if hasattr(card, 'name') and card.name == 'a' and card.get('href'):
                return self._parse_job_from_link(card)
            
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
            logger.warning(f"Error parsing Indeed job card: {e}", exc_info=True)
            return None
    
    def _parse_job_from_link(self, link) -> Optional[JobListing]:
        """Parse job information from a link element (fallback method)."""
        try:
            href = link.get('href', '')
            # Extract job ID from URL
            job_id_match = re.search(r'jk=([^&]+)', href)
            job_id = job_id_match.group(1) if job_id_match else None
            
            # Get title from link text or parent
            title = link.get_text(strip=True) or "Unknown Title"
            
            # Try to find company and location in nearby elements
            parent = link.parent
            company = "Unknown Company"
            location = None
            
            # Look for company name nearby
            if parent:
                company_elem = parent.find('span', class_=re.compile('company', re.I)) or parent.find('div', class_=re.compile('company', re.I))
                if company_elem:
                    company = company_elem.get_text(strip=True)
                
                location_elem = parent.find('div', class_=re.compile('location', re.I)) or parent.find('span', class_=re.compile('location', re.I))
                if location_elem:
                    location = location_elem.get_text(strip=True)
            
            # Build URL
            if href.startswith('/'):
                url = urljoin(self.base_url, href)
            elif href.startswith('http'):
                url = href
            elif job_id:
                url = f"{self.base_url}/viewjob?jk={job_id}"
            else:
                return None  # Can't build valid URL
            
            # Extract keywords from title
            keywords = self.extract_keywords(title)
            
            return JobListing(
                title=title,
                company=company,
                location=location,
                source="indeed",
                source_url=url,
                description=None,  # Would need to fetch full page for description
                keywords=keywords,
                application_type="unknown",
            )
        except Exception as e:
            logger.warning(f"Error parsing job from link: {e}", exc_info=True)
            return None
    
    def _scrape_with_playwright(
        self,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """Scrape Indeed jobs using Playwright to handle JavaScript rendering."""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
            
            logger.info("=== STARTING INDEED PLAYWRIGHT SCRAPING ===")
            
            if not self._playwright:
                self._playwright = sync_playwright().start()
                # Launch with stealth settings to avoid detection
                self._browser = self._playwright.chromium.launch(
                    headless=False,  # Use non-headless to avoid detection
                    args=['--disable-blink-features=AutomationControlled']
                )
            
            page = self._browser.new_page()
            # Set realistic headers to avoid detection
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            # Remove webdriver flag
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # Build search URL
            search_url = f"{self.base_url}/jobs"
            params = {
                'q': query,
            }
            
            if location:
                params['l'] = location
            
            if remote:
                params['remotejob'] = '1'
            
            # Build URL with params
            param_str = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
            url = f"{search_url}?{param_str}"
            
            logger.info(f"Navigating to Indeed with Playwright: {url}")
            # Use 'load' instead of 'networkidle' - Indeed may have continuous network activity
            try:
                page.goto(url, wait_until='load', timeout=60000)
                logger.info("Page loaded, waiting for JavaScript to render...")
            except Exception as e:
                logger.warning(f"Page load timeout, but continuing anyway: {e}")
                # Page may have partially loaded
            
            # Give time for JavaScript to render
            time.sleep(8)  # Increased wait time for JS rendering
            
            # Wait for page to be interactive
            try:
                page.wait_for_load_state('domcontentloaded', timeout=5000)
            except:
                logger.debug("domcontentloaded timeout (may be OK)")
                pass
            
            jobs = []
            page_num = 0
            max_pages = max(5, (max_results // 15) + 1)  # Indeed shows ~15 jobs per page
            
            while len(jobs) < max_results and page_num < max_pages:
                logger.info(f"=== PLAYWRIGHT PAGE {page_num + 1} ===")
                
                # Try to wait for any job-related elements (try multiple selectors)
                job_found = False
                selectors_to_wait = [
                    'div[data-jk]',
                    'a[href*="/viewjob"]',
                    '.job_seen_beacon',
                    '.jobCard',
                    'div[id*="job"]',
                    'ul.resultsList',
                    '[data-testid*="job"]',
                ]
                
                for selector in selectors_to_wait:
                    try:
                        page.wait_for_selector(selector, timeout=5000)
                        logger.info(f"Found page element with selector: {selector}")
                        job_found = True
                        break
                    except PlaywrightTimeout:
                        continue
                
                if not job_found and page_num == 0:
                    logger.warning("No job-related elements found, page may be blocked or have no results")
                    # Try to get page title to see what we got
                    try:
                        title = page.title()
                        logger.info(f"Page title: {title}")
                    except:
                        pass
                    break
                
                # Try multiple selectors for job cards - Indeed uses various structures
                job_cards = []
                selectors = [
                    'div[data-jk]',  # Primary selector
                    'a[href*="/viewjob"]',  # Job links
                    'a[href*="/viewjob?jk="]',  # More specific job links
                    '.job_seen_beacon',  # Job card container
                    '.jobCard',  # Job card class
                    'div[class*="job"]',  # Any div with "job" in class
                    'div[class*="result"]',  # Result containers
                    'li[data-jk]',  # List items with job ID
                    'div[id*="job_"]',  # Divs with job ID in id
                    '[data-testid*="job"]',  # Elements with job test ID
                ]
                
                for selector in selectors:
                    try:
                        found = page.query_selector_all(selector)
                        if found and len(found) > 0:
                            job_cards = found
                            logger.info(f"✓ Found {len(job_cards)} job cards using selector: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue
                
                # If still no cards, try getting all links and filtering
                if not job_cards:
                    logger.info("Trying alternative: looking for all links with /viewjob")
                    all_links = page.query_selector_all('a[href]')
                    viewjob_links = []
                    for link in all_links:
                        href = link.get_attribute('href') or ''
                        if '/viewjob' in href or 'jk=' in href:
                            viewjob_links.append(link)
                    if viewjob_links:
                        job_cards = viewjob_links
                        logger.info(f"✓ Found {len(job_cards)} job links via alternative method")
                
                if not job_cards:
                    logger.warning(f"No job cards found on page {page_num + 1}")
                    break
                
                logger.info(f"Processing {len(job_cards)} job cards (already have {len(jobs)} jobs)")
                
                # Parse each card
                parsed_count = 0
                for card in job_cards:
                    if len(jobs) >= max_results:
                        break
                    
                    try:
                        job = self._parse_indeed_card_playwright(card, page)
                        if job:
                            # Check for duplicates
                            if not any(j.source_url == job.source_url for j in jobs):
                                jobs.append(job)
                                parsed_count += 1
                    except Exception as e:
                        logger.warning(f"Error parsing Indeed job card: {e}")
                        continue
                
                logger.info(f"Successfully parsed {parsed_count} jobs from {len(job_cards)} cards")
                
                # Try to go to next page if we need more results
                if len(jobs) < max_results and len(job_cards) >= 10:  # If we got a full page
                    try:
                        # Look for next page button
                        next_button = page.query_selector('a[aria-label="Next Page"], a[data-testid="pagination-page-next"], a[aria-label="Next"]')
                        if next_button:
                            next_button.click()
                            page.wait_for_load_state('networkidle', timeout=10000)
                            time.sleep(2)
                            page_num += 1
                        else:
                            logger.info("No next page button found, stopping pagination")
                            break
                    except Exception as e:
                        logger.warning(f"Error navigating to next page: {e}")
                        break
                else:
                    break
            
            page.close()
            logger.info(f"=== INDEED PLAYWRIGHT SCRAPING COMPLETE ===")
            logger.info(f"Total jobs found: {len(jobs)}")
            return jobs[:max_results]
            
        except ImportError:
            logger.error("Playwright not installed. Install with: pip install playwright && playwright install")
            raise Exception("Playwright not installed. Required for Indeed scraping. Install with: pip install playwright && playwright install chromium")
        except Exception as e:
            logger.error(f"Error in Playwright scraping: {e}", exc_info=True)
            raise Exception(f"Failed to scrape Indeed with Playwright: {str(e)}")
    
    def _parse_indeed_card_playwright(self, card, page) -> Optional[JobListing]:
        """Parse a job card from Indeed using Playwright element."""
        try:
            # Get job ID from data-jk attribute or href
            job_id = card.get_attribute('data-jk') or ''
            if not job_id:
                href = card.get_attribute('href') or ''
                match = re.search(r'jk=([^&]+)', href)
                if match:
                    job_id = match.group(1)
            
            # Try to get title - Indeed uses various structures
            title = "Unknown Title"
            title_selectors = [
                'h2.jobTitle a',
                'h2 a',
                'a[data-jk]',
                '.jobTitle',
                'span[title]',
            ]
            for selector in title_selectors:
                try:
                    title_elem = card.query_selector(selector)
                    if title_elem:
                        title = title_elem.inner_text().strip()
                        if title and title != "Unknown Title":
                            break
                except:
                    continue
            
            # If still no title, try getting text directly
            if title == "Unknown Title":
                try:
                    title = card.inner_text().strip().split('\n')[0][:100]
                except:
                    pass
            
            # Company
            company = "Unknown Company"
            company_selectors = [
                'span[data-testid="company-name"]',
                '.companyName',
                '[data-testid="company-name"]',
            ]
            for selector in company_selectors:
                try:
                    company_elem = card.query_selector(selector)
                    if company_elem:
                        company = company_elem.inner_text().strip()
                        if company:
                            break
                except:
                    continue
            
            # Location
            location = None
            location_selectors = [
                'div[data-testid="text-location"]',
                '.companyLocation',
                '[data-testid="job-location"]',
            ]
            for selector in location_selectors:
                try:
                    location_elem = card.query_selector(selector)
                    if location_elem:
                        location = location_elem.inner_text().strip()
                        if location:
                            break
                except:
                    continue
            
            # Build URL
            if job_id:
                url = f"{self.base_url}/viewjob?jk={job_id}"
            else:
                href = card.get_attribute('href') if hasattr(card, 'get_attribute') else None
                if href:
                    if href.startswith('/'):
                        url = urljoin(self.base_url, href)
                    elif href.startswith('http'):
                        url = href
                    else:
                        return None  # Can't build valid URL
                else:
                    return None
            
            # Description snippet (if available)
            description = None
            try:
                desc_elem = card.query_selector('.job-snippet, .summary')
                if desc_elem:
                    description = desc_elem.inner_text().strip()
            except:
                pass
            
            # Extract keywords from title and description
            keywords = self.extract_keywords(f"{title} {description or ''}")
            
            return JobListing(
                title=title,
                company=company,
                location=location,
                source="indeed",
                source_url=url,
                description=description,
                raw_description=description,
                keywords=keywords,
                application_type="external",
                metadata={"job_id": job_id}
            )
        except Exception as e:
            logger.warning(f"Error parsing Indeed Playwright card: {e}", exc_info=True)
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
