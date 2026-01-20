"""Application Templates for common job application questions."""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models import Job, UserProfile
from app.user_profile import get_user_profile

logger = logging.getLogger(__name__)


@dataclass
class QuestionTemplate:
    """Template for a common application question."""
    patterns: List[str]  # Regex patterns to match the question
    template: str        # Template with {placeholders}
    required_fields: List[str]  # Required profile fields


# Common application questions and templates
# Templates use placeholders that are populated from profile data or config defaults
QUESTION_TEMPLATES = [
    # Work Authorization
    QuestionTemplate(
        patterns=[
            r"authorized.*work.*(?:us|united states)",
            r"work.*authorization",
            r"legally.*work.*(?:us|united states)",
            r"eligible.*work.*(?:us|united states)",
        ],
        template="{work_authorization_response}",
        required_fields=["work_authorization_response"]
    ),
    # Visa Sponsorship
    QuestionTemplate(
        patterns=[
            r"require.*sponsorship",
            r"need.*visa.*sponsorship",
            r"require.*work.*visa",
        ],
        template="{visa_sponsorship_response}",
        required_fields=["visa_sponsorship_response"]
    ),

    # Availability / Start Date
    QuestionTemplate(
        patterns=[
            r"(?:when|how soon).*(?:start|available|begin)",
            r"earliest.*start.*date",
            r"availability",
            r"notice.*period",
        ],
        template="{notice_period_response}",
        required_fields=["notice_period_response"]
    ),

    # Salary Expectations
    QuestionTemplate(
        patterns=[
            r"salary.*expectation",
            r"desired.*salary",
            r"compensation.*expectation",
            r"salary.*requirement",
            r"expected.*compensation",
        ],
        template="{salary_response}",
        required_fields=["salary_response"]
    ),

    # Remote Work
    QuestionTemplate(
        patterns=[
            r"willing.*(?:remote|work from home|wfh)",
            r"comfortable.*remote",
            r"remote.*work.*preference",
            r"(?:hybrid|onsite|in-office).*requirement",
        ],
        template="{remote_response}",
        required_fields=["remote_response"]
    ),

    # Relocation
    QuestionTemplate(
        patterns=[
            r"willing.*relocate",
            r"open.*relocation",
            r"relocation.*preference",
        ],
        template="{relocation_response}",
        required_fields=["relocation_response"]
    ),

    # Why this company
    QuestionTemplate(
        patterns=[
            r"why.*(?:interested|apply|join|work).*(?:company|organization|us)",
            r"what.*attract.*(?:company|role|position)",
            r"why.*want.*work.*here",
        ],
        template="I am excited about {company}'s mission and the opportunity to contribute to {job_title}. The role aligns well with my experience in {skills}, and I am particularly drawn to the company's commitment to innovation and growth.",
        required_fields=["skills"]
    ),

    # Why this role
    QuestionTemplate(
        patterns=[
            r"why.*(?:interested|apply).*(?:role|position)",
            r"what.*interest.*(?:role|position)",
            r"why.*this.*(?:job|opportunity)",
        ],
        template="This {job_title} role is an excellent match for my background in {skills}. I am particularly excited about the opportunity to {experience_summary}",
        required_fields=["skills", "experience_summary"]
    ),

    # Experience with specific technology/skill
    QuestionTemplate(
        patterns=[
            r"(?:years|experience).*(?:with|using|in).*(?:python|java|sql|aws|cloud|agile|scrum)",
            r"proficiency.*(?:python|java|sql|aws|cloud)",
        ],
        template="I have extensive experience with the technologies mentioned, having used them throughout my career. Specifically, {experience_summary}",
        required_fields=["experience_summary"]
    ),

    # Leadership experience
    QuestionTemplate(
        patterns=[
            r"(?:leadership|management|team lead).*experience",
            r"managed.*(?:team|people|direct reports)",
            r"supervisory.*experience",
        ],
        template="Yes, I have leadership experience. {experience_summary}",
        required_fields=["experience_summary"]
    ),

    # Strengths
    QuestionTemplate(
        patterns=[
            r"(?:greatest|top|key).*strength",
            r"what.*strength.*bring",
        ],
        template="My key strengths include strategic thinking, cross-functional collaboration, and data-driven decision making. I excel at {skills} and have a proven track record of delivering results.",
        required_fields=["skills"]
    ),

    # Challenge/Weakness
    QuestionTemplate(
        patterns=[
            r"(?:weakness|challenge|area.*improvement)",
            r"what.*work.*on",
        ],
        template="I continuously work on improving my skills in emerging areas. Currently, I am focused on deepening my expertise in {growth_focus} and staying current with industry best practices.",
        required_fields=[]
    ),

    # LinkedIn profile
    QuestionTemplate(
        patterns=[
            r"linkedin.*(?:url|profile|link)",
        ],
        template="{linkedin_url}",
        required_fields=["linkedin_url"]
    ),

    # Portfolio/Website
    QuestionTemplate(
        patterns=[
            r"portfolio.*(?:url|link|website)",
            r"personal.*(?:website|site)",
            r"github.*(?:url|profile)",
        ],
        template="{portfolio_url}",
        required_fields=["portfolio_url"]
    ),

    # How did you hear about us
    QuestionTemplate(
        patterns=[
            r"how.*(?:hear|learn|find).*(?:about|us|position|role|job)",
            r"where.*(?:find|see).*(?:job|position|posting)",
        ],
        template="I discovered this opportunity through {source} while researching companies in the {company} space.",
        required_fields=[]
    ),

    # Cover letter
    QuestionTemplate(
        patterns=[
            r"cover.*letter",
            r"letter.*introduction",
            r"why.*should.*hire",
        ],
        template="{cover_letter}",
        required_fields=["cover_letter"]
    ),
]


