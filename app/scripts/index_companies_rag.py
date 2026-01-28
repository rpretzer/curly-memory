"""Index companies in RAG vector store for semantic search."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db import get_db_context
from app.rag.company_service import CompanyRAGService


def index_companies():
    """Index all companies in the RAG vector store."""

    print("Indexing companies in RAG vector store...\n")

    with get_db_context() as db:
        # Initialize RAG service
        rag_service = CompanyRAGService(db=db)

        # Index all companies
        results = rag_service.index_all_companies()

        print(f"\n✓ Indexing completed")
        print(f"  - Total: {results['total']} companies")
        print(f"  - Success: {results['success']} companies")
        print(f"  - Failed: {results['failed']} companies")

        if results['errors']:
            print(f"\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")
            return False

        return True


if __name__ == "__main__":
    success = index_companies()
    sys.exit(0 if success else 1)
