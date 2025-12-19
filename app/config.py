"""Configuration management for the job search pipeline."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml


class LLMConfig(BaseSettings):
    """LLM configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    api_key: str = Field(..., validation_alias="OPENAI_API_KEY")
    model: str = Field(default="gpt-4-turbo-preview", env="LLM_MODEL")
    temperature: float = Field(default=0.7, env="LLM_TEMPERATURE")
    top_p: float = Field(default=1.0, env="LLM_TOP_P")
    max_tokens: int = Field(default=2000, env="LLM_MAX_TOKENS")


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    url: str = Field(default="sqlite:///./job_pipeline.db", env="DATABASE_URL")


class PlaywrightConfig(BaseSettings):
    """Playwright browser automation configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    enabled: bool = Field(default=True, env="ENABLE_PLAYWRIGHT")
    headless: bool = Field(default=True, env="PLAYWRIGHT_HEADLESS")


class APIConfig(BaseSettings):
    """API server configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    host: str = Field(default="0.0.0.0", env="API_HOST")
    port: int = Field(default=8000, env="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:3000", 
        env="CORS_ORIGINS"
    )


class Config:
    """Main configuration class that loads from YAML and environment."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration from YAML file and environment variables."""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        
        # Load YAML config if it exists
        if config_path.exists():
            with open(config_path, "r") as f:
                self.yaml_config = yaml.safe_load(f) or {}
        else:
            self.yaml_config = {}
        
        # Load environment-based configs
        self.llm = LLMConfig()
        self.database = DatabaseConfig()
        self.playwright = PlaywrightConfig()
        self.api = APIConfig()
        
        # Job source API keys
        self.linkedin_api_key = os.getenv("LINKEDIN_API_KEY", "")
        self.indeed_api_key = os.getenv("INDEED_API_KEY", "")
        self.wellfound_api_key = os.getenv("WELLFOUND_API_KEY", "")
        
        # LinkedIn credentials for authenticated scraping
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL", "")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD", "")
        
        # Third-party scraping API keys
        self.scrapeops_api_key = os.getenv("SCRAPEOPS_API_KEY", "")
        self.hasdata_api_key = os.getenv("HASDATA_API_KEY", "")
        self.apify_api_key = os.getenv("APIFY_API_KEY", "")
        self.mantiks_api_key = os.getenv("MANTIKS_API_KEY", "")
        
        # Feature flags
        self.human_in_the_loop = os.getenv("HUMAN_IN_THE_LOOP", "true").lower() == "true"
        self.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        
        # LangSmith
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
        self.langsmith_project = os.getenv("LANGSMITH_PROJECT", "job-search-pipeline")
    
    def get_search_config(self) -> Dict:
        """Get search configuration from YAML."""
        return self.yaml_config.get("search", {})
    
    def get_scoring_config(self) -> Dict:
        """Get scoring configuration from YAML."""
        return self.yaml_config.get("scoring", {})
    
    def get_verticals(self) -> List[str]:
        """Get target verticals list."""
        return self.yaml_config.get("verticals", [])
    
    def get_thresholds(self) -> Dict:
        """Get scoring thresholds."""
        return self.yaml_config.get("thresholds", {})
    
    def get_llm_defaults(self) -> Dict:
        """Get LLM defaults from YAML, merged with env config."""
        yaml_llm = self.yaml_config.get("llm", {})
        return {
            "model": yaml_llm.get("model", self.llm.model),
            "temperature": yaml_llm.get("temperature", self.llm.temperature),
            "top_p": yaml_llm.get("top_p", self.llm.top_p),
            "max_tokens": yaml_llm.get("max_tokens", self.llm.max_tokens),
        }
    
    def get_job_sources_config(self) -> Dict:
        """Get job sources configuration."""
        return self.yaml_config.get("job_sources", {})
    
    def get_feature_flags(self) -> Dict:
        """Get feature flags."""
        yaml_flags = self.yaml_config.get("features", {})
        return {
            "enable_playwright": yaml_flags.get("enable_playwright", True),
            "enable_auto_apply": yaml_flags.get("enable_auto_apply", False),
            "enable_content_generation": yaml_flags.get("enable_content_generation", True),
            "enable_email_notifications": yaml_flags.get("enable_email_notifications", False),
        }
    
    def get_scheduler_config(self) -> Dict:
        """Get scheduler configuration."""
        return self.yaml_config.get("scheduler", {})
    
    def get_content_prompts(self) -> Dict:
        """Get content generation prompts."""
        return self.yaml_config.get("content_prompts", {})


# Global config instance
config = Config()
