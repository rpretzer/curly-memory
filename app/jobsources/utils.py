"""Utility functions for job source adapters."""

import time
import random
import logging
from typing import Optional, List, Dict, Any, Callable, TypeVar
from functools import wraps
import requests

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter to delays
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        if jitter:
                            delay = min(
                                delay * exponential_base + random.uniform(0, 1),
                                max_delay
                            )
                        else:
                            delay = min(delay * exponential_base, max_delay)
                        
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
            
            raise last_exception
        return wrapper
    return decorator


class ProxyRotator:
    """Manages proxy rotation for requests."""
    
    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize proxy rotator.
        
        Args:
            proxies: List of proxy URLs in format "http://user:pass@host:port"
        """
        self.proxies = proxies or []
        self.current_index = 0
        self.failed_proxies = set()
    
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get the next proxy in rotation.
        
        Returns:
            Proxy dictionary for requests, or None if no proxies available
        """
        if not self.proxies:
            return None
        
        # Filter out failed proxies
        available = [p for i, p in enumerate(self.proxies) if i not in self.failed_proxies]
        
        if not available:
            # Reset failed proxies if all are marked as failed
            logger.warning("All proxies marked as failed, resetting...")
            self.failed_proxies.clear()
            available = self.proxies
        
        # Round-robin selection
        proxy_url = available[self.current_index % len(available)]
        self.current_index += 1
        
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def mark_failed(self, proxy_url: str):
        """Mark a proxy as failed."""
        try:
            index = self.proxies.index(proxy_url)
            self.failed_proxies.add(index)
            logger.warning(f"Marked proxy {index} as failed")
        except ValueError:
            pass
    
    def reset(self):
        """Reset failed proxies."""
        self.failed_proxies.clear()
        logger.info("Reset failed proxies")


class ThirdPartyAPI:
    """Base class for third-party job API integrations."""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize third-party API client.
        
        Args:
            api_key: API key for authentication
            base_url: Base URL for the API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
    
    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for jobs using the third-party API.
        
        Args:
            query: Job title or search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results
            **kwargs: Additional parameters
            
        Returns:
            List of raw job dictionaries
        """
        raise NotImplementedError("Subclasses must implement search_jobs")


class ScrapeOpsAPI(ThirdPartyAPI):
    """ScrapeOps Indeed Job Search API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ScrapeOps API client.
        
        Args:
            api_key: ScrapeOps API key (get from https://scrapeops.io)
        """
        super().__init__(api_key, "https://proxy.scrapeops.io/v1")
        if api_key:
            self.session.headers.update({
                'X-ScrapeOps-API-Key': api_key
            })
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search Indeed jobs via ScrapeOps API."""
        if not self.api_key:
            raise ValueError("ScrapeOps API key required")
        
        # Build the Indeed URL with query parameters
        from urllib.parse import urlencode
        indeed_params = {'q': query}
        if location:
            indeed_params['l'] = location
        if remote:
            indeed_params['remotejob'] = '1'
        
        indeed_url = f"https://www.indeed.com/jobs?{urlencode(indeed_params)}"
        
        # ScrapeOps API parameters
        params = {
            'api_key': self.api_key,
            'url': indeed_url,
        }
        
        response = self.session.get(
            f"{self.base_url}/scrape",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        # ScrapeOps returns data in different formats - try multiple paths
        jobs = []
        if isinstance(data, dict):
            # Try common response formats
            jobs = (
                data.get('results', {}).get('jobs', []) or
                data.get('jobs', []) or
                data.get('data', {}).get('jobs', []) or
                data.get('body', {}).get('jobs', []) or
                []
            )
        
        # If no jobs found in structured format, the HTML is in the response
        # We'd need to parse it, but for now return what we found
        return jobs[:max_results] if jobs else []


class HasDataAPI(ThirdPartyAPI):
    """HasData Indeed API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize HasData API client.
        
        Args:
            api_key: HasData API key (get from https://hasdata.com)
        """
        super().__init__(api_key, "https://api.hasdata.com/v1")
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search Indeed jobs via HasData API."""
        if not self.api_key:
            raise ValueError("HasData API key required")
        
        params = {
            'query': query,
            'limit': min(max_results, 100),
        }
        
        if location:
            params['location'] = location
        
        if remote:
            params['remote'] = 'true'
        
        response = self.session.get(
            f"{self.base_url}/indeed/jobs",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get('jobs', [])


class ApifyLinkedInAPI(ThirdPartyAPI):
    """Apify LinkedIn Jobs API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Apify API client for LinkedIn.
        
        Args:
            api_key: Apify API key (get from https://apify.com)
        """
        super().__init__(api_key, "https://api.apify.com/v2")
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}'
            })
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search LinkedIn jobs via Apify API."""
        if not self.api_key:
            raise ValueError("Apify API key required")
        
        # Apify uses actor runs - this is a simplified version
        # You'd typically use their LinkedIn Jobs Scraper actor
        params = {
            'keywords': query,
            'location': location or '',
            'limit': min(max_results, 100),
        }
        
        if remote:
            params['remote'] = 'true'
        
        # Note: This is a placeholder - actual Apify integration requires
        # running an actor and polling for results
        # For now, return empty list - full implementation would require
        # actor run management
        logger.warning("Apify LinkedIn API requires actor run management - not fully implemented")
        return []


class MantiksLinkedInAPI(ThirdPartyAPI):
    """Mantiks LinkedIn Jobs API integration."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Mantiks API client for LinkedIn.
        
        Args:
            api_key: Mantiks API key (get from https://mantiks.io)
        """
        super().__init__(api_key, "https://api.mantiks.io/v1")
        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })
    
    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    def search_jobs(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search LinkedIn jobs via Mantiks API."""
        if not self.api_key:
            raise ValueError("Mantiks API key required")
        
        payload = {
            'query': query,
            'limit': min(max_results, 100),
        }
        
        if location:
            payload['location'] = location
        
        if remote:
            payload['remote'] = True
        
        response = self.session.post(
            f"{self.base_url}/linkedin/jobs",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get('jobs', [])


def get_user_agents() -> List[str]:
    """Get a list of realistic user agents for rotation."""
    return [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    ]


def rotate_user_agent(session: requests.Session):
    """Set a random user agent on a requests session."""
    session.headers.update({
        'User-Agent': random.choice(get_user_agents()),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    })

