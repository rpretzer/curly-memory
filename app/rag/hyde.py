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

    def __init__(self, llm=None, expand_terms: bool = True, expansion_template: Optional[str] = None):
        """
        Initialize query expansion.

        Args:
            llm: Optional LLM instance (will be initialized if not provided)
            expand_terms: Whether to expand query with related terms
            expansion_template: Optional custom prompt template for expansion
        """
        self.expand_terms = expand_terms
        self.expansion_template = expansion_template or self._default_expansion_template()
        self.llm = llm

        if self.llm is None and self.expand_terms:
            self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM for query expansion."""
        try:
            default_llm = config.get_llm_defaults()
            provider = default_llm.get("provider", "openai")
            model = default_llm.get("model", "gpt-4o-mini")
            temperature = default_llm.get("temperature", 0.3)  # Lower temp for more focused expansions
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

            logger.info(f"Initialized Query Expansion LLM: {provider}/{model}")
        except Exception as e:
            logger.error(f"Failed to initialize Query Expansion LLM: {e}")
            self.expand_terms = False

    def _default_expansion_template(self) -> str:
        """Default prompt template for query expansion."""
        return """You are an expert at expanding job search queries with related terms, synonyms, and variations.

Given a job search query, generate related terms that would help find relevant results. Include:
1. Synonyms and alternative phrasings
2. Related job titles (if applicable)
3. Related skills and technologies (if applicable)
4. Industry-specific terminology
5. Common abbreviations or expansions

Original Query: {query}

Generate 5-8 related terms or phrases (comma-separated, no explanations):"""

    def expand_query(self, query: str) -> str:
        """
        Expand query with additional terms using LLM.

        Args:
            query: Original query

        Returns:
            Expanded query with original + related terms
        """
        if not self.expand_terms or not self.llm:
            logger.debug("Query expansion disabled or LLM not available, using original query")
            return query

        try:
            # Generate related terms
            prompt = self.expansion_template.format(query=query)

            response = self.llm.invoke([HumanMessage(content=prompt)])
            related_terms = response.content.strip()

            # Combine original query with related terms
            expanded_query = f"{query} {related_terms}"

            logger.debug(f"Query expansion: '{query}' -> added {len(related_terms)} chars of related terms")
            logger.debug(f"Expanded query: {expanded_query}")

            return expanded_query

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}, using original query")
            return query

    def expand_queries(self, queries: list[str]) -> list[str]:
        """
        Expand multiple queries.

        Args:
            queries: List of original queries

        Returns:
            List of expanded queries
        """
        return [self.expand_query(query) for query in queries]
