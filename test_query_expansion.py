"""
Test script for HyDE query expansion implementation.

Usage:
    python test_query_expansion.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from app.rag.hyde import QueryExpansion, HyDEQueryTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_query_expansion():
    """Test QueryExpansion class."""
    logger.info("Testing QueryExpansion...")

    # Test with expansion enabled
    expander = QueryExpansion(expand_terms=True)

    test_queries = [
        "software engineer",
        "machine learning jobs",
        "remote product manager positions"
    ]

    for query in test_queries:
        logger.info(f"\nOriginal query: {query}")
        expanded = expander.expand_query(query)
        logger.info(f"Expanded query: {expanded}")
        logger.info(f"Length increase: {len(query)} -> {len(expanded)} chars")

def test_hyde():
    """Test HyDE query transformation."""
    logger.info("\n\nTesting HyDE Query Transformation...")

    hyde = HyDEQueryTransformer(use_hyde=True)

    query = "What are the best practices for API design?"
    logger.info(f"\nOriginal query: {query}")

    transformed = hyde.transform_query(query)
    logger.info(f"\nHyDE document generated ({len(transformed)} chars):")
    logger.info(transformed)

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Query Expansion and HyDE Implementation")
    print("=" * 60)

    test_query_expansion()
    test_hyde()

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
