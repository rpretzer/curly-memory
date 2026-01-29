"""
API adapters for job application submission.

IMPORTANT LIMITATION:
Most major job boards (LinkedIn, Indeed, Monster, etc.) do NOT provide public APIs
for programmatic job application submission. They only offer APIs for job search and
retrieval. The adapters below document what IS and ISN'T possible with current APIs.

For job boards without application APIs, use browser automation (Playwright) instead.
"""

import logging
from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
import requests

logger = logging.getLogger(__name__)


class JobApplicationAPIAdapter(ABC):
    """Base class for job application API adapters."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """
        Initialize API adapter.

        Args:
            api_key: Optional API key for authentication
            config: Optional configuration dictionary
        """
        self.api_key = api_key
        self.config = config or {}

    @abstractmethod
    def submit_application(
        self,
        job_id: str,
        application_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Submit a job application via API.

        Args:
            job_id: Job identifier from the source platform
            application_data: Application form data including:
                - resume_url or resume_file: Resume content
                - cover_letter: Cover letter text
                - answers: Dict of application question answers
                - contact_info: Contact information

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        pass

    @abstractmethod
    def get_application_questions(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve application questions for a job posting.

        Args:
            job_id: Job identifier from the source platform

        Returns:
            List of question dictionaries with fields like:
            - question_id: Unique identifier
            - question_text: The question text
            - question_type: Type (text, select, multiselect, etc.)
            - required: Whether the question is required
            - options: List of options for select questions
        """
        pass


class LinkedInAPIAdapter(JobApplicationAPIAdapter):
    """
    LinkedIn API adapter.

    LIMITATION: LinkedIn does NOT provide a public API for job applications.
    Their Jobs API only supports:
    - Searching for jobs
    - Retrieving job details
    - Posting jobs (for employers)

    This adapter documents the limitation and returns NotImplementedError.
    """

    def submit_application(
        self,
        job_id: str,
        application_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """LinkedIn does not support programmatic job applications via API."""
        error = "LinkedIn does not provide a public API for job application submission. Use browser automation (Easy Apply) instead."
        logger.warning(error)
        return False, error

    def get_application_questions(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """LinkedIn does not support retrieving application questions via API."""
        logger.warning("LinkedIn API does not support retrieving application questions")
        return None


class IndeedAPIAdapter(JobApplicationAPIAdapter):
    """
    Indeed API adapter.

    LIMITATION: Indeed does NOT provide a public API for job applications.
    Their Publisher API only supports:
    - Searching for jobs
    - Retrieving job details
    - Job posting (for employers)

    This adapter documents the limitation and returns NotImplementedError.
    """

    def submit_application(
        self,
        job_id: str,
        application_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Indeed does not support programmatic job applications via API."""
        error = "Indeed does not provide a public API for job application submission. Use browser automation instead."
        logger.warning(error)
        return False, error

    def get_application_questions(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """Indeed does not support retrieving application questions via API."""
        logger.warning("Indeed API does not support retrieving application questions")
        return None


class GreenhouseAPIAdapter(JobApplicationAPIAdapter):
    """
    Greenhouse ATS API adapter.

    PARTIAL SUPPORT: Greenhouse provides APIs for employers/recruiters, not candidates.
    However, Greenhouse has a public Job Board API that can:
    - Retrieve job postings
    - Get application form structure
    - NOT supported: Programmatic application submission

    Job applications must be submitted through their web forms or integrated with
    the employer's website.
    """

    BASE_URL = "https://boards-api.greenhouse.io/v1"

    def submit_application(
        self,
        job_id: str,
        application_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Greenhouse does not support programmatic application submission via public API.

        Applications must go through the web form. However, we can fetch the form
        structure to assist with browser automation.
        """
        error = "Greenhouse does not support direct application submission via API. Use browser automation with the application form structure."
        logger.warning(error)
        return False, error

    def get_application_questions(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve application questions from Greenhouse job board API.

        Args:
            job_id: Greenhouse job ID (numeric)

        Returns:
            List of question dictionaries
        """
        try:
            # Greenhouse job board API endpoint
            # Format: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}
            # Note: Requires knowing the board_token (company identifier)

            board_token = self.config.get("board_token")
            if not board_token:
                logger.error("Greenhouse board_token not configured")
                return None

            url = f"{self.BASE_URL}/boards/{board_token}/jobs/{job_id}"
            response = requests.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"Greenhouse API error: {response.status_code}")
                return None

            job_data = response.json()

            # Extract application questions from job data
            questions = job_data.get("questions", [])

            return [
                {
                    "question_id": q.get("id"),
                    "question_text": q.get("label"),
                    "question_type": q.get("type"),  # text, textarea, select, multi_select
                    "required": q.get("required", False),
                    "options": q.get("values", []) if q.get("type") in ["select", "multi_select"] else None
                }
                for q in questions
            ]

        except Exception as e:
            logger.error(f"Error fetching Greenhouse application questions: {e}")
            return None


class WorkdayAPIAdapter(JobApplicationAPIAdapter):
    """
    Workday ATS API adapter.

    LIMITATION: Workday does NOT provide a public API for candidate job applications.
    Their APIs are designed for:
    - HR/recruiting team internal workflows
    - Integration with employer systems
    - NOT for candidate-facing application submission

    Applications must be submitted through Workday's web interface.
    """

    def submit_application(
        self,
        job_id: str,
        application_data: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Workday does not support programmatic candidate applications via public API."""
        error = "Workday does not provide a public API for candidate job applications. Use browser automation instead."
        logger.warning(error)
        return False, error

    def get_application_questions(self, job_id: str) -> Optional[List[Dict[str, Any]]]:
        """Workday does not support retrieving application questions via public API."""
        logger.warning("Workday does not provide public API for candidate application questions")
        return None


# Factory function to get the appropriate API adapter
def get_api_adapter(source: str, config: Optional[Dict[str, Any]] = None) -> Optional[JobApplicationAPIAdapter]:
    """
    Get the appropriate API adapter for a job source.

    Args:
        source: Job source name (linkedin, indeed, greenhouse, workday, etc.)
        config: Optional configuration for the adapter

    Returns:
        API adapter instance or None if not supported
    """
    adapters = {
        "linkedin": LinkedInAPIAdapter,
        "indeed": IndeedAPIAdapter,
        "greenhouse": GreenhouseAPIAdapter,
        "workday": WorkdayAPIAdapter,
    }

    adapter_class = adapters.get(source.lower())
    if not adapter_class:
        logger.warning(f"No API adapter available for source: {source}")
        return None

    return adapter_class(config=config)
