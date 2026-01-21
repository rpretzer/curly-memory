"""Agent for searching job boards."""

import logging
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session
import concurrent.futures
from functools import partial

from app.jobsources import (
    LinkedInAdapter, IndeedAdapter, WellfoundAdapter, MonsterAdapter,
    GreenhouseAdapter, WorkdayAdapter
)
from app.jobsources.base import JobListing
from app.config import config
from app.agents.log_agent import LogAgent
from app.agents.query_enhancer import QueryEnhancer, enhance_search_queries

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
        
        # Initialize query enhancer
        search_config = config.get_search_config()
        min_query_length = search_config.get("min_query_length", 5)
        self.query_enhancer = QueryEnhancer(min_query_length=min_query_length)
        
        # Get search configuration
        self.enable_parallel = search_config.get("enable_parallel_search", True)
        self.search_timeout = search_config.get("search_timeout_seconds", 90)
        self.max_total_results = search_config.get("max_total_results", 500)
        
        # Initialize job source adapters
        self.sources = {}
        job_sources_config = config.get_job_sources_config()
        
        # Get profile for credentials override
        from app.user_profile import get_user_profile
        from app.security import get_fernet
        try:
            profile = get_user_profile(db)
            profile_li_user = profile.linkedin_user if profile else None
            profile_li_pass = None
            if profile and profile.linkedin_password:
                try:
                    fernet = get_fernet()
                    profile_li_pass = fernet.decrypt(profile.linkedin_password.encode()).decode()
                except Exception as e:
                    logger.error(f"Failed to decrypt LinkedIn password: {e}")
        except Exception as e:
            logger.warning(f"Error fetching profile credentials: {e}")
            profile_li_user = None
            profile_li_pass = None
        
        # LinkedIn
        if job_sources_config.get("linkedin", {}).get("enabled", True):
            linkedin_config = job_sources_config.get("linkedin", {})
            # Add third-party API keys to config if available
            if config.apify_api_key:
                linkedin_config["apify_api_key"] = config.apify_api_key
            if config.mantiks_api_key:
                linkedin_config["mantiks_api_key"] = config.mantiks_api_key
            # Add LinkedIn credentials from env if available
            if config.linkedin_email:
                linkedin_config["linkedin_email"] = config.linkedin_email
            if config.linkedin_password:
                linkedin_config["linkedin_password"] = config.linkedin_password
            
            # Override with profile credentials if set
            if profile_li_user:
                linkedin_config["linkedin_email"] = profile_li_user
            if profile_li_pass:
                linkedin_config["linkedin_password"] = profile_li_pass
                
            self.sources["linkedin"] = LinkedInAdapter(
                config=linkedin_config,
                api_key=config.linkedin_api_key
            )
        
        # Indeed
        if job_sources_config.get("indeed", {}).get("enabled", True):
            indeed_config = job_sources_config.get("indeed", {})
            # Add third-party API keys to config if available
            if config.scrapeops_api_key:
                indeed_config["scrapeops_api_key"] = config.scrapeops_api_key
            if config.hasdata_api_key:
                indeed_config["hasdata_api_key"] = config.hasdata_api_key
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
        
        # Monster / Ohio Means Jobs
        if job_sources_config.get("monster", {}).get("enabled", False):
            monster_config = job_sources_config.get("monster", {})
            # Add third-party API keys to config if available
            if config.scrapeops_api_key:
                monster_config["scrapeops_api_key"] = config.scrapeops_api_key
            self.sources["monster"] = MonsterAdapter(
                config=monster_config,
                api_key=None  # Monster doesn't have API key
            )

        # Greenhouse - public API, no scraping needed
        if job_sources_config.get("greenhouse", {}).get("enabled", True):
            greenhouse_config = job_sources_config.get("greenhouse", {})
            self.sources["greenhouse"] = GreenhouseAdapter(config=greenhouse_config)
            logger.info(f"Greenhouse adapter initialized with {len(self.sources['greenhouse'].companies)} companies")

        # Workday - direct API access to company instances
        if job_sources_config.get("workday", {}).get("enabled", True):
            workday_config = job_sources_config.get("workday", {})
            self.sources["workday"] = WorkdayAdapter(config=workday_config)
            logger.info(f"Workday adapter initialized with {len(self.sources['workday'].companies)} companies")
    
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
        
        # Validate and enhance titles
        enhanced_titles = []
        for title in titles:
            is_valid, error = self.query_enhancer.validate_query(title)
            if not is_valid:
                logger.warning(f"Invalid title '{title}': {error}. Skipping.")
                if self.log_agent and run_id:
                    self.log_agent.log(
                        agent_name=self.agent_name,
                        status="warning",
                        message=f"Invalid title '{title}': {error}",
                        run_id=run_id,
                        step="validate_query",
                    )
                continue
            enhanced_title = self.query_enhancer.enhance_query(title, keywords)
            enhanced_titles.append(enhanced_title)
            if enhanced_title != title:
                logger.info(f"Enhanced query '{title}' -> '{enhanced_title}'")
        
        if not enhanced_titles:
            raise ValueError(f"All titles were invalid. Please provide valid job titles (minimum {self.query_enhancer.min_query_length} characters, not generic terms).")
        
        # Determine which sources to search
        # Default sources: greenhouse and workday (most reliable), linkedin, indeed
        if sources:
            sources_to_search = sources
        else:
            default_sources = ["greenhouse", "workday", "linkedin", "indeed"]
            sources_to_search = [s for s in default_sources if s in self.sources]
        sources_searched = []
        all_jobs = []
        
        if self.log_agent and run_id:
            self.log_agent.log_search_start(
                run_id=run_id,
                search_params={
                    "titles": enhanced_titles,
                    "original_titles": titles,
                    "locations": locations,
                    "remote": remote,
                    "keywords": keywords,
                    "sources": sources_to_search,
                }
            )
        
        # Build search tasks
        search_tasks = []
        for source_name in sources_to_search:
            if source_name not in self.sources:
                logger.warning(f"Source '{source_name}' not available, skipping")
                continue
            
            source = self.sources[source_name]
            
            # Search each enhanced title
            for title in enhanced_titles:
                # Determine location string
                location_str = None
                if locations:
                    # Use first location for now (could be enhanced to search all)
                    location_str = locations[0]
                
                # Build optimized query
                query = self.query_enhancer.build_search_query(
                    title=title,
                    keywords=keywords,
                    locations=locations,
                    remote=remote,
                )
                
                # Create search task
                search_tasks.append({
                    'source_name': source_name,
                    'source': source,
                    'query': query,
                    'location': location_str,
                    'remote': remote,
                    'max_results': max_results_per_source,
                    'title': title,
                })
        
        # Execute searches (parallel or sequential)
        if self.enable_parallel and len(search_tasks) > 1:
            logger.info(f"Searching {len(search_tasks)} queries in parallel across {len(sources_to_search)} sources...")
            all_jobs, sources_searched = self._search_parallel(search_tasks, run_id)
        else:
            logger.info(f"Searching {len(search_tasks)} queries sequentially...")
            all_jobs, sources_searched = self._search_sequential(search_tasks, run_id)
        
        # Apply max_total_results limit if configured
        if self.max_total_results and len(all_jobs) > self.max_total_results:
            logger.info(f"Limiting results from {len(all_jobs)} to {self.max_total_results} (max_total_results)")
            all_jobs = all_jobs[:self.max_total_results]
        
        # Deduplicate jobs by source_url
        seen_urls = set()
        unique_jobs = []
        for job in all_jobs:
            if job.source_url not in seen_urls:
                seen_urls.add(job.source_url)
                unique_jobs.append(job)
        
        logger.info(f"=== SEARCH AGENT SUMMARY ===")
        logger.info(f"Total jobs from all sources: {len(all_jobs)}")
        logger.info(f"Unique jobs (after deduplication): {len(unique_jobs)}")
        logger.info(f"Duplicates removed: {len(all_jobs) - len(unique_jobs)}")
        logger.info(f"Sources searched: {sources_searched}")
        if unique_jobs:
            logger.info(f"Sample unique jobs: {[f'{j.title} @ {j.company} ({j.source})' for j in unique_jobs[:5]]}")
        
        if self.log_agent and run_id:
            self.log_agent.log_search_complete(
                run_id=run_id,
                jobs_found=len(unique_jobs),
                sources_searched=list(set(sources_searched)),
            )
        
        return unique_jobs
    
    def _search_sequential(self, search_tasks: List[Dict], run_id: Optional[int]) -> Tuple[List[JobListing], List[str]]:
        """Execute searches sequentially."""
        all_jobs = []
        sources_searched = []
        
        for task in search_tasks:
            source_name = task['source_name']
            query = task['query']
            location_str = task['location']
            remote = task['remote']
            max_results = task['max_results']
            title = task['title']
            
            # Create a fresh adapter instance
            source = self._create_adapter(source_name)
            if not source:
                continue
            
            try:
                logger.info(f"=== SEARCHING {source_name.upper()} ===")
                logger.info(f"Query: '{query}' (from title: '{title}')")
                logger.info(f"Location: {location_str}")
                logger.info(f"Remote: {remote}")
                logger.info(f"Max results: {max_results}")
                
                jobs = source.search(
                    query=query,
                    location=location_str,
                    remote=remote,
                    max_results=max_results,
                )
                
                logger.info(f"=== {source_name.upper()} SEARCH RESULT ===")
                logger.info(f"Jobs returned: {len(jobs)}")
                if jobs:
                    logger.info(f"Sample jobs: {[f'{j.title} @ {j.company}' for j in jobs[:3]]}")
                
                all_jobs.extend(jobs)
                if source_name not in sources_searched:
                    sources_searched.append(source_name)
                
                logger.info(f"✓ {source_name}: Found {len(jobs)} jobs for '{title}'")
            
            except Exception as e:
                logger.error(f"Error searching {source_name} with query '{query}': {e}", exc_info=True)
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        step=f"search_{source_name}",
                    )
        
        return all_jobs, sources_searched
    
    def _search_parallel(self, search_tasks: List[Dict], run_id: Optional[int]) -> Tuple[List[JobListing], List[str]]:
        """Execute searches in parallel using ThreadPoolExecutor."""
        all_jobs = []
        sources_searched = []
        max_workers = min(len(search_tasks), 4)  # Limit concurrent searches to avoid overwhelming sources
        
        def execute_search(task: Dict) -> tuple[List[JobListing], str]:
            """Execute a single search task."""
            source_name = task['source_name']
            query = task['query']
            location_str = task['location']
            remote = task['remote']
            max_results = task['max_results']
            title = task['title']
            
            # Create a fresh adapter instance for this thread to ensure thread safety
            # (Playwright sync API is not thread-safe when sharing instances)
            source = self._create_adapter(source_name)
            if not source:
                return [], source_name
            
            try:
                logger.info(f"=== SEARCHING {source_name.upper()} (parallel) ===")
                logger.info(f"Query: '{query}' (from title: '{title}')")
                
                jobs = source.search(
                    query=query,
                    location=location_str,
                    remote=remote,
                    max_results=max_results,
                )
                
                logger.info(f"✓ {source_name}: Found {len(jobs)} jobs for '{title}'")
                return jobs, source_name
            except Exception as e:
                logger.error(f"Error searching {source_name} with query '{query}': {e}", exc_info=True)
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        step=f"search_{source_name}",
                    )
                return [], source_name

        # Execute searches in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(execute_search, task): task for task in search_tasks}

            for future in concurrent.futures.as_completed(future_to_task, timeout=self.search_timeout * len(search_tasks)):
                task = future_to_task[future]
                try:
                    jobs, source_name = future.result(timeout=self.search_timeout)
                    all_jobs.extend(jobs)
                    if source_name not in sources_searched:
                        sources_searched.append(source_name)
                except concurrent.futures.TimeoutError:
                    logger.error(f"Search task timed out: {task['source_name']} - {task['query']}")
                except Exception as e:
                    logger.error(f"Search task failed: {task['source_name']} - {task['query']}: {e}", exc_info=True)

        return all_jobs, sources_searched

    def _create_adapter(self, source_name: str):
        """Create a fresh instance of a job source adapter."""
        job_sources_config = config.get_job_sources_config()
        
        # Get profile for credentials override
        from app.user_profile import get_user_profile
        from app.security import get_fernet
        try:
            profile = get_user_profile(self.db)
            profile_li_user = profile.linkedin_user if profile else None
            profile_li_pass = None
            if profile and profile.linkedin_password:
                try:
                    fernet = get_fernet()
                    profile_li_pass = fernet.decrypt(profile.linkedin_password.encode()).decode()
                except Exception as e:
                    logger.error(f"Failed to decrypt LinkedIn password: {e}")
        except Exception as e:
            logger.warning(f"Error fetching profile credentials: {e}")
            profile_li_user = None
            profile_li_pass = None

        if source_name == "linkedin":
            linkedin_config = job_sources_config.get("linkedin", {}).copy()
            if config.apify_api_key:
                linkedin_config["apify_api_key"] = config.apify_api_key
            if config.mantiks_api_key:
                linkedin_config["mantiks_api_key"] = config.mantiks_api_key
            if config.linkedin_email:
                linkedin_config["linkedin_email"] = config.linkedin_email
            if config.linkedin_password:
                linkedin_config["linkedin_password"] = config.linkedin_password
            if profile_li_user:
                linkedin_config["linkedin_email"] = profile_li_user
            if profile_li_pass:
                linkedin_config["linkedin_password"] = profile_li_pass
            return LinkedInAdapter(config=linkedin_config, api_key=config.linkedin_api_key)
            
        elif source_name == "indeed":
            indeed_config = job_sources_config.get("indeed", {}).copy()
            if config.scrapeops_api_key:
                indeed_config["scrapeops_api_key"] = config.scrapeops_api_key
            if config.hasdata_api_key:
                indeed_config["hasdata_api_key"] = config.hasdata_api_key
            return IndeedAdapter(config=indeed_config, api_key=config.indeed_api_key)
            
        elif source_name == "wellfound":
            return WellfoundAdapter(config=job_sources_config.get("wellfound", {}), api_key=config.wellfound_api_key)
            
        elif source_name == "monster":
            monster_config = job_sources_config.get("monster", {}).copy()
            if config.scrapeops_api_key:
                monster_config["scrapeops_api_key"] = config.scrapeops_api_key
            return MonsterAdapter(config=monster_config)
            
        elif source_name == "greenhouse":
            return GreenhouseAdapter(config=job_sources_config.get("greenhouse", {}))
            
        elif source_name == "workday":
            return WorkdayAdapter(config=job_sources_config.get("workday", {}))

        return None
