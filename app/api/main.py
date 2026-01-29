"""FastAPI main application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import asyncio
from datetime import datetime
import yaml
from pathlib import Path

from app.db import get_db, init_db
from app.models import Run, Job, JobStatus, RunStatus, UserProfile, RateLimitRecord, Company
from app.orchestrator import PipelineOrchestrator
from app.config import config
from app.user_profile import get_user_profile, create_default_profile
from app.services.rate_limiter import RateLimiter, rate_limit_dependency

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('scraping_debug.log')
    ]
)
logger = logging.getLogger(__name__)


# Background task storage
active_runs: Dict[int, Dict[str, Any]] = {}


# API Key Authentication
import os
from fastapi.security import APIKeyHeader
import secrets

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
_API_KEY = os.getenv("API_KEY", "")
_API_KEY_ENABLED = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"


async def verify_api_key(api_key: Optional[str] = Depends(API_KEY_HEADER)) -> bool:
    """Verify API key for protected endpoints.

    API key authentication can be enabled by setting:
    - API_KEY_REQUIRED=true (environment variable)
    - API_KEY=your-secret-key (environment variable)

    When disabled (default for development), all requests are allowed.
    """
    if not _API_KEY_ENABLED:
        return True

    if not _API_KEY:
        logger.warning("API_KEY_REQUIRED is true but API_KEY is not set!")
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: API key not configured"
        )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header."
        )

    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, _API_KEY):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    return True


def generate_api_key() -> str:
    """Generate a secure API key. Use this to create a new key."""
    return secrets.token_urlsafe(32)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")

    # Recover stuck runs from previous crashes
    try:
        from app.recovery import recover_stuck_runs
        from app.db import get_db_context
        with get_db_context() as db:
            recovered = recover_stuck_runs(db)
            if recovered > 0:
                logger.warning(f"Recovered {recovered} stuck runs on startup")
    except Exception as e:
        logger.error(f"Error recovering stuck runs: {e}", exc_info=True)

    # Start scheduler if enabled (single worker only)
    scheduler_lock = Path("scheduler.lock")
    scheduler_started = False
    
    try:
        from app.scheduling import get_scheduler
        scheduler_config = config.get_scheduler_config()
        if scheduler_config.get("enabled", True):
            # Try to acquire lock using exclusive creation
            try:
                # Create lock file - fails if exists
                with open(scheduler_lock, "x"):
                    scheduler_started = True
                    scheduler = get_scheduler()
                    scheduler.start()
                    logger.info("Scheduler started (lock acquired)")
            except FileExistsError:
                logger.info("Scheduler already running in another worker (lock exists)")
            except Exception as e:
                logger.warning(f"Error acquiring scheduler lock: {e}")

    except Exception as e:
        logger.warning(f"Could not start scheduler: {e}")
    
    yield
    # Shutdown
    logger.info("Shutting down...")
    try:
        if scheduler_started:
            from app.scheduling import get_scheduler
            scheduler = get_scheduler()
            scheduler.stop()
            logger.info("Scheduler stopped")
            # Release lock
            if scheduler_lock.exists():
                scheduler_lock.unlink()
                logger.info("Scheduler lock released")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")


app = FastAPI(
    title="Agentic Job Search Pipeline API",
    description="API for automated job search and application pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware - restrict methods and headers for production security
origins = [origin.strip() for origin in config.api.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)


# Pydantic models for requests/responses
class SearchRequest(BaseModel):
    titles: List[str] = Field(
        ...,
        description="Job titles to search for",
        min_length=1,
        max_length=10,
    )
    locations: Optional[List[str]] = Field(
        None,
        description="Location filters",
        max_length=20,
    )
    remote: bool = Field(False, description="Remote filter")
    keywords: Optional[List[str]] = Field(
        None,
        description="Keywords",
        max_length=50,
    )
    sources: Optional[List[str]] = Field(
        None,
        description="Job sources to search",
        max_length=10,
    )
    max_results: int = Field(
        50,
        description="Max results per source",
        ge=1,
        le=200,
    )


class BulkApproveRequest(BaseModel):
    job_ids: List[int]


class JobRejectRequest(BaseModel):
    reason: Optional[str] = None


class BulkRejectRequest(BaseModel):
    job_ids: List[int]
    reason: Optional[str] = None


class ScoringWeights(BaseModel):
    title_match: float = 8.0
    vertical_match: float = 6.0
    remote_preference: float = 5.0
    comp_match: float = 7.0
    keyword_overlap: float = 6.0
    company_match: float = 5.0
    posting_recency: float = 3.0


class RunRequest(BaseModel):
    search: SearchRequest
    target_companies: Optional[List[str]] = Field(None, max_length=100)
    must_have_keywords: Optional[List[str]] = Field(None, max_length=50)
    nice_to_have_keywords: Optional[List[str]] = Field(None, max_length=50)
    remote_preference: str = Field("any", description="remote, hybrid, on-site, any")
    salary_min: Optional[int] = Field(None, ge=0, le=10_000_000)
    scoring_weights: Optional[ScoringWeights] = None
    llm_config: Optional[Dict[str, Any]] = None
    generate_content: bool = True
    auto_apply: bool = False

    @field_validator('remote_preference')
    @classmethod
    def validate_remote_preference(cls, v):
        valid_values = {'remote', 'hybrid', 'on-site', 'any'}
        if v.lower() not in valid_values:
            raise ValueError(f"remote_preference must be one of: {', '.join(valid_values)}")
        return v.lower()


class RunResponse(BaseModel):
    run_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    jobs_found: int = 0
    jobs_scored: int = 0
    jobs_above_threshold: int = 0
    jobs_approved: int = 0
    jobs_applied: int = 0
    jobs_failed: int = 0


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    linkedin_user: Optional[str] = None
    linkedin_password: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    other_links: Optional[List[str]] = None
    current_title: Optional[str] = None
    target_titles: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    experience_summary: Optional[str] = None
    resume_text: Optional[str] = None
    target_companies: Optional[List[str]] = None
    must_have_keywords: Optional[List[str]] = None
    nice_to_have_keywords: Optional[List[str]] = None
    # Application preferences
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    work_authorization: Optional[str] = None
    visa_sponsorship_required: Optional[bool] = None
    notice_period: Optional[str] = None
    relocation_preference: Optional[str] = None
    remote_preference: Optional[str] = None
    # Company preferences (for RAG-based suggestions)
    preferred_industries: Optional[List[str]] = None
    preferred_company_sizes: Optional[List[str]] = None
    preferred_company_stages: Optional[List[str]] = None
    preferred_tech_stack: Optional[List[str]] = None
    is_onboarded: Optional[bool] = None


class ConfigUpdate(BaseModel):
    search: Optional[Dict[str, Any]] = None
    scoring: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, Any]] = None
    content_prompts: Optional[Dict[str, str]] = None
    job_sources: Optional[Dict[str, Any]] = None


# Health check
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "unknown",
            "system": "ok"
        }
    }
    
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        status["components"]["database"] = "up"
    except Exception as e:
        status["status"] = "degraded"
        status["components"]["database"] = f"down: {str(e)}"
        
    return status


# Run endpoints
@app.post("/runs", response_model=RunResponse)
async def create_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
    __: bool = Depends(rate_limit_dependency("run_pipeline")),
):
    """Create and start a new pipeline run. Requires API key when enabled."""
    try:
        orchestrator = PipelineOrchestrator(db)
        
        # Create run
        run = orchestrator.create_run(
            search_config={
                "titles": request.search.titles,
                "locations": request.search.locations,
            },
            scoring_config=request.scoring_weights.dict() if request.scoring_weights else {},
            llm_config=request.llm_config or {},
        )
        
        # Start pipeline in background - need to capture values before async context
        run_id = run.id
        search_titles = request.search.titles
        search_locations = request.search.locations or []
        search_remote = request.search.remote
        search_keywords = request.search.keywords
        search_sources = request.search.sources
        search_max_results = request.search.max_results
        search_target_companies = request.target_companies or []
        search_must_have = request.must_have_keywords or []
        search_nice_to_have = request.nice_to_have_keywords or []
        search_remote_pref = request.remote_preference
        search_salary_min = request.salary_min
        search_generate_content = request.generate_content
        search_auto_apply = request.auto_apply
        
        def run_pipeline():
            """Run pipeline in background with new database session.

            Uses context manager for guaranteed session cleanup.
            """
            logger.info(f"Background task starting for run {run_id}")
            from app.db import get_db_context
            from app.models import Run as RunModel, RunStatus

            try:
                # Use context manager for guaranteed session cleanup
                with get_db_context() as db:
                    logger.info(f"Background task: Database session created for run {run_id}")

                    # Create a new orchestrator with the new session
                    bg_orchestrator = PipelineOrchestrator(db)
                    logger.info(f"Background task: Orchestrator created for run {run_id}")

                    try:
                        result = bg_orchestrator.run_full_pipeline(
                            run_id=run_id,
                            titles=search_titles,
                            locations=search_locations,
                            remote=search_remote,
                            keywords=search_keywords,
                            sources=search_sources,
                            max_results=search_max_results,
                            target_companies=search_target_companies,
                            must_have_keywords=search_must_have,
                            nice_to_have_keywords=search_nice_to_have,
                            remote_preference=search_remote_pref,
                            salary_min=search_salary_min,
                            generate_content=search_generate_content,
                            auto_apply=search_auto_apply,
                        )
                        logger.info(f"Pipeline run {run_id} completed: {result}")
                    except Exception as pipeline_err:
                        # Import CancelledException for special handling
                        from app.orchestrator import CancelledException

                        # Check if this is a cancellation (not an error)
                        if isinstance(pipeline_err, CancelledException):
                            logger.info(f"Pipeline run {run_id} was cancelled")
                            # Run status already set to CANCELLED by cancel endpoint
                            # No need to update status here
                            return

                        # Handle other errors
                        logger.error(f"Error in pipeline run {run_id}: {pipeline_err}", exc_info=True)
                        # Update run status to failed (within same session)
                        try:
                            bg_run = db.query(RunModel).filter(RunModel.id == run_id).first()
                            if bg_run:
                                bg_run.status = RunStatus.FAILED
                                bg_run.error_message = str(pipeline_err)
                                bg_run.completed_at = datetime.utcnow()
                                db.commit()
                                logger.info(f"Run {run_id} marked as failed")
                        except Exception as status_err:
                            logger.error(f"Error updating run status: {status_err}", exc_info=True)

            except Exception as e:
                # Session creation itself failed - try with a fresh session
                logger.error(f"Fatal error in background pipeline task for run {run_id}: {e}", exc_info=True)
                try:
                    with get_db_context() as fallback_db:
                        bg_run = fallback_db.query(RunModel).filter(RunModel.id == run_id).first()
                        if bg_run:
                            bg_run.status = RunStatus.FAILED
                            bg_run.error_message = f"Fatal error: {str(e)}"
                            bg_run.completed_at = datetime.utcnow()
                            fallback_db.commit()
                except Exception as db_fallback_err:
                    logger.error(
                        f"Failed to update run {run_id} status after fatal error: {db_fallback_err}"
                    )
        
        background_tasks.add_task(run_pipeline)
        active_runs[run.id] = {"status": "started", "run": run}
        
        return RunResponse(
            run_id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            jobs_found=run.jobs_found,
            jobs_scored=run.jobs_scored,
            jobs_above_threshold=run.jobs_above_threshold,
            jobs_applied=run.jobs_applied,
            jobs_failed=run.jobs_failed,
        )
    except Exception as e:
        logger.error(f"Error creating run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs", response_model=List[RunResponse])
async def list_runs(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all pipeline runs with pagination.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum records to return (default: 50, max: 100)
    """
    # Enforce max limit to prevent OOM
    limit = min(limit, 100)
    skip = max(skip, 0)

    runs = db.query(Run).order_by(Run.started_at.desc()).offset(skip).limit(limit).all()
    return [
        RunResponse(
            run_id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            jobs_found=run.jobs_found,
            jobs_scored=run.jobs_scored,
            jobs_above_threshold=run.jobs_above_threshold,
            jobs_approved=run.jobs_approved,
            jobs_applied=run.jobs_applied,
            jobs_failed=run.jobs_failed,
        )
        for run in runs
    ]


