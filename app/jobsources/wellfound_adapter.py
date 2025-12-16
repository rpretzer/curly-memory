"""Wellfound (formerly AngelList) job source adapter (stubbed for API integration)."""

import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.jobsources.base import BaseJobSource, JobListing

logger = logging.getLogger(__name__)


class WellfoundAdapter(BaseJobSource):
    """Wellfound job search adapter."""
    
    def __init__(self, config: Optional[Dict] = None, api_key: Optional[str] = None):
        """
        Initialize Wellfound adapter.
        
        Args:
            config: Configuration dictionary
            api_key: Wellfound API key (if available)
        """
        super().__init__(config)
        self.api_key = api_key
        self.rate_limit_delay = config.get("rate_limit_delay", 2.0) if config else 2.0
        self.base_url = "https://api.angel.co"  # Placeholder - Wellfound may have different API
    
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[JobListing]:
        """
        Search Wellfound jobs.
        
        TODO: Integrate with Wellfound API when available.
        For now, returns mock data for demonstration.
        
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
        
        # TODO: Implement actual Wellfound API integration
        # Example API call structure:
        # response = requests.get(
        #     f"{self.base_url}/jobs",
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        #     params={
        #         "keywords": query,
        #         "location": location or "",
        #         "remote": remote,
        #         "per_page": max_results,
        #     }
        # )
        
        # For now, return mock data
        mock_jobs = self._generate_mock_jobs(query, location, remote, max_results)
        return mock_jobs
    
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
