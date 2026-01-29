"""Orchestrator for coordinating agents in the job search pipeline."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Run, RunStatus, JobStatus, compute_content_hash
from app.agents import (
    SearchAgent,
    FilterAndScoreAgent,
    ContentGenerationAgent,
    ApplyAgent,
    LogAgent,
)
from app.config import config
from app.db import get_db_context

logger = logging.getLogger(__name__)


class CancelledException(Exception):
    """Exception raised when a run is cancelled."""
    pass


class PipelineOrchestrator:
    """Orchestrates the job search and application pipeline."""

    def __init__(
        self,
        db: Session,
        search_config: Optional[Dict[str, Any]] = None,
        scoring_config: Optional[Dict[str, Any]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            db: Database session
            search_config: Optional search configuration override
            scoring_config: Optional scoring configuration override
            llm_config: Optional LLM configuration override
        """
        self.db = db
        
        # Initialize log agent
        self.log_agent = LogAgent(db)
        
        # Initialize agents
        self.search_agent = SearchAgent(db, log_agent=self.log_agent)
        self.filter_score_agent = FilterAndScoreAgent(
            db,
            log_agent=self.log_agent,
            scoring_weights=scoring_config,
        )
        self.content_agent = ContentGenerationAgent(
            db,
            log_agent=self.log_agent,
            llm_config=llm_config,
        )
        self.apply_agent = ApplyAgent(
            db,
            log_agent=self.log_agent,
        )
        
        # Configuration
        self.search_config = search_config or {}
        self.scoring_config = scoring_config or {}
        self.llm_config = llm_config or {}
    
    def create_run(
        self,
        search_config: Dict[str, Any],
        scoring_config: Dict[str, Any],
        llm_config: Dict[str, Any],
    ) -> Run:
        """
        Create a new pipeline run.
        
        Args:
            search_config: Search configuration
            scoring_config: Scoring configuration
            llm_config: LLM configuration
            
        Returns:
            Created Run model
        """
        run = Run(
            status=RunStatus.PENDING,
            search_config=search_config,
            scoring_config=scoring_config,
            llm_config=llm_config,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        self.log_agent.log(
            agent_name="Orchestrator",
            status="info",
            message=f"Created new run: {run.id}",
            run_id=run.id,
            step="create_run",
        )

        return run

    def check_cancelled(self, run_id: int):
        """
        Check if a run has been cancelled.

        Args:
            run_id: Run ID to check

        Raises:
            CancelledException: If the run has been cancelled
        """
        # Refresh run status from database
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if run and run.status == RunStatus.CANCELLED:
            logger.info(f"Run {run_id} has been cancelled")
            raise CancelledException(f"Run {run_id} was cancelled")

    def run_search_only(
        self,
        run_id: int,
        titles: List[str],
        locations: Optional[List[str]] = None,
        remote: bool = False,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> List[int]:
        """
        Run only the search phase.
        
        Args:
            run_id: Run ID
            titles: Job titles to search for
            locations: Optional location filters
            remote: Remote filter
            keywords: Optional keywords
            sources: Optional source filters
            max_results: Max results per source (defaults to config value)
            
        Returns:
            List of job IDs found
        """
        run = self.db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        # Get max_results from config if not provided
        if max_results is None:
            search_config = config.get_search_config()
            max_results = search_config.get("default_max_results_per_source", 100)
        
        run.status = RunStatus.SEARCHING
        self.db.commit()
        
        try:
            logger.info(f"=== ORCHESTRATOR: STARTING SEARCH PHASE ===")
            logger.info(f"Run ID: {run_id}")
            logger.info(f"Titles: {titles}")
            logger.info(f"Locations: {locations}")
            logger.info(f"Remote: {remote}")
            logger.info(f"Keywords: {keywords}")
            logger.info(f"Sources: {sources}")
            logger.info(f"Max results per source: {max_results}")
            
            # Search for jobs
            job_listings = self.search_agent.search(
                titles=titles,
                locations=locations,
                remote=remote,
                keywords=keywords,
                sources=sources,
                max_results_per_source=max_results,
                run_id=run_id,
            )
            
            logger.info(f"=== ORCHESTRATOR: SAVING JOBS TO DATABASE ===")
            logger.info(f"Job listings to save: {len(job_listings)}")
            
            # Save jobs to database
            job_ids = []
            saved_count = 0
            existing_count = 0
            duplicate_content_count = 0
            from app.models import Job, JobSource, ApplicationType
            from sqlalchemy import or_

            for idx, listing in enumerate(job_listings, 1):
                logger.debug(f"Processing listing {idx}/{len(job_listings)}: {listing.title} @ {listing.company}")

                # Compute content hash for deduplication
                content_hash = compute_content_hash(
                    listing.title,
                    listing.company,
                    listing.location or ""
                )

                # Check if job already exists by URL OR content hash (cross-run deduplication)
                existing = self.db.query(Job).filter(
                    or_(
                        Job.source_url == listing.source_url,
                        Job.content_hash == content_hash
                    )
                ).first()

                if existing:
                    if existing.source_url == listing.source_url:
                        existing_count += 1
                        logger.debug(f"  → Job already exists by URL (ID: {existing.id})")
                    else:
                        duplicate_content_count += 1
                        logger.debug(f"  → Job already exists by content hash (ID: {existing.id}, same job different source)")
                    # Don't overwrite run_id - keep original run for history
                    # Just add to our job_ids list so it appears in this run's results
                    job_ids.append(existing.id)
                    continue
                
                # Map source string to enum
                source_enum = JobSource.UNKNOWN
                try:
                    source_enum = JobSource(listing.source.lower())
                except ValueError:
                    pass
                
                # Map application type
                app_type = ApplicationType.UNKNOWN
                if listing.application_type == "easy_apply":
                    app_type = ApplicationType.EASY_APPLY
                elif listing.application_type == "external":
                    app_type = ApplicationType.EXTERNAL
                elif listing.application_type == "api":
                    app_type = ApplicationType.API
                
                job = Job(
                    run_id=run_id,
                    title=listing.title,
                    company=listing.company,
                    location=listing.location,
                    source=source_enum,
                    source_url=listing.source_url,
                    application_type=app_type,
                    description=listing.description,
                    raw_description=listing.raw_description,
                    qualifications=listing.qualifications,
                    keywords=listing.keywords,
                    salary_min=listing.salary_min,
                    salary_max=listing.salary_max,
                    posting_date=listing.posting_date,
                    status=JobStatus.FOUND,
                )
                self.db.add(job)
                self.db.commit()
                self.db.refresh(job)
                job_ids.append(job.id)
                saved_count += 1
                logger.debug(f"  → Saved new job (ID: {job.id})")
            
            logger.info(f"=== ORCHESTRATOR: SEARCH PHASE COMPLETE ===")
            logger.info(f"New jobs saved: {saved_count}")
            logger.info(f"Existing jobs reused: {existing_count}")
            logger.info(f"Total job IDs: {len(job_ids)}")
            
            run.jobs_found = len(job_ids)
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Run {run_id} updated: jobs_found={run.jobs_found}, status={run.status}")
            
            return job_ids
        
        except Exception as e:
            logger.error(f"Error in search phase: {e}", exc_info=True)
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            self.db.commit()
            
            self.log_agent.log_error(
                agent_name="Orchestrator",
                error=e,
                run_id=run_id,
                step="search",
            )
            raise
    
    def run_search_and_score(
        self,
        run_id: int,
        titles: List[str],
        locations: Optional[List[str]] = None,
        remote: bool = False,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        target_companies: Optional[List[str]] = None,
        must_have_keywords: Optional[List[str]] = None,
        nice_to_have_keywords: Optional[List[str]] = None,
        remote_preference: str = "any",
        salary_min: Optional[int] = None,
    ) -> List[int]:
        """
        Run search and scoring phases.

        Returns:
            List of job IDs that passed the scoring threshold
        """
        # Get max_results from config if not provided
        if max_results is None:
            search_config = config.get_search_config()
            max_results = search_config.get("default_max_results_per_source", 100)

        # Run search phase
        job_ids = self.run_search_only(
            run_id=run_id,
            titles=titles,
            locations=locations,
            remote=remote,
            keywords=keywords,
            sources=sources,
            max_results=max_results,
        )

        run = self.db.query(Run).filter(Run.id == run_id).first()
        run.status = RunStatus.SCORING
        self.db.commit()
        
        try:
            # Get job listings from database
            from app.models import Job
            jobs = self.db.query(Job).filter(Job.id.in_(job_ids)).all()
            
            logger.info(f"=== ORCHESTRATOR: SCORING {len(jobs)} JOBS ===")
            
            # Convert to JobListing objects for scoring
            from app.jobsources.base import JobListing
            job_listings = []
            for job in jobs:
                listing = JobListing(
                    title=job.title,
                    company=job.company,
                    location=job.location,
                    description=job.description,
                    raw_description=job.raw_description,
                    qualifications=job.qualifications,
                    keywords=job.keywords or [],
                    salary_min=job.salary_min,
                    salary_max=job.salary_max,
                    posting_date=job.posting_date,
                    source=job.source.value,
                    source_url=job.source_url,
                    application_type=job.application_type.value,
                )
                job_listings.append(listing)
            
            # Score and filter
            scored_jobs = self.filter_score_agent.score_and_filter(
                job_listings=job_listings,
                target_titles=titles,
                target_companies=target_companies,
                must_have_keywords=must_have_keywords,
                nice_to_have_keywords=nice_to_have_keywords,
                remote_preference=remote_preference,
                salary_min=salary_min,
                run_id=run_id,
            )
            
            logger.info(f"=== ORCHESTRATOR: SCORING COMPLETE ===")
            logger.info(f"Jobs found: {len(job_listings)}")
            logger.info(f"Jobs above threshold: {len(scored_jobs)}")
            
            # Log completion
            self.log_agent.log(
                agent_name="Orchestrator",
                status="info",
                message=f"Scoring complete. {len(scored_jobs)} jobs above threshold.",
                run_id=run_id,
                step="score_complete",
                metadata={"scored_count": len(scored_jobs)}
            )

            # Count auto-approved jobs (approval happened in filter_score_agent)
            auto_approved_count = sum(1 for job in scored_jobs if job.approved)

            run.jobs_scored = len(scored_jobs)
            run.jobs_above_threshold = len(scored_jobs)
            run.jobs_approved = auto_approved_count
            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            self.db.commit()

            return [job.id for job in scored_jobs]
        
        except Exception as e:
            logger.error(f"Error in scoring phase: {e}", exc_info=True)
            run.status = RunStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()
            self.db.commit()
            
            self.log_agent.log_error(
                agent_name="Orchestrator",
                error=e,
                run_id=run_id,
                step="score",
            )
            raise
    
    def run_full_pipeline(
        self,
        run_id: int,
        titles: List[str],
        locations: Optional[List[str]] = None,
        remote: bool = False,
        keywords: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        target_companies: Optional[List[str]] = None,
        must_have_keywords: Optional[List[str]] = None,
        nice_to_have_keywords: Optional[List[str]] = None,
        remote_preference: str = "any",
        salary_min: Optional[int] = None,
        generate_content: bool = True,
        auto_apply: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the full pipeline: search, score, generate content, and optionally apply.

        Args:
            run_id: Run ID
            titles: Job titles
            locations: Optional locations
            remote: Remote filter
            keywords: Optional keywords
            sources: Optional sources
            max_results: Max results
            target_companies: Optional target companies
            must_have_keywords: Optional must-have keywords
            nice_to_have_keywords: Optional nice-to-have keywords
            remote_preference: Remote preference
            salary_min: Optional salary minimum
            generate_content: Whether to generate content
            auto_apply: Whether to auto-apply (still requires approval)

        Returns:
            Dictionary with results summary
        """
        try:
            # Check if cancelled before starting
            self.check_cancelled(run_id)

            # Run search and score
            job_ids = self.run_search_and_score(
                run_id=run_id,
                titles=titles,
                locations=locations,
                remote=remote,
                keywords=keywords,
                sources=sources,
                max_results=max_results,
                target_companies=target_companies,
                must_have_keywords=must_have_keywords,
                nice_to_have_keywords=nice_to_have_keywords,
                remote_preference=remote_preference,
                salary_min=salary_min,
            )

            run = self.db.query(Run).filter(Run.id == run_id).first()

            # Log that search phase is complete before moving to content generation
            logger.info(f"=== SEARCH PHASE COMPLETE ===")
            logger.info(f"Jobs found and scored: {len(job_ids)}")
            logger.info(f"Run status: {run.status}")

            # Generate content if requested
            if generate_content:
                # Check if cancelled before content generation
                self.check_cancelled(run_id)

                logger.info(f"=== STARTING CONTENT GENERATION PHASE ===")
                self.log_agent.log(
                    agent_name="Orchestrator",
                    status="info",
                    message=f"Search phase complete. Starting content generation for {len(job_ids)} jobs.",
                    run_id=run_id,
                    step="search_complete",
                    metadata={"job_count": len(job_ids)}
                )

                run.status = RunStatus.CONTENT_GENERATING
                self.db.commit()

                from app.models import Job
                jobs = self.db.query(Job).filter(Job.id.in_(job_ids)).all()

                for job in jobs:
                    # Check cancellation before each job
                    self.check_cancelled(run_id)

                    try:
                        self.content_agent.generate_all_content(job, run_id=run_id)
                    except Exception as e:
                        logger.error(f"Error generating content for job {job.id}: {e}", exc_info=True)
                        self.log_agent.log_error(
                            agent_name="Orchestrator",
                            error=e,
                            run_id=run_id,
                            job_id=job.id,
                            step="generate_content",
                        )

                logger.info(f"=== CONTENT GENERATION PHASE COMPLETE ===")
                self.log_agent.log(
                    agent_name="Orchestrator",
                    status="info",
                    message=f"Content generation complete for {len(job_ids)} jobs.",
                    run_id=run_id,
                    step="content_generation_complete",
                    metadata={"job_count": len(job_ids)}
                )
            else:
                # If content generation not selected, log that search is the final phase
                logger.info(f"=== SEARCH PHASE COMPLETE (No content generation selected) ===")
                self.log_agent.log(
                    agent_name="Orchestrator",
                    status="info",
                    message=f"Search phase complete. Content generation not selected.",
                    run_id=run_id,
                    step="search_complete_no_content",
                    metadata={"job_count": len(job_ids)}
                )

            # Auto-apply only if enabled and jobs are approved
            if auto_apply:
                # Check if cancelled before auto-apply
                self.check_cancelled(run_id)

                run.status = RunStatus.APPLYING
                self.db.commit()

                self.log_agent.log(
                    agent_name="Orchestrator",
                    status="info",
                    message="Starting auto-apply phase",
                    run_id=run_id,
                    step="start_apply"
                )

                from app.models import Job
                approved_jobs = self.db.query(Job).filter(
                    Job.id.in_(job_ids),
                    Job.approved == True,
                ).all()

                applied_count = 0
                failed_count = 0

                for job in approved_jobs:
                    # Check cancellation before each application
                    self.check_cancelled(run_id)

                    try:
                        success = self.apply_agent.apply_to_job(
                            job,
                            run_id=run_id,
                            human_approval_required=True,  # Always require approval flag
                        )
                        if success:
                            applied_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        logger.error(f"Error applying to job {job.id}: {e}", exc_info=True)
                        self.log_agent.log_error(
                            agent_name="Orchestrator",
                            error=e,
                            run_id=run_id,
                            job_id=job.id,
                            step="batch_apply_job"
                        )
                        failed_count += 1

                run.jobs_applied = applied_count
                run.jobs_failed = failed_count

            run.status = RunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            self.db.commit()

            return {
                "run_id": run_id,
                "jobs_found": run.jobs_found,
                "jobs_scored": run.jobs_scored,
                "jobs_above_threshold": run.jobs_above_threshold,
                "jobs_applied": run.jobs_applied,
                "jobs_failed": run.jobs_failed,
            }

        finally:
            # CRITICAL: Always finalize run status, even if process crashes
            try:
                run = self.db.query(Run).filter(Run.id == run_id).first()
                if run and run.status not in [RunStatus.COMPLETED, RunStatus.FAILED]:
                    logger.warning(
                        f"Run {run_id} finalized in finally block "
                        f"(previous status: {run.status})"
                    )
                    run.status = RunStatus.COMPLETED
                    run.completed_at = datetime.utcnow()
                    self.db.commit()
            except Exception as e:
                logger.error(f"Error in finally block for run {run_id}: {e}", exc_info=True)