class ApplicationTemplateManager:
    """
    Manages application templates and generates answers for common questions.
    Falls back to LLM for unmatched questions when enabled.
    """

    def __init__(self, db: Session, enable_llm_fallback: bool = True):
        """
        Initialize the template manager.

        Args:
            db: Database session
            enable_llm_fallback: Whether to use LLM for unmatched questions
        """
        self.db = db
        self.templates = QUESTION_TEMPLATES
        self._compiled_patterns: Dict[int, List[re.Pattern]] = {}
        self.enable_llm_fallback = enable_llm_fallback
        self._llm = None  # Lazy initialization

        # Compile regex patterns
        for i, template in enumerate(self.templates):
            self._compiled_patterns[i] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in template.patterns
            ]

    def _get_llm(self):
        """Lazy initialize LLM for fallback answers."""
        if self._llm is None:
            try:
                from app.config import config

                llm_defaults = config.get_llm_defaults()
                provider = llm_defaults.get("provider", "ollama")

                if provider.lower() == "ollama":
                    from langchain_community.chat_models import ChatOllama
                    self._llm = ChatOllama(
                        model=llm_defaults.get("model", "llama3.2"),
                        temperature=0.7,
                        base_url=llm_defaults.get("ollama_base_url", "http://localhost:11434"),
                    )
                else:
                    from langchain_openai import ChatOpenAI
                    self._llm = ChatOpenAI(
                        model=llm_defaults.get("model", "gpt-4o-mini"),
                        temperature=0.7,
                        api_key=config.llm.api_key if config.llm.api_key else None,
                    )
            except Exception as e:
                logger.warning(f"Failed to initialize LLM for fallback: {e}")
                self._llm = None
        return self._llm

    def _generate_llm_answer(
        self,
        question: str,
        job: Optional[Job] = None,
        profile: Optional[UserProfile] = None,
    ) -> Optional[str]:
        """
        Generate an answer using LLM when no template matches.

        Args:
            question: The application question
            job: Optional job for context
            profile: User profile for personalization

        Returns:
            Generated answer or None if LLM fails
        """
        if not self.enable_llm_fallback:
            return None

        try:
            from langchain_core.messages import HumanMessage
            from app.user_profile import get_profile_dict

            llm = self._get_llm()
            if not llm:
                return None

            # Build context
            profile_dict = get_profile_dict(profile.id if profile else 1)
            job_context = ""
            if job:
                job_context = f"""
Job Context:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location or 'Not specified'}
"""

            skills_str = ', '.join(profile_dict.get('skills', [])[:10]) if profile_dict.get('skills') else 'various technical and professional skills'
            experience = profile_dict.get('experience_summary', '')[:300] if profile_dict.get('experience_summary') else ''

            prompt = f"""You are helping a job applicant answer an application question.
Generate a concise, professional answer (50-100 words) based on their profile.

{job_context}

Candidate Profile:
- Name: {profile_dict.get('name', 'Candidate')}
- Current Title: {profile_dict.get('current_title', 'Professional')}
- Skills: {skills_str}
- Experience: {experience}

Question: {question}

Provide a direct, professional answer that demonstrates relevant experience and enthusiasm.
Do not include any preamble like "Here is my answer:" - just provide the answer directly.
"""

            response = llm.invoke([HumanMessage(content=prompt)])
            answer = response.content.strip()

            logger.info(f"Generated LLM fallback answer for question: {question[:50]}...")
            return answer

        except Exception as e:
            logger.error(f"Error generating LLM fallback answer: {e}")
            return None

    def find_matching_template(self, question: str) -> Optional[QuestionTemplate]:
        """
        Find a template that matches the given question.

        Args:
            question: The application question

        Returns:
            Matching template or None
        """
        question_lower = question.lower().strip()

        for i, template in enumerate(self.templates):
            patterns = self._compiled_patterns[i]
            for pattern in patterns:
                if pattern.search(question_lower):
                    return template

        return None

    def generate_answer(
        self,
        question: str,
        job: Optional[Job] = None,
        profile: Optional[UserProfile] = None,
        custom_values: Optional[Dict[str, str]] = None,
        use_llm_fallback: bool = True,
    ) -> Optional[str]:
        """
        Generate an answer for a question using templates and profile data.
        Falls back to LLM for unmatched questions when enabled.

        Args:
            question: The application question
            job: Optional job for context
            profile: Optional user profile (fetched if not provided)
            custom_values: Optional custom placeholder values
            use_llm_fallback: Whether to use LLM if no template matches

        Returns:
            Generated answer or None if no answer could be generated
        """
        template = self.find_matching_template(question)

        # Get profile if not provided
        if profile is None:
            profile = get_user_profile(self.db, profile_id=1)

        # Try template-based answer first
        if template:
            # Build placeholder values
            values = self._build_placeholder_values(job, profile, custom_values)

            # Check required fields
            missing_fields = [
                field for field in template.required_fields
                if not values.get(field)
            ]

            if missing_fields:
                logger.warning(f"Missing required fields for template: {missing_fields}")
                # Still try to generate with available fields

            # Fill in template
            try:
                answer = template.template.format(**values)
                return answer.strip()
            except KeyError as e:
                logger.warning(f"Missing placeholder in template: {e}")
                # Fall through to LLM fallback

        # No template match or template failed - try LLM fallback
        if use_llm_fallback and self.enable_llm_fallback:
            logger.info(f"No template match for question, trying LLM fallback: {question[:50]}...")
            return self._generate_llm_answer(question, job, profile)

        return None

    def _build_placeholder_values(
        self,
        job: Optional[Job],
        profile: Optional[UserProfile],
        custom_values: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        """Build dictionary of placeholder values from job, profile, and config defaults.

        Priority order:
        1. Custom values (highest)
        2. Profile fields
        3. Config defaults (lowest)
        """
        from app.config import config

        values = {}
        defaults = config.get_application_defaults()

        # Job-based values
        if job:
            values["job_title"] = job.title or "this role"
            values["company"] = job.company or "your company"
            values["source"] = job.source.value if job.source else "online job search"
            values["cover_letter"] = job.cover_letter_draft or ""

        # Profile-based values (basic contact info)
        if profile:
            values["name"] = profile.name or ""
            values["email"] = profile.email or ""
            values["phone"] = profile.phone or ""
            values["location"] = profile.location or ""
            values["linkedin_url"] = profile.linkedin_url or ""
            values["portfolio_url"] = profile.portfolio_url or profile.github_url or ""
            values["current_title"] = profile.current_title or ""
            values["experience_summary"] = profile.experience_summary or ""

            if profile.skills:
                values["skills"] = ", ".join(profile.skills[:5])  # Top 5 skills
            else:
                values["skills"] = "relevant skills"

            if profile.target_titles:
                values["target_titles"] = ", ".join(profile.target_titles)
            else:
                values["target_titles"] = "product management"

        # Application preference values: profile overrides config defaults
        # Work authorization
        work_auth = None
        if profile and profile.work_authorization:
            work_auth = profile.work_authorization
        else:
            work_auth = defaults.get("work_authorization", "Yes, I am authorized to work in the United States")
        values["work_authorization_response"] = work_auth

        # Visa sponsorship
        needs_sponsorship = False
        if profile and profile.visa_sponsorship_required is not None:
            needs_sponsorship = profile.visa_sponsorship_required
        else:
            needs_sponsorship = defaults.get("visa_sponsorship_required", False)

        if needs_sponsorship:
            values["visa_sponsorship_response"] = "Yes, I require visa sponsorship"
        else:
            values["visa_sponsorship_response"] = defaults.get(
                "visa_sponsorship_response",
                "No, I do not require visa sponsorship"
            )

        # Notice period / availability
        notice = None
        if profile and profile.notice_period:
            notice = profile.notice_period
        else:
            notice = defaults.get("notice_period", "2-3 weeks")
        notice_template = defaults.get(
            "notice_period_response",
            "I am available to start within {notice_period} of offer acceptance."
        )
        values["notice_period_response"] = notice_template.replace("{notice_period}", notice)

        # Salary
        salary_min = None
        salary_max = None
        if profile and profile.salary_min:
            salary_min = profile.salary_min
        else:
            salary_min = defaults.get("salary_range", {}).get("min", 115000)

        if profile and profile.salary_max:
            salary_max = profile.salary_max
        else:
            salary_max = defaults.get("salary_range", {}).get("max", 200000)

        salary_template = defaults.get("salary_range", {}).get(
            "response_template",
            "My salary expectation is in the range of ${salary_min}-${salary_max}, depending on the total compensation package and responsibilities."
        )
        # Format salary with commas
        values["salary_response"] = salary_template.replace(
            "{salary_min}", f"{salary_min:,}"
        ).replace(
            "{salary_max}", f"{salary_max:,}"
        ).replace(
            "${salary_min}", f"${salary_min:,}"
        ).replace(
            "${salary_max}", f"${salary_max:,}"
        )
        values["salary_min"] = str(salary_min)
        values["salary_max"] = str(salary_max)

        # Remote preference
        remote_pref = None
        if profile and profile.remote_preference:
            remote_pref = profile.remote_preference
        else:
            remote_pref = defaults.get("remote_preference", "flexible")
        values["remote_response"] = defaults.get(
            "remote_response",
            "Yes, I am comfortable working remotely and have extensive experience with remote collaboration. I am also open to hybrid arrangements if preferred."
        )
        values["remote_preference"] = remote_pref

        # Relocation
        reloc_pref = None
        if profile and profile.relocation_preference:
            reloc_pref = profile.relocation_preference
        else:
            reloc_pref = defaults.get("relocation_preference", "open to discussing")
        values["relocation_response"] = defaults.get(
            "relocation_response",
            "I am open to discussing relocation for the right opportunity."
        )
        values["relocation_preference"] = reloc_pref

        # Growth focus (for weakness/challenge question)
        values["growth_focus"] = defaults.get("growth_focus", "AI/ML applications")

        # Custom overrides (highest priority)
        if custom_values:
            values.update(custom_values)

        return values

    def generate_all_answers(
        self,
        questions: List[str],
        job: Optional[Job] = None,
        profile: Optional[UserProfile] = None,
        use_llm_fallback: bool = True,
    ) -> Dict[str, Optional[str]]:
        """
        Generate answers for multiple questions.

        Args:
            questions: List of questions
            job: Optional job for context
            profile: Optional user profile
            use_llm_fallback: Whether to use LLM for unmatched questions

        Returns:
            Dictionary mapping questions to answers
        """
        results = {}
        for question in questions:
            results[question] = self.generate_answer(
                question, job, profile, use_llm_fallback=use_llm_fallback
            )
        return results

    def get_field_values(
        self,
        job: Optional[Job] = None,
        profile: Optional[UserProfile] = None
    ) -> Dict[str, str]:
        """
        Get all field values for form filling.

        Useful for pre-filling standard form fields like name, email, phone, etc.

        Args:
            job: Optional job for context
            profile: Optional user profile

        Returns:
            Dictionary of field values
        """
        if profile is None:
            profile = get_user_profile(self.db, profile_id=1)

        values = self._build_placeholder_values(job, profile, None)

        # Add common form field mappings
        if profile:
            # Name variations
            if profile.name:
                name_parts = profile.name.split()
                values["first_name"] = name_parts[0] if name_parts else ""
                values["last_name"] = name_parts[-1] if len(name_parts) > 1 else ""
                values["full_name"] = profile.name

            # Add resume bullet points as a formatted string
            if profile.resume_bullet_points:
                values["resume_bullets"] = "\n".join(
                    f"• {point}" for point in profile.resume_bullet_points
                )

        return values

    def add_custom_template(
        self,
        patterns: List[str],
        template: str,
        required_fields: Optional[List[str]] = None
    ):
        """
        Add a custom question template.

        Args:
            patterns: Regex patterns to match
            template: Answer template with {placeholders}
            required_fields: Required profile fields
        """
        custom_template = QuestionTemplate(
            patterns=patterns,
            template=template,
            required_fields=required_fields or []
        )

        index = len(self.templates)
        self.templates.append(custom_template)
        self._compiled_patterns[index] = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in patterns
        ]

        logger.info(f"Added custom template with {len(patterns)} patterns")