@app.delete("/runs")
async def delete_all_runs(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Delete all runs and associated jobs. Requires API key when enabled."""
    try:
        # Delete all runs (cascade will handle jobs and logs)
        deleted_count = db.query(Run).delete()
        db.commit()
        return {"status": "deleted", "count": deleted_count}
    except Exception as e:
        logger.error(f"Error deleting runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get a specific pipeline run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return RunResponse(
        run_id=run.id,
        status=run.status.value,
        started_at=run.started_at,
        completed_at=run.completed_at,
        jobs_found=run.jobs_found,
        jobs_scored=run.jobs_scored,
        jobs_above_threshold=run.jobs_above_threshold,
        jobs_approved=run.jobs_approved,
        jobs_applied=run.jobs_applied,
        jobs_failed=run.jobs_failed,
    )


@app.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Cancel a running pipeline run.

    Sets the run status to CANCELLED, which will cause the background
    task to stop processing.
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Only allow cancelling runs that are still in progress
    if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel run with status: {run.status.value}"
        )

    try:
        run.status = RunStatus.CANCELLED
        run.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Run {run_id} cancelled")

        return {
            "status": "cancelled",
            "run_id": run_id,
            "message": "Run has been cancelled"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs/{run_id}/jobs")
async def get_run_jobs(
    run_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get jobs from a specific run with pagination.

    Args:
        run_id: The run ID to get jobs for
        skip: Number of records to skip (default: 0)
        limit: Maximum records to return (default: 100, max: 500)
    """
    # Enforce max limit to prevent OOM
    limit = min(limit, 500)
    skip = max(skip, 0)

    # Get total count for pagination info
    total = db.query(Job).filter(Job.run_id == run_id).count()

    jobs = (
        db.query(Job)
        .filter(Job.run_id == run_id)
        .order_by(Job.relevance_score.desc().nullslast())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "jobs": [
            {
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "source_url": job.source_url,
                "relevance_score": job.relevance_score,
                "status": job.status.value,
                "approved": job.approved,
                "created_at": job.created_at.isoformat(),
            }
            for job in jobs
        ],
    }


# Job endpoints
@app.get("/jobs")
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all jobs across all runs."""
    limit = min(limit, 500)
    skip = max(skip, 0)
    
    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return [
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "source": job.source,
            "source_url": job.source_url,
            "relevance_score": job.relevance_score,
            "status": job.status.value,
            "approved": job.approved,
            "created_at": job.created_at.isoformat(),
            "posting_date": job.posting_date.isoformat() if job.posting_date else None,
            "run_id": job.run_id
        }
        for job in jobs
    ]


@app.post("/jobs/bulk-approve")
async def bulk_approve_jobs(
    request: BulkApproveRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Approve multiple jobs at once."""
    jobs = db.query(Job).filter(Job.id.in_(request.job_ids)).all()
    count = 0
    for job in jobs:
        job.approved = True
        count += 1

    db.commit()

    # Auto-queue approved jobs if auto-apply is enabled
    queued_count = 0
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        if service.enabled:
            # Queue all approved jobs
            queued_count = service.queue_manager.add_jobs(jobs)
            if queued_count > 0:
                logger.info(f"Auto-queued {queued_count} jobs for application")

                # Start background processing if not already running
                status = service.get_status()
                if not status["is_processing"] and status["queue_size"] > 0:
                    service.start_background_processing()
                    logger.info("Started background processing for queued jobs")
    except Exception as e:
        logger.warning(f"Failed to auto-queue jobs: {e}")

    return {"status": "approved", "count": count, "queued": queued_count}


@app.post("/jobs/bulk-reject")
async def bulk_reject_jobs(
    request: BulkRejectRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Reject multiple jobs at once."""
    jobs = db.query(Job).filter(Job.id.in_(request.job_ids)).all()
    count = 0
    for job in jobs:
        job.status = JobStatus.REJECTED
        job.approved = False
        if request.reason:
            job.rejection_reason = request.reason
        count += 1
    
    db.commit()
    return {"status": "rejected", "count": count}


@app.get("/jobs/{job_id}")
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get a specific job with full details."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source,
        "source_url": job.source_url,
        "description": job.description,
        "raw_description": job.raw_description,
        "qualifications": job.qualifications,
        "keywords": job.keywords or [],
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "relevance_score": job.relevance_score,
        "scoring_breakdown": job.scoring_breakdown or {},
        "status": job.status.value,
        "approved": job.approved,
        "llm_summary": job.llm_summary,
        "tailored_resume_points": job.tailored_resume_points or [],
        "cover_letter_draft": job.cover_letter_draft,
        "application_answers": job.application_answers or {},
        "application_error": job.application_error,
        "application_started_at": job.application_started_at.isoformat() if job.application_started_at else None,
        "application_completed_at": job.application_completed_at.isoformat() if job.application_completed_at else None,
        "created_at": job.created_at.isoformat(),
    }


@app.post("/jobs/{job_id}/approve")
async def approve_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Approve a job for application. Requires API key when enabled."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.approved = True
    db.commit()

    # Auto-queue for application if auto-apply is enabled
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        if service.enabled:
            # Queue this specific job
            queued = service.queue_manager.add_job(job)
            if queued:
                logger.info(f"Auto-queued job {job_id} for application")

                # Start background processing if not already running
                status = service.get_status()
                if not status["is_processing"] and status["queue_size"] > 0:
                    service.start_background_processing()
                    logger.info("Started background processing for queued job")

                return {"status": "approved", "job_id": job_id, "queued": True}
    except Exception as e:
        logger.warning(f"Failed to auto-queue job {job_id}: {e}")

    return {"status": "approved", "job_id": job_id, "queued": False}


@app.post("/jobs/{job_id}/reject")
async def reject_job(
    job_id: int,
    request: JobRejectRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Reject a job. Requires API key when enabled."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.status = JobStatus.REJECTED
    job.approved = False
    job.rejection_reason = request.reason
    db.commit()
    return {"status": "rejected", "job_id": job_id}


@app.post("/jobs/{job_id}/generate-content")
async def generate_content(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate content for a job (summary, resume points, cover letter)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    from app.agents.content_agent import ContentGenerationAgent
    from app.agents.log_agent import LogAgent
    from app.models import JobStatus
    
    log_agent = LogAgent(db)
    content_agent = ContentGenerationAgent(db, log_agent=log_agent)
    
    def generate():
        try:
            # Refresh job from database in this context
            from app.db import get_db_context
            with get_db_context() as db_session:
                job = db_session.query(Job).filter(Job.id == job_id).first()
                if not job:
                    logger.error(f"Job {job_id} not found during content generation")
                    return
                
                content_agent = ContentGenerationAgent(db_session, log_agent=LogAgent(db_session))
                content_agent.generate_all_content(job, run_id=job.run_id)
                logger.info(f"Content generation completed for job {job_id}")
        except Exception as e:
            logger.error(f"Fatal error generating content for job {job_id}: {e}", exc_info=True)
            # Update job with error message
            try:
                from app.db import get_db_context
                with get_db_context() as db_session:
                    job = db_session.query(Job).filter(Job.id == job_id).first()
                    if job:
                        job.application_error = f"Content generation failed: {str(e)}"
                        db_session.commit()
            except Exception as db_error:
                logger.error(f"Error updating job error message: {db_error}", exc_info=True)
    
    background_tasks.add_task(generate)
    return {"status": "generating", "job_id": job_id, "message": "Content generation started"}


@app.post("/jobs/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    dry_run: bool = False,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
    __: bool = Depends(rate_limit_dependency("apply_to_job")),
):
    """Apply to a job (requires approval). Requires API key when enabled. Set dry_run=True to simulate."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.approved:
        raise HTTPException(status_code=400, detail="Job must be approved before applying")
    
    if job.status == JobStatus.APPLICATION_COMPLETED and not dry_run:
        return {"status": "already_applied", "job_id": job_id}
    
    # Import apply agent
    from app.agents.apply_agent import ApplyAgent
    from app.agents.log_agent import LogAgent
    
    log_agent = LogAgent(db)
    apply_agent = ApplyAgent(db, log_agent=log_agent, enable_playwright=True)
    
    # Run application in background
    async def run_application():
        try:
            # Refresh job from DB to get latest state
            db.refresh(job)
            success = apply_agent.apply_to_job(
                job=job,
                run_id=None,
                human_approval_required=True,
                max_retries=2,
                dry_run=dry_run
            )
            if success:
                if dry_run:
                    logger.info(f"Dry-run successful for job {job_id}")
                else:
                    logger.info(f"Successfully applied to job {job_id}")
            else:
                logger.warning(f"Failed to apply to job {job_id}: {job.application_error}")
        except Exception as e:
            logger.error(f"Error applying to job {job_id}: {e}", exc_info=True)
            db.refresh(job)
            job.status = JobStatus.APPLICATION_FAILED
            job.application_error = str(e)
            db.commit()
    
    background_tasks.add_task(run_application)
    
    return {
        "status": "started",
        "job_id": job_id,
        "dry_run": dry_run,
        "message": f"Application process started (dry_run={dry_run}). Check job status for updates."
    }


async def get_current_user_profile(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key)
) -> UserProfile:
    """Get the current authenticated user's profile.
    
    Currently defaults to profile_id=1 for single-user mode.
    Future: Extract user ID from JWT/Session.
    """
    profile = get_user_profile(db, profile_id=1)
    if not profile:
        # Create default profile if not exists
        profile = create_default_profile(
            name="Default User",
            email=None,
            current_title="Product Manager",
            target_titles=["Product Manager", "Senior Product Manager"],
            skills=["Product Management", "Agile", "Data Analysis"],
        )
        db.refresh(profile)
    return profile

# User Profile endpoints
@app.get("/profile")
async def get_profile(
    profile: UserProfile = Depends(get_current_user_profile)
):
    """Get user profile."""
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url,
        "linkedin_user": profile.linkedin_user,
        "has_linkedin_password": bool(profile.linkedin_password),
        "portfolio_url": profile.portfolio_url,
        "github_url": profile.github_url,
        "other_links": profile.other_links or [],
        "current_title": profile.current_title,
        "target_titles": profile.target_titles or [],
        "skills": profile.skills or [],
        "experience_summary": profile.experience_summary,
        "resume_text": profile.resume_text,
        "resume_bullet_points": profile.resume_bullet_points or [],
        "target_companies": profile.target_companies or [],
        "must_have_keywords": profile.must_have_keywords or [],
        "nice_to_have_keywords": profile.nice_to_have_keywords or [],
        # Application preferences
        "salary_min": profile.salary_min,
        "salary_max": profile.salary_max,
        "work_authorization": profile.work_authorization,
        "visa_sponsorship_required": profile.visa_sponsorship_required,
        "notice_period": profile.notice_period,
        "relocation_preference": profile.relocation_preference,
        "remote_preference": profile.remote_preference,
        "is_onboarded": profile.is_onboarded,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@app.put("/profile")
async def update_profile(
    update: UserProfileUpdate,
    db: Session = Depends(get_db),
    profile: UserProfile = Depends(get_current_user_profile),
):
    """Update user profile. Requires API key when enabled."""
    # Profile is already retrieved by dependency
    
    # Update fields
    update_dict = update.dict(exclude_unset=True)
    
    # Encrypt LinkedIn password if provided
    if "linkedin_password" in update_dict and update_dict["linkedin_password"]:
        from app.security import get_fernet
        fernet = get_fernet()
        encrypted_pwd = fernet.encrypt(update_dict["linkedin_password"].encode()).decode()
        update_dict["linkedin_password"] = encrypted_pwd
    
    for key, value in update_dict.items():
        setattr(profile, key, value)
    
    profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(profile)
    
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url,
        "linkedin_user": profile.linkedin_user,
        "has_linkedin_password": bool(profile.linkedin_password),
        "portfolio_url": profile.portfolio_url,
        "github_url": profile.github_url,
        "other_links": profile.other_links or [],
        "current_title": profile.current_title,
        "target_titles": profile.target_titles or [],
        "skills": profile.skills or [],
        "experience_summary": profile.experience_summary,
        "resume_text": profile.resume_text,
        "resume_bullet_points": profile.resume_bullet_points or [],
        "target_companies": profile.target_companies or [],
        "must_have_keywords": profile.must_have_keywords or [],
        "nice_to_have_keywords": profile.nice_to_have_keywords or [],
        # Application preferences
        "salary_min": profile.salary_min,
        "salary_max": profile.salary_max,
        "work_authorization": profile.work_authorization,
        "visa_sponsorship_required": profile.visa_sponsorship_required,
        "notice_period": profile.notice_period,
        "relocation_preference": profile.relocation_preference,
        "remote_preference": profile.remote_preference,
        "is_onboarded": profile.is_onboarded,
    }


