"""Greenhouse Job Board API adapter for fetching jobs from companies using Greenhouse ATS."""

import logging
import time
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from urllib.parse import urljoin

import requests

from app.jobsources.base import BaseJobSource, JobListing

logger = logging.getLogger(__name__)


class GreenhouseAdapter(BaseJobSource):
    """
    Greenhouse Job Board API adapter.

    Fetches jobs directly from Greenhouse's public API. No authentication required.
    Each company has a unique board_token (e.g., 'stripe', 'airbnb').

    API Docs: https://developers.greenhouse.io/job-board.html
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Greenhouse adapter.

        Args:
            config: Configuration dictionary with optional keys:
                - companies: List of Greenhouse board tokens to search
                - rate_limit_delay: Delay between API calls (default: 0.5s)
                - include_content: Whether to fetch full job descriptions (default: True)
        """
        super().__init__(config)
        self.base_api_url = "https://boards-api.greenhouse.io/v1/boards"
        self.rate_limit_delay = config.get("rate_limit_delay", 0.5) if config else 0.5
        self.include_content = config.get("include_content", True) if config else True

        # Companies to search - user can provide custom list or use defaults
        self.companies = config.get("companies", []) if config else []
        
        # If no companies provided in init config, check global config
        if not self.companies:
            from app.config import config as global_config
            job_sources_config = global_config.get_job_sources_config()
            self.companies = job_sources_config.get("greenhouse_companies", [])
        
        # Fallback to defaults only if absolutely nothing else is configured
        if not self.companies:
             self.companies = [
                "stripe", "airbnb", "twitch", "cloudflare", "figma",
                "notion", "databricks", "plaid", "reddit", "coinbase",
                "ramp", "robinhood", "doordash", "instacart", "affirm",
                "brex", "chime", "gusto", "rippling", "airtable",
            ]

        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'JobSearchPipeline/1.0'
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
        Search Greenhouse jobs across configured companies.

        Args:
            query: Job title or search query (matched against job titles)
            location: Location filter (matched against job location)
            remote: If True, prioritize remote positions
            max_results: Maximum total results to return
            **kwargs: Additional parameters:
                - companies: Override default company list for this search

        Returns:
            List of JobListing objects
        """
        logger.info(f"=== STARTING GREENHOUSE SEARCH ===")
        logger.info(f"Query: '{query}', Location: {location}, Remote: {remote}, Max Results: {max_results}")

        # Allow per-search company override
        companies = kwargs.get("companies", self.companies)
        logger.info(f"Searching {len(companies)} Greenhouse companies")

        all_jobs = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for company in companies:
            if len(all_jobs) >= max_results:
                break

            try:
                company_jobs = self._fetch_company_jobs(company)
                logger.info(f"  {company}: fetched {len(company_jobs)} total jobs")

                # Filter jobs by query and location
                for job_data in company_jobs:
                    if len(all_jobs) >= max_results:
                        break

                    # Match against query
                    title = job_data.get("title", "").lower()
                    title_words = set(title.split())

                    # Check if any query word appears in title
                    if not query_words.intersection(title_words):
                        # Also check for partial matches
                        if not any(qw in title for qw in query_words):
                            continue

                    # Match against location if specified
                    job_location = job_data.get("location", {}).get("name", "")
                    if location:
                        location_lower = location.lower()
                        job_location_lower = job_location.lower()
                        if location_lower not in job_location_lower:
                            # Check for remote if that's what we want
                            if remote and "remote" not in job_location_lower:
                                continue
                            elif not remote:
                                continue

                    # If remote filter is on, check for remote positions
                    if remote and "remote" not in job_location.lower():
                        continue

                    # Convert to JobListing
                    job_listing = self._convert_to_job_listing(job_data, company)
                    if job_listing:
                        all_jobs.append(job_listing)

                # Rate limiting between companies
                time.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.warning(f"  {company}: error fetching jobs - {e}")
                continue

        logger.info(f"=== GREENHOUSE SEARCH COMPLETE ===")
        logger.info(f"Total matching jobs found: {len(all_jobs)}")

        return all_jobs[:max_results]

    def _fetch_company_jobs(self, board_token: str) -> List[Dict]:
        """
        Fetch all jobs from a specific Greenhouse company board.

        Args:
            board_token: The company's Greenhouse board token (e.g., 'stripe')

        Returns:
            List of job dictionaries from the API
        """
        url = f"{self.base_api_url}/{board_token}/jobs"
        params = {}

        if self.include_content:
            params["content"] = "true"

        try:
            response = self.session.get(url, params=params, timeout=30)

            if response.status_code == 404:
                logger.debug(f"Board '{board_token}' not found")
                return []

            response.raise_for_status()
            data = response.json()

            return data.get("jobs", [])

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching jobs from {board_token}: {e}")
            return []

    def get_job_details(self, board_token: str, job_id: int) -> Optional[Dict]:
        """
        Fetch detailed information about a specific job.

        Args:
            board_token: The company's Greenhouse board token
            job_id: The job post ID

        Returns:
            Job details dictionary or None if not found
        """
        url = f"{self.base_api_url}/{board_token}/jobs/{job_id}"
        params = {
            "questions": "true",
            "pay_transparency": "true"
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Error fetching job details: {e}")
            return None

    def _convert_to_job_listing(self, job_data: Dict, company: str) -> Optional[JobListing]:
        """
        Convert Greenhouse API response to JobListing object.

        Args:
            job_data: Job dictionary from Greenhouse API
            company: The board token (company identifier)

        Returns:
            JobListing object or None if conversion fails
        """
        try:
            title = job_data.get("title", "")
            location_data = job_data.get("location", {})
            location = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)

            # Get description content
            content = job_data.get("content", "")

            # Clean HTML from content if present
            if content:
                # Simple HTML tag removal
                description = re.sub(r'<[^>]+>', ' ', content)
                description = re.sub(r'\s+', ' ', description).strip()
            else:
                description = None

            # Get departments
            departments = job_data.get("departments", [])
            dept_names = [d.get("name", "") for d in departments if isinstance(d, dict)]

            # Get offices
            offices = job_data.get("offices", [])
            office_names = [o.get("name", "") for o in offices if isinstance(o, dict)]

            # Parse updated_at date
            updated_at = job_data.get("updated_at")
            posting_date = None
            if updated_at:
                try:
                    # Greenhouse uses ISO format
                    posting_date = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except:
                    posting_date = datetime.utcnow()

            # Build source URL
            absolute_url = job_data.get("absolute_url", "")
            if not absolute_url:
                job_id = job_data.get("id")
                absolute_url = f"https://boards.greenhouse.io/{company}/jobs/{job_id}"

            # Extract keywords from title and description
            keywords = self.extract_keywords(f"{title} {description or ''} {' '.join(dept_names)}")

            # Determine if this is likely an easy apply (Greenhouse has built-in applications)
            application_type = "easy_apply"  # Greenhouse jobs typically support direct application

            # Get pay transparency data if available
            salary_min = None
            salary_max = None
            pay_data = job_data.get("pay_input_ranges", [])
            if pay_data and len(pay_data) > 0:
                first_range = pay_data[0]
                salary_min = first_range.get("min_cents", 0) // 100 if first_range.get("min_cents") else None
                salary_max = first_range.get("max_cents", 0) // 100 if first_range.get("max_cents") else None

            return JobListing(
                title=title,
                company=company.title(),  # Capitalize company name
                location=location,
                description=description,
                raw_description=content,  # Keep original HTML
                qualifications=None,  # Would need to parse from description
                keywords=keywords,
                salary_min=salary_min,
                salary_max=salary_max,
                posting_date=posting_date,
                source="greenhouse",
                source_url=absolute_url,
                application_type=application_type,
                metadata={
                    "greenhouse_id": job_data.get("id"),
                    "internal_job_id": job_data.get("internal_job_id"),
                    "requisition_id": job_data.get("requisition_id"),
                    "departments": dept_names,
                    "offices": office_names,
                    "board_token": company,
                }
            )

        except Exception as e:
            logger.warning(f"Error converting Greenhouse job to JobListing: {e}")
            return None

    def get_available_companies(self) -> List[str]:
        """Return the list of configured companies to search."""
        return self.companies.copy()

    def add_company(self, board_token: str) -> None:
        """Add a company to the search list."""
        if board_token not in self.companies:
            self.companies.append(board_token)
            logger.info(f"Added company '{board_token}' to Greenhouse search list")

    def remove_company(self, board_token: str) -> bool:
        """Remove a company from the search list."""
        if board_token in self.companies:
            self.companies.remove(board_token)
            logger.info(f"Removed company '{board_token}' from Greenhouse search list")
            return True
        return False
