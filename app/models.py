"""SQLAlchemy models for the job search pipeline database."""

from datetime import datetime
from typing import Optional
import hashlib
import re
from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean,
    DateTime, ForeignKey, JSON, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum


def normalize_text(text: str) -> str:
    """Normalize text for consistent comparison."""
    if not text:
        return ""
    # Lowercase, remove extra whitespace, remove special chars
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def compute_content_hash(title: str, company: str, location: str = "") -> str:
    """
    Compute a hash from normalized job content for deduplication.

    This enables detecting duplicate jobs even when URLs differ
    (e.g., same job posted on multiple boards or with different tracking params).
    """
    normalized = f"{normalize_text(title)}|{normalize_text(company)}|{normalize_text(location)}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]

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
    MONSTER = "monster"
    GREENHOUSE = "greenhouse"
    WORKDAY = "workday"
    UNKNOWN = "unknown"


class Job(Base):
    """Job listing model."""
    
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # Job metadata
    title = Column(String(500), nullable=False, index=True)
    company = Column(String(200), nullable=False, index=True)
    location = Column(String(200), nullable=True, index=True)
    source = Column(SQLEnum(JobSource), default=JobSource.UNKNOWN, index=True)
    source_url = Column(Text, nullable=False, unique=True)
    content_hash = Column(String(32), nullable=True, index=True)  # For cross-source deduplication
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
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    
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
    extra_metadata = Column(JSON, nullable=True)  # Additional structured data
    
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
    linkedin_user = Column(String(200), nullable=True)  # LinkedIn Login Email
    linkedin_password = Column(Text, nullable=True)     # Encrypted Password
    portfolio_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    other_links = Column(JSON, nullable=True)  # Additional links (personal website, blog, etc.)

    # Professional information
    current_title = Column(String(200), nullable=True)
    target_titles = Column(JSON, nullable=True)  # List of target job titles
    skills = Column(JSON, nullable=True)  # List of skills
    experience_summary = Column(Text, nullable=True)

    # Resume content
    resume_text = Column(Text, nullable=True)  # Full resume text
    resume_bullet_points = Column(JSON, nullable=True)  # Structured bullet points
    resume_file_path = Column(String(500), nullable=True)  # Path to uploaded resume file

    # Preferences
    target_companies = Column(JSON, nullable=True)  # List of target companies
    must_have_keywords = Column(JSON, nullable=True)
    nice_to_have_keywords = Column(JSON, nullable=True)
    is_onboarded = Column(Boolean, default=False)

    # Company preferences (for RAG-based suggestions)
    preferred_industries = Column(JSON, nullable=True)  # ["fintech", "insurtech", "ai"]
    preferred_company_sizes = Column(JSON, nullable=True)  # ["startup", "mid-size"]
    preferred_company_stages = Column(JSON, nullable=True)  # ["series-b", "unicorn"]
    preferred_tech_stack = Column(JSON, nullable=True)  # ["python", "kubernetes"]

    # Application preferences (for auto-apply)
    salary_min = Column(Integer, nullable=True)  # Minimum salary expectation
    salary_max = Column(Integer, nullable=True)  # Maximum salary expectation
    work_authorization = Column(String(200), nullable=True)  # e.g., "US Citizen", "Authorized to work in US"
    visa_sponsorship_required = Column(Boolean, default=False, nullable=True)  # Whether needs visa sponsorship
    notice_period = Column(String(100), nullable=True)  # e.g., "2 weeks", "immediate", "1 month"
    relocation_preference = Column(String(200), nullable=True)  # e.g., "open", "not willing", "for right opportunity"
    remote_preference = Column(String(100), nullable=True)  # e.g., "remote only", "hybrid", "flexible"

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserProfile(id={self.id}, name='{self.name}')>"


class Company(Base):
    """Company information for RAG-based company suggestions."""

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    normalized_name = Column(String(200), nullable=False, index=True)  # For matching

    # Core attributes
    industries = Column(JSON, nullable=True)  # ["fintech", "payments", "infrastructure"]
    verticals = Column(JSON, nullable=True)   # ["financial services", "b2b saas"]
    size = Column(String(50), nullable=True)  # "startup", "mid-size", "enterprise"
    stage = Column(String(50), nullable=True)  # "series-a", "public", "unicorn"

    # Additional metadata
    tech_stack = Column(JSON, nullable=True)  # ["python", "react", "aws"]
    description = Column(Text, nullable=True)
    headquarters = Column(String(200), nullable=True)

    # Data sources
    greenhouse_token = Column(String(100), nullable=True)
    workday_slug = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Company(id={self.id}, name='{self.name}', industries={self.industries})>"


class RateLimitRecord(Base):
    """Rate limit tracking for API endpoints.

    SQLite-backed rate limiting that persists across restarts.
    """

    __tablename__ = "rate_limit_records"

    id = Column(Integer, primary_key=True, index=True)

    # Identifier for rate limiting (e.g., IP address, API key, or client_id)
    client_id = Column(String(255), nullable=False, index=True)

    # Endpoint or resource being rate limited
    endpoint = Column(String(255), nullable=False, index=True)

    # Timestamp of the request
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<RateLimitRecord(client_id='{self.client_id}', endpoint='{self.endpoint}')>"
