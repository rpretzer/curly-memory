"""Semantic chunking utilities for advanced RAG."""

import logging
from typing import List, Dict, Any, Optional
import re
import math

from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter, SentenceTransformersTokenTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import config

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Implements semantic chunking by splitting text where meaning changes.
    Uses cosine similarity between consecutive sentences to identify boundaries.
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 100,
    ):
        """
        Initialize semantic chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
            similarity_threshold: Minimum similarity between consecutive sentences (lower = more chunks)
            min_chunk_size: Minimum chunk size to keep
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        
        # Initialize embedding model for semantic analysis
        try:
            embedding_config = config.yaml_config.get("rag", {}).get("embeddings", {})
            embedding_provider = embedding_config.get("provider", "huggingface")
            
            if embedding_provider == "huggingface":
                model_name = embedding_config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
                self.embedder = HuggingFaceEmbeddings(model_name=model_name)
            else:
                # Fallback to fast local model
                self.embedder = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            logger.info(f"Semantic chunker initialized with threshold: {similarity_threshold}")
        except Exception as e:
            logger.warning(f"Could not initialize embedding model for semantic chunking: {e}")
            self.embedder = None
    
    def chunk_text(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """
        Chunk text using semantic boundaries.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to all chunks
            
        Returns:
            List of Document chunks
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return [Document(page_content=text, metadata=metadata or {})]
        
        # If embedding model is not available, fall back to recursive splitting
        if self.embedder is None:
            return self._fallback_chunk(text, metadata)
        
        try:
            # Step 1: Split into sentences
            sentences = self._split_sentences(text)
            
            if len(sentences) <= 1:
                return [Document(page_content=text, metadata=metadata or {})]
            
            # Step 2: Compute embeddings for sentences
            sentence_embeddings = self.embedder.embed_documents(sentences)
            
            # Step 3: Compute similarity between consecutive sentences
            similarities = []
            for i in range(len(sentence_embeddings) - 1):
                sim = cosine_similarity(
                    [sentence_embeddings[i]],
                    [sentence_embeddings[i + 1]]
                )[0][0]
                similarities.append(sim)
            
            # Step 4: Identify split points where similarity drops below threshold
            split_points = [0]  # Always start at beginning
            for i, sim in enumerate(similarities):
                if sim < self.similarity_threshold:
                    split_points.append(i + 1)
            split_points.append(len(sentences))  # Always end at the end
            
            # Step 5: Group sentences into chunks
            chunks = []
            i = 0
            while i < len(split_points) - 1:
                start = split_points[i]
                end = split_points[i + 1]
                chunk_text = " ".join(sentences[start:end])
                
                # Merge small chunks with next chunk if possible
                if len(chunk_text) < self.min_chunk_size and i < len(split_points) - 2:
                    next_end = split_points[i + 2]
                    chunk_text = " ".join(sentences[start:next_end])
                    i += 1  # Skip next split point since we merged
                    end = next_end
                
                if len(chunk_text) >= self.min_chunk_size:
                    chunk_metadata = (metadata or {}).copy()
                    chunk_metadata.update({
                        "chunk_index": len(chunks),
                        "chunk_size": len(chunk_text),
                        "sentence_start": start,
                        "sentence_end": end,
                    })
                    chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))
                
                i += 1
            
            # If semantic chunking produced no valid chunks, fall back
            if not chunks:
                return self._fallback_chunk(text, metadata)
            
            # Step 6: Apply size constraints and overlap
            final_chunks = []
            for chunk in chunks:
                if len(chunk.page_content) > self.chunk_size:
                    # Recursively split oversized chunks
                    sub_chunks = self._split_large_chunk(chunk.page_content, chunk.metadata)
                    final_chunks.extend(sub_chunks)
                else:
                    final_chunks.append(chunk)
            
            # Add overlap between chunks
            overlapped_chunks = self._add_overlap(final_chunks)
            
            logger.debug(f"Semantic chunking: {len(text)} chars -> {len(overlapped_chunks)} chunks")
            return overlapped_chunks
            
        except Exception as e:
            logger.warning(f"Semantic chunking failed, falling back: {e}")
            return self._fallback_chunk(text, metadata)
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Use regex to split on sentence boundaries
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        # Filter out empty strings and clean up
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences
    
    def _split_large_chunk(self, text: str, metadata: Dict[str, Any]) -> List[Document]:
        """Split a chunk that exceeds the target size."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        sub_chunks = splitter.split_text(text)
        return [
            Document(
                page_content=chunk,
                metadata={**metadata, "sub_chunk_index": i}
            )
            for i, chunk in enumerate(sub_chunks)
        ]
    
    def _add_overlap(self, chunks: List[Document]) -> List[Document]:
        """Add overlap between chunks to preserve context."""
        if len(chunks) <= 1 or self.chunk_overlap <= 0:
            return chunks
        
        overlapped = []
        for i, chunk in enumerate(chunks):
            content = chunk.page_content
            
            # Add overlap from previous chunk
            if i > 0:
                prev_content = chunks[i - 1].page_content
                overlap_text = prev_content[-self.chunk_overlap:]
                content = overlap_text + " " + content
            
            # Add overlap to next chunk
            if i < len(chunks) - 1:
                next_content = chunks[i + 1].page_content
                overlap_text = next_content[:self.chunk_overlap]
                content = content + " " + overlap_text
            
            overlapped.append(Document(
                page_content=content,
                metadata={**chunk.metadata, "has_overlap": True}
            ))
        
        return overlapped
    
    def _fallback_chunk(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Document]:
        """Fallback to recursive character splitting."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        chunks = splitter.split_text(text)
        return [
            Document(
                page_content=chunk,
                metadata={**(metadata or {}), "chunk_index": i, "chunking_method": "recursive"}
            )
            for i, chunk in enumerate(chunks)
        ]


def chunk_job_description(
    job_description: str,
    job_id: Optional[int] = None,
    job_title: Optional[str] = None,
    company: Optional[str] = None,
    **kwargs
) -> List[Document]:
    """
    Chunk a job description with appropriate metadata.
    
    Args:
        job_description: Full job description text
        job_id: Job ID from database
        job_title: Job title
        company: Company name
        **kwargs: Additional metadata to attach
        
    Returns:
        List of Document chunks
    """
    chunker = SemanticChunker(
        chunk_size=kwargs.get("chunk_size", 500),
        chunk_overlap=kwargs.get("chunk_overlap", 50),
        similarity_threshold=kwargs.get("similarity_threshold", 0.7),
    )
    
    metadata = {
        "job_id": job_id,
        "job_title": job_title,
        "company": company,
        "chunk_type": "job_description",
        **kwargs
    }
    
    return chunker.chunk_text(job_description, metadata=metadata)