@app.post("/profile/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    profile: UserProfile = Depends(get_current_user_profile),
):
    """Upload and parse resume document (supports PDF, DOCX, DOC, TXT). Requires API key when enabled."""
    import os
    import uuid
    from pathlib import Path

    # Security constants
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'text/plain',
    }
    # Magic bytes for file type validation
    MAGIC_BYTES = {
        b'%PDF': '.pdf',
        b'PK\x03\x04': '.docx',  # DOCX is a ZIP file
        b'\xd0\xcf\x11\xe0': '.doc',  # Old DOC format (OLE)
    }

    try:
        # Get original filename and validate extension
        original_filename = file.filename or "unknown"
        # Sanitize filename - remove path components
        safe_filename = os.path.basename(original_filename)
        file_ext = os.path.splitext(safe_filename.lower())[1]

        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Read file content with size limit
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB"
            )

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Validate MIME type if provided
        if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
            # Log but don't reject - MIME types from clients are unreliable
            logger.warning(f"Unexpected MIME type: {file.content_type} for file {safe_filename}")

        # Validate magic bytes for binary files
        detected_ext = None
        for magic, ext in MAGIC_BYTES.items():
            if content[:len(magic)] == magic:
                detected_ext = ext
                break

        # For non-text files, verify magic bytes match extension
        if file_ext in {'.pdf', '.docx', '.doc'}:
            if detected_ext and detected_ext != file_ext:
                # Special case: .docx might be detected as .doc or vice versa
                if not (file_ext in {'.doc', '.docx'} and detected_ext in {'.doc', '.docx'}):
                    logger.warning(f"File extension mismatch: claimed {file_ext}, detected {detected_ext}")
                    raise HTTPException(
                        status_code=400,
                        detail="File content does not match extension"
                    )

        # Extract text based on file type
        text_content = ""
        if file_ext == '.pdf':
            try:
                from PyPDF2 import PdfReader
                import io
                pdf_file = io.BytesIO(content)
                pdf_reader = PdfReader(pdf_file)
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                text_content = "\n".join(text_parts)
            except ImportError:
                logger.warning("PyPDF2 not installed. Unable to extract text from PDF.")
                text_content = ""
            except Exception as e:
                logger.warning(f"Error parsing PDF: {e}. Unable to extract text.")
                text_content = ""
        elif file_ext in {'.docx', '.doc'}:
            try:
                from docx import Document
                import io
                doc_file = io.BytesIO(content)
                doc = Document(doc_file)
                text_parts = []
                for para in doc.paragraphs:
                    text_parts.append(para.text)
                text_content = "\n".join(text_parts)
            except ImportError:
                logger.warning("python-docx not installed. Unable to extract text from DOCX/DOC.")
                text_content = ""
            except Exception as e:
                logger.warning(f"Error parsing DOCX: {e}. Unable to extract text.")
                text_content = ""
        else:
            # Plain text file
            text_content = content.decode('utf-8', errors='ignore')

        # Store resume file with secure random filename
        resume_dir = Path("resumes")
        resume_dir.mkdir(exist_ok=True)
        # Use UUID to prevent path traversal and filename collisions
        secure_filename = f"resume_{uuid.uuid4().hex}{file_ext}"
        resume_path = resume_dir / secure_filename

        # Delete old resume file if it exists (prevents disk space exhaustion)
        old_resume_path = profile.resume_file_path
        if old_resume_path:
            old_path = Path(old_resume_path)
            if old_path.exists() and old_path.is_file():
                try:
                    old_path.unlink()
                    logger.info(f"Deleted old resume file: {old_resume_path}")
                except Exception as delete_err:
                    logger.warning(f"Could not delete old resume file: {delete_err}")

        # Write new resume file
        with open(resume_path, "wb") as f:
            f.write(content)

        # Encrypt the file - if this fails, delete the unencrypted file and raise error
        try:
            from app.security import encrypt_file
            encrypt_file(resume_path)
        except Exception as e:
            logger.error(f"Failed to encrypt resume file: {e}")
            # Delete the unencrypted file to prevent storing sensitive data in plaintext
            try:
                os.remove(resume_path)
                logger.info(f"Deleted unencrypted resume file after encryption failure")
            except Exception as delete_err:
                logger.error(f"Failed to delete unencrypted resume file: {delete_err}")
            raise HTTPException(
                status_code=500,
                detail="Failed to securely store resume. Please try again or contact support."
            )

        # Update profile with resume text and path
        profile.resume_text = text_content
        profile.resume_file_path = str(resume_path)
        profile.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(profile)

        return {
            "status": "success",
            "original_filename": safe_filename,
            "size": len(content),
            "resume_text_length": len(text_content),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process resume file")


# Company endpoints
class CompanySuggestionRequest(BaseModel):
    """Request model for company suggestions."""
    industries: Optional[List[str]] = None
    company_sizes: Optional[List[str]] = None
    company_stages: Optional[List[str]] = None
    tech_stack: Optional[List[str]] = None
    limit: int = 15


@app.get("/companies")
async def list_companies(
    db: Session = Depends(get_db),
    industry: Optional[str] = None,
    size: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 100,
    _: bool = Depends(verify_api_key),
):
    """List all companies with optional filtering."""
    try:
        query = db.query(Company)

        if size:
            query = query.filter(Company.size == size)

        if stage:
            query = query.filter(Company.stage == stage)

        companies = query.limit(limit).all()

        # Filter by industry in Python (JSON filtering in SQLite is complex)
        if industry:
            companies = [c for c in companies if c.industries and industry.lower() in [i.lower() for i in c.industries]]

        return [{
            "id": c.id,
            "name": c.name,
            "industries": c.industries,
            "verticals": c.verticals,
            "size": c.size,
            "stage": c.stage,
            "tech_stack": c.tech_stack,
            "description": c.description,
            "headquarters": c.headquarters,
            "website": c.website
        } for c in companies]

    except Exception as e:
        logger.error(f"Error listing companies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list companies")


@app.post("/companies/suggest")
async def suggest_companies(
    request: CompanySuggestionRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Get company suggestions based on user preferences (with RAG fallback to simple matching)."""
    try:
        # Try RAG-based suggestions first
        try:
            from app.rag.company_service import CompanyRAGService

            rag_service = CompanyRAGService(db=db)
            suggestions = rag_service.suggest_companies(
                industries=request.industries,
                company_sizes=request.company_sizes,
                company_stages=request.company_stages,
                tech_stack=request.tech_stack,
                k=request.limit
            )

            return {"suggestions": suggestions, "method": "rag"}

        except (ImportError, Exception) as rag_error:
            logger.warning(f"RAG not available, using fallback matching: {rag_error}")

            # Fallback: Simple filtering and scoring
            companies = db.query(Company).all()
            scored_companies = []

            for company in companies:
                score = 0
                reasons = []

                # Score by industries
                if request.industries and company.industries:
                    industry_matches = sum(1 for i in request.industries
                                         if any(i.lower() in ci.lower() for ci in company.industries))
                    if industry_matches > 0:
                        score += industry_matches * 30
                        reasons.append(f"{industry_matches} industry matches")

                # Score by size
                if request.company_sizes and company.size:
                    for size_pref in request.company_sizes:
                        # Normalize size strings (remove parentheses)
                        size_clean = size_pref.split('(')[0].strip() if '(' in size_pref else size_pref
                        if size_clean.lower() in company.size.lower():
                            score += 20
                            reasons.append("size match")
                            break

                # Score by stage
                if request.company_stages and company.stage:
                    if any(stage.lower() in company.stage.lower() for stage in request.company_stages):
                        score += 15
                        reasons.append("stage match")

                # Score by tech stack
                if request.tech_stack and company.tech_stack:
                    tech_matches = sum(1 for t in request.tech_stack
                                     if any(t.lower() in ct.lower() for ct in company.tech_stack))
                    if tech_matches > 0:
                        score += tech_matches * 25
                        reasons.append(f"{tech_matches} tech matches")

                if score > 0:
                    scored_companies.append({
                        'id': company.id,
                        'name': company.name,
                        'industries': company.industries,
                        'verticals': company.verticals,
                        'size': company.size,
                        'stage': company.stage,
                        'tech_stack': company.tech_stack,
                        'description': company.description,
                        'headquarters': company.headquarters,
                        'website': company.website,
                        'relevance_score': score / 100.0,  # Normalize to 0-1 scale
                        'match_reasons': reasons
                    })

            # Sort by score and return top k
            scored_companies.sort(key=lambda x: x['relevance_score'], reverse=True)
            suggestions = scored_companies[:request.limit]

            return {"suggestions": suggestions, "method": "fallback"}

    except Exception as e:
        logger.error(f"Error generating company suggestions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@app.post("/companies/index")
async def index_companies(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Index all companies in RAG vector store."""
    try:
        from app.rag.company_service import CompanyRAGService

        rag_service = CompanyRAGService(db=db)
        results = rag_service.index_all_companies()

        return {
            "status": "success" if results["failed"] == 0 else "partial",
            "total": results["total"],
            "indexed": results["success"],
            "failed": results["failed"],
            "errors": results["errors"]
        }

    except Exception as e:
        logger.error(f"Error indexing companies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to index companies")


# Scheduler endpoints
@app.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status."""
    try:
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler_config = config.get_scheduler_config()
        return {
            "enabled": scheduler_config.get("enabled", True),
            "running": scheduler.running,
            "frequency_hours": scheduler.frequency_hours,
            "run_at_time": scheduler.run_at_time,
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/start")
async def start_scheduler(_: bool = Depends(verify_api_key)):
    """Start the scheduler. Requires API key when enabled."""
    try:
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()
        return {"status": "started", "message": "Scheduler started successfully"}
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/stop")
async def stop_scheduler(_: bool = Depends(verify_api_key)):
    """Stop the scheduler. Requires API key when enabled."""
    try:
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler.stop()
        return {"status": "stopped", "message": "Scheduler stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/scheduler/config")
async def update_scheduler_config(
    enabled: Optional[bool] = None,
    frequency_hours: Optional[int] = None,
    run_at_time: Optional[str] = None,
    _: bool = Depends(verify_api_key),
):
    """Update scheduler configuration. Requires API key when enabled."""
    try:
        config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path, "r") as f:
                yaml_config = yaml.safe_load(f) or {}
        else:
            yaml_config = {}
        
        if "scheduler" not in yaml_config:
            yaml_config["scheduler"] = {}
        
        if enabled is not None:
            yaml_config["scheduler"]["enabled"] = enabled
        if frequency_hours is not None:
            yaml_config["scheduler"]["run_frequency_hours"] = frequency_hours
        if run_at_time is not None:
            yaml_config["scheduler"]["run_at_time"] = run_at_time
        
        with open(config_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False)
        
        # Restart scheduler with new config
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler.stop()
        scheduler.enabled = yaml_config["scheduler"].get("enabled", True)
        scheduler.frequency_hours = yaml_config["scheduler"].get("run_frequency_hours", 24)
        scheduler.run_at_time = yaml_config["scheduler"].get("run_at_time", "09:00")
        if scheduler.enabled:
            scheduler.start()
        
        return {"status": "updated", "config": yaml_config["scheduler"]}
    except Exception as e:
        logger.error(f"Error updating scheduler config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Debug endpoints
# Lock for thread-safe config reload
import threading
_config_lock = threading.Lock()


class LinkedInCredentials(BaseModel):
    """LinkedIn credentials for validation - use request body, not query params."""
    email: str
    password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if not v or '@' not in v or len(v) > 254:
            raise ValueError('Invalid email format')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not v or len(v) < 1 or len(v) > 128:
            raise ValueError('Invalid password')
        return v


@app.post("/linkedin/validate-credentials")
async def validate_linkedin_credentials(
    credentials: LinkedInCredentials,
    request: Request,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
    __: bool = Depends(rate_limit_dependency("validate_linkedin")),
):
    """Validate LinkedIn credentials by attempting to log in. Requires API key when enabled.

    WARNING: This endpoint should only be used over HTTPS in production.
    Credentials are sensitive and should never be transmitted over unencrypted connections.
    """
    # Rate limiting handled by dependency

    try:
        from app.agents.search_agent import SearchAgent
        from app.agents.log_agent import LogAgent
        from playwright.async_api import async_playwright
        import asyncio

        log_agent = LogAgent(db)
        search_agent = SearchAgent(db, log_agent=log_agent)

        if 'linkedin' not in search_agent.sources:
            raise HTTPException(status_code=400, detail="LinkedIn source not enabled")

        # Extract client IP for logging
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )

        # Log attempt without exposing email
        logger.info(f"LinkedIn credential validation attempt from {client_ip}")

        try:
            async with async_playwright() as playwright:
                browser = None
                context = None
                result = None

                try:
                    # Launch browser with stealth settings
                    browser = await playwright.chromium.launch(
                        headless=False,
                        args=[
                            '--disable-blink-features=AutomationControlled',
                            '--disable-dev-shm-usage',
                            '--no-sandbox',
                        ]
                    )

                    # Create context with realistic viewport and user agent
                    context = await browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        locale='en-US',
                        timezone_id='America/New_York',
                    )

                    # Add stealth scripts to avoid detection
                    await context.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                        window.chrome = { runtime: {} };
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );
                    """)

                    page = await context.new_page()

                    # Navigate to login page
                    await page.goto("https://www.linkedin.com/login", wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(3)

                    # Enter email
                    email_input = await page.query_selector('input[name="session_key"]')
                    if not email_input:
                        result = {"valid": False, "error": "Could not find email input field on LinkedIn login page"}
                    else:
                        await email_input.fill(credentials.email)
                        await asyncio.sleep(1)

                        # Enter password
                        password_input = await page.query_selector('input[name="session_password"]')
                        if not password_input:
                            result = {"valid": False, "error": "Could not find password input field on LinkedIn login page"}
                        else:
                            await password_input.fill(credentials.password)
                            await asyncio.sleep(1)

                            # Click sign in button
                            sign_in_button = await page.query_selector('button[type="submit"]')
                            if sign_in_button:
                                await sign_in_button.click()
                                await asyncio.sleep(5)

                            # Check if login was successful
                            current_url = page.url
                            login_successful = 'feed' in current_url or 'jobs' in current_url or 'login' not in current_url

                            # Check for error messages
                            error_message = None
                            if not login_successful:
                                error_elem = await page.query_selector('.form__label--error, .alert-error, [role="alert"]')
                                if error_elem:
                                    error_message = await error_elem.inner_text()
                                    error_message = error_message.strip() if error_message else None

                                captcha = await page.query_selector('iframe[title*="captcha"], iframe[src*="captcha"]')
                                if captcha:
                                    error_message = "LinkedIn is requesting CAPTCHA verification. Please try again later."

                            if login_successful:
                                logger.info(f"LinkedIn credentials validated successfully")
                                result = {"valid": True, "message": "Credentials validated successfully"}
                            else:
                                error_msg = error_message or "Login failed - invalid credentials or account issue"
                                logger.warning(f"LinkedIn credentials validation failed: {error_msg}")
                                result = {"valid": False, "error": error_msg}

                finally:
                    # Guaranteed cleanup - always runs even on early returns or exceptions
                    if context:
                        try:
                            await context.close()
                        except Exception as e:
                            logger.debug(f"Error closing context: {e}")
                    if browser:
                        try:
                            await browser.close()
                        except Exception as e:
                            logger.debug(f"Error closing browser: {e}")

                return result if result else {"valid": False, "error": "Unknown validation error"}

        except ImportError:
            raise HTTPException(status_code=500, detail="Playwright not installed. Install with: pip install playwright && playwright install")
        except Exception as e:
            logger.error(f"Error validating LinkedIn credentials: {e}", exc_info=True)
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating LinkedIn credentials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/linkedin/hiring-connections")
async def get_hiring_connections(
    max_connections: int = 100,
    db: Session = Depends(get_db)
):
    """Get LinkedIn connections who are hiring."""
    try:
        from app.agents.search_agent import SearchAgent
        from app.agents.log_agent import LogAgent
        
        log_agent = LogAgent(db)
        search_agent = SearchAgent(db, log_agent=log_agent)
        
        if 'linkedin' not in search_agent.sources:
            raise HTTPException(status_code=400, detail="LinkedIn source not enabled")
        
        linkedin_adapter = search_agent.sources['linkedin']
        hiring_connections = linkedin_adapter.get_hiring_connections(max_connections=max_connections)
        
        return {
            "status": "success",
            "connections_checked": len(hiring_connections),
            "hiring_connections": hiring_connections,
        }
    except Exception as e:
        logger.error(f"Error getting hiring connections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/scraping-stats")
async def get_scraping_stats(db: Session = Depends(get_db)):
    """Get debugging information about scraping results.

    Uses SQL aggregations to avoid loading all jobs into memory.
    """
    try:
        from app.models import Job, Run, JobStatus
        from sqlalchemy import func, desc

        # Get latest run
        latest_run = db.query(Run).order_by(desc(Run.id)).first()
        if not latest_run:
            return {"error": "No runs found"}

        run_id = latest_run.id

        # Get total count using SQL
        total_jobs = db.query(func.count(Job.id)).filter(Job.run_id == run_id).scalar() or 0

        # Get counts by source using SQL GROUP BY
        source_counts = (
            db.query(Job.source, func.count(Job.id))
            .filter(Job.run_id == run_id)
            .group_by(Job.source)
            .all()
        )
        jobs_by_source = {
            (s.value if hasattr(s, 'value') else str(s)): count
            for s, count in source_counts
        }

        # Get counts by status using SQL GROUP BY
        status_counts = (
            db.query(Job.status, func.count(Job.id))
            .filter(Job.run_id == run_id)
            .group_by(Job.status)
            .all()
        )
        jobs_by_status = {
            (s.value if hasattr(s, 'value') else str(s)): count
            for s, count in status_counts
        }

        # Get top 50 jobs by score (only load what we need)
        top_jobs = (
            db.query(Job.id, Job.title, Job.relevance_score, Job.source, Job.status)
            .filter(Job.run_id == run_id, Job.relevance_score.isnot(None))
            .order_by(Job.relevance_score.desc())
            .limit(50)
            .all()
        )
        score_distribution = [
            {
                "id": job.id,
                "title": job.title,
                "score": job.relevance_score,
                "source": job.source.value if hasattr(job.source, 'value') else str(job.source),
                "status": job.status.value if hasattr(job.status, 'value') else str(job.status),
            }
            for job in top_jobs
        ]

        return {
            "latest_run_id": latest_run.id,
            "run_status": latest_run.status.value if hasattr(latest_run.status, 'value') else str(latest_run.status),
            "jobs_found": latest_run.jobs_found,
            "jobs_scored": latest_run.jobs_scored,
            "jobs_above_threshold": latest_run.jobs_above_threshold,
            "total_jobs_in_db": total_jobs,
            "jobs_by_source": jobs_by_source,
            "jobs_by_status": jobs_by_status,
            "score_distribution": score_distribution,
            "min_score": config.get_thresholds().get("min_relevance_score", 5.0),
            "auto_approval_threshold": config.get_thresholds().get("auto_approval_threshold", 8.0),
        }
    except Exception as e:
        logger.error(f"Error getting scraping stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoints
@app.get("/analytics/applications")
async def get_application_analytics(db: Session = Depends(get_db)):
    """Get application analytics and success rates."""
    try:
        from sqlalchemy import func, case
        from datetime import datetime, timedelta
        
        # Total applications
        total_applied = db.query(func.count(Job.id)).filter(
            Job.status.in_([JobStatus.APPLICATION_COMPLETED, JobStatus.APPLICATION_FAILED, JobStatus.APPLICATION_STARTED])
        ).scalar() or 0
        
        # Successful applications
        successful = db.query(func.count(Job.id)).filter(
            Job.status == JobStatus.APPLICATION_COMPLETED
        ).scalar() or 0
        
        # Failed applications
        failed = db.query(func.count(Job.id)).filter(
            Job.status == JobStatus.APPLICATION_FAILED
        ).scalar() or 0
        
        # In progress
        in_progress = db.query(func.count(Job.id)).filter(
            Job.status == JobStatus.APPLICATION_STARTED
        ).scalar() or 0
        
        # Success rate
        success_rate = (successful / total_applied * 100) if total_applied > 0 else 0
        
        # Applications by source
        apps_by_source = db.query(
            Job.source,
            func.count(Job.id).label('count'),
            func.sum(case((Job.status == JobStatus.APPLICATION_COMPLETED, 1), else_=0)).label('successful')
        ).filter(
            Job.status.in_([JobStatus.APPLICATION_COMPLETED, JobStatus.APPLICATION_FAILED])
        ).group_by(Job.source).all()
        
        source_stats = {}
        for source, count, successful_count in apps_by_source:
            source_stats[source.value if hasattr(source, 'value') else str(source)] = {
                "total": count,
                "successful": successful_count or 0,
                "failed": count - (successful_count or 0),
                "success_rate": ((successful_count or 0) / count * 100) if count > 0 else 0
            }
        
        # Recent activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_applied = db.query(func.count(Job.id)).filter(
            Job.application_started_at >= seven_days_ago
        ).scalar() or 0
        
        recent_successful = db.query(func.count(Job.id)).filter(
            Job.status == JobStatus.APPLICATION_COMPLETED,
            Job.application_completed_at >= seven_days_ago
        ).scalar() or 0
        
        # Average time to apply (for completed applications)
        avg_time_query = db.query(
            func.avg(
                func.extract('epoch', Job.application_completed_at - Job.application_started_at)
            )
        ).filter(
            Job.status == JobStatus.APPLICATION_COMPLETED,
            Job.application_started_at.isnot(None),
            Job.application_completed_at.isnot(None)
        ).scalar()
        
        avg_apply_time_seconds = avg_time_query if avg_time_query else None
        
        return {
            "total_applied": total_applied,
            "successful": successful,
            "failed": failed,
            "in_progress": in_progress,
            "success_rate": round(success_rate, 2),
            "by_source": source_stats,
            "recent_7_days": {
                "total": recent_applied,
                "successful": recent_successful,
                "success_rate": round((recent_successful / recent_applied * 100) if recent_applied > 0 else 0, 2)
            },
            "average_apply_time_seconds": round(avg_apply_time_seconds, 2) if avg_apply_time_seconds else None
        }
    except Exception as e:
        logger.error(f"Error getting application analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Config endpoints
@app.get("/config")
async def get_config():
    """Get current configuration."""
    config_path = Path("config.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f) or {}
    else:
        yaml_config = {}
    
    return {
        "search": yaml_config.get("search", {}),
        "scoring": yaml_config.get("scoring", {}),
        "thresholds": yaml_config.get("thresholds", {}),
        "content_prompts": yaml_config.get("content_prompts", {}),
        "job_sources": yaml_config.get("job_sources", {}),
    }


@app.put("/config")
async def update_config(
    config_update: ConfigUpdate,
    _: bool = Depends(verify_api_key),
):
    """Update configuration. Requires API key when enabled."""
    config_path = Path("config.yaml")

    # Load existing config
    if config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f) or {}
    else:
        yaml_config = {}

    # Update sections
    if config_update.search:
        yaml_config["search"] = {**yaml_config.get("search", {}), **config_update.search}
    if config_update.scoring:
        yaml_config["scoring"] = {**yaml_config.get("scoring", {}), **config_update.scoring}
    if config_update.thresholds:
        yaml_config["thresholds"] = {**yaml_config.get("thresholds", {}), **config_update.thresholds}
    if config_update.content_prompts:
        yaml_config["content_prompts"] = {**yaml_config.get("content_prompts", {}), **config_update.content_prompts}
    if config_update.job_sources:
        yaml_config["job_sources"] = {**yaml_config.get("job_sources", {}), **config_update.job_sources}

    # Save config
    with open(config_path, "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

    return {"status": "updated", "config": yaml_config}


# Application Defaults endpoints
@app.get("/application-defaults")
async def get_application_defaults():
    """Get application defaults from config.

    These are the default values used when user profile fields are not set.
    Users can override these by updating their profile.
    """
    return config.get_application_defaults()


@app.put("/application-defaults")
async def update_application_defaults(
    defaults: Dict[str, Any],
    _: bool = Depends(verify_api_key),
):
    """Update application defaults in config.yaml. Requires API key when enabled.

    These defaults apply to all users who haven't set their own preferences.
    """
    config_path = Path("config.yaml")

    if config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f) or {}
    else:
        yaml_config = {}

    # Merge new defaults with existing
    existing_defaults = yaml_config.get("application_defaults", {})
    for key, value in defaults.items():
        if isinstance(value, dict) and key in existing_defaults and isinstance(existing_defaults[key], dict):
            existing_defaults[key].update(value)
        else:
            existing_defaults[key] = value

    yaml_config["application_defaults"] = existing_defaults

    with open(config_path, "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

    # Reload config with thread-safe lock
    with _config_lock:
        global config
        from app.config import Config
        config = Config()

    return {"status": "updated", "application_defaults": yaml_config["application_defaults"]}


# Rate limit status endpoint
@app.get("/rate-limit/status")
async def get_rate_limit_status(
    request: Request,
    db: Session = Depends(get_db),
):
    """Get current rate limit status for the requesting client."""
    limiter = RateLimiter(db)
    client_id = limiter._get_client_id(request)
    status = limiter.get_status(client_id)

    return {
        "client_id": client_id,
        "limits": status,
    }


# Metrics endpoint
@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get pipeline metrics."""
    total_runs = db.query(Run).count()
    total_jobs = db.query(Job).count()
    approved_jobs = db.query(Job).filter(Job.approved == True).count()
    applied_jobs = db.query(Job).filter(Job.status == JobStatus.APPLICATION_COMPLETED).count()
    
    return {
        "total_runs": total_runs,
        "total_jobs": total_jobs,
        "approved_jobs": approved_jobs,
        "applied_jobs": applied_jobs,
    }


# =============================================================================
# Auto-Apply Endpoints
# =============================================================================

class AutoApplyRequest(BaseModel):
    """Request model for auto-apply actions."""
    job_ids: Optional[List[int]] = Field(
        None,
        description="Specific job IDs to queue",
        max_length=100,  # Prevent OOM from huge arrays
    )
    min_score: Optional[float] = Field(
        None,
        description="Minimum relevance score threshold",
        ge=0.0,
        le=10.0,
    )
    batch_size: Optional[int] = Field(
        5,
        description="Number of jobs to process in batch",
        ge=1,
        le=20,
    )
    run_id: Optional[int] = Field(None, ge=1)


@app.get("/auto-apply/status")
async def get_auto_apply_status(db: Session = Depends(get_db)):
    """Get current auto-apply service status."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        return service.get_status()
    except Exception as e:
        logger.error(f"Error getting auto-apply status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/enable")
async def enable_auto_apply(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Enable the auto-apply feature. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)
        service.enable()

        return {"status": "enabled", "message": "Auto-apply feature enabled"}
    except Exception as e:
        logger.error(f"Error enabling auto-apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/disable")
async def disable_auto_apply(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Disable the auto-apply feature. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)
        service.disable()

        return {"status": "disabled", "message": "Auto-apply feature disabled"}
    except Exception as e:
        logger.error(f"Error disabling auto-apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/queue")
async def queue_jobs_for_application(
    request: AutoApplyRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Queue jobs for automatic application. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        if request.job_ids:
            # Queue specific jobs
            jobs = db.query(Job).filter(Job.id.in_(request.job_ids)).all()
            added = service.queue_manager.add_jobs(jobs)
        elif request.min_score:
            # Queue jobs above score threshold
            added = service.queue_high_score_jobs(request.min_score)
        elif request.run_id:
            # Queue all approved jobs from a run
            added = service.queue_approved_jobs(request.run_id)
        else:
            # Queue all approved jobs
            added = service.queue_approved_jobs()

        return {
            "status": "queued",
            "jobs_added": added,
            "queue_size": service.queue_manager.get_queue_status()["queue_size"],
        }
    except Exception as e:
        logger.error(f"Error queueing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/process-batch")
async def process_application_batch(
    request: AutoApplyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Process a batch of queued applications. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        if not service.enabled:
            raise HTTPException(status_code=400, detail="Auto-apply is disabled")

        batch_size = request.batch_size or 5

        # Process in background
        def process():
            results = service.process_batch(batch_size)
            logger.info(f"Batch processing complete: {len(results)} applications processed")

        background_tasks.add_task(process)

        return {
            "status": "processing",
            "batch_size": batch_size,
            "message": "Batch processing started in background",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing batch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/start")
async def start_auto_apply_processing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Start background processing of all queued applications. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        if not service.enabled:
            raise HTTPException(status_code=400, detail="Auto-apply is disabled. Enable it first.")

        service.start_background_processing()

        return {
            "status": "started",
            "message": "Background application processing started",
            "queue_size": service.queue_manager.get_queue_status()["queue_size"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting auto-apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/stop")
async def stop_auto_apply_processing(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Stop background application processing. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)
        service.stop()

        return {"status": "stopped", "message": "Auto-apply processing stopped"}
    except Exception as e:
        logger.error(f"Error stopping auto-apply: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/apply/{job_id}")
async def apply_to_single_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Apply to a specific job immediately. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        result = service.apply_to_job(job_id)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying to job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class AnswerQuestionRequest(BaseModel):
    """Request model for answering application questions."""
    question: str
    job_id: Optional[int] = None


@app.post("/auto-apply/answer-question")
async def generate_question_answer(
    request: AnswerQuestionRequest,
    db: Session = Depends(get_db)
):
    """Generate an answer for a common application question."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)

        answer = service.generate_answer(request.question, request.job_id)

        return {
            "question": request.question,
            "answer": answer,
            "matched": answer is not None,
        }
    except Exception as e:
        logger.error(f"Error generating answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auto-apply/clear-queue")
async def clear_application_queue(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_api_key),
):
    """Clear the application queue. Requires API key when enabled."""
    try:
        from app.services.auto_apply_service import AutoApplyService
        from app.agents.log_agent import LogAgent

        log_agent = LogAgent(db)
        service = AutoApplyService(db, log_agent)
        service.queue_manager.clear()

        return {"status": "cleared", "message": "Application queue cleared"}
    except Exception as e:
        logger.error(f"Error clearing queue: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import os
    import uvicorn

    # Environment detection
    env = os.getenv("ENVIRONMENT", "development").lower()
    is_production = env in ("production", "prod")

    if is_production:
        # Production settings - NEVER use reload in production
        logger.warning("Starting in PRODUCTION mode")
        if config.api.host == "0.0.0.0":
            logger.warning(
                "Server binding to 0.0.0.0 - ensure this is behind a reverse proxy with HTTPS"
            )
        uvicorn.run(
            "app.api.main:app",
            host=config.api.host,
            port=config.api.port,
            reload=False,
            workers=int(os.getenv("WORKERS", "1")),
            log_level="info",
        )
    else:
        # Development settings
        logger.info("Starting in DEVELOPMENT mode (reload enabled)")
        uvicorn.run(
            "app.api.main:app",
            host=config.api.host,
            port=config.api.port,
            reload=True,
            log_level="debug",
        )
