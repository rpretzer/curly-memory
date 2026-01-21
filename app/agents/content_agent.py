"""Agent for generating tailored content using LLMs."""

import logging
import html
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.models import Job
from app.config import config
from app.user_profile import get_profile_dict
from app.agents.log_agent import LogAgent

logger = logging.getLogger(__name__)

# Optional RAG integration
try:
    from app.rag.service import JobRAGService
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("RAG module not available, content generation will use basic approach")


class ContentGenerationAgent:
    """Agent responsible for generating tailored resume, cover letter, and application content."""
    
    def __init__(
        self,
        db: Session,
        log_agent: Optional[LogAgent] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        profile_id: int = 1,
        use_rag: bool = True,
        rag_service: Optional[Any] = None,
    ):
        """
        Initialize the content generation agent.
        
        Args:
            db: Database session
            log_agent: Optional log agent for structured logging
            llm_config: Optional LLM configuration override
            profile_id: User profile ID to use
            use_rag: Whether to use RAG for context retrieval (default: True)
            rag_service: Optional JobRAGService instance (will be created if not provided and use_rag=True)
        """
        self.db = db
        self.log_agent = log_agent
        self.agent_name = "ContentGenerationAgent"
        self.profile_id = profile_id
        
        # Check if RAG should be enabled
        rag_config = config.yaml_config.get("rag", {})
        self.use_rag = use_rag and rag_config.get("enabled", True) and RAG_AVAILABLE
        
        # Initialize RAG service if enabled
        self.rag_service = None
        if self.use_rag:
            try:
                if rag_service:
                    self.rag_service = rag_service
                else:
                    self.rag_service = JobRAGService(db=db)
                logger.info("RAG service initialized for ContentGenerationAgent")
            except Exception as e:
                logger.warning(f"Failed to initialize RAG service: {e}, falling back to basic generation")
                self.use_rag = False
        
        # Get LLM configuration
        default_llm = config.get_llm_defaults()
        llm_config = llm_config or {}
        
        self.llm_provider = llm_config.get("provider", default_llm.get("provider", "openai"))
        self.llm_model = llm_config.get("model", default_llm["model"])
        self.temperature = llm_config.get("temperature", default_llm["temperature"])
        self.top_p = llm_config.get("top_p", default_llm["top_p"])
        self.max_tokens = llm_config.get("max_tokens", default_llm["max_tokens"])
        self.ollama_base_url = llm_config.get("ollama_base_url", default_llm.get("ollama_base_url", "http://localhost:11434"))
        
        # Initialize LLM based on provider
        try:
            if self.llm_provider.lower() == "ollama":
                logger.info(f"Initializing Ollama LLM with model: {self.llm_model} at {self.ollama_base_url}")
                self.llm = ChatOllama(
                    model=self.llm_model,
                    temperature=self.temperature,
                    base_url=self.ollama_base_url,
                    num_predict=self.max_tokens,  # Ollama uses num_predict instead of max_tokens
                )
            else:
                # Default to OpenAI
                logger.info(f"Initializing OpenAI LLM with model: {self.llm_model}")
                if not config.llm.api_key and self.llm_provider.lower() == "openai":
                    logger.warning("OpenAI API key not found, but OpenAI provider selected")
                self.llm = ChatOpenAI(
                    model=self.llm_model,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens,
                    api_key=config.llm.api_key if config.llm.api_key else None,
                )
        except Exception as e:
            logger.error(f"Failed to initialize LLM ({self.llm_provider}): {e}")
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
            job_desc = html.unescape(job.description or job.raw_description or "No description available.")
            prompt = f"""Summarize this job posting in 2-3 sentences, highlighting:
1. Key responsibilities
2. Required qualifications
3. What makes this role unique

Job Title: {job.title}
Company: {job.company}
Location: {job.location}

Job Description:
{job_desc}
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
        Uses RAG to retrieve similar job descriptions for better context if enabled.
        
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
            
            # Build query for RAG retrieval if enabled
            similar_jobs_context = ""
            if self.use_rag and self.rag_service:
                try:
                    # Build query from job title and key requirements
                    query = f"{job.title} {job.company}"
                    if job.description:
                        # Extract first few sentences as query
                        sentences = job.description.split(".")[:2]
                        query += " " + ". ".join(sentences)
                    
                    # Retrieve similar jobs for context
                    similar_jobs = self.rag_service.retrieve_similar_jobs(
                        query=query,
                        job_id=job.id,
                        k=3,  # Get top 3 similar jobs
                    )
                    
                    if similar_jobs:
                        context_parts = []
                        for similar in similar_jobs[:2]:  # Use top 2
                            similar_job = similar.get("job")
                            if similar_job and similar_job.description:
                                context_parts.append(
                                    f"Similar Role: {similar_job.title} at {similar_job.company}\n"
                                    f"Requirements: {similar_job.description[:300]}..."
                                )
                        
                        if context_parts:
                            similar_jobs_context = "\n\nSimilar Job Requirements for Context:\n" + "\n\n".join(context_parts)
                            logger.debug(f"Retrieved {len(similar_jobs)} similar jobs for context")
                except Exception as e:
                    logger.warning(f"RAG retrieval failed for resume points: {e}, continuing without context")
            
            prompt_template = self.prompts.get("resume_summary", """
