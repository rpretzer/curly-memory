"""Application Queue Manager for automated job applications."""

import logging
import time
import threading
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from queue import PriorityQueue
from sqlalchemy.orm import Session

from app.models import Job, JobStatus
from app.config import config

logger = logging.getLogger(__name__)


class ApplicationPriority(Enum):
    """Priority levels for application queue."""
    HIGH = 1      # Score >= 8.0, recently posted
    MEDIUM = 2    # Score >= 6.0
    LOW = 3       # Score >= 4.5


@dataclass(order=True)
class QueuedApplication:
    """Represents a job application in the queue."""
    priority: int
    job_id: int = field(compare=False)
    added_at: datetime = field(compare=False, default_factory=datetime.utcnow)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    last_error: Optional[str] = field(compare=False, default=None)


class ApplicationQueueManager:
    """
    Manages a queue of job applications with rate limiting and retry logic.

    Features:
    - Priority queue based on job score
    - Rate limiting to avoid detection
    - Exponential backoff for retries
    - Batch processing
    - Thread-safe operations
    """

    def __init__(
        self,
        db: Session,
        rate_limit_delay: float = 30.0,
        max_applications_per_hour: int = 20,
        max_retries: int = 3,
        base_retry_delay: float = 60.0,
    ):
        """
        Initialize the application queue manager.

        Args:
            db: Database session
            rate_limit_delay: Minimum seconds between applications
            max_applications_per_hour: Maximum applications per hour
            max_retries: Maximum retry attempts per job
            base_retry_delay: Base delay for exponential backoff (seconds)
        """
        self.db = db
        self.rate_limit_delay = rate_limit_delay
        self.max_applications_per_hour = max_applications_per_hour
        self.max_retries = max_retries
        self.base_retry_delay = base_retry_delay

        self.queue: PriorityQueue = PriorityQueue()
        self.applications_this_hour: List[datetime] = []
        self.is_processing = False
        self.stop_requested = False
        self._lock = threading.Lock()

        # Callbacks
        self.on_application_start: Optional[Callable] = None
        self.on_application_success: Optional[Callable] = None
        self.on_application_failure: Optional[Callable] = None
        self.on_queue_empty: Optional[Callable] = None

    def get_priority(self, job: Job) -> ApplicationPriority:
        """Determine application priority based on job score and recency."""
        score = job.relevance_score or 0

        if score >= 8.0:
            return ApplicationPriority.HIGH
        elif score >= 6.0:
            return ApplicationPriority.MEDIUM
        else:
            return ApplicationPriority.LOW

    def add_job(self, job: Job) -> bool:
        """
        Add a job to the application queue.

        Args:
            job: Job to add

        Returns:
            True if added, False if job is invalid or already queued
        """
        if not job.approved:
            logger.warning(f"Job {job.id} not approved, skipping")
            return False

        if job.status in [JobStatus.APPLICATION_COMPLETED, JobStatus.APPLIED]:
            logger.info(f"Job {job.id} already applied, skipping")
            return False

        priority = self.get_priority(job)
        queued_app = QueuedApplication(
            priority=priority.value,
            job_id=job.id,
            max_retries=self.max_retries,
        )

        with self._lock:
            self.queue.put(queued_app)

        logger.info(f"Added job {job.id} to queue with priority {priority.name}")
        return True

    def add_jobs(self, jobs: List[Job]) -> int:
        """
        Add multiple jobs to the queue.

        Args:
            jobs: List of jobs to add

        Returns:
            Number of jobs added
        """
        added = 0
        for job in jobs:
            if self.add_job(job):
                added += 1
        return added

    def add_approved_jobs(self) -> int:
        """
        Add all approved jobs that haven't been applied to.

        Returns:
            Number of jobs added
        """
        pending_jobs = self.db.query(Job).filter(
            Job.approved == True,
            Job.status.notin_([
                JobStatus.APPLICATION_COMPLETED,
                JobStatus.APPLIED,
                JobStatus.APPLICATION_FAILED
            ])
        ).all()

        return self.add_jobs(pending_jobs)

    def _can_apply_now(self) -> bool:
        """Check if we can apply now based on rate limits."""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Clean up old timestamps
        self.applications_this_hour = [
            ts for ts in self.applications_this_hour if ts > hour_ago
        ]

        return len(self.applications_this_hour) < self.max_applications_per_hour

    def _get_retry_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay."""
        return self.base_retry_delay * (2 ** retry_count)

    def process_next(self, apply_func: Callable[[Job], bool]) -> Optional[Dict[str, Any]]:
        """
        Process the next job in the queue.

        Args:
            apply_func: Function to apply to a job (returns True on success)

        Returns:
            Result dictionary or None if queue is empty
        """
        if self.queue.empty():
            return None

        if not self._can_apply_now():
            wait_time = 60  # Wait a minute and try again
            logger.info(f"Rate limit reached, waiting {wait_time}s")
            return {"status": "rate_limited", "wait_time": wait_time}

        with self._lock:
            if self.queue.empty():
                return None
            queued_app = self.queue.get()

        # Get job from database
        job = self.db.query(Job).filter(Job.id == queued_app.job_id).first()
        if not job:
            logger.warning(f"Job {queued_app.job_id} not found in database")
            return {"status": "not_found", "job_id": queued_app.job_id}

        # Check if already applied
        if job.status in [JobStatus.APPLICATION_COMPLETED, JobStatus.APPLIED]:
            return {"status": "already_applied", "job_id": job.id}

        # Callback: application starting
        if self.on_application_start:
            self.on_application_start(job)

        # Update job status
        job.status = JobStatus.APPLICATION_STARTED
        job.application_started_at = datetime.utcnow()
        self.db.commit()

        result = {
            "job_id": job.id,
            "title": job.title,
            "company": job.company,
            "retry_count": queued_app.retry_count,
        }

        try:
            logger.info(f"Applying to job {job.id}: {job.title} @ {job.company}")
            success = apply_func(job)

            if success:
                job.status = JobStatus.APPLICATION_COMPLETED
                job.application_completed_at = datetime.utcnow()
                job.application_error = None
                self.db.commit()

                self.applications_this_hour.append(datetime.utcnow())

                result["status"] = "success"
                logger.info(f"Successfully applied to job {job.id}")

                if self.on_application_success:
                    self.on_application_success(job)
            else:
                raise Exception("Application returned False")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to apply to job {job.id}: {error_msg}")

            job.application_error = error_msg
            queued_app.last_error = error_msg
            queued_app.retry_count += 1

            if queued_app.retry_count < queued_app.max_retries:
                # Re-queue with lower priority
                queued_app.priority = ApplicationPriority.LOW.value
                retry_delay = self._get_retry_delay(queued_app.retry_count)

                with self._lock:
                    self.queue.put(queued_app)

                job.status = JobStatus.SCORED  # Reset to allow retry
                result["status"] = "retry_scheduled"
                result["retry_delay"] = retry_delay
                result["retry_count"] = queued_app.retry_count

                logger.info(f"Job {job.id} scheduled for retry #{queued_app.retry_count} in {retry_delay}s")
            else:
                job.status = JobStatus.APPLICATION_FAILED
                result["status"] = "failed"
                result["error"] = error_msg

                logger.error(f"Job {job.id} failed after {queued_app.max_retries} retries")

                if self.on_application_failure:
                    self.on_application_failure(job, error_msg)

            self.db.commit()

        return result

    def process_batch(
        self,
        apply_func: Callable[[Job], bool],
        batch_size: int = 5,
        delay_between: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Process a batch of applications.

        Args:
            apply_func: Function to apply to a job
            batch_size: Number of applications to process
            delay_between: Delay between applications (uses rate_limit_delay if None)

        Returns:
            List of result dictionaries
        """
        delay = delay_between if delay_between is not None else self.rate_limit_delay
        results = []

        for i in range(batch_size):
            if self.stop_requested:
                logger.info("Stop requested, ending batch processing")
                break

            if self.queue.empty():
                if self.on_queue_empty:
                    self.on_queue_empty()
                break

            result = self.process_next(apply_func)
            if result:
                results.append(result)

                # Handle rate limiting
                if result.get("status") == "rate_limited":
                    time.sleep(result.get("wait_time", 60))
                elif result.get("status") in ["success", "failed", "retry_scheduled"]:
                    if i < batch_size - 1:  # Don't wait after last application
                        logger.info(f"Waiting {delay}s before next application...")
                        time.sleep(delay)

        return results

    def process_all(
        self,
        apply_func: Callable[[Job], bool],
        delay_between: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Process all jobs in the queue.

        Args:
            apply_func: Function to apply to a job
            delay_between: Delay between applications

        Returns:
            Summary dictionary
        """
        self.is_processing = True
        self.stop_requested = False

        summary = {
            "started_at": datetime.utcnow().isoformat(),
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "retried": 0,
            "results": []
        }

        delay = delay_between if delay_between is not None else self.rate_limit_delay

        try:
            while not self.queue.empty() and not self.stop_requested:
                result = self.process_next(apply_func)

                if result:
                    summary["results"].append(result)
                    summary["total_processed"] += 1

                    if result.get("status") == "success":
                        summary["successful"] += 1
                    elif result.get("status") == "failed":
                        summary["failed"] += 1
                    elif result.get("status") == "retry_scheduled":
                        summary["retried"] += 1

                    # Rate limiting
                    if result.get("status") == "rate_limited":
                        time.sleep(result.get("wait_time", 60))
                    elif result.get("status") in ["success", "failed", "retry_scheduled"]:
                        if not self.queue.empty():
                            time.sleep(delay)

        finally:
            self.is_processing = False
            summary["completed_at"] = datetime.utcnow().isoformat()

        if self.on_queue_empty and self.queue.empty():
            self.on_queue_empty()

        return summary

    def stop(self):
        """Request stop of processing."""
        self.stop_requested = True
        logger.info("Stop requested for application queue")

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queue_size": self.queue.qsize(),
            "is_processing": self.is_processing,
            "applications_this_hour": len(self.applications_this_hour),
            "max_per_hour": self.max_applications_per_hour,
            "rate_limit_delay": self.rate_limit_delay,
        }

    def clear(self):
        """Clear the queue."""
        with self._lock:
            while not self.queue.empty():
                self.queue.get()
        logger.info("Application queue cleared")
