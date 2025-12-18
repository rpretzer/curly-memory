"""FastAPI main application."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import asyncio
from datetime import datetime
import yaml
from pathlib import Path

from app.db import get_db, init_db
from app.models import Run, Job, JobStatus, RunStatus, UserProfile
from app.orchestrator import PipelineOrchestrator
from app.config import config
from app.user_profile import get_user_profile, create_default_profile

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


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    github_url: Optional[str] = None
    current_title: Optional[str] = None
    target_titles: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    experience_summary: Optional[str] = None
    resume_text: Optional[str] = None
    target_companies: Optional[List[str]] = None
    must_have_keywords: Optional[List[str]] = None
    nice_to_have_keywords: Optional[List[str]] = None


class ConfigUpdate(BaseModel):
    search: Optional[Dict[str, Any]] = None
    scoring: Optional[Dict[str, Any]] = None
    thresholds: Optional[Dict[str, Any]] = None
    content_prompts: Optional[Dict[str, str]] = None


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Run endpoints
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
            search_config={
                "titles": request.search.titles,
                "locations": request.search.locations,
            },
            scoring_config=request.scoring_weights.dict() if request.scoring_weights else {},
            llm_config=request.llm_config or {},
        )
        
        # Start pipeline in background
        async def run_pipeline():
            try:
                result = orchestrator.run_full_pipeline(
                    run_id=run.id,
                    titles=request.search.titles,
                    locations=request.search.locations or [],
                    remote=request.search.remote,
                    keywords=request.search.keywords,
                    sources=request.search.sources,
                    max_results=request.search.max_results,
                    target_companies=request.target_companies or [],
                    must_have_keywords=request.must_have_keywords or [],
                    nice_to_have_keywords=request.nice_to_have_keywords or [],
                    remote_preference=request.remote_preference,
                    salary_min=request.salary_min,
                    generate_content=request.generate_content,
                    auto_apply=request.auto_apply,
                )
                logger.info(f"Pipeline run {run.id} completed: {result}")
            except Exception as e:
                logger.error(f"Error in pipeline run {run.id}: {e}", exc_info=True)
                run.status = RunStatus.FAILED
                db.commit()
        
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
async def list_runs(db: Session = Depends(get_db)):
    """List all pipeline runs."""
    runs = db.query(Run).order_by(Run.started_at.desc()).limit(100).all()
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
        jobs_applied=run.jobs_applied,
        jobs_failed=run.jobs_failed,
    )


@app.get("/runs/{run_id}/jobs")
async def get_run_jobs(run_id: int, db: Session = Depends(get_db)):
    """Get all jobs from a specific run."""
    jobs = db.query(Job).filter(Job.run_id == run_id).order_by(Job.relevance_score.desc().nullslast()).all()
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
        }
        for job in jobs
    ]


# Job endpoints
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
async def approve_job(job_id: int, db: Session = Depends(get_db)):
    """Approve a job for application."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.approved = True
    db.commit()
    return {"status": "approved", "job_id": job_id}


@app.post("/jobs/{job_id}/generate-content")
async def generate_content(job_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate content for a job (summary, resume points, cover letter)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    from app.agents.content_agent import ContentGenerationAgent
    from app.agents.log_agent import LogAgent
    
    log_agent = LogAgent(db)
    content_agent = ContentGenerationAgent(db, log_agent=log_agent)
    
    async def generate():
        try:
            content_agent.generate_all_content(job, run_id=job.run_id)
        except Exception as e:
            logger.error(f"Error generating content: {e}", exc_info=True)
    
    background_tasks.add_task(generate)
    return {"status": "generating", "job_id": job_id}


@app.post("/jobs/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Apply to a job (requires approval)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.approved:
        raise HTTPException(status_code=400, detail="Job must be approved before applying")
    
    if job.status == JobStatus.APPLICATION_COMPLETED:
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
                max_retries=2
            )
            if success:
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
        "message": "Application process started. Check job status for updates."
    }


