"""Job source adapters for various job boards."""

from app.jobsources.base import BaseJobSource, JobListing
from app.jobsources.linkedin_adapter import LinkedInAdapter
from app.jobsources.indeed_adapter import IndeedAdapter
from app.jobsources.wellfound_adapter import WellfoundAdapter
from app.jobsources.monster_adapter import MonsterAdapter

__all__ = [
    "BaseJobSource",
    "JobListing",
    "LinkedInAdapter",
    "IndeedAdapter",
    "WellfoundAdapter",
    "MonsterAdapter",
]
