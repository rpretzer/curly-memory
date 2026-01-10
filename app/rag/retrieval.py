"""Two-stage retrieval system with re-ranker for advanced RAG."""

import logging
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Container for retrieval results with scores."""
    document: Document
    vector_score: float
    rerank_score: Optional[float] = None
    final_score: Optional[float] = None


class Reranker:
    """Base class for re-ranking retrieved documents."""
    
    def rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """
        Re-rank documents based on query relevance.
        
        Args:
            query: Search query
            documents: List of (Document, vector_score) tuples
            top_k: Number of top documents to return
            
        Returns:
            List of (Document, rerank_score) tuples sorted by relevance
        """
        raise NotImplementedError


class CrossEncoderReranker(Reranker):
    """
    Cross-encoder re-ranker for improved precision.
    Uses sentence-transformers CrossEncoder model.
    """
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        device: Optional[str] = None,
    ):
        """
        Initialize cross-encoder re-ranker.
        
        Args:
            model_name: Name of the reranker model
            device: Device to run model on ('cpu', 'cuda', etc.)
        """
        self.model_name = model_name
        self.device = device
        
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_name, device=device)
            logger.info(f"Initialized CrossEncoder re-ranker: {model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available, using LLM-based reranking")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to initialize CrossEncoder: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Re-rank using cross-encoder model."""
        if not documents:
            return []
        
        if self.model is None:
            # Fallback to LLM-based reranking
            return self._llm_rerank(query, documents, top_k)
        
        try:
            # Prepare pairs for cross-encoder
            pairs = [[query, doc.page_content] for doc, _ in documents]
            
            # Compute scores
            scores = self.model.predict(pairs)
            
            # Combine documents with scores
            scored_docs = [
                RetrievalResult(
                    document=doc,
                    vector_score=vec_score,
                    rerank_score=float(score),
                    final_score=float(score),  # Use rerank score as final
                )
                for (doc, vec_score), score in zip(documents, scores)
            ]
            
            # Sort by rerank score (higher is better)
            scored_docs.sort(key=lambda x: x.rerank_score or 0.0, reverse=True)
            
            # Return top k
            results = [
                (result.document, result.rerank_score or 0.0)
                for result in scored_docs[:top_k]
            ]
            
            logger.debug(f"Re-ranked {len(documents)} documents, returning top {len(results)}")
            return results
            
        except Exception as e:
            logger.error(f"Error in cross-encoder reranking: {e}", exc_info=True)
            # Fallback: return top k by vector score
            return sorted(documents, key=lambda x: x[1], reverse=True)[:top_k]
    
    def _llm_rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Fallback LLM-based reranking."""
        # Simple heuristic: combine vector score with keyword match
        scored_docs = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for doc, vec_score in documents:
            doc_lower = doc.page_content.lower()
            doc_words = set(doc_lower.split())
            
            # Keyword overlap score
            overlap = len(query_words.intersection(doc_words))
            keyword_score = overlap / len(query_words) if query_words else 0.0
            
            # Combined score (weighted average)
            combined_score = 0.7 * vec_score + 0.3 * keyword_score
            
            scored_docs.append((doc, combined_score))
        
        # Sort and return top k
        scored_docs.sort(key=lambda x: x[1], reverse=True)
        return scored_docs[:top_k]


class TwoStageRetriever:
    """
    Two-stage retrieval system:
    Stage 1: Fast vector search (retrieve top 50)
    Stage 2: Re-ranker (narrow to top 5)
    """
    
    def __init__(
        self,
        vector_store,
        reranker: Optional[Reranker] = None,
        stage1_k: int = 50,
        stage2_k: int = 5,
        rerank_threshold: Optional[float] = None,
    ):
        """
        Initialize two-stage retriever.
        
        Args:
            vector_store: VectorStoreManager instance
            reranker: Optional Reranker instance (defaults to CrossEncoder)
            stage1_k: Number of candidates to retrieve in stage 1
            stage2_k: Number of final results to return after reranking
            rerank_threshold: Optional minimum rerank score threshold
        """
        self.vector_store = vector_store
        self.reranker = reranker or CrossEncoderReranker()
        self.stage1_k = stage1_k
        self.stage2_k = stage2_k
        self.rerank_threshold = rerank_threshold
        
        logger.info(
            f"Initialized TwoStageRetriever: stage1_k={stage1_k}, stage2_k={stage2_k}"
        )
    
    def retrieve(
        self,
        query: str,
        filter: Optional[Dict[str, Any]] = None,
        k: Optional[int] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Perform two-stage retrieval.
        
        Args:
            query: Search query
            filter: Optional metadata filter for vector search
            k: Optional override for stage2_k
            
        Returns:
            List of (Document, score) tuples sorted by relevance
        """
        final_k = k or self.stage2_k
        
        try:
            # Stage 1: Fast vector search (retrieve candidates)
            logger.debug(f"Stage 1: Retrieving top {self.stage1_k} candidates")
            candidates = self.vector_store.similarity_search(
                query=query,
                k=self.stage1_k,
                filter=filter,
            )
            
            if not candidates:
                logger.warning(f"No candidates retrieved for query: {query}")
                return []
            
            logger.debug(f"Stage 1: Retrieved {len(candidates)} candidates")
            
            # Stage 2: Re-rank to narrow down
            logger.debug(f"Stage 2: Re-ranking to top {final_k}")
            reranked = self.reranker.rerank(
                query=query,
                documents=candidates,
                top_k=final_k,
            )
            
            # Apply threshold if specified
            if self.rerank_threshold is not None:
                reranked = [
                    (doc, score) for doc, score in reranked
                    if score >= self.rerank_threshold
                ]
            
            logger.info(
                f"Retrieval complete: {len(candidates)} candidates -> {len(reranked)} results"
            )
            
            return reranked
            
        except Exception as e:
            logger.error(f"Error in two-stage retrieval: {e}", exc_info=True)
            # Fallback to simple vector search
            return self.vector_store.similarity_search(
                query=query,
                k=min(final_k, 10),
                filter=filter,
            )
