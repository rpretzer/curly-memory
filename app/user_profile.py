"""User profile management for content generation."""

from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models import UserProfile
from app.db import get_db_context


def get_user_profile(db: Session, profile_id: int = 1) -> Optional[UserProfile]:
    """Get the user profile (defaults to ID 1)."""
    return db.query(UserProfile).filter(UserProfile.id == profile_id).first()


def create_default_profile(
    name: str,
    email: Optional[str] = None,
    current_title: Optional[str] = None,
    target_titles: Optional[List[str]] = None,
    skills: Optional[List[str]] = None,
    resume_text: Optional[str] = None,
    target_companies: Optional[List[str]] = None,
    must_have_keywords: Optional[List[str]] = None,
    nice_to_have_keywords: Optional[List[str]] = None,
) -> UserProfile:
    """Create a default user profile."""
    with get_db_context() as db:
        profile = UserProfile(
            name=name,
            email=email,
            current_title=current_title,
            target_titles=target_titles or [],
            skills=skills or [],
            resume_text=resume_text,
            target_companies=target_companies or [],
            must_have_keywords=must_have_keywords or [],
            nice_to_have_keywords=nice_to_have_keywords or [],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile


def get_profile_dict(profile_id: int = 1) -> Dict:
    """Get user profile as a dictionary for LLM prompts."""
    with get_db_context() as db:
        profile = get_user_profile(db, profile_id)
        if not profile:
            return {}
        
        return {
            "name": profile.name,
            "email": profile.email,
            "current_title": profile.current_title,
            "target_titles": profile.target_titles or [],
            "skills": profile.skills or [],
            "experience_summary": profile.experience_summary,
            "resume_text": profile.resume_text,
            "resume_bullet_points": profile.resume_bullet_points or [],
            "target_companies": profile.target_companies or [],
            "must_have_keywords": profile.must_have_keywords or [],
            "nice_to_have_keywords": profile.nice_to_have_keywords or [],
            "linkedin_url": profile.linkedin_url,
            "portfolio_url": profile.portfolio_url,
            "github_url": profile.github_url,
        }
