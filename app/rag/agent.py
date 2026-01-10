"""LangGraph-based RAG agent with state management and self-correction cycles."""

import logging
from typing import TypedDict, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from app.config import config
from app.rag.vector_store import VectorStoreManager
from app.rag.retrieval import TwoStageRetriever
from app.rag.hyde import HyDEQueryTransformer

logger = logging.getLogger(__name__)


class RAGState(TypedDict):
    """State for the RAG agent."""
    query: str
    transformed_query: str
    retrieved_documents: List[Dict[str, Any]]
    graded_documents: List[Dict[str, Any]]
    context: str
    answer: str
    iterations: int
    max_iterations: int
    should_continue: bool
    relevance_ratio: float
    filter_metadata: Optional[Dict[str, Any]]


class RAGAgent:
    """
    Advanced RAG agent using LangGraph for state management.
    Implements cycles for:
    - Query transformation (HyDE)
    - Document retrieval (two-stage)
    - Document grading (relevance check)
    - Query rewriting if documents are poor
    - Answer generation when quality is confirmed
    """
    
    def __init__(
        self,
        vector_store: Optional[VectorStoreManager] = None,
        retriever: Optional[TwoStageRetriever] = None,
        hyde_transformer: Optional[HyDEQueryTransformer] = None,
        llm=None,
        max_iterations: int = 3,
        min_relevance_score: float = 0.7,
    ):
        """
        Initialize RAG agent.
        
        Args:
            vector_store: VectorStoreManager instance
            retriever: TwoStageRetriever instance
            hyde_transformer: HyDEQueryTransformer instance
            llm: Optional LLM instance
            max_iterations: Maximum number of retrieval cycles
            min_relevance_score: Minimum score for documents to be considered relevant
        """
        self.vector_store = vector_store
        self.retriever = retriever
        self.hyde_transformer = hyde_transformer or HyDEQueryTransformer()
        self.max_iterations = max_iterations
        self.min_relevance_score = min_relevance_score
        
        # Initialize LLM
        if llm is None:
            self._initialize_llm()
        else:
            self.llm = llm
        
        # Build LangGraph workflow
        self.graph = self._build_graph()
    
    def _initialize_llm(self):
        """Initialize LLM for the agent."""
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
            
            logger.info(f"Initialized RAG Agent LLM: {provider}/{model}")
        except Exception as e:
            logger.error(f"Failed to initialize RAG Agent LLM: {e}")
            raise
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph state machine."""
        workflow = StateGraph(RAGState)
        
        # Add nodes
        workflow.add_node("transform_query", self._transform_query_node)
        workflow.add_node("retrieve_documents", self._retrieve_documents_node)
        workflow.add_node("grade_documents", self._grade_documents_node)
        workflow.add_node("rewrite_query", self._rewrite_query_node)
        workflow.add_node("generate_answer", self._generate_answer_node)
        
        # Define edges
        workflow.set_entry_point("transform_query")
        workflow.add_edge("transform_query", "retrieve_documents")
        workflow.add_edge("retrieve_documents", "grade_documents")
        
        # Conditional edge: continue or generate answer
        workflow.add_conditional_edges(
            "grade_documents",
            self._should_continue,
            {
                "continue": "rewrite_query",
                "generate": "generate_answer",
            }
        )
        
        workflow.add_edge("rewrite_query", "retrieve_documents")
        workflow.add_edge("generate_answer", END)
        
        return workflow.compile()
    
    def _transform_query_node(self, state: RAGState) -> RAGState:
        """Transform query using HyDE."""
        query = state.get("query", "")
        logger.debug(f"Transforming query: {query}")
        
        transformed_query = self.hyde_transformer.transform_query(query)
        
        return {
            **state,
            "transformed_query": transformed_query,
            "iterations": state.get("iterations", 0),
        }
    
    def _retrieve_documents_node(self, state: RAGState) -> RAGState:
        """Retrieve documents using two-stage retrieval."""
        query = state.get("transformed_query", state.get("query", ""))
        filter_metadata = state.get("filter_metadata")
        
        logger.debug(f"Retrieving documents for query: {query[:100]}...")
        
        try:
            # Use retriever if available, otherwise fallback to vector store
            if self.retriever:
                results = self.retriever.retrieve(
                    query=query,
                    filter=filter_metadata,
                )
            elif self.vector_store:
                results = self.vector_store.similarity_search(
                    query=query,
                    k=5,
                    filter=filter_metadata,
                )
            else:
                logger.warning("No retriever or vector store available")
                results = []
            
            # Convert to dict format
            retrieved_documents = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score,
                }
                for doc, score in results
            ]
            
            logger.info(f"Retrieved {len(retrieved_documents)} documents")
            
            return {
                **state,
                "retrieved_documents": retrieved_documents,
                "iterations": state.get("iterations", 0) + 1,
            }
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}", exc_info=True)
            return {
                **state,
                "retrieved_documents": [],
                "iterations": state.get("iterations", 0) + 1,
            }
    
    def _grade_documents_node(self, state: RAGState) -> RAGState:
        """Grade documents for relevance using LLM."""
        query = state.get("query", "")
        documents = state.get("retrieved_documents", [])
        
        if not documents:
            logger.warning("No documents to grade")
            return {
                **state,
                "graded_documents": [],
                "should_continue": True,
            }
        
        logger.debug(f"Grading {len(documents)} documents")
        
        try:
            # Use LLM to grade each document
            graded_docs = []
            relevant_count = 0
            
            for doc in documents:
                grade_prompt = f"""You are a document relevance grader. Given a user's question and a retrieved document, determine if the document is relevant.

