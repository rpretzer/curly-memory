#!/usr/bin/env python3
"""
Example script demonstrating how to use the job search pipeline.

This script shows a complete example of running a search for
"Senior Product Manager" roles in InsurTech/FinTech.
"""

import logging
from app.db import get_db_context
from app.orchestrator import PipelineOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run an example pipeline execution."""
    logger.info("Starting example job search pipeline run")
    
    with get_db_context() as db:
        # Create orchestrator
        orchestrator = PipelineOrchestrator(db)
        
        # Create a new run
        run = orchestrator.create_run(
            search_config={
                "titles": ["Senior Product Manager"],
                "locations": ["Remote, US"],
            },
            scoring_config={},  # Use defaults
            llm_config={},      # Use defaults
        )
        
        logger.info(f"Created run: {run.id}")
        
        # Run the full pipeline
        result = orchestrator.run_full_pipeline(
            run_id=run.id,
            titles=[
                "Senior Product Manager",
                "Principal Product Manager",
                "Product Manager",
            ],
            locations=["Remote, US", "San Francisco, CA"],
            remote=True,
            keywords=["insurance", "insurtech", "fintech"],
            sources=None,  # Use all enabled sources
            max_results=50,
            target_companies=["TechCorp Insurance", "InsureTech Solutions"],
            must_have_keywords=["product management", "B2B", "SaaS"],
            nice_to_have_keywords=[
                "data analytics",
                "API",
                "machine learning",
                "insurance industry",
            ],
            remote_preference="remote",
            salary_min=120000,
            generate_content=True,
            auto_apply=False,  # Always requires manual approval
        )
        
        logger.info("=" * 60)
        logger.info("Pipeline Run Complete!")
        logger.info("=" * 60)
        logger.info(f"Run ID: {result['run_id']}")
        logger.info(f"Jobs Found: {result['jobs_found']}")
        logger.info(f"Jobs Scored: {result['jobs_scored']}")
        logger.info(f"Jobs Above Threshold: {result['jobs_above_threshold']}")
        logger.info(f"Jobs Applied: {result['jobs_applied']}")
        logger.info(f"Jobs Failed: {result['jobs_failed']}")
        logger.info("=" * 60)
        
        # Show some example jobs
        from app.models import Job
        jobs = db.query(Job).filter(
            Job.run_id == run.id
        ).order_by(Job.relevance_score.desc().nullslast()).limit(5).all()
        
        if jobs:
            logger.info("\nTop 5 Jobs Found:")
            for i, job in enumerate(jobs, 1):
                logger.info(f"\n{i}. {job.title} at {job.company}")
                logger.info(f"   Location: {job.location}")
                logger.info(f"   Score: {job.relevance_score:.2f}" if job.relevance_score else "   Score: N/A")
                logger.info(f"   URL: {job.source_url}")
        
        logger.info("\nExample run complete! Check the database or API for full results.")


if __name__ == "__main__":
    main()
