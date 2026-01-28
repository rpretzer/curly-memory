"""Service layer for RAG operations with companies."""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Company
from app.rag import VectorStoreManager
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class CompanyRAGService:
    """
    Service for managing RAG operations with companies.
    Handles indexing company data and suggesting relevant companies based on preferences.
    """

    def __init__(
        self,
        db: Session,
        vector_store: Optional[VectorStoreManager] = None,
        collection_name: str = "companies",
    ):
        """
        Initialize company RAG service.

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

        logger.info("CompanyRAGService initialized")

    def index_company(self, company: Company) -> bool:
        """
        Index a company in the vector store.

        Args:
            company: Company model to index

        Returns:
            True if successful, False otherwise
        """
        try:
            # Build rich text representation for embedding
            text_parts = [
                f"Company: {company.name}",
            ]

            if company.description:
                text_parts.append(f"Description: {company.description}")

            if company.industries:
                text_parts.append(f"Industries: {', '.join(company.industries)}")

            if company.verticals:
                text_parts.append(f"Verticals: {', '.join(company.verticals)}")

            if company.size:
                text_parts.append(f"Company Size: {company.size}")

            if company.stage:
                text_parts.append(f"Stage: {company.stage}")

            if company.tech_stack:
                text_parts.append(f"Tech Stack: {', '.join(company.tech_stack)}")

            if company.headquarters:
                text_parts.append(f"Headquarters: {company.headquarters}")

            document_text = "\n".join(text_parts)

            # Build metadata
            metadata = {
                "company_id": company.id,
                "company_name": company.name,
                "industries": company.industries or [],
                "verticals": company.verticals or [],
                "size": company.size or "unknown",
                "stage": company.stage or "unknown",
                "tech_stack": company.tech_stack or [],
                "headquarters": company.headquarters or "",
            }

            # Add to vector store
            doc_id = f"company_{company.id}"
            self.vector_store.add_documents(
                documents=[document_text],
                metadatas=[metadata],
                ids=[doc_id]
            )

            logger.info(f"Successfully indexed company: {company.name} (ID: {company.id})")
            return True

        except Exception as e:
            logger.error(f"Error indexing company {company.id}: {e}", exc_info=True)
            return False

    def index_companies(self, companies: List[Company]) -> Dict[str, Any]:
        """
        Index multiple companies in batch.

        Args:
            companies: List of Company models to index

        Returns:
            Dict with results: {total, success, failed, errors}
        """
        results = {
            "total": len(companies),
            "success": 0,
            "failed": 0,
            "errors": []
        }

        for company in companies:
            try:
                if self.index_company(company):
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to index company {company.id}")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error indexing company {company.id}: {str(e)}")

        logger.info(f"Indexed {results['success']}/{results['total']} companies successfully")
        return results

    def index_all_companies(self) -> Dict[str, Any]:
        """
        Index all companies from the database.

        Returns:
            Dict with results: {total, success, failed, errors}
        """
        companies = self.db.query(Company).all()
        logger.info(f"Found {len(companies)} companies to index")
        return self.index_companies(companies)

    def suggest_companies(
        self,
        industries: Optional[List[str]] = None,
        company_sizes: Optional[List[str]] = None,
        company_stages: Optional[List[str]] = None,
        tech_stack: Optional[List[str]] = None,
        k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Suggest companies based on user preferences using RAG.

        Args:
            industries: List of preferred industries
            company_sizes: List of preferred company sizes
            company_stages: List of preferred company stages
            tech_stack: List of preferred technologies
            k: Number of suggestions to return

        Returns:
            List of company suggestions with metadata and scores
        """
        try:
            # Build semantic query from preferences
            query_parts = []

            if industries and len(industries) > 0:
                query_parts.append(f"Industries: {', '.join(industries)}")

            if company_sizes and len(company_sizes) > 0:
                # Normalize size strings (remove parentheses and numbers)
                sizes = [s.split('(')[0].strip() if '(' in s else s for s in company_sizes]
                query_parts.append(f"Company size: {', '.join(sizes)}")

            if company_stages and len(company_stages) > 0:
                query_parts.append(f"Company stage: {', '.join(company_stages)}")

            if tech_stack and len(tech_stack) > 0:
                query_parts.append(f"Technologies: {', '.join(tech_stack)}")

            if not query_parts:
                logger.warning("No preferences provided for company suggestions")
                return []

            query = " ".join(query_parts)
            logger.info(f"Generating company suggestions for query: {query}")

            # Perform similarity search
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k
            )

            # Build suggestions list
            suggestions = []
            for doc, score in results:
                company_id = doc.metadata.get('company_id')
                if not company_id:
                    continue

                # Fetch full company data from database
                company = self.db.query(Company).filter(Company.id == company_id).first()
                if not company:
                    continue

                suggestion = {
                    'id': company.id,
                    'name': company.name,
                    'industries': company.industries,
                    'verticals': company.verticals,
                    'size': company.size,
                    'stage': company.stage,
                    'tech_stack': company.tech_stack,
                    'description': company.description,
                    'headquarters': company.headquarters,
                    'website': company.website,
                    'relevance_score': float(score)
                }
                suggestions.append(suggestion)

            logger.info(f"Generated {len(suggestions)} company suggestions")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating company suggestions: {e}", exc_info=True)
            return []

    def get_company_by_name(self, name: str) -> Optional[Company]:
        """
        Get a company by name.

        Args:
            name: Company name

        Returns:
            Company model or None
        """
        return self.db.query(Company).filter(Company.name.ilike(f"%{name}%")).first()

    def list_companies(
        self,
        industry: Optional[str] = None,
        size: Optional[str] = None,
        stage: Optional[str] = None,
        limit: int = 100
    ) -> List[Company]:
        """
        List companies with optional filtering.

        Args:
            industry: Filter by industry
            size: Filter by company size
            stage: Filter by company stage
            limit: Maximum number of results

        Returns:
            List of Company models
        """
        query = self.db.query(Company)

        # Note: JSON contains filtering in SQLite is limited
        # For better filtering, consider using raw SQL or filtering in Python

        if size:
            query = query.filter(Company.size == size)

        if stage:
            query = query.filter(Company.stage == stage)

        companies = query.limit(limit).all()

        # Filter by industry in Python (since JSON filtering is complex in SQLite)
        if industry:
            companies = [c for c in companies if c.industries and industry.lower() in [i.lower() for i in c.industries]]

        return companies
