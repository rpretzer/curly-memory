"""Vector store management for advanced RAG system."""

import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings

from app.config import config

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """Manages vector store operations with support for metadata filtering and semantic search."""
    
    def __init__(
        self,
        collection_name: str = "job_descriptions",
        persist_directory: Optional[Path] = None,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize vector store manager.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the vector store
            embedding_model: Embedding model name (defaults to config)
        """
        if persist_directory is None:
            persist_directory = Path(__file__).parent.parent.parent / "vector_store"
        
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # Get embedding model configuration
        embedding_config = config.yaml_config.get("rag", {}).get("embeddings", {})
        embedding_provider = embedding_config.get("provider", "openai")
        embedding_model = embedding_model or embedding_config.get("model", "text-embedding-3-small")
        
        # Initialize embeddings based on provider
        try:
            if embedding_provider == "ollama":
                self.embeddings = OllamaEmbeddings(
                    model=embedding_model or "llama3.2",
                    base_url=config.get_llm_defaults().get("ollama_base_url", "http://localhost:11434"),
                )
                logger.info(f"Using Ollama embeddings: {embedding_model}")
            elif embedding_provider == "huggingface":
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=embedding_model or "sentence-transformers/all-MiniLM-L6-v2",
                )
                logger.info(f"Using HuggingFace embeddings: {embedding_model}")
            else:
                # Default to OpenAI
                self.embeddings = OpenAIEmbeddings(
                    model=embedding_model,
                    api_key=config.llm.api_key if config.llm.api_key else None,
                )
                logger.info(f"Using OpenAI embeddings: {embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            # Fallback to HuggingFace local model
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
            )
            logger.warning("Fell back to HuggingFace embeddings")
        
        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                )
            )
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            
            # Initialize LangChain Chroma wrapper for compatibility
            self.vector_store = Chroma(
                client=self.client,
                collection_name=collection_name,
                embedding_function=self.embeddings,
                persist_directory=str(self.persist_directory),
            )
            
            logger.info(f"Vector store initialized: {collection_name} at {self.persist_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}", exc_info=True)
            raise
    
    def add_documents(
        self,
        documents: List[Document],
        ids: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of Document objects
            ids: Optional list of document IDs
            metadata: Optional list of metadata dicts (one per document)
            
        Returns:
            List of document IDs
        """
        try:
            # Generate IDs if not provided
            if ids is None:
                ids = [f"doc_{i}_{datetime.now().timestamp()}" for i in range(len(documents))]
            
            # Add metadata to documents if provided
            if metadata:
                for doc, meta in zip(documents, metadata):
                    if doc.metadata:
                        doc.metadata.update(meta)
                    else:
                        doc.metadata = meta
            
            # Add to vector store
            result_ids = self.vector_store.add_documents(
                documents=documents,
                ids=ids,
            )
            
            logger.info(f"Added {len(documents)} documents to vector store")
            return result_ids
            
        except Exception as e:
            logger.error(f"Error adding documents to vector store: {e}", exc_info=True)
            raise
    
    def similarity_search(
        self,
        query: str,
        k: int = 50,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """
        Perform similarity search with optional metadata filtering.
        
        Args:
            query: Search query
            k: Number of results to retrieve (default: 50 for two-stage retrieval)
            filter: Optional metadata filter dict (ChromaDB where clause format)
            score_threshold: Optional minimum similarity score (lower is better for cosine distance)
            
        Returns:
            List of (Document, score) tuples. Score is distance (lower is better).
        """
        try:
            # Convert filter to ChromaDB format if needed
            chroma_filter = None
            if filter:
                # ChromaDB uses where clauses with $ operators
                # Simple conversion - for complex filters, user should provide ChromaDB format
                if isinstance(filter, dict):
                    chroma_filter = filter
                else:
                    logger.warning(f"Filter format may not be compatible with ChromaDB: {filter}")
                    chroma_filter = filter
            
            # Use similarity_search_with_score to get scores
            # Note: ChromaDB returns distance (lower is better), not similarity
            # LangChain's Chroma wrapper uses 'filter' parameter
            if chroma_filter:
                results = self.vector_store.similarity_search_with_score(
                    query=query,
                    k=k,
                    filter=chroma_filter,
                )
            else:
                results = self.vector_store.similarity_search_with_score(
                    query=query,
                    k=k,
                )
            
            # Convert distance to similarity if needed (cosine distance: 1 - similarity)
            # For now, we'll use distance as-is (lower is better)
            # Filter by score threshold if provided
            if score_threshold is not None:
                # For cosine distance, threshold means max distance
                results = [(doc, score) for doc, score in results if score <= score_threshold]
            
            logger.debug(f"Retrieved {len(results)} documents from vector store")
            return results
            
        except Exception as e:
            logger.error(f"Error performing similarity search: {e}", exc_info=True)
            # Fallback: try without filter
            try:
                results = self.vector_store.similarity_search_with_score(query=query, k=k)
                logger.warning(f"Retried without filter, got {len(results)} results")
                return results
            except Exception as e2:
                logger.error(f"Fallback search also failed: {e2}")
                return []
    
    def delete_documents(self, ids: List[str]) -> bool:
        """Delete documents by IDs."""
        try:
            self.vector_store.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents from vector store")
            return True
        except Exception as e:
            logger.error(f"Error deleting documents: {e}", exc_info=True)
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the collection."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": str(self.persist_directory),
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}", exc_info=True)
            return {}
