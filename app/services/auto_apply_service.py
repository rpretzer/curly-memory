"""Auto-Apply Service for automated job applications."""

import logging
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, Run
from app.config import config
from app.agents.apply_agent import ApplyAgent
from app.agents.application_queue import ApplicationQueueManager, ApplicationPriority
from app.agents.application_templates import ApplicationTemplateManager
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)


class AutoApplyService:
    """
    Service for managing automated job applications.

    Features:
    - Queue-based application processing
    - Rate limiting and exponential backoff
    - Template-based answer generation
    - Integration with scheduler
    - Real-time status updates
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern for service."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db: Session,
        log_agent: Optional[LogAgent] = None,
        rate_limit_delay: float = 30.0,
        max_applications_per_hour: int = 20,
    ):
        """
        Initialize the auto-apply service.

        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
            rate_limit_delay: Seconds between applications
            max_applications_per_hour: Maximum applications per hour
        """
        # Check if this is first initialization
        first_init = not hasattr(self, '_initialized') or not self._initialized

        if first_init:
            # First time initialization - set up all components
            # Get config
            thresholds = config.get_thresholds()
            feature_flags = config.get_feature_flags()

            # Settings (only set once)
            self.auto_apply_threshold = thresholds.get("auto_approval_threshold", 8.0)
            self.enabled = feature_flags.get("enable_auto_apply", False)

            # State (only set once)
            self._processing_thread: Optional[threading.Thread] = None
            self._status_callbacks: List[Callable] = []
            self._rate_limit_delay = rate_limit_delay
            self._max_applications_per_hour = max_applications_per_hour

            self._initialized = True
            logger.info("AutoApplyService initialized")

        # Always update database session and session-dependent components
        # This ensures we don't use stale/expired sessions
        self.db = db
        self.log_agent = log_agent

        # Recreate components with fresh database session
        self.apply_agent = ApplyAgent(db, log_agent)
        self.queue_manager = ApplicationQueueManager(
            db=db,
            rate_limit_delay=getattr(self, '_rate_limit_delay', rate_limit_delay),
            max_applications_per_hour=getattr(self, '_max_applications_per_hour', max_applications_per_hour),
        )
        self.template_manager = ApplicationTemplateManager(db)

        # Set up queue callbacks
        self.queue_manager.on_application_start = self._on_application_start
        self.queue_manager.on_application_success = self._on_application_success
        self.queue_manager.on_application_failure = self._on_application_failure
        self.queue_manager.on_queue_empty = self._on_queue_empty

    def enable(self):
        """Enable auto-apply feature."""
        self.enabled = True
        logger.info("Auto-apply enabled")

    def disable(self):
        """Disable auto-apply feature."""
        self.enabled = False
        self.stop()
        logger.info("Auto-apply disabled")

    def add_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add a callback for status updates."""
        self._status_callbacks.append(callback)

    def _notify_status(self, status: Dict[str, Any]):
        """Notify all status callbacks."""
        for callback in self._status_callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def _on_application_start(self, job: Job):
        """Called when application starts."""
        self._notify_status({
            "event": "application_start",
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if self.log_agent:
            self.log_agent.log(
                agent_name="AutoApplyService",
                status="info",
                message=f"Starting application for {job.title} @ {job.company}",
                job_id=job.id,
                step="application_start",
            )

    def _on_application_success(self, job: Job):
        """Called when application succeeds."""
        self._notify_status({
            "event": "application_success",
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if self.log_agent:
            self.log_agent.log(
                agent_name="AutoApplyService",
                status="success",
                message=f"Successfully applied to {job.title} @ {job.company}",
                job_id=job.id,
                step="application_complete",
            )

    def _on_application_failure(self, job: Job, error: str):
        """Called when application fails."""
        self._notify_status({
            "event": "application_failure",
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        })

        if self.log_agent:
            self.log_agent.log_error(
                agent_name="AutoApplyService",
                error=Exception(error),
                job_id=job.id,
                step="application_failed",
            )

    def _on_queue_empty(self):
        """Called when queue is empty."""
        self._notify_status({
            "event": "queue_empty",
            "timestamp": datetime.utcnow().isoformat(),
        })

    def _apply_with_templates(self, job: Job) -> bool:
        """
        Apply to a job using templates for common questions.

        Args:
            job: Job to apply to

        Returns:
            True if successful
        """
        # Get field values for form filling
        field_values = self.template_manager.get_field_values(job=job)

        # Build application payload
        payload = {
            "name": field_values.get("full_name", ""),
            "email": field_values.get("email", ""),
            "phone": field_values.get("phone", ""),
            "linkedin_url": field_values.get("linkedin_url", ""),
            "portfolio_url": field_values.get("portfolio_url", ""),
            "cover_letter": job.cover_letter_draft or "",
            "resume_points": field_values.get("resume_bullets", ""),
        }

        # Use apply agent
        return self.apply_agent.apply_to_job(
            job=job,
            application_data=payload,
            run_id=job.run_id,
        )

    def queue_approved_jobs(self, run_id: Optional[int] = None) -> int:
        """
        Queue all approved jobs for application.

        Args:
            run_id: Optional run ID to filter jobs

        Returns:
            Number of jobs queued
        """
        query = self.db.query(Job).filter(
            Job.approved == True,
            Job.status.notin_([
                JobStatus.APPLICATION_COMPLETED,
                JobStatus.APPLIED,
                JobStatus.APPLICATION_FAILED,
            ])
        )

        if run_id:
            query = query.filter(Job.run_id == run_id)

        jobs = query.all()
        added = self.queue_manager.add_jobs(jobs)

        logger.info(f"Queued {added} jobs for application")
        return added

    def queue_high_score_jobs(self, min_score: Optional[float] = None) -> int:
        """
        Queue jobs above a certain score threshold.

        Args:
            min_score: Minimum score (uses auto_apply_threshold if not provided)

        Returns:
            Number of jobs queued
        """
        threshold = min_score or self.auto_apply_threshold

        jobs = self.db.query(Job).filter(
            Job.approved == True,
            Job.relevance_score >= threshold,
            Job.status.notin_([
                JobStatus.APPLICATION_COMPLETED,
                JobStatus.APPLIED,
                JobStatus.APPLICATION_FAILED,
            ])
        ).all()

        added = self.queue_manager.add_jobs(jobs)
        logger.info(f"Queued {added} high-score jobs (>= {threshold})")
        return added

    def process_batch(self, batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Process a batch of queued applications.

        Args:
            batch_size: Number of applications to process

        Returns:
            List of results
        """
        if not self.enabled:
            logger.warning("Auto-apply is disabled")
            return []

        return self.queue_manager.process_batch(
            apply_func=self._apply_with_templates,
            batch_size=batch_size,
        )

    def start_background_processing(self):
        """Start processing queue in background thread."""
        if not self.enabled:
            logger.warning("Auto-apply is disabled, not starting background processing")
            return

        if self._processing_thread and self._processing_thread.is_alive():
            logger.warning("Background processing already running")
            return

        def process_loop():
            logger.info("Starting background application processing")
            summary = self.queue_manager.process_all(
                apply_func=self._apply_with_templates
            )
            logger.info(f"Background processing complete: {summary}")
            self._notify_status({
                "event": "processing_complete",
                "summary": summary,
                "timestamp": datetime.utcnow().isoformat(),
            })

        self._processing_thread = threading.Thread(
            target=process_loop,
            daemon=True,
            name="AutoApplyProcessor"
        )
        self._processing_thread.start()
        logger.info("Background processing thread started")

    def stop(self):
        """Stop background processing."""
        self.queue_manager.stop()
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
        logger.info("Auto-apply processing stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get current service status."""
        queue_status = self.queue_manager.get_queue_status()

        return {
            "enabled": self.enabled,
            "is_processing": queue_status["is_processing"],
            "queue_size": queue_status["queue_size"],
            "applications_this_hour": queue_status["applications_this_hour"],
            "max_per_hour": queue_status["max_per_hour"],
            "rate_limit_delay": queue_status["rate_limit_delay"],
            "auto_apply_threshold": self.auto_apply_threshold,
        }

    def apply_to_job(self, job_id: int) -> Dict[str, Any]:
        """
        Apply to a specific job immediately.

        Args:
            job_id: Job ID to apply to

        Returns:
            Result dictionary
        """
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        if not job.approved:
            return {"status": "error", "message": "Job not approved"}

        if job.status in [JobStatus.APPLICATION_COMPLETED, JobStatus.APPLIED]:
            return {"status": "error", "message": "Already applied"}

        try:
            success = self._apply_with_templates(job)
            return {
                "status": "success" if success else "failed",
                "job_id": job.id,
                "title": job.title,
                "company": job.company,
            }
        except Exception as e:
            return {
                "status": "error",
                "job_id": job.id,
                "message": str(e),
            }

    def generate_answer(
        self,
        question: str,
        job_id: Optional[int] = None
    ) -> Optional[str]:
        """
        Generate an answer for an application question.

        Args:
            question: The question to answer
            job_id: Optional job ID for context

        Returns:
            Generated answer or None
        """
        job = None
        if job_id:
            job = self.db.query(Job).filter(Job.id == job_id).first()

        return self.template_manager.generate_answer(question, job)
