"""Agent for filtering and scoring job listings."""

import logging
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy.orm import Session

from app.jobsources.base import JobListing
from app.models import Job, JobStatus
from app.config import config
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)


class FilterAndScoreAgent:
    """Agent responsible for scoring and filtering job listings."""
    
    def __init__(
        self,
        db: Session,
        log_agent: Optional[LogAgent] = None,
        scoring_weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize the filter and score agent.
        
        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
            scoring_weights: Optional custom scoring weights (overrides config)
        """
        self.db = db
        self.log_agent = log_agent
        self.agent_name = "FilterAndScoreAgent"
        
        # Get scoring configuration
        default_weights = config.get_scoring_config()
        self.weights = scoring_weights or {
            "title_match": default_weights.get("title_match_weight", 8.0),
            "vertical_match": default_weights.get("vertical_match_weight", 6.0),
            "remote_preference": default_weights.get("remote_preference_weight", 5.0),
            "comp_match": default_weights.get("comp_match_weight", 7.0),
            "keyword_overlap": default_weights.get("keyword_overlap_weight", 6.0),
            "company_match": default_weights.get("company_match_weight", 5.0),
            "posting_recency": default_weights.get("posting_recency_weight", 3.0),
        }
        
        # Get thresholds
        thresholds = config.get_thresholds()
        self.min_score = thresholds.get("min_relevance_score", 5.0)
        self.high_score = thresholds.get("high_relevance_score", 8.0)
        
        # Get target verticals
        self.target_verticals = config.get_verticals()
    
    def score_job(
        self,
        job_listing: JobListing,
        target_titles: List[str],
        target_companies: Optional[List[str]] = None,
        must_have_keywords: Optional[List[str]] = None,
        nice_to_have_keywords: Optional[List[str]] = None,
        remote_preference: str = "any",  # remote, hybrid, on-site, any
        salary_min: Optional[int] = None,
        run_id: Optional[int] = None,
    ) -> Tuple[float, Dict[str, Any], str]:
        """
        Score a job listing based on various criteria.
        
        Args:
            job_listing: Job listing to score
            target_titles: List of target job titles
            target_companies: Optional list of target companies
            must_have_keywords: Optional list of must-have keywords
            nice_to_have_keywords: Optional list of nice-to-have keywords
            remote_preference: Remote preference (remote, hybrid, on-site, any)
            salary_min: Optional minimum salary requirement
            run_id: Optional run ID for logging
            
        Returns:
            Tuple of (score, breakdown_dict, reasoning_string)
        """
        breakdown = {}
        reasoning_parts = []
        
        # 1. Title match score (0-10)
        title_score = self._score_title_match(job_listing.title, target_titles)
        breakdown["title_match"] = title_score
        if title_score > 7:
            reasoning_parts.append(f"Strong title match ({title_score:.1f}/10)")
        elif title_score > 4:
            reasoning_parts.append(f"Partial title match ({title_score:.1f}/10)")
        
        # 2. Vertical match score (0-10)
        vertical_score = self._score_vertical_match(job_listing.description or "")
        breakdown["vertical_match"] = vertical_score
        if vertical_score > 6:
            reasoning_parts.append(f"Matches target verticals ({vertical_score:.1f}/10)")
        
        # 3. Remote preference score (0-10)
        remote_score = self._score_remote_preference(
            job_listing.location or "",
            remote_preference
        )
        breakdown["remote_preference"] = remote_score
        if remote_score > 7:
            reasoning_parts.append(f"Matches location preference ({remote_score:.1f}/10)")
        
        # 4. Compensation match score (0-10)
        comp_score = self._score_compensation(
            job_listing.salary_min,
            job_listing.salary_max,
            salary_min
        )
        breakdown["comp_match"] = comp_score
        if comp_score > 7:
            reasoning_parts.append(f"Compensation in range ({comp_score:.1f}/10)")
        elif job_listing.salary_min is None:
            reasoning_parts.append("No salary information available")
        
        # 5. Keyword overlap score (0-10)
        keyword_score = self._score_keyword_overlap(
            job_listing.description or "",
            job_listing.keywords or [],
            must_have_keywords or [],
            nice_to_have_keywords or [],
        )
        breakdown["keyword_overlap"] = keyword_score
        if keyword_score > 6:
            reasoning_parts.append(f"Good keyword match ({keyword_score:.1f}/10)")
        
        # 6. Company match score (0-10)
        company_score = 0.0
        if target_companies:
            company_score = self._score_company_match(
                job_listing.company,
                target_companies
            )
        breakdown["company_match"] = company_score
        if company_score > 7:
            reasoning_parts.append(f"Target company match ({company_score:.1f}/10)")
        
        # 7. Posting recency score (0-10)
        recency_score = self._score_posting_recency(job_listing.posting_date)
        breakdown["posting_recency"] = recency_score
        
        # Calculate weighted total score
        total_score = (
            title_score * self.weights["title_match"] +
            vertical_score * self.weights["vertical_match"] +
            remote_score * self.weights["remote_preference"] +
            comp_score * self.weights["comp_match"] +
            keyword_score * self.weights["keyword_overlap"] +
            company_score * self.weights["company_match"] +
            recency_score * self.weights["posting_recency"]
        )
        
        # Normalize to 0-10 scale
        total_weight = sum(self.weights.values())
        normalized_score = total_score / total_weight if total_weight > 0 else 0.0
        
        breakdown["total_score"] = normalized_score
        
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No specific matches identified"
        
        return normalized_score, breakdown, reasoning
    
    def _score_title_match(self, job_title: str, target_titles: List[str]) -> float:
        """Score title match (0-10)."""
        job_title_lower = job_title.lower()
        
        for target in target_titles:
            target_lower = target.lower()
            # Exact match
            if target_lower in job_title_lower or job_title_lower in target_lower:
                return 10.0
            # Partial match (keywords)
            target_words = set(target_lower.split())
            job_words = set(job_title_lower.split())
            common_words = target_words.intersection(job_words)
            if len(common_words) >= 2:
                return 8.0
            elif len(common_words) == 1:
                return 5.0
        
        return 0.0
    
    def _score_vertical_match(self, description: str) -> float:
        """Score vertical match based on target verticals (0-10)."""
        if not description or not self.target_verticals:
            return 0.0
        
        desc_lower = description.lower()
        matches = sum(1 for vertical in self.target_verticals if vertical.lower() in desc_lower)
        
        if matches >= 3:
            return 10.0
        elif matches == 2:
            return 7.0
        elif matches == 1:
            return 4.0
        else:
            return 0.0
    
    def _score_remote_preference(self, location: str, preference: str) -> float:
        """Score remote preference match (0-10)."""
        if preference == "any":
            return 5.0  # Neutral score
        
        location_lower = location.lower()
        is_remote = "remote" in location_lower or location_lower == ""
        
        if preference == "remote":
            return 10.0 if is_remote else 2.0
        elif preference == "on-site":
            return 2.0 if is_remote else 8.0
        elif preference == "hybrid":
            if "hybrid" in location_lower:
                return 10.0
            elif is_remote:
                return 6.0
            else:
                return 4.0
        else:
            return 5.0
    
    def _score_compensation(
        self,
        salary_min: Optional[int],
        salary_max: Optional[int],
        target_min: Optional[int]
    ) -> float:
        """Score compensation match (0-10)."""
        if salary_min is None or target_min is None:
            return 5.0  # Neutral if no data
        
        # Check if salary range meets minimum
        effective_min = salary_min
        if salary_max:
            # Use midpoint if range is provided
            effective_min = (salary_min + salary_max) / 2
        
        if effective_min >= target_min * 1.2:
            return 10.0
        elif effective_min >= target_min:
            return 8.0
        elif effective_min >= target_min * 0.9:
            return 6.0
        elif effective_min >= target_min * 0.8:
            return 4.0
        else:
            return 2.0
    
    def _score_keyword_overlap(
        self,
        description: str,
        job_keywords: List[str],
        must_have: List[str],
        nice_to_have: List[str]
    ) -> float:
        """Score keyword overlap (0-10)."""
        desc_lower = description.lower()
        all_keywords = set(job_keywords) | {w.lower() for w in desc_lower.split()}
        
        must_have_matches = sum(1 for kw in must_have if kw.lower() in desc_lower)
        nice_have_matches = sum(1 for kw in nice_to_have if kw.lower() in desc_lower)
        
        # Must-have keywords are critical
        if must_have:
            must_score = (must_have_matches / len(must_have)) * 7.0
        else:
            must_score = 0.0
        
        # Nice-to-have keywords add bonus
        if nice_to_have:
            nice_score = (nice_have_matches / len(nice_to_have)) * 3.0
        else:
            nice_score = 0.0
        
        return min(10.0, must_score + nice_score)
    
    def _score_company_match(self, company: str, target_companies: List[str]) -> float:
        """Score company match (0-10)."""
        company_lower = company.lower()
        for target in target_companies:
            if target.lower() in company_lower or company_lower in target.lower():
                return 10.0
        return 0.0
    
    def _score_posting_recency(self, posting_date: Optional[Any]) -> float:
        """Score posting recency (0-10)."""
        if posting_date is None:
            return 5.0  # Neutral if unknown
        
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        if isinstance(posting_date, str):
            # Try to parse date string
            try:
                from dateutil import parser
                posting_date = parser.parse(posting_date)
            except:
                return 5.0
        
        age_days = (now - posting_date).days
        
        if age_days <= 1:
            return 10.0
        elif age_days <= 7:
            return 8.0
        elif age_days <= 30:
            return 6.0
        elif age_days <= 60:
            return 4.0
        else:
            return 2.0
    
    def score_and_filter(
        self,
        job_listings: List[JobListing],
        target_titles: List[str],
        target_companies: Optional[List[str]] = None,
        must_have_keywords: Optional[List[str]] = None,
        nice_to_have_keywords: Optional[List[str]] = None,
        remote_preference: str = "any",
        salary_min: Optional[int] = None,
        run_id: Optional[int] = None,
    ) -> List[Job]:
        """
        Score multiple jobs and save them to the database.
        
        Returns list of Job models (only those above threshold).
        """
        scored_jobs = []
        
        for listing in job_listings:
            try:
                score, breakdown, reasoning = self.score_job(
                    listing,
                    target_titles=target_titles,
                    target_companies=target_companies,
                    must_have_keywords=must_have_keywords,
                    nice_to_have_keywords=nice_to_have_keywords,
                    remote_preference=remote_preference,
                    salary_min=salary_min,
                    run_id=run_id,
                )
                
                # Only keep jobs above threshold
                if score < self.min_score:
                    if self.log_agent and run_id:
                        self.log_agent.log(
                            agent_name=self.agent_name,
                            status="info",
                            message=f"Job below threshold: {score:.2f} < {self.min_score}",
                            run_id=run_id,
                            step="filter",
                            metadata={"score": score, "title": listing.title},
                        )
                    continue
                
                # Create or update Job record
                job = self.db.query(Job).filter(
                    Job.source_url == listing.source_url
                ).first()
                
                if not job:
                    job = Job(
                        run_id=run_id,
                        title=listing.title,
                        company=listing.company,
                        location=listing.location,
                        source=listing.source,
                        source_url=listing.source_url,
                        application_type=listing.application_type,
                        description=listing.description,
                        raw_description=listing.raw_description,
                        qualifications=listing.qualifications,
                        keywords=listing.keywords,
                        salary_min=listing.salary_min,
                        salary_max=listing.salary_max,
                        posting_date=listing.posting_date,
                        relevance_score=score,
                        scoring_breakdown=breakdown,
                        status=JobStatus.SCORED,
                    )
                    self.db.add(job)
                else:
                    # Update existing job
                    job.relevance_score = score
                    job.scoring_breakdown = breakdown
                    job.status = JobStatus.SCORED
                    if run_id:
                        job.run_id = run_id
                
                self.db.commit()
                self.db.refresh(job)
                
                # Log scoring
                if self.log_agent and run_id:
                    self.log_agent.log_scoring(
                        run_id=run_id,
                        job_id=job.id,
                        score=score,
                        breakdown=breakdown,
                        reasoning=reasoning,
                    )
                
                scored_jobs.append(job)
                
            except Exception as e:
                logger.error(f"Error scoring job: {e}", exc_info=True)
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        step="score_job",
                    )
        
        logger.info(f"Scored {len(scored_jobs)} jobs above threshold ({self.min_score})")
        return scored_jobs
