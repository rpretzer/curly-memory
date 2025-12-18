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
        
        Implements form filling for Indeed Easy Apply and other job boards.
        Handles form fields, file uploads, and error detection.
        
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
        
        logger.info(f"Attempting Playwright application for job {job.id} from {job.source}")
        
        if self.log_agent and run_id:
            self.log_agent.log_application_start(
                run_id=run_id,
                job_id=job.id,
                application_type="playwright",
            )
        
        try:
            # Launch browser if not already launched
            if not self.browser:
                from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
                playwright = sync_playwright().start()
                # Launch browser - use headless=False for debugging, can be changed to True for production
                headless_mode = getattr(config, 'playwright', {}).get('headless', False) if hasattr(config, 'playwright') else False
                self.browser = playwright.chromium.launch(
                    headless=headless_mode
                )
            
            if not self.page:
                self.page = self.browser.new_page()
                # Set a reasonable timeout
                self.page.set_default_timeout(30000)
            
            # Navigate to job application URL
            logger.info(f"Navigating to: {job.source_url}")
            self.page.goto(job.source_url, wait_until="networkidle", timeout=30000)
            
            # Wait a bit for dynamic content
            self.page.wait_for_timeout(2000)
            
            # Get user profile for application data
            from app.user_profile import get_user_profile
            profile = get_user_profile(self.db, profile_id=1)
            
            # Route to job-board-specific application logic
            if job.source == "indeed":
                return self._apply_indeed(job, application_data, profile, run_id)
            elif job.source == "linkedin" and job.application_type == ApplicationType.EASY_APPLY:
                return self._apply_linkedin_easy_apply(job, application_data, profile, run_id)
            else:
                logger.warning(f"Application method not implemented for source: {job.source}")
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
    
    def _apply_indeed(
        self,
        job: Job,
        application_data: Dict[str, Any],
        profile,
        run_id: Optional[int] = None
    ) -> bool:
        """Apply to an Indeed job using Playwright."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from pathlib import Path
        
        try:
            logger.info("Starting Indeed application flow")
            
            # Look for "Apply now" or "Apply" button
            apply_selectors = [
                'button:has-text("Apply now")',
                'button:has-text("Apply")',
                'a:has-text("Apply now")',
                'a:has-text("Apply")',
                '[data-testid="apply-button"]',
                'button[id*="apply"]',
                'a[id*="apply"]',
            ]
            
            apply_button = None
            for selector in apply_selectors:
                try:
                    apply_button = self.page.query_selector(selector)
                    if apply_button:
                        logger.info(f"Found apply button with selector: {selector}")
                        break
                except:
                    continue
            
            if not apply_button:
                logger.warning("Could not find apply button on Indeed page")
                return False
            
            # Click apply button
            apply_button.click()
            self.page.wait_for_timeout(2000)
            
            # Indeed may redirect to external site or show a form
            # Check if we're on an external application page
            current_url = self.page.url
            if "indeed.com" not in current_url:
                logger.info(f"Redirected to external application: {current_url}")
                # External application - can't automate
                return False
            
            # Try to find and fill form fields
            # Indeed application forms vary, so we'll try common fields
            
            # Email field
            email_selectors = ['input[type="email"]', 'input[name*="email"]', 'input[id*="email"]']
            for selector in email_selectors:
                try:
                    email_field = self.page.query_selector(selector)
                    if email_field and profile and profile.email:
                        email_field.fill(profile.email)
                        logger.info("Filled email field")
                        break
                except:
                    continue
            
            # Phone field
            phone_selectors = ['input[type="tel"]', 'input[name*="phone"]', 'input[id*="phone"]']
            for selector in phone_selectors:
                try:
                    phone_field = self.page.query_selector(selector)
                    if phone_field and profile and profile.phone:
                        phone_field.fill(profile.phone)
                        logger.info("Filled phone field")
                        break
                except:
                    continue
            
            # Resume upload
            resume_path = self._get_resume_path()
            if resume_path and Path(resume_path).exists():
                file_input_selectors = [
                    'input[type="file"]',
                    'input[accept*="pdf"]',
                    'input[accept*="doc"]',
                ]
                for selector in file_input_selectors:
                    try:
                        file_input = self.page.query_selector(selector)
                        if file_input:
                            file_input.set_input_files(resume_path)
                            logger.info(f"Uploaded resume: {resume_path}")
                            self.page.wait_for_timeout(1000)
                            break
                    except:
                        continue
            
            # Cover letter textarea
            cover_letter = application_data.get('cover_letter', '') or job.cover_letter_draft or ''
            if cover_letter:
                textarea_selectors = [
                    'textarea[name*="cover"]',
                    'textarea[name*="letter"]',
                    'textarea[id*="cover"]',
                    'textarea[placeholder*="cover"]',
                ]
                for selector in textarea_selectors:
                    try:
                        textarea = self.page.query_selector(selector)
                        if textarea:
                            textarea.fill(cover_letter[:2000])  # Limit length
                            logger.info("Filled cover letter")
                            break
                    except:
                        continue
            
            # Look for submit button
            submit_selectors = [
                'button:has-text("Submit application")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                'button[id*="submit"]',
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.page.query_selector(selector)
                    if submit_button:
                        logger.info(f"Found submit button with selector: {selector}")
                        break
                except:
                    continue
            
            if not submit_button:
                logger.warning("Could not find submit button")
                # Check if there's a CAPTCHA
                captcha_selectors = ['iframe[title*="captcha"]', '[class*="captcha"]', '[id*="captcha"]']
                for selector in captcha_selectors:
                    if self.page.query_selector(selector):
                        logger.warning("CAPTCHA detected - manual intervention required")
                        return False
                return False
            
            # Click submit
            submit_button.click()
            self.page.wait_for_timeout(3000)
            
            # Check for success indicators
            success_indicators = [
                'text=Application submitted',
                'text=Thank you',
                'text=successfully',
                '[class*="success"]',
                '[id*="success"]',
            ]
            
            for indicator in success_indicators:
                try:
                    if self.page.query_selector(indicator):
                        logger.info("Application submitted successfully")
                        return True
                except:
                    continue
            
            # Check for error indicators
            error_indicators = [
                'text=Error',
                'text=Failed',
                '[class*="error"]',
                '[id*="error"]',
            ]
            
            for indicator in error_indicators:
                try:
                    if self.page.query_selector(indicator):
                        logger.warning("Error detected in application")
                        return False
                except:
                    continue
            
            # If we got here, assume success (form was submitted)
            logger.info("Application form submitted (assuming success)")
            return True
            
        except PlaywrightTimeout:
            logger.error("Timeout waiting for page elements")
            return False
        except Exception as e:
            logger.error(f"Error in Indeed application: {e}", exc_info=True)
            return False
    
    def _apply_linkedin_easy_apply(
        self,
        job: Job,
        application_data: Dict[str, Any],
        profile,
        run_id: Optional[int] = None
    ) -> bool:
        """Apply to a LinkedIn Easy Apply job using Playwright."""
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from pathlib import Path
        
        try:
            logger.info("Starting LinkedIn Easy Apply flow")
            
            # Look for Easy Apply button
            easy_apply_selectors = [
                'button:has-text("Easy Apply")',
                'button[aria-label*="Easy Apply"]',
                '[data-testid*="easy-apply"]',
            ]
            
            easy_apply_button = None
            for selector in easy_apply_selectors:
                try:
                    easy_apply_button = self.page.query_selector(selector)
                    if easy_apply_button:
                        logger.info(f"Found Easy Apply button")
                        break
                except:
                    continue
            
            if not easy_apply_button:
                logger.warning("Could not find Easy Apply button")
                return False
            
            easy_apply_button.click()
            self.page.wait_for_timeout(2000)
            
            # Fill form fields (LinkedIn Easy Apply typically has multiple steps)
            # Step 1: Basic info
            if profile:
                # Phone
                phone_selectors = ['input[name*="phone"]', 'input[id*="phone"]']
                for selector in phone_selectors:
                    try:
                        field = self.page.query_selector(selector)
                        if field and profile.phone:
                            field.fill(profile.phone)
                            break
                    except:
                        continue
                
                # Resume upload (LinkedIn usually has this in first step)
                resume_path = self._get_resume_path()
                if resume_path and Path(resume_path).exists():
                    file_input = self.page.query_selector('input[type="file"]')
                    if file_input:
                        file_input.set_input_files(resume_path)
                        self.page.wait_for_timeout(2000)
            
            # Click Next/Continue button
            next_selectors = [
                'button:has-text("Next")',
                'button:has-text("Continue")',
                'button[aria-label*="Next"]',
            ]
            
            for selector in next_selectors:
                try:
                    next_button = self.page.query_selector(selector)
                    if next_button:
                        next_button.click()
                        self.page.wait_for_timeout(2000)
                        break
                except:
                    continue
            
            # Step 2: Cover letter (if present)
            cover_letter = application_data.get('cover_letter', '') or job.cover_letter_draft or ''
            if cover_letter:
                textarea = self.page.query_selector('textarea[name*="cover"]')
                if textarea:
                    textarea.fill(cover_letter[:2000])
            
            # Submit
            submit_selectors = [
                'button:has-text("Submit application")',
                'button[aria-label*="Submit"]',
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.page.query_selector(selector)
                    if submit_button:
                        submit_button.click()
                        self.page.wait_for_timeout(3000)
                        
                        # Check for success
                        if self.page.query_selector('text=Application sent'):
                            logger.info("LinkedIn application submitted successfully")
                            return True
                        break
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error in LinkedIn Easy Apply: {e}", exc_info=True)
            return False
    
    def _get_resume_path(self) -> Optional[str]:
        """Get the path to the most recent resume file."""
        from pathlib import Path
        
        resume_dir = Path("resumes")
        if not resume_dir.exists():
            return None
        
        # Get most recent resume file
        resume_files = sorted(resume_dir.glob("resume_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if resume_files:
            return str(resume_files[0])
        
        return None
    
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
        human_approval_required: bool = True,
        max_retries: int = 2,
        dry_run: bool = False
    ) -> bool:
        """
        Apply to a job using the appropriate method with retry logic.
        
        Args:
            job: Job to apply to
            application_data: Optional application form data
            run_id: Optional run ID for logging
            human_approval_required: Whether human approval is required (safety check)
            max_retries: Maximum number of retry attempts
            dry_run: If True, simulate application without actually submitting
            
        Returns:
            True if application successful, False otherwise
        """
        if human_approval_required and not job.approved:
            logger.warning(f"Job {job.id} not approved for application")
            return False
        
        if job.status == JobStatus.APPLICATION_COMPLETED and not dry_run:
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
        
        # In dry-run mode, simulate success without actually applying
        if dry_run:
            logger.info(f"DRY-RUN: Simulating application to job {job.id}")
            job.status = JobStatus.APPLICATION_COMPLETED
            job.application_completed_at = datetime.utcnow()
            job.application_error = None
            self.db.commit()
            return True
        
        self.db.commit()
        
        success = False
        error_message = None
        last_exception = None
        
        # Retry logic
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries} for job {job.id}")
                    import time
                    time.sleep(2 * attempt)  # Exponential backoff
                
                # Try API first if available
                if job.application_type == ApplicationType.API:
                    success = self.apply_via_api(job, payload, run_id)
                    if success:
                        break
                
                # Fall back to browser automation
                elif job.application_type == ApplicationType.EASY_APPLY and self.enable_playwright:
                    success = self.apply_via_playwright(job, payload, run_id)
                    if success:
                        break
                    # If Playwright failed but no exception, check for specific error
                    if not success and attempt < max_retries:
                        # Check if it's a recoverable error (e.g., timeout)
                        if "timeout" in str(job.application_error or "").lower():
                            continue  # Retry on timeout
                
                # External applications require manual intervention
                elif job.application_type == ApplicationType.EXTERNAL:
                    logger.info(f"External application for job {job.id} - manual intervention required")
                    success = False
                    error_message = "External application - manual intervention required"
                    break  # Don't retry external applications
                
                else:
                    error_message = f"Application method not supported: {job.application_type}"
                    break  # Don't retry unsupported methods
            
            except Exception as e:
                last_exception = e
                error_message = str(e)
                logger.error(f"Error applying to job {job.id} (attempt {attempt + 1}): {e}", exc_info=True)
                
                # Don't retry on certain errors
                if "CAPTCHA" in str(e) or "manual intervention" in str(e).lower():
                    error_message = f"{error_message} - Manual intervention required"
                    break
                
                # Retry on network/timeout errors
                if attempt < max_retries and ("timeout" in str(e).lower() or "network" in str(e).lower()):
                    continue
        
        # Use last exception message if we have one
        if last_exception:
            error_message = str(last_exception)
        
        # Update job status
        if success:
            job.status = JobStatus.APPLICATION_COMPLETED
            job.application_completed_at = datetime.utcnow()
            job.application_error = None
            logger.info(f"Successfully applied to job {job.id}")
        else:
            job.status = JobStatus.APPLICATION_FAILED
            job.application_error = error_message or "Application failed after retries"
            logger.warning(f"Failed to apply to job {job.id}: {job.application_error}")
        
        self.db.commit()
        
        if self.log_agent and run_id:
            self.log_agent.log_application_complete(
                run_id=run_id,
                job_id=job.id,
                success=success,
                error_message=error_message,
            )
        
        return success
