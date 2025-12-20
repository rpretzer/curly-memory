"""Agent for structured logging of pipeline activities."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import AgentLog, Run, Job

logger = logging.getLogger(__name__)


class LogAgent:
    """Agent responsible for structured logging."""
    
    def __init__(self, db: Session):
        """
        Initialize the log agent.
        
        Args:
            db: Database session
        """
        self.db = db
        self.agent_name = "LogAgent"
    
    def log(
        self,
        agent_name: str,
        status: str,
        message: str,
        run_id: Optional[int] = None,
        job_id: Optional[int] = None,
        step: Optional[str] = None,
        reasoning: Optional[str] = None,
        error_message: Optional[str] = None,
        error_stack: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        llm_model: Optional[str] = None,
        llm_tokens_used: Optional[int] = None,
        llm_temperature: Optional[float] = None,
    ) -> AgentLog:
        """
        Create a structured log entry.
        
        Args:
            agent_name: Name of the agent performing the action
            status: Status (success, error, warning, info)
            message: Log message
            run_id: Optional run ID
            job_id: Optional job ID
            step: Optional step name
            reasoning: Optional agent reasoning
            error_message: Optional error message
            error_stack: Optional error stack trace
            metadata: Optional metadata dictionary
            llm_model: Optional LLM model used
            llm_tokens_used: Optional token count
            llm_temperature: Optional LLM temperature
            
        Returns:
            Created AgentLog entry
        """
        log_entry = AgentLog(
            agent_name=agent_name,
            step=step,
            status=status,
            message=message,
            error_message=error_message,
            error_stack=error_stack,
            reasoning=reasoning,
            extra_metadata=metadata or {},
            llm_model=llm_model,
            llm_tokens_used=llm_tokens_used,
            llm_temperature=llm_temperature,
            run_id=run_id,
            job_id=job_id,
        )
        
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        # Also log to Python logging
        log_level = {
            "success": logging.INFO,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "info": logging.INFO,
        }.get(status, logging.INFO)
        
        logger.log(
            log_level,
            f"[{agent_name}] {message}",
            extra={
                "run_id": run_id,
                "job_id": job_id,
                "step": step,
            }
        )
        
        return log_entry
    
    def log_search_start(self, run_id: int, search_params: Dict[str, Any]) -> AgentLog:
        """Log the start of a search operation."""
        return self.log(
            agent_name="SearchAgent",
            status="info",
            message=f"Starting job search with params: {search_params}",
            run_id=run_id,
            step="search_start",
            metadata=search_params,
        )
    
    def log_search_complete(
        self,
        run_id: int,
        jobs_found: int,
        sources_searched: list
    ) -> AgentLog:
        """Log the completion of a search operation."""
        return self.log(
            agent_name="SearchAgent",
            status="success",
            message=f"Search complete: {jobs_found} jobs found from {len(sources_searched)} sources",
            run_id=run_id,
            step="search_complete",
            metadata={
                "jobs_found": jobs_found,
                "sources_searched": sources_searched,
            },
        )
    
    def log_scoring(
        self,
        run_id: int,
        job_id: int,
        score: float,
        breakdown: Dict[str, Any],
        reasoning: Optional[str] = None
    ) -> AgentLog:
        """Log a job scoring event."""
        return self.log(
            agent_name="FilterAndScoreAgent",
            status="success",
            message=f"Job scored: {score:.2f}",
            run_id=run_id,
            job_id=job_id,
            step="score",
            reasoning=reasoning,
            metadata={
                "score": score,
                "breakdown": breakdown,
            },
        )
    
    def log_content_generation(
        self,
        run_id: int,
        job_id: int,
        content_type: str,
        llm_model: str,
        tokens_used: int,
        reasoning: Optional[str] = None
    ) -> AgentLog:
        """Log content generation event."""
        return self.log(
            agent_name="ContentGenerationAgent",
            status="success",
            message=f"Generated {content_type} for job",
            run_id=run_id,
            job_id=job_id,
            step=f"generate_{content_type}",
            reasoning=reasoning,
            llm_model=llm_model,
            llm_tokens_used=tokens_used,
            metadata={"content_type": content_type},
        )
    
    def log_application_start(
        self,
        run_id: int,
        job_id: int,
        application_type: str
    ) -> AgentLog:
        """Log the start of an application."""
        return self.log(
            agent_name="ApplyAgent",
            status="info",
            message=f"Starting application via {application_type}",
            run_id=run_id,
            job_id=job_id,
            step="application_start",
            metadata={"application_type": application_type},
        )
    
    def log_application_complete(
        self,
        run_id: int,
        job_id: int,
        success: bool,
        error_message: Optional[str] = None
    ) -> AgentLog:
        """Log the completion of an application."""
        status = "success" if success else "error"
        message = "Application completed successfully" if success else f"Application failed: {error_message}"
        
        return self.log(
            agent_name="ApplyAgent",
            status=status,
            message=message,
            run_id=run_id,
            job_id=job_id,
            step="application_complete",
            error_message=error_message if not success else None,
        )
    
    def log_error(
        self,
        agent_name: str,
        error: Exception,
        run_id: Optional[int] = None,
        job_id: Optional[int] = None,
        step: Optional[str] = None,
    ) -> AgentLog:
        """Log an error with full stack trace."""
        import traceback
        
        return self.log(
            agent_name=agent_name,
            status="error",
            message=f"Error in {agent_name}: {str(error)}",
            run_id=run_id,
            job_id=job_id,
            step=step,
            error_message=str(error),
            error_stack=traceback.format_exc(),
        )
