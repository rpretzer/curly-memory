"""Service layer for RAG operations with job descriptions."""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Job
from app.rag import (
    VectorStoreManager,
    chunk_job_description,
    TwoStageRetriever,
    RAGAgent,
    HyDEQueryTransformer,
)
from app.rag.retrieval import CrossEncoderReranker
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class JobRAGService:
    """
    Service for managing RAG operations with job descriptions.
    Handles indexing job descriptions and retrieving relevant context.
    """
    
    def __init__(
        self,
        db: Session,
        vector_store: Optional[VectorStoreManager] = None,
        collection_name: str = "job_descriptions",
    ):
        """
        Initialize job RAG service.
        
        Args:
            db: Database session
            vector_store: Optional VectorStoreManager instance
            collection_name: Name of the ChromaDB collection
        """
        self.db = db
        
        # Initialize vector store if not provided
        if vector_store is None:
            self.vector_store = VectorStoreManager(collection_name=collection_name)
        else:
            self.vector_store = vector_store
        
        # Initialize retriever
        self.retriever = TwoStageRetriever(
            vector_store=self.vector_store,
            reranker=CrossEncoderReranker(),
            stage1_k=50,
            stage2_k=5,
        )
        
        # Initialize RAG agent
        self.rag_agent = RAGAgent(
            vector_store=self.vector_store,
            retriever=self.retriever,
            hyde_transformer=HyDEQueryTransformer(),
            max_iterations=3,
            min_relevance_score=0.7,
        )
        
        logger.info("JobRAGService initialized")
    
    def index_job(self, job: Job) -> bool:
        """
        Index a job description in the vector store.
        
        Args:
            job: Job model to index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not job.description and not job.raw_description:
                logger.warning(f"Job {job.id} has no description to index")
                return False
            
            # Get description text
            description_text = job.description or job.raw_description or ""
            
            if not description_text.strip():
                logger.warning(f"Job {job.id} has empty description")
                return False
            
            # Chunk the description
            chunks = chunk_job_description(
                job_description=description_text,
                job_id=job.id,
                job_title=job.title,
                company=job.company,
                source=job.source.value if hasattr(job.source, 'value') else str(job.source),
                posting_date=job.posting_date.isoformat() if job.posting_date else None,
            )
            
            if not chunks:
                logger.warning(f"No chunks generated for job {job.id}")
                return False
            
            # Generate IDs for chunks
            ids = [f"job_{job.id}_chunk_{i}" for i in range(len(chunks))]
            
            # Add to vector store
            self.vector_store.add_documents(
                documents=chunks,
                ids=ids,
            )
            
            logger.info(f"Indexed job {job.id} ({len(chunks)} chunks)")
            return True
            
        except Exception as e:
            logger.error(f"Error indexing job {job.id}: {e}", exc_info=True)
            return False
    
    def index_jobs(self, jobs: List[Job]) -> Dict[str, Any]:
        """
        Index multiple jobs.
        
        Args:
            jobs: List of Job models to index
            
        Returns:
            Dictionary with indexing results
        """
        results = {
            "total": len(jobs),
            "success": 0,
            "failed": 0,
            "errors": [],
        }
        
        for job in jobs:
            try:
                if self.index_job(job):
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "job_id": job.id,
                    "error": str(e),
                })
        
        logger.info(
            f"Indexing complete: {results['success']} succeeded, "
            f"{results['failed']} failed out of {results['total']}"
        )
        
        return results
    
    def index_all_jobs(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Index all jobs from the database.
        
        Args:
            limit: Optional limit on number of jobs to index
            
        Returns:
            Dictionary with indexing results
        """
        query = self.db.query(Job).filter(
            (Job.description != None) | (Job.raw_description != None)
        ).filter(
            (Job.description != "") | (Job.raw_description != "")
        )
        
        if limit:
            query = query.limit(limit)
        
        jobs = query.all()
        logger.info(f"Found {len(jobs)} jobs to index")
        
        return self.index_jobs(jobs)
    
    def retrieve_similar_jobs(
        self,
        query: str,
        job_id: Optional[int] = None,
        k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar jobs using semantic search.
        
        Args:
            query: Search query
            job_id: Optional job ID to exclude from results
            k: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of dictionaries with job information and similarity scores
        """
        try:
            # Build filter
            if filter_metadata is None:
                filter_metadata = {}
            
            if job_id:
                filter_metadata["job_id"] = {"$ne": job_id}
            
            # Retrieve using two-stage retrieval
            results = self.retriever.retrieve(
                query=query,
                filter=filter_metadata,
                k=k,
            )
            
            # Extract job IDs and fetch from database
            similar_jobs = []
            for doc, score in results:
                metadata = doc.metadata
                job_id_from_doc = metadata.get("job_id")
                
                if job_id_from_doc:
                    job = self.db.query(Job).filter(Job.id == job_id_from_doc).first()
                    if job:
                        similar_jobs.append({
                            "job": job,
                            "similarity_score": score,
                            "chunk_content": doc.page_content,
                            "chunk_metadata": metadata,
                        })
            
            logger.debug(f"Retrieved {len(similar_jobs)} similar jobs")
            return similar_jobs
            
        except Exception as e:
            logger.error(f"Error retrieving similar jobs: {e}", exc_info=True)
            return []
    
    def answer_query(self, query: str, filter_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Answer a query using RAG with job descriptions.
        
        Args:
            query: User query
            filter_metadata: Optional metadata filter for retrieval
            
        Returns:
            Dictionary with answer, context, and metadata
        """
        try:
            result = self.rag_agent.query(
                query=query,
                filter_metadata=filter_metadata,
            )
            
            logger.info(f"RAG query answered: {len(result.get('answer', ''))} chars")
            return result
            
        except Exception as e:
            logger.error(f"Error answering query with RAG: {e}", exc_info=True)
            return {
                "answer": f"Error processing query: {str(e)}",
                "context": "",
                "documents": [],
                "query": query,
            }
