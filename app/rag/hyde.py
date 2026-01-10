"""Hypothetical Document Embeddings (HyDE) for query transformation."""

import logging
from typing import Optional, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import config

logger = logging.getLogger(__name__)


class HyDEQueryTransformer:
    """
    Implements Hypothetical Document Embeddings (HyDE).
    Generates a "fake" ideal answer to the query, then uses that
    to search the vector database for better results.
    """
    
    def __init__(
        self,
        llm=None,
        use_hyde: bool = True,
        hyde_template: Optional[str] = None,
    ):
        """
        Initialize HyDE query transformer.
        
        Args:
            llm: Optional LLM instance (will be initialized if not provided)
            use_hyde: Whether to enable HyDE transformation
            hyde_template: Optional custom prompt template
        """
        self.use_hyde = use_hyde
        self.hyde_template = hyde_template or self._default_template()
        self.llm = llm
        
        if self.llm is None and self.use_hyde:
            self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize LLM for HyDE generation."""
        try:
            default_llm = config.get_llm_defaults()
            provider = default_llm.get("provider", "openai")
            model = default_llm.get("model", "gpt-4o-mini")
            temperature = default_llm.get("temperature", 0.7)
            ollama_base_url = default_llm.get("ollama_base_url", "http://localhost:11434")
            
            if provider.lower() == "ollama":
                self.llm = ChatOllama(
                    model=model,
                    temperature=temperature,
                    base_url=ollama_base_url,
                )
            else:
                self.llm = ChatOpenAI(
                    model=model,
                    temperature=temperature,
                    api_key=config.llm.api_key if config.llm.api_key else None,
                )
            
            logger.info(f"Initialized HyDE LLM: {provider}/{model}")
        except Exception as e:
            logger.error(f"Failed to initialize HyDE LLM: {e}")
            self.use_hyde = False
    
    def _default_template(self) -> str:
        """Default prompt template for HyDE generation."""
        return """You are an expert at understanding information needs. Given a user's question, generate a hypothetical document that would be an ideal answer to that question.

The hypothetical document should:
1. Contain the key information the user is seeking
2. Use terminology and concepts relevant to the query
3. Be written in a natural, document-like format
4. Be concise (2-3 paragraphs, ~200-300 words)

User Question: {query}

Generate the hypothetical ideal document that answers this question:"""
    
    def transform_query(self, query: str) -> str:
        """
        Transform query using HyDE.
        
        Args:
            query: Original user query
            
        Returns:
            Transformed query (hypothetical document or original if HyDE fails)
        """
        if not self.use_hyde or not self.llm:
            logger.debug("HyDE disabled or LLM not available, using original query")
            return query
        
        try:
            # Generate hypothetical document
            prompt = self.hyde_template.format(query=query)
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            hyde_document = response.content.strip()
            
            logger.debug(f"HyDE transformation: {len(query)} chars -> {len(hyde_document)} chars")
            logger.debug(f"HyDE document preview: {hyde_document[:200]}...")
            
            # Use the hypothetical document as the search query
            return hyde_document
            
        except Exception as e:
            logger.warning(f"HyDE transformation failed: {e}, using original query")
            return query
    
    def transform_queries(self, queries: list[str]) -> list[str]:
        """
        Transform multiple queries using HyDE.
        
        Args:
            queries: List of original queries
            
        Returns:
            List of transformed queries
        """
        return [self.transform_query(query) for query in queries]


class QueryExpansion:
    """
    Alternative to HyDE: expands query with related terms and synonyms.
    Can be used alongside or instead of HyDE.
    """
    
    def __init__(self, expand_terms: bool = True):
        """
        Initialize query expansion.
        
        Args:
            expand_terms: Whether to expand query with related terms
        """
        self.expand_terms = expand_terms
    
    def expand_query(self, query: str) -> str:
        """
        Expand query with additional terms.
        
        Args:
            query: Original query
            
        Returns:
            Expanded query
        """
        if not self.expand_terms:
            return query
        
        # Simple keyword expansion (can be enhanced with thesaurus/synonyms)
        # For now, just return the original query
        # TODO: Implement proper synonym expansion or LLM-based expansion
        
        return query
