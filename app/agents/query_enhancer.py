"""Query enhancement and validation for better search results."""

import logging
from typing import List, Optional, Set, Tuple
import re

logger = logging.getLogger(__name__)


class QueryEnhancer:
    """Enhances and validates search queries for better results."""
    
    # Generic terms that should be rejected or expanded
    GENERIC_TERMS = {
        'test', 'demo', 'sample', 'example', 'temp', 'temporary', 
        'placeholder', 'job', 'position', 'role', 'work'
    }
    
    # Common job title synonyms and expansions
    TITLE_SYNONYMS = {
        'pm': ['product manager', 'program manager', 'project manager'],
        'pm role': ['product manager', 'program manager'],
        'product': ['product manager', 'product owner', 'product lead'],
        'engineer': ['software engineer', 'engineer', 'engineering'],
        'developer': ['software developer', 'developer', 'software engineer'],
        'dev': ['developer', 'software developer', 'software engineer'],
        'qa': ['quality assurance', 'qa engineer', 'quality engineer', 'test engineer'],
        'swe': ['software engineer'],
        'sde': ['software development engineer', 'software engineer'],
        'ds': ['data scientist', 'data science'],
        'da': ['data analyst', 'data analytics'],
    }
    
    def __init__(self, min_query_length: int = 3):
        """
        Initialize query enhancer.
        
        Args:
            min_query_length: Minimum acceptable query length
        """
        self.min_query_length = min_query_length
    
    def validate_query(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Validate if a query is acceptable for searching.
        
        Args:
            query: Search query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query cannot be empty"
        
        query_stripped = query.strip()
        
        # Check minimum length
        if len(query_stripped) < self.min_query_length:
            return False, f"Query must be at least {self.min_query_length} characters"
        
        # Check if query is too generic
        query_lower = query_stripped.lower()
        query_words = set(query_lower.split())
        
        # If query is only generic terms, reject it
        if query_words.issubset(self.GENERIC_TERMS):
            return False, f"Query '{query}' is too generic. Please use a specific job title (e.g., 'Product Manager', 'Software Engineer')"
        
        # If query is a single generic word, reject it (be stricter)
        if len(query_words) == 1 and query_words.intersection(self.GENERIC_TERMS):
            generic_word = list(query_words.intersection(self.GENERIC_TERMS))[0]
            return False, f"Query '{query}' is too generic (single generic term: '{generic_word}'). Please use a specific job title (e.g., 'Product Manager', 'Software Engineer', 'Quality Assurance Engineer')"
        
        return True, None
    
    def enhance_query(self, query: str, keywords: Optional[List[str]] = None) -> str:
        """
        Enhance a query with synonyms, expansions, and keywords.
        
        Args:
            query: Original query
            keywords: Optional additional keywords to include
            
        Returns:
            Enhanced query string
        """
        if not query:
            return ""
        
        query_stripped = query.strip()
        query_lower = query_stripped.lower()
        
        # Expand common abbreviations and synonyms
        enhanced = query_stripped
        query_words = query_lower.split()
        
        # Expand single-word abbreviations
        if len(query_words) == 1 and query_words[0] in self.TITLE_SYNONYMS:
            expansions = self.TITLE_SYNONYMS[query_words[0]]
            # Use the first expansion (most common)
            enhanced = expansions[0].title() if expansions else enhanced
            logger.debug(f"Expanded query '{query}' to '{enhanced}'")
        # Expand multi-word abbreviations
        elif ' '.join(query_words[:2]) in self.TITLE_SYNONYMS:
            key = ' '.join(query_words[:2])
            expansions = self.TITLE_SYNONYMS[key]
            enhanced = expansions[0].title() + ' ' + ' '.join(query_words[2:])
            logger.debug(f"Expanded query '{query}' to '{enhanced}'")
        
        # Add keywords if provided
        if keywords:
            keyword_str = ' '.join(keywords[:3])  # Limit to top 3 keywords
            if keyword_str and keyword_str.lower() not in enhanced.lower():
                enhanced = f"{enhanced} {keyword_str}"
        
        return enhanced.strip()
    
    def build_search_query(
        self, 
        title: str, 
        keywords: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        remote: bool = False
    ) -> str:
        """
        Build an optimized search query from components.
        
        Args:
            title: Job title
            keywords: Optional keywords
            locations: Optional locations (for context, not search)
            remote: Whether this is a remote search
            
        Returns:
            Optimized search query
        """
        # Validate title
        is_valid, error = self.validate_query(title)
        if not is_valid:
            logger.warning(f"Invalid query '{title}': {error}")
            # Still return it but log warning
        
        # Enhance the title
        enhanced_title = self.enhance_query(title, keywords)
        
        # Build query - prioritize title, add keywords for context
        query_parts = [enhanced_title]
        
        if keywords:
            # Add top keywords that aren't already in the title
            title_lower = enhanced_title.lower()
            unique_keywords = [
                kw for kw in keywords[:3]
                if kw.lower() not in title_lower and len(kw) > 2
            ]
            if unique_keywords:
                query_parts.extend(unique_keywords[:2])  # Add top 2 unique keywords
        
        # Add remote indicator for context (some job boards use this)
        if remote:
            # Don't add "remote" to the query - it's handled separately
            pass
        
        return ' '.join(query_parts)
    
    def normalize_title(self, title: str) -> str:
        """
        Normalize a job title for consistent matching.
        
        Args:
            title: Job title to normalize
            
        Returns:
            Normalized title
        """
        # Remove extra whitespace
        normalized = ' '.join(title.split())
        
        # Capitalize properly (title case)
        # But preserve abbreviations like "QA", "PM", etc.
        words = normalized.split()
        normalized_words = []
        for word in words:
            word_upper = word.upper()
            # Preserve common abbreviations
            if word_upper in ['QA', 'PM', 'PMO', 'API', 'SDK', 'SRE', 'DevOps', 'ML', 'AI', 'DS', 'DA']:
                normalized_words.append(word_upper)
            elif word_upper in ['II', 'III', 'IV', 'JR', 'SR', 'SR.']:
                normalized_words.append(word_upper)
            else:
                normalized_words.append(word.capitalize())
        
        return ' '.join(normalized_words)


def enhance_search_queries(
    titles: List[str],
    keywords: Optional[List[str]] = None,
    min_query_length: int = 3
) -> List[str]:
    """
    Enhance a list of search titles.
    
    Args:
        titles: List of job titles to enhance
        keywords: Optional keywords to add
        min_query_length: Minimum query length
        
    Returns:
        List of enhanced titles
    """
    enhancer = QueryEnhancer(min_query_length=min_query_length)
    
    enhanced_titles = []
    for title in titles:
        is_valid, error = enhancer.validate_query(title)
        if not is_valid:
            logger.warning(f"Skipping invalid title '{title}': {error}")
            continue
        
        enhanced = enhancer.enhance_query(title, keywords)
        enhanced_titles.append(enhanced)
    
    return enhanced_titles if enhanced_titles else titles
