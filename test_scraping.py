
import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from app.jobsources import LinkedInAdapter, IndeedAdapter
from app.config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_indeed():
    logger.info("Testing Indeed Scraping...")
    indeed_config = config.get_job_sources_config().get("indeed", {}).copy()
    if config.scrapeops_api_key:
        indeed_config["scrapeops_api_key"] = config.scrapeops_api_key
    if config.hasdata_api_key:
        indeed_config["hasdata_api_key"] = config.hasdata_api_key
        
    adapter = IndeedAdapter(config=indeed_config)
    
    try:
        jobs = adapter.search("Product Manager", location="Remote", max_results=5)
        logger.info(f"Indeed found {len(jobs)} jobs")
        for job in jobs:
            logger.info(f"  - {job.title} @ {job.company}")
    except Exception as e:
        logger.error(f"Indeed failed: {e}")

def test_linkedin():
    logger.info("Testing LinkedIn Scraping...")
    from app.db import get_db_context
    from app.user_profile import get_user_profile
    from app.security import get_fernet
    
    with get_db_context() as db:
        profile = get_user_profile(db)
        linkedin_config = config.get_job_sources_config().get("linkedin", {}).copy()
        
        if profile and profile.linkedin_user:
            linkedin_config["linkedin_email"] = profile.linkedin_user
            logger.info(f"Using LinkedIn email: {profile.linkedin_user}")
        if profile and profile.linkedin_password:
            try:
                fernet = get_fernet()
                profile_li_pass = fernet.decrypt(profile.linkedin_password.encode()).decode()
                linkedin_config["linkedin_password"] = profile_li_pass
                logger.info("Using LinkedIn password from database")
            except Exception as e:
                logger.error(f"Failed to decrypt LinkedIn password: {e}")
        
        adapter = LinkedInAdapter(config=linkedin_config)
        
        try:
            jobs = adapter.search("Product Manager", location="Remote", max_results=5)
            logger.info(f"LinkedIn found {len(jobs)} jobs")
            for job in jobs:
                logger.info(f"  - {job.title} @ {job.company}")
        except Exception as e:
            logger.error(f"LinkedIn failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "indeed":
            test_indeed()
        elif sys.argv[1] == "linkedin":
            test_linkedin()
    else:
        test_indeed()
        test_linkedin()
