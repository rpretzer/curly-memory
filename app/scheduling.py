"""Scheduler for automated pipeline runs."""

import schedule
import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime

from app.db import get_db_context
from app.orchestrator import PipelineOrchestrator
from app.config import config

logger = logging.getLogger(__name__)


class PipelineScheduler:
    """Scheduler for running the pipeline at regular intervals."""
    
    def __init__(self, run_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the scheduler.
        
        Args:
            run_config: Default configuration for scheduled runs
        """
        self.run_config = run_config or {}
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Get scheduler config
        scheduler_config = config.get_scheduler_config()
        self.enabled = scheduler_config.get("enabled", True)
        self.frequency_hours = scheduler_config.get("run_frequency_hours", 24)
        self.run_at_time = scheduler_config.get("run_at_time", "09:00")
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default run configuration from config file."""
        search_config = config.get_search_config()
        
        return {
            "search": {
                "titles": search_config.get("default_titles", ["Senior Product Manager"]),
                "locations": search_config.get("default_locations", ["Remote, US"]),
                "remote": True,
                "keywords": [],
                "sources": None,  # All enabled sources
                "max_results": search_config.get("default_max_results_per_source", 50),
            },
            "target_companies": None,
            "must_have_keywords": [],
            "nice_to_have_keywords": [],
            "remote_preference": search_config.get("default_remote_preference", "remote"),
            "salary_min": search_config.get("default_salary_min", 120000),
            "scoring_weights": None,  # Use defaults
            "llm_config": None,  # Use defaults
            "generate_content": True,
            "auto_apply": False,  # Never auto-apply in scheduled runs
        }
    
    def _run_scheduled_job(self):
        """Execute a scheduled pipeline run."""
        logger.info("Starting scheduled pipeline run")
        
        try:
            with get_db_context() as db:
                run_config = self.run_config or self._create_default_config()
                
                orchestrator = PipelineOrchestrator(db)
                
                # Create run
                run = orchestrator.create_run(
                    search_config=run_config.get("search", {}),
                    scoring_config=run_config.get("scoring_weights", {}),
                    llm_config=run_config.get("llm_config", {}),
                )
                
                # Run pipeline
                result = orchestrator.run_full_pipeline(
                    run_id=run.id,
                    titles=run_config["search"]["titles"],
                    locations=run_config["search"].get("locations"),
                    remote=run_config["search"].get("remote", False),
                    keywords=run_config["search"].get("keywords"),
                    sources=run_config["search"].get("sources"),
                    max_results=run_config["search"].get("max_results", 50),
                    target_companies=run_config.get("target_companies"),
                    must_have_keywords=run_config.get("must_have_keywords"),
                    nice_to_have_keywords=run_config.get("nice_to_have_keywords"),
                    remote_preference=run_config.get("remote_preference", "any"),
                    salary_min=run_config.get("salary_min"),
                    generate_content=run_config.get("generate_content", True),
                    auto_apply=run_config.get("auto_apply", False),
                )
                
                logger.info(f"Scheduled run {run.id} completed: {result}")
        
        except Exception as e:
            logger.error(f"Error in scheduled run: {e}", exc_info=True)
    
    def start(self):
        """Start the scheduler."""
        if not self.enabled:
            logger.info("Scheduler is disabled")
            return
        
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        # Schedule job
        schedule.every(self.frequency_hours).hours.do(self._run_scheduled_job)
        
        # Also schedule at specific time if configured
        if self.run_at_time:
            schedule.every().day.at(self.run_at_time).do(self._run_scheduled_job)
        
        self.running = True
        
        def run_scheduler():
            """Run the scheduler loop."""
            logger.info(f"Scheduler started (frequency: {self.frequency_hours} hours, time: {self.run_at_time})")
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True)
        self.thread.start()
        
        logger.info("Scheduler thread started")
    
    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        self.running = False
        schedule.clear()
        logger.info("Scheduler stopped")


# Global scheduler instance
_scheduler: Optional[PipelineScheduler] = None


def get_scheduler() -> PipelineScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PipelineScheduler()
    return _scheduler