Generate 3-5 tailored bullet points for a resume based on the job description.
Focus on matching the job requirements with relevant experience.

Job Requirements:
{job_description}
{similar_jobs_context}

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
            
            job_desc = html.unescape(job.description or job.raw_description or "No description available.")
            prompt = prompt_template.format(
                job_description=job_desc,
                similar_jobs_context=similar_jobs_context,
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
            cover_letter_temp = config.get_llm_defaults().get("cover_letter_temperature", 0.7)
            if self.llm_provider.lower() == "ollama":
                temp_llm = ChatOllama(
                    model=self.llm_model,
                    temperature=cover_letter_temp,
                    base_url=self.ollama_base_url,
                    num_predict=self.max_tokens,
                )
            else:
                temp_llm = ChatOpenAI(
                    model=self.llm_model,
                    temperature=cover_letter_temp,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens,
                    api_key=config.llm.api_key if config.llm.api_key else None,
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
            
            job_desc = html.unescape(job.description or job.raw_description or "No description available.")
            prompt = prompt_template.format(
                job_title=job.title,
                company=job.company,
                job_description=job_desc[:1500],  # Increased context window
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
            job_desc = html.unescape(job.description or job.raw_description or "No description available.")
            for question in questions:
                prompt = prompt_template.format(
                    question=question,
                    job_title=job.title,
                    company=job.company,
                    job_description=job_desc[:500],
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
        run_id: Optional[int] = None,
        skip_existing: bool = True
    ) -> Job:
        """
        Generate all content for a job and update the job record.
        
        Args:
            job: Job to generate content for
            run_id: Optional run ID for logging
            skip_existing: If True, skip generating content that already exists (efficiency)
            
        Returns:
            Updated Job model
        """
        logger.info(f"Generating content for job: {job.id} - {job.title}")
        
        errors = []
        content_generated = False
        
        # Check if LLM is available
        if not self.llm:
            error_msg = f"LLM not initialized (provider: {self.llm_provider})"
            logger.error(error_msg)
            if self.log_agent and run_id:
                self.log_agent.log_error(
                    agent_name=self.agent_name,
                    error=Exception(error_msg),
                    run_id=run_id,
                    job_id=job.id,
                    step="generate_all_content",
                )
            job.application_error = error_msg
            self.db.commit()
            return job
        
        # Generate summary (skip if already exists and skip_existing is True)
        if not skip_existing or not job.llm_summary:
            try:
                logger.debug(f"Generating summary for job {job.id} (existing: {bool(job.llm_summary)})")
                job.llm_summary = self.generate_summary(job, run_id)
                content_generated = True
            except Exception as e:
                logger.error(f"Error generating summary for job {job.id}: {e}", exc_info=True)
                errors.append(f"Summary generation failed: {str(e)}")
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        job_id=job.id,
                        step="generate_summary",
                    )
        else:
            logger.debug(f"Skipping summary generation for job {job.id} (already exists)")
        
        # Generate resume points (skip if already exists)
        if not skip_existing or not job.tailored_resume_points:
            try:
                logger.debug(f"Generating resume points for job {job.id} (existing: {bool(job.tailored_resume_points)})")
                job.tailored_resume_points = self.generate_resume_points(job, run_id)
                content_generated = True
            except Exception as e:
                logger.error(f"Error generating resume points for job {job.id}: {e}", exc_info=True)
                errors.append(f"Resume points generation failed: {str(e)}")
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        job_id=job.id,
                        step="generate_resume_points",
                    )
        else:
            logger.debug(f"Skipping resume points generation for job {job.id} (already exists)")
        
        # Generate cover letter (skip if already exists)
        if not skip_existing or not job.cover_letter_draft:
            try:
                logger.debug(f"Generating cover letter for job {job.id} (existing: {bool(job.cover_letter_draft)})")
                job.cover_letter_draft = self.generate_cover_letter(job, run_id)
                content_generated = True
            except Exception as e:
                logger.error(f"Error generating cover letter for job {job.id}: {e}", exc_info=True)
                errors.append(f"Cover letter generation failed: {str(e)}")
                if self.log_agent and run_id:
                    self.log_agent.log_error(
                        agent_name=self.agent_name,
                        error=e,
                        run_id=run_id,
                        job_id=job.id,
                        step="generate_cover_letter",
                    )
        else:
            logger.debug(f"Skipping cover letter generation for job {job.id} (already exists)")
        
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
