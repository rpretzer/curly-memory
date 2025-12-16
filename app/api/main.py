"""FastAPI main application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime

from app.db import get_db, init_db
from app.models import Run, Job, JobStatus, RunStatus
from app.orchestrator import PipelineOrchestrator
from app.config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Background task storage
active_runs: Dict[int, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down...")


app = FastAPI(
    title="Agentic Job Search Pipeline API",
    description="API for automated job search and application pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
origins = config.api.cors_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for requests/responses
class SearchRequest(BaseModel):
    titles: List[str] = Field(..., description="Job titles to search for")
    locations: Optional[List[str]] = Field(None, description="Location filters")
    remote: bool = Field(False, description="Remote filter")
    keywords: Optional[List[str]] = Field(None, description="Keywords")
    sources: Optional[List[str]] = Field(None, description="Job sources to search")
    max_results: int = Field(50, description="Max results per source")


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
    target_companies: Optional[List[str]] = None
    must_have_keywords: Optional[List[str]] = None
    nice_to_have_keywords: Optional[List[str]] = None
    remote_preference: str = Field("any", description="remote, hybrid, on-site, any")
    salary_min: Optional[int] = None
    scoring_weights: Optional[ScoringWeights] = None
    llm_config: Optional[Dict[str, Any]] = None
    generate_content: bool = True
    auto_apply: bool = False


class RunResponse(BaseModel):
    run_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    jobs_found: int = 0
    jobs_scored: int = 0
    jobs_above_threshold: int = 0
    jobs_applied: int = 0
    jobs_failed: int = 0


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: Optional[str]
    source: str
    source_url: str
    relevance_score: Optional[float]
    status: str
    approved: bool
    created_at: datetime

    class Config:
        from_attributes = True


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Agentic Job Search Pipeline API", "version": "0.1.0"}


@app.post("/runs", response_model=RunResponse)
async def create_run(
    request: RunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create and start a new pipeline run."""
    try:
        orchestrator = PipelineOrchestrator(db)
        
        # Create run
        run = orchestrator.create_run(
            search_config=request.search.dict(),
            scoring_config=request.scoring_weights.dict() if request.scoring_weights else {},
            llm_config=request.llm_config or {},
        )
        
        # Store run info
        active_runs[run.id] = {
            "status": run.status.value,
            "orchestrator": orchestrator,
        }
        
        # Run pipeline in background
        background_tasks.add_task(
            _run_pipeline_async,
            orchestrator,
            run.id,
            request,
        )
        
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


async def _run_pipeline_async(
    orchestrator: PipelineOrchestrator,
    run_id: int,
    request: RunRequest,
):
    """Run pipeline asynchronously."""
    try:
        orchestrator.run_full_pipeline(
            run_id=run_id,
            titles=request.search.titles,
            locations=request.search.locations,
            remote=request.search.remote,
            keywords=request.search.keywords,
            sources=request.search.sources,
            max_results=request.search.max_results,
            target_companies=request.target_companies,
            must_have_keywords=request.must_have_keywords,
            nice_to_have_keywords=request.nice_to_have_keywords,
            remote_preference=request.remote_preference,
            salary_min=request.salary_min,
            generate_content=request.generate_content,
            auto_apply=request.auto_apply,
        )
    except Exception as e:
        logger.error(f"Error running pipeline for run {run_id}: {e}", exc_info=True)


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get run status."""
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
        jobs_applied=run.jobs_applied,
        jobs_failed=run.jobs_failed,
    )


@app.get("/runs", response_model=List[RunResponse])
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List all runs."""
    runs = db.query(Run).order_by(Run.started_at.desc()).offset(offset).limit(limit).all()
    return [
        RunResponse(
            run_id=run.id,
            status=run.status.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            jobs_found=run.jobs_found,
            jobs_scored=run.jobs_scored,
            jobs_above_threshold=run.jobs_above_threshold,
            jobs_applied=run.jobs_applied,
            jobs_failed=run.jobs_failed,
        )
        for run in runs
    ]


@app.get("/runs/{run_id}/jobs", response_model=List[JobResponse])
async def get_run_jobs(
    run_id: int,
    min_score: Optional[float] = None,
    approved_only: bool = False,
    db: Session = Depends(get_db),
):
    """Get jobs from a run."""
    query = db.query(Job).filter(Job.run_id == run_id)
    
    if min_score is not None:
        query = query.filter(Job.relevance_score >= min_score)
    
    if approved_only:
        query = query.filter(Job.approved == True)
    
    jobs = query.order_by(Job.relevance_score.desc().nullslast()).all()
    
    return [
        JobResponse(
            id=job.id,
            title=job.title,
            company=job.company,
            location=job.location,
            source=job.source.value,
            source_url=job.source_url,
            relevance_score=job.relevance_score,
            status=job.status.value,
            approved=job.approved,
            created_at=job.created_at,
        )
        for job in jobs
    ]


@app.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get job details."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source.value,
        "source_url": job.source_url,
        "description": job.description,
        "qualifications": job.qualifications,
        "keywords": job.keywords,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "relevance_score": job.relevance_score,
        "scoring_breakdown": job.scoring_breakdown,
        "status": job.status.value,
        "approved": job.approved,
        "llm_summary": job.llm_summary,
        "tailored_resume_points": job.tailored_resume_points,
        "cover_letter_draft": job.cover_letter_draft,
        "application_answers": job.application_answers,
        "created_at": job.created_at.isoformat(),
    }


@app.post("/jobs/{job_id}/approve")
async def approve_job(job_id: int, db: Session = Depends(get_db)):
    """Approve a job for application."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.approved = True
    db.commit()
    
    return {"message": "Job approved", "job_id": job_id}


@app.post("/jobs/{job_id}/reject")
async def reject_job(
    job_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Reject a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.approved = False
    job.rejection_reason = reason
    job.status = JobStatus.REJECTED
    db.commit()
    
    return {"message": "Job rejected", "job_id": job_id}


@app.post("/jobs/{job_id}/generate-content")
async def generate_content_for_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Generate content for a specific job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    orchestrator = PipelineOrchestrator(db)
    
    background_tasks.add_task(
        orchestrator.content_agent.generate_all_content,
        job,
        run_id=job.run_id,
    )
    
    return {"message": "Content generation started", "job_id": job_id}


@app.post("/jobs/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Apply to a job."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.approved:
        raise HTTPException(status_code=400, detail="Job must be approved before applying")
    
    orchestrator = PipelineOrchestrator(db)
    
    background_tasks.add_task(
        orchestrator.apply_agent.apply_to_job,
        job,
        run_id=job.run_id,
        human_approval_required=True,
    )
    
    return {"message": "Application started", "job_id": job_id}


@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get pipeline metrics."""
    from sqlalchemy import func
    
    total_runs = db.query(func.count(Run.id)).scalar()
    total_jobs = db.query(func.count(Job.id)).scalar()
    avg_score = db.query(func.avg(Job.relevance_score)).filter(
        Job.relevance_score.isnot(None)
    ).scalar()
    
    applied_jobs = db.query(func.count(Job.id)).filter(
        Job.status == JobStatus.APPLICATION_COMPLETED
    ).scalar()
    
    return {
        "total_runs": total_runs or 0,
        "total_jobs": total_jobs or 0,
        "average_score": float(avg_score) if avg_score else 0.0,
        "jobs_applied": applied_jobs or 0,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True,
    )
