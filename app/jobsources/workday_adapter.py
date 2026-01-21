"""Workday job source adapter for fetching jobs from company Workday instances."""

import logging
import time
import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from urllib.parse import urlparse

import requests

from app.jobsources.base import BaseJobSource, JobListing

logger = logging.getLogger(__name__)

# Known Workday company configurations
# Format: (company_slug, wd_instance, site_name, display_name)
DEFAULT_WORKDAY_COMPANIES = [
    ("adobe", "wd5", "external_experienced", "Adobe"),
    ("salesforce", "wd12", "External_Career_Site", "Salesforce"),
    ("visa", "wd5", "Visa", "Visa"),
    ("mastercard", "wd1", "CorporateCareers", "Mastercard"),
    ("servicenow", "wd1", "ServiceNow", "ServiceNow"),
    ("paloaltonetworks", "wd1", "External", "Palo Alto Networks"),
    ("nvidia", "wd5", "NVIDIAExternalCareerSite", "NVIDIA"),
    ("atlassian", "wd5", "external_career_site", "Atlassian"),
    ("okta", "wd1", "Okta", "Okta"),
    ("zscaler", "wd1", "Zscaler", "Zscaler"),
    ("crowdstrike", "wd5", "crowdstrikecareers", "CrowdStrike"),
    ("docusign", "wd5", "External", "DocuSign"),
    ("veeva", "wd1", "Veeva", "Veeva Systems"),
    ("procore", "wd1", "External_Career_Site", "Procore"),
    ("dropbox", "wd5", "External", "Dropbox"),
]


