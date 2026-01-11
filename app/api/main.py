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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")
    
    # Start scheduler if enabled
    try:
        from app.scheduling import get_scheduler
        scheduler_config = config.get_scheduler_config()
        if scheduler_config.get("enabled", True):
            scheduler = get_scheduler()
            scheduler.start()
            logger.info("Scheduler started")
    except Exception as e:
        logger.warning(f"Could not start scheduler: {e}")
    
    yield
    # Shutdown
    logger.info("Shutting down...")
    try:
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler.stop()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping scheduler: {e}")


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
    job_sources: Optional[Dict[str, Any]] = None


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
            """Run pipeline in background with new database session."""
            logger.info(f"Background task starting for run {run_id}")
            try:
                # Use a new database session for background task
                from app.db import get_db
                from app.models import Run as RunModel, RunStatus
                
                db_gen = get_db()
                db = next(db_gen)
                try:
                    logger.info(f"Background task: Database session created for run {run_id}")
                    
                    # Create a new orchestrator with the new session
                    bg_orchestrator = PipelineOrchestrator(db)
                    logger.info(f"Background task: Orchestrator created for run {run_id}")
                    
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
                    logger.error(f"Error in pipeline run {run_id}: {pipeline_err}", exc_info=True)
                    # Update run status to failed
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
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Fatal error in background pipeline task for run {run_id}: {e}", exc_info=True)
                # Try to update status even if database session failed
                try:
                    from app.db import get_db
                    from app.models import Run as RunModel, RunStatus
                    db_gen = get_db()
                    db = next(db_gen)
                    try:
                        bg_run = db.query(RunModel).filter(RunModel.id == run_id).first()
                        if bg_run:
                            bg_run.status = RunStatus.FAILED
                            bg_run.error_message = f"Fatal error: {str(e)}"
                            bg_run.completed_at = datetime.utcnow()
                            db.commit()
                    finally:
                        db.close()
                except Exception:
                    pass  # Can't do anything if we can't update the database
        
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
    from app.models import JobStatus
    
    log_agent = LogAgent(db)
    content_agent = ContentGenerationAgent(db, log_agent=log_agent)
    
    async def generate():
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
    db: Session = Depends(get_db)
):
    """Apply to a job (requires approval). Set dry_run=True to simulate without actually applying."""
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
    """Upload and parse resume document (supports PDF, DOCX, DOC, TXT)."""
    try:
        import os
        from pathlib import Path
        
        # Read file content
        content = await file.read()
        filename = file.filename.lower() if file.filename else ""
        
        # Extract text based on file type
        text_content = ""
        if filename.endswith('.pdf'):
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
                logger.warning("PyPDF2 not installed, falling back to text extraction")
                text_content = content.decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Error parsing PDF: {e}, falling back to text extraction")
                text_content = content.decode('utf-8', errors='ignore')
        elif filename.endswith(('.docx', '.doc')):
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
                logger.warning("python-docx not installed, falling back to text extraction")
                text_content = content.decode('utf-8', errors='ignore')
            except Exception as e:
                logger.warning(f"Error parsing DOCX: {e}, falling back to text extraction")
                text_content = content.decode('utf-8', errors='ignore')
        else:
            # Plain text file
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
async def start_scheduler():
    """Start the scheduler."""
    try:
        from app.scheduling import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()
        return {"status": "started", "message": "Scheduler started successfully"}
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the scheduler."""
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
    run_at_time: Optional[str] = None
):
    """Update scheduler configuration."""
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
@app.post("/linkedin/validate-credentials")
async def validate_linkedin_credentials(
    email: str,
    password: str,
    db: Session = Depends(get_db)
):
    """Validate LinkedIn credentials by attempting to log in."""
    try:
        from app.agents.search_agent import SearchAgent
        from app.agents.log_agent import LogAgent
        from playwright.async_api import async_playwright
        import asyncio
        
        log_agent = LogAgent(db)
        search_agent = SearchAgent(db, log_agent=log_agent)
        
        if 'linkedin' not in search_agent.sources:
            raise HTTPException(status_code=400, detail="LinkedIn source not enabled")
        
        # Test login with provided credentials
        logger.info(f"Validating LinkedIn credentials for: {email}")
        
        try:
            async with async_playwright() as playwright:
                # Launch browser with stealth settings (headless=False helps avoid detection)
                browser = await playwright.chromium.launch(
                    headless=False,  # Visible browser is less likely to trigger CAPTCHA
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
                    // Remove webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Chrome runtime
                    window.chrome = {
                        runtime: {}
                    };
                    
                    // Permissions
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                page = await context.new_page()
                
                try:
                    # Navigate to login page
                    await page.goto("https://www.linkedin.com/login", wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(3)  # Slightly longer wait
                    
                    # Enter email
                    email_input = await page.query_selector('input[name="session_key"]')
                    if not email_input:
                        await context.close()
                        await browser.close()
                        return {
                            "valid": False,
                            "error": "Could not find email input field on LinkedIn login page"
                        }
                    await email_input.fill(email)
                    await asyncio.sleep(1)
                    
                    # Enter password
                    password_input = await page.query_selector('input[name="session_password"]')
                    if not password_input:
                        await context.close()
                        await browser.close()
                        return {
                            "valid": False,
                            "error": "Could not find password input field on LinkedIn login page"
                        }
                    await password_input.fill(password)
                    await asyncio.sleep(1)
                    
                    # Click sign in button
                    sign_in_button = await page.query_selector('button[type="submit"]')
                    if sign_in_button:
                        await sign_in_button.click()
                        await asyncio.sleep(5)  # Wait for login to complete
                    
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
                        
                        # Also check for CAPTCHA
                        captcha = await page.query_selector('iframe[title*="captcha"], iframe[src*="captcha"]')
                        if captcha:
                            error_message = "LinkedIn is requesting CAPTCHA verification. Please try again later."
                    
                    await context.close()
                    await browser.close()
                    
                    if login_successful:
                        logger.info(f"LinkedIn credentials validated successfully for: {email}")
                        return {
                            "valid": True,
                            "message": "Credentials validated successfully"
                        }
                    else:
                        error_msg = error_message or "Login failed - invalid credentials or account issue"
                        logger.warning(f"LinkedIn credentials validation failed for {email}: {error_msg}")
                        return {
                            "valid": False,
                            "error": error_msg
                        }
                except Exception as e:
                    try:
                        await context.close()
                    except:
                        pass
                    try:
                        await browser.close()
                    except:
                        pass
                    raise
                
        except ImportError:
            raise HTTPException(status_code=500, detail="Playwright not installed. Install with: pip install playwright && playwright install")
        except Exception as e:
            logger.error(f"Error validating LinkedIn credentials: {e}", exc_info=True)
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }
            
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
    """Get debugging information about scraping results."""
    try:
        from app.models import Job, Run, JobStatus
        from sqlalchemy import func, desc
        
        # Get latest run
        latest_run = db.query(Run).order_by(desc(Run.id)).first()
        if not latest_run:
            return {"error": "No runs found"}
        
        # Get all jobs from latest run (before and after filtering)
        all_jobs = db.query(Job).filter(Job.run_id == latest_run.id).all()
        
        # Count jobs by source
        jobs_by_source = {}
        jobs_by_status = {}
        score_distribution = []
        
        for job in all_jobs:
            source = job.source.value if hasattr(job.source, 'value') else str(job.source)
            jobs_by_source[source] = jobs_by_source.get(source, 0) + 1
            
            status = job.status.value if hasattr(job.status, 'value') else str(job.status)
            jobs_by_status[status] = jobs_by_status.get(status, 0) + 1
            
            if job.relevance_score is not None:
                score_distribution.append({
                    "id": job.id,
                    "title": job.title,
                    "score": job.relevance_score,
                    "source": source,
                    "status": status,
                })
        
        # Sort by score
        score_distribution.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "latest_run_id": latest_run.id,
            "run_status": latest_run.status.value if hasattr(latest_run.status, 'value') else str(latest_run.status),
            "jobs_found": latest_run.jobs_found,
            "jobs_scored": latest_run.jobs_scored,
            "jobs_above_threshold": latest_run.jobs_above_threshold,
            "total_jobs_in_db": len(all_jobs),
            "jobs_by_source": jobs_by_source,
            "jobs_by_status": jobs_by_status,
            "score_distribution": score_distribution[:50],  # Top 50 by score
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
    if config_update.job_sources:
        yaml_config["job_sources"] = {**yaml_config.get("job_sources", {}), **config_update.job_sources}
    
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