# User Profile endpoints
@app.get("/profile")
async def get_profile(db: Session = Depends(get_db)):
    """Get user profile."""
    profile = get_user_profile(db, profile_id=1)
    if not profile:
        # Create default profile
        profile = create_default_profile(
            name="Default User",
            email=None,
            current_title="Product Manager",
            target_titles=["Product Manager", "Senior Product Manager"],
            skills=["Product Management", "Agile", "Data Analysis"],
        )
        db.refresh(profile)
    
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "location": profile.location,
        "linkedin_url": profile.linkedin_url,
        "portfolio_url": profile.portfolio_url,
        "github_url": profile.github_url,
        "current_title": profile.current_title,
        "target_titles": profile.target_titles or [],
        "skills": profile.skills or [],
        "experience_summary": profile.experience_summary,
        "resume_text": profile.resume_text,
        "resume_bullet_points": profile.resume_bullet_points or [],
        "target_companies": profile.target_companies or [],
        "must_have_keywords": profile.must_have_keywords or [],
        "nice_to_have_keywords": profile.nice_to_have_keywords or [],
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


@app.put("/profile")
async def update_profile(update: UserProfileUpdate, db: Session = Depends(get_db)):
    """Update user profile."""
    profile = get_user_profile(db, profile_id=1)
    if not profile:
        profile = UserProfile(name=update.name or "Default User")
        db.add(profile)
    
    # Update fields
    update_dict = update.dict(exclude_unset=True)
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
        "portfolio_url": profile.portfolio_url,
        "github_url": profile.github_url,
        "current_title": profile.current_title,
        "target_titles": profile.target_titles or [],
        "skills": profile.skills or [],
        "experience_summary": profile.experience_summary,
        "resume_text": profile.resume_text,
        "resume_bullet_points": profile.resume_bullet_points or [],
        "target_companies": profile.target_companies or [],
        "must_have_keywords": profile.must_have_keywords or [],
        "nice_to_have_keywords": profile.nice_to_have_keywords or [],
    }


@app.post("/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload and parse resume document."""
    try:
        import os
        from pathlib import Path
        
        # Read file content
        content = await file.read()
        text_content = content.decode('utf-8', errors='ignore')
        
        # Store resume file for use in applications
        resume_dir = Path("resumes")
        resume_dir.mkdir(exist_ok=True)
        resume_path = resume_dir / f"resume_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        
        with open(resume_path, "wb") as f:
            f.write(content)
        
        # Update profile with resume text and path
        profile = get_user_profile(db, profile_id=1)
        if not profile:
            profile = UserProfile(name="Default User")
            db.add(profile)
        
        profile.resume_text = text_content
        profile.updated_at = datetime.utcnow()
        
        # Store resume path in profile metadata if available
        # For now, we'll store it in a known location
        db.commit()
        db.refresh(profile)
        
        return {
            "status": "success",
            "filename": file.filename,
            "size": len(content),
            "resume_text_length": len(text_content),
            "resume_path": str(resume_path),
        }
    except Exception as e:
        logger.error(f"Error uploading resume: {e}", exc_info=True)
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
    }


@app.put("/config")
async def update_config(config_update: ConfigUpdate):
    """Update configuration."""
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
    
    # Save config
    with open(config_path, "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)
    
    return {"status": "updated", "config": yaml_config}


# Metrics endpoint
@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get pipeline metrics."""
    total_runs = db.query(Run).count()
    total_jobs = db.query(Job).count()
    approved_jobs = db.query(Job).filter(Job.approved == True).count()
    applied_jobs = db.query(Job).filter(Job.status == JobStatus.APPLIED).count()
    
    return {
        "total_runs": total_runs,
        "total_jobs": total_jobs,
        "approved_jobs": approved_jobs,
        "applied_jobs": applied_jobs,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True,
    )
