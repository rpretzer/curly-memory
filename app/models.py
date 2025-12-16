"""SQLAlchemy models for the job search pipeline database."""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, 
    DateTime, ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class ApplicationType(str, enum.Enum):
    """Types of job applications."""
    EASY_APPLY = "easy_apply"
    EXTERNAL = "external"
    API = "api"
    UNKNOWN = "unknown"


class JobStatus(str, enum.Enum):
    """Status of a job in the pipeline."""
    FOUND = "found"
    SCORED = "scored"
    APPROVED = "approved"
    CONTENT_GENERATED = "content_generated"
    APPLICATION_STARTED = "application_started"
    APPLICATION_COMPLETED = "application_completed"
    APPLICATION_FAILED = "application_failed"
    REJECTED = "rejected"


class RunStatus(str, enum.Enum):
    """Status of a pipeline run."""
    PENDING = "pending"
    SEARCHING = "searching"
    SCORING = "scoring"
    CONTENT_GENERATING = "content_generating"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSource(str, enum.Enum):
    """Job board sources."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    WELLFOUND = "wellfound"
    UNKNOWN = "unknown"


class Job(Base):
    """Job listing model."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True, index=True)
    
    # Job metadata
    title = Column(String(500), nullable=False, index=True)
    company = Column(String(200), nullable=False, index=True)
    location = Column(String(200), nullable=True, index=True)
    source = Column(SQLEnum(JobSource), default=JobSource.UNKNOWN, index=True)
    source_url = Column(Text, nullable=False, unique=True)
    application_type = Column(SQLEnum(ApplicationType), default=ApplicationType.UNKNOWN)
    
    # Parsed content
    description = Column(Text, nullable=True)
    raw_description = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)  # List of extracted keywords
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    posting_date = Column(DateTime, nullable=True, index=True)
    
    # Scoring
    relevance_score = Column(Float, nullable=True, index=True)
    scoring_breakdown = Column(JSON, nullable=True)  # Detailed scoring components
    
    # Status and workflow
    status = Column(SQLEnum(JobStatus), default=JobStatus.FOUND, index=True)
    approved = Column(Boolean, default=False, index=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Generated content
    llm_summary = Column(Text, nullable=True)
    tailored_resume_points = Column(JSON, nullable=True)
    cover_letter_draft = Column(Text, nullable=True)
    application_answers = Column(JSON, nullable=True)
    
    # Application tracking
    application_started_at = Column(DateTime, nullable=True)
    application_completed_at = Column(DateTime, nullable=True)
    application_error = Column(Text, nullable=True)
    application_payload = Column(JSON, nullable=True)  # What was submitted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    run = relationship("Run", back_populates="jobs")
    logs = relationship("AgentLog", back_populates="job")
    
    def __repr__(self):
        return f"<Job(id={self.id}, title='{self.title}', company='{self.company}', score={self.relevance_score})>"


class Run(Base):
    """Pipeline run model."""
    
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Run configuration snapshot
    search_config = Column(JSON, nullable=True)
    scoring_config = Column(JSON, nullable=True)
    llm_config = Column(JSON, nullable=True)
    
    # Run status
    status = Column(SQLEnum(RunStatus), default=RunStatus.PENDING, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Results summary
    jobs_found = Column(Integer, default=0)
    jobs_scored = Column(Integer, default=0)
    jobs_above_threshold = Column(Integer, default=0)
    jobs_approved = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    jobs_failed = Column(Integer, default=0)
    
    # Relationships
    jobs = relationship("Job", back_populates="run")
    logs = relationship("AgentLog", back_populates="run")
    
    def __repr__(self):
        return f"<Run(id={self.id}, status='{self.status}', jobs_found={self.jobs_found})>"


class AgentLog(Base):
    """Structured logging for agent activities."""
    
    __tablename__ = "agent_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True, index=True)
    
    # Agent identification
    agent_name = Column(String(100), nullable=False, index=True)
    step = Column(String(200), nullable=True)  # e.g., "search", "score", "generate_content"
    
    # Log content
    status = Column(String(50), nullable=False, index=True)  # success, error, warning, info
    message = Column(Text, nullable=False)
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    
    # Context
    reasoning = Column(Text, nullable=True)  # Agent's reasoning/summary
    metadata = Column(JSON, nullable=True)  # Additional structured data
    
    # LLM usage tracking
    llm_model = Column(String(100), nullable=True)
    llm_tokens_used = Column(Integer, nullable=True)
    llm_temperature = Column(Float, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    run = relationship("Run", back_populates="logs")
    job = relationship("Job", back_populates="logs")
    
    def __repr__(self):
        return f"<AgentLog(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"


class UserProfile(Base):
    """User profile and resume data for content generation."""
    
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    
    # Contact information
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(200), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    
    # Professional information
    current_title = Column(String(200), nullable=True)
    target_titles = Column(JSON, nullable=True)  # List of target job titles
    skills = Column(JSON, nullable=True)  # List of skills
    experience_summary = Column(Text, nullable=True)
    
    # Resume content
    resume_text = Column(Text, nullable=True)  # Full resume text
    resume_bullet_points = Column(JSON, nullable=True)  # Structured bullet points
    
    # Preferences
    target_companies = Column(JSON, nullable=True)  # List of target companies
    must_have_keywords = Column(JSON, nullable=True)
    nice_to_have_keywords = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserProfile(id={self.id}, name='{self.name}')>"
