"""Utility script to index job descriptions into the vector store."""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import get_db
from app.rag.service import JobRAGService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def index_jobs(limit: int = None, job_ids: list = None):
    """
    Index job descriptions into the vector store.
    
    Args:
        limit: Optional limit on number of jobs to index
        job_ids: Optional list of specific job IDs to index
    """
    logger.info("Starting job indexing...")
    
    try:
        # Get database session
        db_gen = get_db()
        db = next(db_gen)
        
        # Initialize RAG service
        rag_service = JobRAGService(db=db)
        
        if job_ids:
            # Index specific jobs
            from app.models import Job
            jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
            logger.info(f"Indexing {len(jobs)} specific jobs: {job_ids}")
            results = rag_service.index_jobs(jobs)
        else:
            # Index all jobs
            logger.info(f"Indexing all jobs" + (f" (limit: {limit})" if limit else ""))
            results = rag_service.index_all_jobs(limit=limit)
        
        # Print results
        logger.info("=" * 60)
        logger.info("INDEXING RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total jobs processed: {results['total']}")
        logger.info(f"Successfully indexed: {results['success']}")
        logger.info(f"Failed: {results['failed']}")
        
        if results['errors']:
            logger.warning(f"Errors encountered: {len(results['errors'])}")
            for error in results['errors'][:5]:  # Show first 5 errors
                logger.warning(f"  Job {error['job_id']}: {error['error']}")
        
        logger.info("=" * 60)
        
        # Get vector store stats
        stats = rag_service.vector_store.get_collection_stats()
        logger.info(f"Vector store now contains {stats.get('document_count', 0)} documents")
        
        db.close()
        logger.info("Job indexing complete!")
        
    except Exception as e:
        logger.error(f"Error indexing jobs: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Index job descriptions into vector store")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of jobs to index"
    )
    parser.add_argument(
        "--job-ids",
        type=int,
        nargs="+",
        default=None,
        help="Specific job IDs to index"
    )
    
    args = parser.parse_args()
    
    index_jobs(limit=args.limit, job_ids=args.job_ids)