User Question: {query}

Retrieved Document:
{doc['content'][:1000]}

Is this document relevant to answering the user's question? Respond with only:
- "RELEVANT" if the document contains useful information
- "NOT_RELEVANT" if the document is not useful

Response:"""
                
                response = self.llm.invoke([HumanMessage(content=grade_prompt)])
                grade = response.content.strip().upper()
                
                is_relevant = "RELEVANT" in grade
                if is_relevant:
                    relevant_count += 1
                
                doc_with_grade = {
                    **doc,
                    "grade": grade,
                    "is_relevant": is_relevant,
                }
                graded_docs.append(doc_with_grade)
            
            # Calculate relevance ratio
            relevance_ratio = relevant_count / len(documents) if documents else 0.0
            
            logger.info(
                f"Graded documents: {relevant_count}/{len(documents)} relevant "
                f"(ratio: {relevance_ratio:.2f})"
            )
            
            # Determine if we should continue (rewrite query) or generate answer
            should_continue = (
                relevance_ratio < self.min_relevance_score and
                state.get("iterations", 0) < self.max_iterations
            )
            
            return {
                **state,
                "graded_documents": graded_docs,
                "should_continue": should_continue,
                "relevance_ratio": relevance_ratio,
            }
            
        except Exception as e:
            logger.error(f"Error grading documents: {e}", exc_info=True)
            # On error, assume documents are relevant and proceed
            return {
                **state,
                "graded_documents": [
                    {**doc, "grade": "RELEVANT", "is_relevant": True}
                    for doc in documents
                ],
                "should_continue": False,
            }
    
    def _should_continue(self, state: RAGState) -> str:
        """Determine if we should continue (rewrite query) or generate answer."""
        should_continue = state.get("should_continue", False)
        iterations = state.get("iterations", 0)
        max_iterations = state.get("max_iterations", self.max_iterations)
        
        if should_continue and iterations < max_iterations:
            return "continue"
        else:
            return "generate"
    
    def _rewrite_query_node(self, state: RAGState) -> RAGState:
        """Rewrite query based on poor document quality."""
        original_query = state.get("query", "")
        documents = state.get("graded_documents", [])
        
        logger.debug("Rewriting query based on poor document quality")
        
        try:
            # Extract what was missing from documents
            missing_info = []
            for doc in documents:
                if not doc.get("is_relevant", False):
                    # Could extract why it's not relevant, but for now just note it
                    missing_info.append("Previous retrieval lacked relevant information")
            
            rewrite_prompt = f"""The user's original question was: "{original_query}"