class WorkdayAdapter(BaseJobSource):
    """
    Workday job source adapter.

    Fetches jobs directly from Workday company career portals.
    Each company has their own Workday instance with URL pattern:
    https://{company}.wd{N}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs

    Note: This uses undocumented but stable Workday APIs that power their public job boards.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize Workday adapter.

        Args:
            config: Configuration dictionary with optional keys:
                - companies: List of (company, wd_instance, site, display_name) tuples
                - rate_limit_delay: Delay between API calls (default: 1.0s)
                - results_per_company: Max results to fetch per company (default: 50)
        """
        super().__init__(config)
        self.rate_limit_delay = config.get("rate_limit_delay", 1.0) if config else 1.0
        self.results_per_company = config.get("results_per_company", 50) if config else 50

        # Companies to search - user can provide custom list or use defaults
        self.companies = config.get("companies", []) if config else []
        if not self.companies:
            self.companies = DEFAULT_WORKDAY_COMPANIES

        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
        Search Workday jobs across configured companies.

        Args:
            query: Job title or search query
            location: Location filter
            remote: If True, search for remote positions
            max_results: Maximum total results to return
            **kwargs: Additional parameters:
                - companies: Override default company list for this search

        Returns:
            List of JobListing objects
        """
        logger.info(f"=== STARTING WORKDAY SEARCH ===")
        logger.info(f"Query: '{query}', Location: {location}, Remote: {remote}, Max Results: {max_results}")

        # Allow per-search company override
        companies = kwargs.get("companies", self.companies)
        logger.info(f"Searching {len(companies)} Workday companies")

        all_jobs = []

        for company_config in companies:
            if len(all_jobs) >= max_results:
                break

            # Unpack company configuration - accept tuple, list, or dict
            if (isinstance(company_config, (tuple, list)) and len(company_config) >= 4):
                company_slug, wd_instance, site_name, display_name = company_config[:4]
            elif isinstance(company_config, dict):
                company_slug = company_config.get("slug")
                wd_instance = company_config.get("instance", "wd1")
                site_name = company_config.get("site")
                display_name = company_config.get("name", company_slug)
            else:
                logger.warning(f"Invalid company config format: {company_config}")
                continue

            try:
                results_needed = min(self.results_per_company, max_results - len(all_jobs))
                company_jobs = self._search_company(
                    company_slug=company_slug,
                    wd_instance=wd_instance,
                    site_name=site_name,
                    display_name=display_name,
                    query=query,
                    location=location,
                    remote=remote,
                    max_results=results_needed
                )

                logger.info(f"  {display_name}: found {len(company_jobs)} matching jobs")
                all_jobs.extend(company_jobs)

                # Rate limiting between companies
                time.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.warning(f"  {display_name}: error searching - {e}")
                continue

        logger.info(f"=== WORKDAY SEARCH COMPLETE ===")
        logger.info(f"Total matching jobs found: {len(all_jobs)}")

        return all_jobs[:max_results]

    def _search_company(
        self,
        company_slug: str,
        wd_instance: str,
        site_name: str,
        display_name: str,
        query: str,
        location: Optional[str],
        remote: bool,
        max_results: int
    ) -> List[JobListing]:
        """
        Search jobs from a specific Workday company instance.

        Args:
            company_slug: Company identifier in URL (e.g., 'adobe')
            wd_instance: Workday instance (e.g., 'wd5')
            site_name: Site name in URL (e.g., 'external_experienced')
            display_name: Human-readable company name
            query: Search query
            location: Location filter
            remote: Remote filter
            max_results: Maximum results

        Returns:
            List of JobListing objects
        """
        # Construct the API URL
        base_url = f"https://{company_slug}.{wd_instance}.myworkdayjobs.com"
        api_url = f"{base_url}/wday/cxs/{company_slug}/{site_name}/jobs"

        # Workday uses POST with search parameters
        search_payload = {
            "appliedFacets": {},
            "limit": min(max_results, 100),  # Workday typically caps at 100
            "offset": 0,
            "searchText": query
        }

        # Add location facet if specified
        if location:
            search_payload["appliedFacets"]["locations"] = [location]

        # Some Workday instances support remote filtering
        if remote:
            search_payload["appliedFacets"]["workerSubType"] = ["Remote"]

        jobs = []

        try:
            response = self.session.post(
                api_url,
                json=search_payload,
                timeout=30
            )

            if response.status_code == 404:
                logger.debug(f"Workday endpoint not found for {display_name}")
                return []

            response.raise_for_status()
            data = response.json()

            job_postings = data.get("jobPostings", [])
            logger.debug(f"Fetched {len(job_postings)} job postings from {display_name}")

            for job_data in job_postings:
                if len(jobs) >= max_results:
                    break

                job_listing = self._convert_to_job_listing(
                    job_data=job_data,
                    base_url=base_url,
                    display_name=display_name,
                    company_slug=company_slug,
                    site_name=site_name
                )
                if job_listing:
                    jobs.append(job_listing)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error searching {display_name}: {e}")

        return jobs

    def _convert_to_job_listing(
        self,
        job_data: Dict,
        base_url: str,
        display_name: str,
        company_slug: str,
        site_name: str
    ) -> Optional[JobListing]:
        """
        Convert Workday API response to JobListing object.

        Args:
            job_data: Job dictionary from Workday API
            base_url: Base URL for the Workday instance
            display_name: Human-readable company name
            company_slug: Company identifier
            site_name: Site name in URL

        Returns:
            JobListing object or None if conversion fails
        """
        try:
            title = job_data.get("title", "")

            # Location can be in different formats
            location_data = job_data.get("locationsText", "") or job_data.get("location", "")
            if isinstance(location_data, dict):
                location = location_data.get("name", "")
            else:
                location = str(location_data)

            # Get posted date
            posted_on = job_data.get("postedOn")
            posting_date = None
            if posted_on:
                try:
                    # Workday uses various date formats
                    if "T" in posted_on:
                        posting_date = datetime.fromisoformat(posted_on.replace("Z", "+00:00"))
                    else:
                        posting_date = datetime.strptime(posted_on, "%Y-%m-%d")
                except (ValueError, AttributeError):
                    posting_date = datetime.utcnow()

            # Build job URL
            external_path = job_data.get("externalPath", "")
            if external_path:
                job_url = f"{base_url}{external_path}"
            else:
                job_url = f"{base_url}/wday/cxs/{company_slug}/{site_name}/jobs"

            # Get description if available
            description = job_data.get("jobDescription") or job_data.get("bulletFields", "")
            if isinstance(description, list):
                description = " ".join(description)

            # Clean HTML if present
            if description:
                description = re.sub(r'<[^>]+>', ' ', str(description))
                description = re.sub(r'\s+', ' ', description).strip()

            # Extract keywords
            keywords = self.extract_keywords(f"{title} {description or ''}")

            # Workday jobs are typically external applications
            application_type = "external"

            return JobListing(
                title=title,
                company=display_name,
                location=location,
                description=description[:2000] if description else None,  # Limit length
                raw_description=job_data.get("jobDescription"),
                qualifications=None,
                keywords=keywords,
                salary_min=None,  # Workday rarely exposes salary in API
                salary_max=None,
                posting_date=posting_date,
                source="workday",
                source_url=job_url,
                application_type=application_type,
                metadata={
                    "workday_id": job_data.get("bulletFields", [None])[0] if job_data.get("bulletFields") else None,
                    "company_slug": company_slug,
                    "site_name": site_name,
                    "external_path": external_path,
                }
            )

        except Exception as e:
            logger.warning(f"Error converting Workday job to JobListing: {e}")
            return None

    def get_company_jobs_url(self, company_slug: str, wd_instance: str, site_name: str) -> str:
        """Get the public job board URL for a Workday company."""
        return f"https://{company_slug}.{wd_instance}.myworkdayjobs.com/en-US/{site_name}"

    def discover_workday_config(self, url: str) -> Optional[Tuple[str, str, str]]:
        """
        Attempt to discover Workday configuration from a career page URL.

        Args:
            url: A Workday career page URL

        Returns:
            Tuple of (company_slug, wd_instance, site_name) or None if not discoverable
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.netloc

            # Pattern: company.wdN.myworkdayjobs.com
            match = re.match(r'^([^.]+)\.(wd\d+)\.myworkdayjobs\.com$', hostname)
            if match:
                company_slug = match.group(1)
                wd_instance = match.group(2)

                # Try to extract site name from path
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 1:
                    # Skip language codes like 'en-US'
                    site_name = path_parts[-1] if not re.match(r'^[a-z]{2}-[A-Z]{2}$', path_parts[-1]) else path_parts[-2] if len(path_parts) > 1 else "External"
                else:
                    site_name = "External"

                return (company_slug, wd_instance, site_name)

        except Exception as e:
            logger.warning(f"Error parsing Workday URL: {e}")

        return None

    def add_company(
        self,
        company_slug: str,
        wd_instance: str,
        site_name: str,
        display_name: Optional[str] = None
    ) -> None:
        """
        Add a company to the search list.

        Args:
            company_slug: Company identifier in URL
            wd_instance: Workday instance (e.g., 'wd5')
            site_name: Site name in URL
            display_name: Human-readable name (defaults to company_slug)
        """
        display_name = display_name or company_slug.title()
        config = (company_slug, wd_instance, site_name, display_name)

        if config not in self.companies:
            self.companies.append(config)
            logger.info(f"Added company '{display_name}' to Workday search list")

    def add_company_from_url(self, url: str, display_name: Optional[str] = None) -> bool:
        """
        Add a company by discovering configuration from its Workday URL.

        Args:
            url: Workday career page URL
            display_name: Optional display name

        Returns:
            True if company was added, False if URL couldn't be parsed
        """
        config = self.discover_workday_config(url)
        if config:
            company_slug, wd_instance, site_name = config
            self.add_company(company_slug, wd_instance, site_name, display_name)
            return True
        return False

    def get_available_companies(self) -> List[Dict[str, str]]:
        """Return the list of configured companies with their details."""
        result = []
        for company_config in self.companies:
            if isinstance(company_config, (tuple, list)) and len(company_config) >= 4:
                result.append({
                    "slug": company_config[0],
                    "instance": company_config[1],
                    "site": company_config[2],
                    "name": company_config[3]
                })
        return result
