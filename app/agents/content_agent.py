"""Agent for generating tailored content using LLMs."""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.models import Job
from app.config import config
from app.user_profile import get_profile_dict
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)


class ContentGenerationAgent:
    """Agent responsible for generating tailored resume, cover letter, and application content."""
    
    def __init__(
        self,
        db: Session,
        log_agent: Optional[LogAgent] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        profile_id: int = 1
    ):
        """
        Initialize the content generation agent.
        
        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
            llm_config: Optional LLM configuration override
            profile_id: User profile ID to use
        """
        self.db = db
        self.log_agent = log_agent
        self.agent_name = "ContentGenerationAgent"
        self.profile_id = profile_id
        
        # Get LLM configuration
        default_llm = config.get_llm_defaults()
        llm_config = llm_config or {}
        
        self.llm_model = llm_config.get("model", default_llm["model"])
        self.temperature = llm_config.get("temperature", default_llm["temperature"])
        self.top_p = llm_config.get("top_p", default_llm["top_p"])
        self.max_tokens = llm_config.get("max_tokens", default_llm["max_tokens"])
        
        # Initialize LLM
        try:
            self.llm = ChatOpenAI(
                model=self.llm_model,
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                api_key=config.llm.api_key,
            )
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            self.llm = None
        
        # Get content prompts
        self.prompts = config.get_content_prompts()
    
    def generate_summary(
        self,
        job: Job,
        run_id: Optional[int] = None
    ) -> str:
        """
        Generate a summary of the job using LLM.
        
        Args:
            job: Job to summarize
            run_id: Optional run ID for logging
            
        Returns:
            Generated summary text
        """
        if not self.llm:
            return job.description[:500] if job.description else "No description available."
        
        try:
            prompt = f"""Summarize this job posting in 2-3 sentences, highlighting:
1. Key responsibilities
2. Required qualifications
3. What makes this role unique

Job Title: {job.title}
Company: {job.company}
Location: {job.location}

Job Description:
{job.description or job.raw_description or 'No description available.'}
"""
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
            
            # Log usage
            tokens_used = getattr(response, 'response_metadata', {}).get('token_usage', {}).get('total_tokens', 0)
            
            if self.log_agent and run_id:
                self.log_agent.log_content_generation(
                    run_id=run_id,
                    job_id=job.id,
                    content_type="summary",
                    llm_model=self.llm_model,
                    tokens_used=tokens_used,
                )
            
            return summary
        
        except Exception as e:
            logger.error(f"Error generating summary: {e}", exc_info=True)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=e,
                    run_id=run_id,
                    job_id=job.id,
                    step="generate_summary",
                )
            return job.description[:500] if job.description else "Error generating summary."
    
    def generate_resume_points(
        self,
        job: Job,
        run_id: Optional[int] = None
    ) -> List[str]:
        """
        Generate tailored resume bullet points for the job.
        
        Args:
            job: Job to tailor resume for
            run_id: Optional run ID for logging
            
        Returns:
            List of tailored bullet points
        """
        if not self.llm:
            return []
        
        try:
            profile = get_profile_dict(self.profile_id)
            
            prompt_template = self.prompts.get("resume_summary", """
Generate 3-5 tailored bullet points for a resume based on the job description.
Focus on matching the job requirements with relevant experience.

Job Requirements:
{job_description}

Candidate Profile:
- Current Title: {current_title}
- Skills: {skills}
- Experience: {experience_summary}

Generate bullet points that:
1. Match key job requirements
2. Highlight relevant experience
3. Use action verbs and quantify achievements when possible
4. Keep each bullet to 1-2 lines
"""
            )
            
            prompt = prompt_template.format(
                job_description=job.description or job.raw_description or "",
                current_title=profile.get("current_title", "Product Manager"),
                skills=", ".join(profile.get("skills", [])[:10]),
                experience_summary=profile.get("experience_summary", "") or profile.get("resume_text", "")[:500],
            )
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content.strip()
            
            # Parse bullet points
            bullet_points = [
                line.strip()[2:].strip()  # Remove "- " or "* "
                for line in content.split("\n")
                if line.strip().startswith("-") or line.strip().startswith("*") or line.strip().startswith("•")
            ]
            
            # If parsing failed, split by lines
            if not bullet_points:
                bullet_points = [line.strip() for line in content.split("\n") if line.strip()]
            
            tokens_used = getattr(response, 'response_metadata', {}).get('token_usage', {}).get('total_tokens', 0)
            
            if self.log_agent and run_id:
                self.log_agent.log_content_generation(
                    run_id=run_id,
                    job_id=job.id,
                    content_type="resume_points",
                    llm_model=self.llm_model,
                    tokens_used=tokens_used,
                )
            
            return bullet_points[:5]  # Limit to 5 points
        
        except Exception as e:
            logger.error(f"Error generating resume points: {e}", exc_info=True)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=e,
                    run_id=run_id,
                    job_id=job.id,
                    step="generate_resume_points",
                )
            return []
    
    def generate_cover_letter(
        self,
        job: Job,
        run_id: Optional[int] = None
    ) -> str:
        """
        Generate a tailored cover letter for the job.
        
        Args:
            job: Job to write cover letter for
            run_id: Optional run ID for logging
            
        Returns:
            Generated cover letter text
        """
        if not self.llm:
            return ""
        
        try:
            profile = get_profile_dict(self.profile_id)
            
            # Use specialized temperature for cover letters
            temp_llm = ChatOpenAI(
                model=self.llm_model,
                temperature=config.get_llm_defaults().get("cover_letter_temperature", 0.7),
                top_p=self.top_p,
                max_tokens=self.max_tokens,
                api_key=config.llm.api_key,
            )
            
            prompt_template = self.prompts.get("cover_letter_template", """
Write a professional cover letter for this position.
Keep it concise (200-300 words) and highlight relevant experience.

Job:
Title: {job_title}
Company: {company}
Description: {job_description}

Candidate:
Name: {name}
Current Title: {current_title}
Skills: {skills}
Experience Summary: {experience_summary}

Write a compelling cover letter that:
1. Expresses genuine interest in the role
2. Highlights 2-3 most relevant experiences/skills
3. Shows understanding of the company/role
4. Ends with a call to action
"""
            )
            
            prompt = prompt_template.format(
                job_title=job.title,
                company=job.company,
                job_description=(job.description or job.raw_description or "")[:1000],
                name=profile.get("name", "Candidate"),
                current_title=profile.get("current_title", ""),
                skills=", ".join(profile.get("skills", [])[:10]),
                experience_summary=profile.get("experience_summary", "") or (profile.get("resume_text", "")[:500] if profile.get("resume_text") else ""),
            )
            
            response = temp_llm.invoke([HumanMessage(content=prompt)])
            cover_letter = response.content.strip()
            
            tokens_used = getattr(response, 'response_metadata', {}).get('token_usage', {}).get('total_tokens', 0)
            
            if self.log_agent and run_id:
                self.log_agent.log_content_generation(
                    run_id=run_id,
                    job_id=job.id,
                    content_type="cover_letter",
                    llm_model=self.llm_model,
                    tokens_used=tokens_used,
                )
            
            return cover_letter
        
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}", exc_info=True)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=e,
                    run_id=run_id,
                    job_id=job.id,
                    step="generate_cover_letter",
                )
            return ""
    
    def generate_application_answers(
        self,
        job: Job,
        questions: List[str],
        run_id: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Generate answers to application questions.
        
        Args:
            job: Job being applied to
            questions: List of application questions
            run_id: Optional run ID for logging
            
        Returns:
            Dictionary mapping questions to generated answers
        """
        if not self.llm or not questions:
            return {}
        
        try:
            profile = get_profile_dict(self.profile_id)
            answers = {}
            
            prompt_template = self.prompts.get("application_answers", """
Generate a concise answer (50-100 words) to this application question
based on the job requirements and candidate profile.

Question: {question}

Job: {job_title} at {company}
Job Requirements: {job_description}

Candidate:
Skills: {skills}
Experience: {experience_summary}

Provide a direct, professional answer that demonstrates relevant experience.
"""
            )
            
            total_tokens = 0
            for question in questions:
                prompt = prompt_template.format(
                    question=question,
                    job_title=job.title,
                    company=job.company,
                    job_description=(job.description or "")[:500],
                    skills=", ".join(profile.get("skills", [])[:10]),
                    experience_summary=profile.get("experience_summary", "")[:300],
                )
                
                response = self.llm.invoke([HumanMessage(content=prompt)])
                answers[question] = response.content.strip()
                
                tokens = getattr(response, 'response_metadata', {}).get('token_usage', {}).get('total_tokens', 0)
                total_tokens += tokens
            
            if self.log_agent and run_id:
                self.log_agent.log_content_generation(
                    run_id=run_id,
                    job_id=job.id,
                    content_type="application_answers",
                    llm_model=self.llm_model,
                    tokens_used=total_tokens,
                )
            
            return answers
        
        except Exception as e:
            logger.error(f"Error generating application answers: {e}", exc_info=True)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=e,
                    run_id=run_id,
                    job_id=job.id,
                    step="generate_application_answers",
                )
            return {}
    
    def generate_all_content(
        self,
        job: Job,
        run_id: Optional[int] = None
    ) -> Job:
        """
        Generate all content for a job and update the job record.
        
        Args:
            job: Job to generate content for
            run_id: Optional run ID for logging
            
        Returns:
            Updated Job model
        """
        logger.info(f"Generating content for job: {job.id} - {job.title}")
        
        errors = []
        
        # Generate summary
        try:
            job.llm_summary = self.generate_summary(job, run_id)
        except Exception as e:
            logger.error(f"Error generating summary for job {job.id}: {e}", exc_info=True)
            errors.append(f"Summary generation failed: {str(e)}")
            job.llm_summary = job.description[:500] if job.description else "Summary generation failed."
        
        # Generate resume points
        try:
            job.tailored_resume_points = self.generate_resume_points(job, run_id)
        except Exception as e:
            logger.error(f"Error generating resume points for job {job.id}: {e}", exc_info=True)
            errors.append(f"Resume points generation failed: {str(e)}")
            job.tailored_resume_points = []
        
        # Generate cover letter
        try:
            job.cover_letter_draft = self.generate_cover_letter(job, run_id)
        except Exception as e:
            logger.error(f"Error generating cover letter for job {job.id}: {e}", exc_info=True)
            errors.append(f"Cover letter generation failed: {str(e)}")
            job.cover_letter_draft = ""
        
        # Update status - mark as generated (even if some parts failed, we have content)
        from app.models import JobStatus
        job.status = JobStatus.CONTENT_GENERATED
        if errors:
            logger.warning(f"Content generation completed with {len(errors)} errors for job {job.id}: {errors}")
            job.application_error = "; ".join(errors)
        else:
            job.application_error = None
        
        self.db.commit()
        self.db.refresh(job)
        
        return job
