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

    # Maximum number of open browser contexts to keep (prevents memory leak)
    MAX_OPEN_CONTEXTS = 10

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
        self.playwright = None
        # Track open contexts for cleanup (context, page, job_id)
        self._open_contexts: list = []
        # Track temp files for cleanup
        self._temp_files: list = []

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
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Email selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Phone selector {selector} failed: {e}")
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
                    except Exception as e:
                        logger.debug(f"Resume upload with {selector} failed: {e}")
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
                    except Exception as e:
                        logger.debug(f"Cover letter selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Submit selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Success indicator {indicator} check failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Error indicator {indicator} check failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Easy Apply selector {selector} failed: {e}")
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
                    except Exception as e:
                        logger.debug(f"LinkedIn phone selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"Next button selector {selector} failed: {e}")
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
                except Exception as e:
                    logger.debug(f"LinkedIn submit selector {selector} failed: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"Error in LinkedIn Easy Apply: {e}", exc_info=True)
            return False
    
    def _apply_external_assisted(
        self,
        job: Job,
        application_data: Dict[str, Any],
        run_id: Optional[int] = None
    ) -> bool:
        """
        Open external application in browser and pre-fill fields where possible.

        This method opens the browser in non-headless mode, navigates to the job URL,
        and attempts to pre-fill common form fields. The user can then complete the
        application manually.
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from pathlib import Path

        try:
            logger.info(f"Starting assisted external application for job {job.id}")

            # Get user profile for application data
            from app.user_profile import get_user_profile
            profile = get_user_profile(self.db, profile_id=1)

            # Launch browser in non-headless mode for user interaction
            if not self.browser:
                from playwright.sync_api import sync_playwright
                playwright = sync_playwright().start()
                self.browser = playwright.chromium.launch(
                    headless=False,  # User needs to see and interact
                    args=['--start-maximized']
                )

            # Create new page for this application
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            # Navigate to job application URL
            logger.info(f"Opening application URL: {job.source_url}")
            page.goto(job.source_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # Try to find and click apply button if on job listing page
            apply_selectors = [
                'button:has-text("Apply")',
                'a:has-text("Apply")',
                'button:has-text("Apply Now")',
                'a:has-text("Apply Now")',
                '[data-testid*="apply"]',
                'button[id*="apply"]',
                'a[id*="apply"]',
            ]

            for selector in apply_selectors:
                try:
                    apply_btn = page.query_selector(selector)
                    if apply_btn and apply_btn.is_visible():
                        logger.info(f"Found apply button, clicking...")
                        apply_btn.click()
                        page.wait_for_timeout(3000)
                        break
                except Exception as e:
                    logger.debug(f"External apply selector {selector} failed: {e}")
                    continue

            # Attempt to pre-fill common form fields
            fields_filled = 0

            if profile:
                # Name fields
                name_selectors = [
                    ('input[name*="name" i]', profile.name),
                    ('input[id*="name" i]', profile.name),
                    ('input[placeholder*="name" i]', profile.name),
                    ('input[name*="first" i]', profile.name.split()[0] if profile.name else ''),
                    ('input[name*="last" i]', profile.name.split()[-1] if profile.name and len(profile.name.split()) > 1 else ''),
                ]

                for selector, value in name_selectors:
                    if value:
                        try:
                            field = page.query_selector(selector)
                            if field and field.is_visible():
                                field.fill(value)
                                fields_filled += 1
                                logger.debug(f"Filled field: {selector}")
                        except Exception as e:
                            logger.debug(f"Name field {selector} failed: {e}")
                            continue

                # Email field
                if profile.email:
                    email_selectors = ['input[type="email"]', 'input[name*="email" i]', 'input[id*="email" i]']
                    for selector in email_selectors:
                        try:
                            field = page.query_selector(selector)
                            if field and field.is_visible():
                                field.fill(profile.email)
                                fields_filled += 1
                                logger.info("Filled email field")
                                break
                        except Exception as e:
                            logger.debug(f"Email field {selector} failed: {e}")
                            continue

                # Phone field
                if profile.phone:
                    phone_selectors = ['input[type="tel"]', 'input[name*="phone" i]', 'input[id*="phone" i]']
                    for selector in phone_selectors:
                        try:
                            field = page.query_selector(selector)
                            if field and field.is_visible():
                                field.fill(profile.phone)
                                fields_filled += 1
                                logger.info("Filled phone field")
                                break
                        except Exception as e:
                            logger.debug(f"Phone field {selector} failed: {e}")
                            continue

                # LinkedIn URL
                if profile.linkedin_url:
                    linkedin_selectors = ['input[name*="linkedin" i]', 'input[id*="linkedin" i]', 'input[placeholder*="linkedin" i]']
                    for selector in linkedin_selectors:
                        try:
                            field = page.query_selector(selector)
                            if field and field.is_visible():
                                field.fill(profile.linkedin_url)
                                fields_filled += 1
                                logger.info("Filled LinkedIn field")
                                break
                        except Exception as e:
                            logger.debug(f"LinkedIn field {selector} failed: {e}")
                            continue

            # Try to upload resume
            resume_path = self._get_resume_path()
            if resume_path and Path(resume_path).exists():
                file_input_selectors = [
                    'input[type="file"]',
                    'input[accept*="pdf"]',
                    'input[accept*="doc"]',
                    'input[name*="resume" i]',
                    'input[id*="resume" i]',
                ]
                for selector in file_input_selectors:
                    try:
                        file_input = page.query_selector(selector)
                        if file_input:
                            file_input.set_input_files(resume_path)
                            fields_filled += 1
                            logger.info(f"Uploaded resume: {resume_path}")
                            page.wait_for_timeout(2000)
                            break
                    except Exception as e:
                        logger.debug(f"Resume upload failed with selector {selector}: {e}")
                        continue

            # Fill cover letter if available
            cover_letter = application_data.get('cover_letter', '') or job.cover_letter_draft or ''
            if cover_letter:
                textarea_selectors = [
                    'textarea[name*="cover" i]',
                    'textarea[name*="letter" i]',
                    'textarea[id*="cover" i]',
                    'textarea[placeholder*="cover" i]',
                    'textarea[name*="message" i]',
                ]
                for selector in textarea_selectors:
                    try:
                        textarea = page.query_selector(selector)
                        if textarea and textarea.is_visible():
                            textarea.fill(cover_letter[:4000])  # Limit length
                            fields_filled += 1
                            logger.info("Filled cover letter/message field")
                            break
                    except Exception as e:
                        logger.debug(f"Cover letter field {selector} failed: {e}")
                        continue

            logger.info(f"Pre-filled {fields_filled} fields. Browser left open for user to complete application.")

            # Check for CAPTCHA
            captcha_detected = self._check_for_captcha(page)
            if captcha_detected:
                logger.warning("CAPTCHA detected - user must solve it manually")
                job.application_error = "CAPTCHA detected - please complete manually"

            # Mark as started but not completed (user needs to submit)
            # Don't close the browser - let user complete the application
            # The job will remain in APPLICATION_STARTED status

            # Clean up oldest contexts if we've hit the limit (prevents memory leak)
            while len(self._open_contexts) >= self.MAX_OPEN_CONTEXTS:
                old_context, old_page, old_job_id = self._open_contexts.pop(0)
                try:
                    old_page.close()
                    old_context.close()
                    logger.debug(f"Closed old browser context for job {old_job_id}")
                except Exception as close_err:
                    logger.debug(f"Error closing old context: {close_err}")

            # Store context reference so it's not garbage collected
            self._open_contexts.append((context, page, job.id))

            # Return True to indicate we successfully opened the application
            # The actual completion will need user action
            return True

        except PlaywrightTimeout:
            logger.error("Timeout during external application")
            return False
        except Exception as e:
            logger.error(f"Error in external assisted application: {e}", exc_info=True)
            return False

    def _check_for_captcha(self, page) -> bool:
        """Check if the page has a CAPTCHA challenge."""
        captcha_selectors = [
            'iframe[title*="captcha" i]',
            'iframe[src*="captcha" i]',
            'iframe[src*="recaptcha" i]',
            'iframe[src*="hcaptcha" i]',
            '[class*="captcha" i]',
            '[id*="captcha" i]',
            '[class*="recaptcha" i]',
            'div[data-sitekey]',  # reCAPTCHA
            '.h-captcha',  # hCaptcha
        ]

        for selector in captcha_selectors:
            try:
                if page.query_selector(selector):
                    return True
            except Exception as e:
                logger.debug(f"CAPTCHA selector {selector} check failed: {e}")
                continue
        return False

    def _get_resume_path(self) -> Optional[str]:
        """Get the path to the user's resume file from profile or fallback to recent file."""
        from pathlib import Path
        from app.user_profile import get_user_profile
        from app.security import decrypt_file_content
        import tempfile
        import os

        # First, try to get resume path from user profile
        try:
            profile = get_user_profile(self.db, profile_id=1)
            if profile and profile.resume_file_path:
                resume_path = Path(profile.resume_file_path)
                if resume_path.exists():
                    logger.info(f"Using resume from profile: {resume_path}")
                    
                    # Decrypt to temp file
                    try:
                        decrypted_data = decrypt_file_content(resume_path)
                        
                        # Create a temp file with same extension
                        suffix = resume_path.suffix
                        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                        os.write(fd, decrypted_data)
                        os.close(fd)
                        
                        # Track for cleanup
                        if not hasattr(self, '_temp_files'):
                            self._temp_files = []
                        self._temp_files.append(tmp_path)
                        
                        return tmp_path
                    except Exception as e:
                        logger.error(f"Error decrypting resume: {e}")
                        # Fallback to original path (maybe it wasn't encrypted?)
                        return str(resume_path)
        except Exception as e:
            logger.warning(f"Error getting resume from profile: {e}")

        # Fallback: search for most recent resume file
        resume_dir = Path("resumes")
        if not resume_dir.exists():
            return None

        # Get most recent resume file
        resume_files = sorted(resume_dir.glob("resume_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if resume_files:
            logger.info(f"Using most recent resume file: {resume_files[0]}")
            # We should probably try to decrypt this one too, but for now assuming profile is main source
            return str(resume_files[0])

        return None
    
    def cleanup(self):
        """Clean up all browser resources including open contexts."""
        # Close main page and browser
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                logger.debug(f"Error closing page: {e}")
            self.page = None
        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                logger.debug(f"Error closing browser: {e}")
            self.browser = None

        # Close all tracked open contexts
        for context, page, job_id in self._open_contexts:
            try:
                page.close()
            except Exception as e:
                logger.debug(f"Error closing page for job {job_id}: {e}")
            try:
                context.close()
            except Exception as e:
                logger.debug(f"Error closing context for job {job_id}: {e}")
        self._open_contexts.clear()

        # Stop playwright instance
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.debug(f"Error stopping playwright: {e}")
            self.playwright = None
            
        # Cleanup temp files
        if hasattr(self, '_temp_files'):
            import os
            for path in self._temp_files:
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.debug(f"Error deleting temp file {path}: {e}")
            self._temp_files.clear()
    
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
                
                # External applications - open browser and assist user
                elif job.application_type == ApplicationType.EXTERNAL:
                    if self.enable_playwright:
                        logger.info(f"Opening external application in browser for job {job.id}")
                        success = self._apply_external_assisted(job, payload, run_id)
                        if success:
                            break
                    else:
                        logger.info(f"External application for job {job.id} - manual intervention required")
                        success = False
                        error_message = "External application - enable Playwright for assisted mode"
                        break  # Don't retry external applications
                
                # Unknown application type - try external assisted mode
                elif job.application_type == ApplicationType.UNKNOWN:
                    if self.enable_playwright:
                        logger.info(f"Unknown application type, trying assisted mode for job {job.id}")
                        success = self._apply_external_assisted(job, payload, run_id)
                        if success:
                            break
                    else:
                        error_message = "Unknown application type - enable Playwright for assisted mode"
                        break

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