The retrieved documents were not sufficiently relevant. Rewrite the search query to better capture what the user is looking for.

Consider:
1. Using different terminology or synonyms
2. Being more specific about what information is needed
3. Focusing on key concepts from the original question

Original Query: {original_query}

Rewritten Query:"""
            
            response = self.llm.invoke([HumanMessage(content=rewrite_prompt)])
            rewritten_query = response.content.strip()
            
            logger.info(f"Query rewritten: {original_query} -> {rewritten_query}")
            
            return {
                **state,
                "transformed_query": rewritten_query,
            }
            
        except Exception as e:
            logger.error(f"Error rewriting query: {e}", exc_info=True)
            # On error, use original query
            return {
                **state,
                "transformed_query": original_query,
            }
    
    def _generate_answer_node(self, state: RAGState) -> RAGState:
        """Generate final answer using retrieved context."""
        query = state.get("query", "")
        documents = state.get("graded_documents", [])
        
        # Filter to only relevant documents
        relevant_docs = [
            doc for doc in documents
            if doc.get("is_relevant", True)  # Default to True if not graded
        ]
        
        # Build context from relevant documents
        context_parts = []
        for i, doc in enumerate(relevant_docs[:5], 1):  # Limit to top 5
            content = doc.get("content", "")
            context_parts.append(f"[Document {i}]\n{content}\n")
        
        context = "\n".join(context_parts)
        
        logger.debug(f"Generating answer using {len(relevant_docs)} relevant documents")
        
        try:
            answer_prompt = f"""You are a helpful assistant. Answer the user's question using only the information provided in the context documents.

Context Documents:
{context}

User Question: {query}

Answer the question based on the context. If the context doesn't contain enough information, say so explicitly. Be concise and accurate.

Answer:"""
            
            response = self.llm.invoke([HumanMessage(content=answer_prompt)])
            answer = response.content.strip()
            
            logger.info(f"Generated answer ({len(answer)} chars)")
            
            return {
                **state,
                "context": context,
                "answer": answer,
            }
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}", exc_info=True)
            return {
                **state,
                "context": context,
                "answer": "Error generating answer. Please try again.",
            }
    
    def query(
        self,
        query: str,
        filter_metadata: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute RAG query with full workflow.
        
        Args:
            query: User query
            filter_metadata: Optional metadata filter for retrieval
            max_iterations: Optional override for max iterations
            
        Returns:
            Dictionary with answer, context, documents, and metadata
        """
        logger.info(f"Processing RAG query: {query}")
        
        # Initialize state
        initial_state: RAGState = {
            "query": query,
            "transformed_query": "",
            "retrieved_documents": [],
            "graded_documents": [],
            "context": "",
            "answer": "",
            "iterations": 0,
            "max_iterations": max_iterations or self.max_iterations,
            "should_continue": True,
            "relevance_ratio": 0.0,
            "filter_metadata": filter_metadata,
        }
        
        # Run graph
        try:
            final_state = self.graph.invoke(initial_state)
            
            return {
                "answer": final_state.get("answer", ""),
                "context": final_state.get("context", ""),
                "documents": final_state.get("graded_documents", []),
                "iterations": final_state.get("iterations", 0),
                "relevance_ratio": final_state.get("relevance_ratio", 0.0),
                "query": query,
                "transformed_query": final_state.get("transformed_query", ""),
            }
            
        except Exception as e:
            logger.error(f"Error executing RAG query: {e}", exc_info=True)
            return {
                "answer": f"Error processing query: {str(e)}",
                "context": "",
                "documents": [],
                "iterations": 0,
                "query": query,
            }
