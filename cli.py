"""Command-line interface for the job search pipeline."""

import argparse
import logging
import sys
from pathlib import Path

from app.db import init_db, get_db_context
from app.orchestrator import PipelineOrchestrator
from app.scheduling import get_scheduler
from app.config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_search(args):
    """Run a search-only pipeline."""
    logger.info("Running search pipeline...")
    
    with get_db_context() as db:
        orchestrator = PipelineOrchestrator(db)
        
        run = orchestrator.create_run(
            search_config={"titles": args.titles},
            scoring_config={},
            llm_config={},
        )
        
        job_ids = orchestrator.run_search_only(
            run_id=run.id,
            titles=args.titles,
            locations=args.locations,
            remote=args.remote,
            keywords=args.keywords,
            sources=args.sources,
            max_results=args.max_results,
        )
        
        logger.info(f"Search complete: {len(job_ids)} jobs found (run_id: {run.id})")


def run_full(args):
    """Run the full pipeline."""
    logger.info("Running full pipeline...")
    
    with get_db_context() as db:
        orchestrator = PipelineOrchestrator(db)
        
        run = orchestrator.create_run(
            search_config={"titles": args.titles},
            scoring_config={},
            llm_config={},
        )
        
        result = orchestrator.run_full_pipeline(
            run_id=run.id,
            titles=args.titles,
            locations=args.locations,
            remote=args.remote,
            keywords=args.keywords,
            sources=args.sources,
            max_results=args.max_results,
            target_companies=args.companies,
            must_have_keywords=args.must_have,
            nice_to_have_keywords=args.nice_to_have,
            remote_preference=args.remote_pref or "any",
            salary_min=args.salary_min,
            generate_content=not args.no_content,
            auto_apply=args.auto_apply,
        )
        
        logger.info(f"Pipeline complete: {result}")


def start_scheduler(args):
    """Start the scheduler."""
    logger.info("Starting scheduler...")
    
    scheduler = get_scheduler()
    scheduler.start()
    
    try:
        # Keep main thread alive
        import time
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Stopping scheduler...")
        scheduler.stop()


def init_database(args):
    """Initialize the database."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Agentic Job Search Pipeline CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Run search only")
    search_parser.add_argument("--titles", nargs="+", required=True, help="Job titles to search")
    search_parser.add_argument("--locations", nargs="+", help="Location filters")
    search_parser.add_argument("--remote", action="store_true", help="Remote filter")
    search_parser.add_argument("--keywords", nargs="+", help="Keywords")
    search_parser.add_argument("--sources", nargs="+", help="Job sources")
    search_parser.add_argument("--max-results", type=int, default=50, help="Max results per source")
    search_parser.set_defaults(func=run_search)
    
    # Full pipeline command
    full_parser = subparsers.add_parser("run", help="Run full pipeline")
    full_parser.add_argument("--titles", nargs="+", required=True, help="Job titles to search")
    full_parser.add_argument("--locations", nargs="+", help="Location filters")
    full_parser.add_argument("--remote", action="store_true", help="Remote filter")
    full_parser.add_argument("--keywords", nargs="+", help="Keywords")
    full_parser.add_argument("--sources", nargs="+", help="Job sources")
    full_parser.add_argument("--max-results", type=int, default=50, help="Max results per source")
    full_parser.add_argument("--companies", nargs="+", help="Target companies")
    full_parser.add_argument("--must-have", nargs="+", help="Must-have keywords")
    full_parser.add_argument("--nice-to-have", nargs="+", help="Nice-to-have keywords")
    full_parser.add_argument("--remote-pref", choices=["remote", "hybrid", "on-site", "any"], help="Remote preference")
    full_parser.add_argument("--salary-min", type=int, help="Minimum salary")
    full_parser.add_argument("--no-content", action="store_true", help="Skip content generation")
    full_parser.add_argument("--auto-apply", action="store_true", help="Auto-apply to approved jobs")
    full_parser.set_defaults(func=run_full)
    
    # Scheduler command
    scheduler_parser = subparsers.add_parser("schedule", help="Start scheduler")
    scheduler_parser.set_defaults(func=start_scheduler)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize database")
    init_parser.set_defaults(func=init_database)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        args.func(args)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
