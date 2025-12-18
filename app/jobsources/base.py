"""Base class for job source adapters."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.jobsources.utils import retry_with_backoff, ProxyRotator, rotate_user_agent


class JobListing(BaseModel):
    """Standardized job listing model."""
    
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    raw_description: Optional[str] = None
    qualifications: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    posting_date: Optional[datetime] = None
    source: str
    source_url: str
    application_type: str = "unknown"  # easy_apply, external, api, unknown
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseJobSource(ABC):
    """Abstract base class for job source adapters."""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the job source adapter.
        
        Args:
            config: Configuration dictionary for this source
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        
        # Initialize proxy rotator if proxies are configured
        proxies = self.config.get('proxies', [])
        if proxies:
            self.proxy_rotator = ProxyRotator(proxies)
        else:
            self.proxy_rotator = None
        
        # Retry configuration
        self.max_retries = self.config.get('max_retries', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
    
    @abstractmethod
    def search(
        self,
        query: str,
        location: Optional[str] = None,
        remote: bool = False,
        max_results: int = 50,
        **kwargs
    ) -> List[JobListing]:
        """
        Search for jobs matching the criteria.
        
        Args:
            query: Job title or search query
            location: Location filter (e.g., "San Francisco, CA")
            remote: Whether to filter for remote positions
            max_results: Maximum number of results to return
            **kwargs: Additional search parameters
            
        Returns:
            List of JobListing objects
        """
        pass
    
    def normalize_job(self, raw_job: Dict[str, Any]) -> JobListing:
        """
        Normalize a raw job listing from the source into a JobListing.
        
        Override this method in subclasses to handle source-specific formats.
        
        Args:
            raw_job: Raw job data from the source
            
        Returns:
            Normalized JobListing
        """
        return JobListing(
            title=raw_job.get("title", ""),
            company=raw_job.get("company", ""),
            location=raw_job.get("location"),
            description=raw_job.get("description"),
            source=self.name.lower(),
            source_url=raw_job.get("url", ""),
            metadata=raw_job,
        )
    
    def extract_keywords(self, text: Optional[str]) -> List[str]:
        """
        Extract keywords from job description text.
        
        This is a basic implementation. Override for more sophisticated extraction.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of extracted keywords
        """
        if not text:
            return []
        
        # Simple keyword extraction - split on common separators
        # In production, use NLP libraries or LLM for better extraction
        import re
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter common stop words
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
            "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
            "man", "new", "now", "old", "see", "two", "way", "who", "its", "may",
            "use", "her", "she", "him", "his", "how", "man", "new", "now", "old",
        }
        
        # Extract unique keywords (3+ chars, not stop words)
        keywords = [w for w in set(words) if w not in stop_words and len(w) >= 3]
        
        # Limit to top keywords by frequency
        from collections import Counter
        keyword_counts = Counter(words)
        top_keywords = [w for w, _ in keyword_counts.most_common(20) if w not in stop_words]
        
        return top_keywords[:15]  # Return top 15 keywords
