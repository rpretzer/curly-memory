"""Agent for searching job boards."""

import logging
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session

from app.jobsources import LinkedInAdapter, IndeedAdapter, WellfoundAdapter
from app.jobsources.base import JobListing
from app.config import config
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)


class SearchAgent:
    """Agent responsible for searching multiple job sources."""
    
    def __init__(self, db: Session, log_agent: Optional[LogAgent] = None):
        """
        Initialize the search agent.
        
        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
        """
        self.db = db
        self.log_agent = log_agent
        self.agent_name = "SearchAgent"
        
        # Initialize job source adapters
        self.sources = {}
        job_sources_config = config.get_job_sources_config()
        
        # LinkedIn
        if job_sources_config.get("linkedin", {}).get("enabled", True):
            linkedin_config = job_sources_config.get("linkedin", {})
            self.sources["linkedin"] = LinkedInAdapter(
                config=linkedin_config,
                api_key=config.linkedin_api_key
            )
        
        # Indeed
        if job_sources_config.get("indeed", {}).get("enabled", True):
            indeed_config = job_sources_config.get("indeed", {})
            self.sources["indeed"] = IndeedAdapter(
                config=indeed_config,
                api_key=config.indeed_api_key
            )
        
        # Wellfound
        if job_sources_config.get("wellfound", {}).get("enabled", True):
            wellfound_config = job_sources_config.get("wellfound", {})
            self.sources["wellfound"] = WellfoundAdapter(
                config=wellfound_config,
                api_key=config.wellfound_api_key
            )
    
    def search(
        self,
        titles: List[str],
        locations: Optional[List[str]] = None,
        remote: bool = False,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        max_results_per_source: int = 50,
        run_id: Optional[int] = None,
    ) -> List[JobListing]:
        """
        Search multiple job sources for matching positions.
        
        Args:
            titles: List of target job titles to search for
            locations: Optional list of location filters
            remote: Whether to prioritize remote positions
            keywords: Optional list of keywords to include
            sources: Optional list of source names to search (default: all enabled)
            max_results_per_source: Maximum results per source
            run_id: Optional run ID for logging
            
        Returns:
            List of JobListing objects from all sources
        """
        if not titles:
            raise ValueError("At least one job title must be provided")
        
        # Determine which sources to search
        sources_to_search = sources or list(self.sources.keys())
        sources_searched = []
        all_jobs = []
        
        if self.log_agent and run_id:
            self.log_agent.log_search_start(
                run_id=run_id,
                search_params={
                    "titles": titles,
                    "locations": locations,
                    "remote": remote,
                    "keywords": keywords,
                    "sources": sources_to_search,
                }
            )
        
        # Search each source
        for source_name in sources_to_search:
            if source_name not in self.sources:
                logger.warning(f"Source '{source_name}' not available, skipping")
                continue
            
            source = self.sources[source_name]
            
            try:
                # Search each title
                for title in titles:
                    # Determine location string
                    location_str = None
                    if locations:
                        # Use first location for now (could be enhanced to search all)
                        location_str = locations[0]
                    
                    # Build query (include keywords if provided)
                    query = title
                    if keywords:
                        query = f"{title} {' '.join(keywords[:3])}"  # Add top 3 keywords
                    
                    logger.info(f"Searching {source_name} for: {query}")
                    
                    jobs = source.search(
                        query=query,
                        location=location_str,
                        remote=remote,
                        max_results=max_results_per_source,
                    )
                    
                    all_jobs.extend(jobs)
                    sources_searched.append(source_name)
                    
                    logger.info(f"Found {len(jobs)} jobs from {source_name} for '{title}'")
            
            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}", exc_info=True)
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        step=f"search_{source_name}",
                    )
        
        # Deduplicate jobs by source_url
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.source_url not in seen_urls:
                seen_urls.add(job.source_url)
                unique_jobs.append(job)
        
        logger.info(f"Total unique jobs found: {len(unique_jobs)} (from {len(all_jobs)} total)")
        
        if self.log_agent and run_id:
            self.log_agent.log_search_complete(
                run_id=run_id,
                jobs_found=len(unique_jobs),
                sources_searched=list(set(sources_searched)),
            )
        
        return unique_jobs
