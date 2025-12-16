"""Agent for applying to jobs via browser automation or APIs."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Job, JobStatus, ApplicationType
from app.config import config
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)


class ApplyAgent:
    """Agent responsible for applying to jobs."""
    
    def __init__(
        self,
        db: Session,
        log_agent: Optional[LogAgent] = None,
        enable_playwright: Optional[bool] = None
    ):
        """
        Initialize the apply agent.
        
        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
            enable_playwright: Whether to enable browser automation
        """
        self.db = db
        self.log_agent = log_agent
        self.agent_name = "ApplyAgent"
        
        feature_flags = config.get_feature_flags()
        self.enable_playwright = enable_playwright if enable_playwright is not None else feature_flags.get("enable_playwright", False)
        
        # Initialize Playwright if enabled
        self.browser = None
        self.page = None
        if self.enable_playwright:
            try:
                from playwright.sync_api import sync_playwright
                self.playwright = sync_playwright().start()
                # Browser will be launched on first use
            except ImportError:
                logger.warning("Playwright not installed. Browser automation disabled.")
                self.enable_playwright = False
            except Exception as e:
                logger.error(f"Failed to initialize Playwright: {e}")
                self.enable_playwright = False
    
    def apply_via_api(
        self,
        job: Job,
        application_data: Dict[str, Any],
        run_id: Optional[int] = None
    ) -> bool:
        """
        Apply to a job via API (if supported by the source).
        
        TODO: Implement API-based applications when job board APIs support it.
        
        Args:
            job: Job to apply to
            application_data: Application form data
            run_id: Optional run ID for logging
            
        Returns:
            True if application successful, False otherwise
        """
        logger.info(f"Attempting API application for job: {job.id}")
        
        if self.log_agent and run_id:
            self.log_agent.log_application_start(
                run_id=run_id,
                job_id=job.id,
                application_type="api",
            )
        
        # TODO: Implement API-based application
        # Example structure:
        # if job.source == "linkedin":
        #     response = requests.post(
        #         f"{LINKEDIN_API_URL}/jobs/{job.source_id}/applications",
        #         headers={"Authorization": f"Bearer {api_key}"},
        #         json=application_data,
        #     )
        #     return response.status_code == 200
        
        logger.warning(f"API application not implemented for source: {job.source}")
        return False
    
    def apply_via_playwright(
        self,
        job: Job,
        application_data: Dict[str, Any],
        run_id: Optional[int] = None
    ) -> bool:
        """
        Apply to a job using browser automation (Playwright).
        
        This is a stub implementation that demonstrates the structure.
        Real implementation would need to handle:
        - Different job board UI structures
        - Form filling
        - File uploads
        - CAPTCHA handling (may require human intervention)
        - Error handling and retries
        
        Args:
            job: Job to apply to
            application_data: Application form data
            run_id: Optional run ID for logging
            
        Returns:
            True if application successful, False otherwise
        """
        if not self.enable_playwright:
            logger.warning("Playwright not enabled")
            return False
        
        logger.info(f"Attempting Playwright application for job: {job.id}")
        
        if self.log_agent and run_id:
            self.log_agent.log_application_start(
                run_id=run_id,
                job_id=job.id,
                application_type="playwright",
            )
        
        try:
            # Launch browser if not already launched
            if not self.browser:
                from playwright.sync_api import sync_playwright
                playwright = sync_playwright().start()
                self.browser = playwright.chromium.launch(
                    headless=config.playwright.headless
                )
            
            if not self.page:
                self.page = self.browser.new_page()
            
            # Navigate to job application URL
            self.page.goto(job.source_url)
            
            # Wait for page to load
            self.page.wait_for_load_state("networkidle")
            
            # TODO: Implement job-board-specific application logic
            # This is a placeholder that shows the structure
            
            if job.application_type == ApplicationType.EASY_APPLY:
                # LinkedIn Easy Apply flow (example structure)
                # 1. Find and click "Easy Apply" button
                # easy_apply_button = self.page.query_selector('button[aria-label*="Easy Apply"]')
                # if easy_apply_button:
                #     easy_apply_button.click()
                #     self.page.wait_for_timeout(1000)
                #
                # 2. Fill out form fields
                # self.page.fill('input[name="phone"]', application_data.get('phone', ''))
                # self.page.fill('textarea[name="coverLetter"]', application_data.get('cover_letter', ''))
                #
                # 3. Upload resume if needed
                # if application_data.get('resume_path'):
                #     self.page.set_input_files('input[type="file"]', application_data['resume_path'])
                #
                # 4. Submit application
                # submit_button = self.page.query_selector('button[aria-label*="Submit"]')
                # submit_button.click()
                #
                # 5. Wait for confirmation
                # self.page.wait_for_selector('.application-confirmation', timeout=10000)
                
                logger.info(f"Easy Apply flow for {job.source} - stub implementation")
                # For now, return False to indicate manual intervention needed
                return False
            
            else:
                # External application - navigate to external URL
                external_url = job.source_url
                logger.info(f"External application URL: {external_url}")
                # Don't auto-apply to external links - require manual intervention
                return False
        
        except Exception as e:
            logger.error(f"Error in Playwright application: {e}", exc_info=True)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=e,
                    run_id=run_id,
                    job_id=job.id,
                    step="playwright_apply",
                )
            return False
        
        finally:
            # Optionally close browser after each application
            # self.cleanup()
            pass
    
    def cleanup(self):
        """Clean up browser resources."""
        if self.page:
            self.page.close()
            self.page = None
        if self.browser:
            self.browser.close()
            self.browser = None
    
    def apply_to_job(
        self,
        job: Job,
        application_data: Optional[Dict[str, Any]] = None,
        run_id: Optional[int] = None,
        human_approval_required: bool = True
    ) -> bool:
        """
        Apply to a job using the appropriate method.
        
        Args:
            job: Job to apply to
            application_data: Optional application form data
            run_id: Optional run ID for logging
            human_approval_required: Whether human approval is required (safety check)
            
        Returns:
            True if application successful, False otherwise
        """
        if human_approval_required and not job.approved:
            logger.warning(f"Job {job.id} not approved for application")
            return False
        
        if job.status == JobStatus.APPLICATION_COMPLETED:
            logger.info(f"Job {job.id} already applied to")
            return True
        
        application_data = application_data or {}
        
        # Prepare application payload
        payload = {
            "cover_letter": job.cover_letter_draft or "",
            "resume_points": job.tailored_resume_points or [],
            "application_answers": job.application_answers or {},
            **application_data,
        }
        
        # Update job status
        job.status = JobStatus.APPLICATION_STARTED
        job.application_started_at = datetime.utcnow()
        job.application_payload = payload
        self.db.commit()
        
        success = False
        error_message = None
        
        try:
            # Try API first if available
            if job.application_type == ApplicationType.API:
                success = self.apply_via_api(job, payload, run_id)
            
            # Fall back to browser automation
            elif job.application_type == ApplicationType.EASY_APPLY and self.enable_playwright:
                success = self.apply_via_playwright(job, payload, run_id)
            
            # External applications require manual intervention
            elif job.application_type == ApplicationType.EXTERNAL:
                logger.info(f"External application for job {job.id} - manual intervention required")
                success = False
                error_message = "External application - manual intervention required"
            
            else:
                error_message = f"Application method not supported: {job.application_type}"
        
        except Exception as e:
            error_message = str(e)
            logger.error(f"Error applying to job {job.id}: {e}", exc_info=True)
        
        # Update job status
        if success:
            job.status = JobStatus.APPLICATION_COMPLETED
            job.application_completed_at = datetime.utcnow()
            job.application_error = None
        else:
            job.status = JobStatus.APPLICATION_FAILED
            job.application_error = error_message
        
        self.db.commit()
        
        if self.log_agent and run_id:
            self.log_agent.log_application_complete(
                run_id=run_id,
                job_id=job.id,
                success=success,
                error_message=error_message,
            )
        
        return success
