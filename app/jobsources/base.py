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
        Improved implementation with better filtering and technical term extraction.
        
        Args:
            text: Text to extract keywords from
            
        Returns:
            List of extracted keywords (prioritized by relevance)
        """
        if not text:
            return []
        
        import re
        from collections import Counter
        
        # Extract words (including hyphenated terms like "machine-learning")
        words = re.findall(r'\b[a-zA-Z][a-zA-Z-]{2,}\b', text.lower())
        
        # Filter common stop words (more comprehensive list)
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
            "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
            "man", "new", "now", "old", "see", "two", "way", "who", "its", "may",
            "use", "she", "this", "that", "with", "from", "than", "more", "most",
            "will", "would", "should", "could", "must", "might", "may", "shall",
            "what", "when", "where", "which", "while", "work", "years", "year",
            "team", "company", "role", "position", "job", "jobs", "will", "be",
            "years", "experience", "experience", "required", "preferred", "skills",
        }
        
        # Technical terms and skills (prioritize these)
        technical_terms = {
            "python", "java", "javascript", "typescript", "react", "angular", "vue",
            "node", "django", "flask", "fastapi", "spring", "sql", "nosql", "mongodb",
            "postgresql", "mysql", "redis", "docker", "kubernetes", "aws", "azure",
            "gcp", "terraform", "ansible", "ci/cd", "jenkins", "git", "github",
            "gitlab", "agile", "scrum", "kanban", "api", "rest", "graphql", "microservices",
            "machine", "learning", "ai", "ml", "deep", "neural", "data", "science",
            "analytics", "analyst", "engineer", "developer", "architect", "manager",
            "product", "manager", "pm", "scrum", "master", "devops", "sre", "qa",
            "testing", "automation", "selenium", "cypress", "junit", "pytest",
        }
        
        # Count word frequency
        word_counts = Counter(words)
        
        # Filter and prioritize
        keywords = []
        
        # 1. Prioritize technical terms and skills (even if less frequent)
        for word, count in word_counts.most_common(50):
            word_clean = word.replace('-', ' ').strip()
            # Check if it's a technical term or multi-word technical term
            is_technical = any(term in word_clean or word_clean in term for term in technical_terms)
            
            if word not in stop_words and len(word.replace('-', '')) >= 3:
                if is_technical or count >= 2:  # Technical terms or words appearing 2+ times
                    keywords.append(word)
        
        # 2. Add high-frequency non-technical but relevant words
        for word, count in word_counts.most_common(30):
            if word not in stop_words and word not in keywords and len(word.replace('-', '')) >= 4 and count >= 3:
                keywords.append(word)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        # Return top 20 keywords
        return unique_keywords[:20]
