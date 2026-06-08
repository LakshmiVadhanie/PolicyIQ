"""
PolicyIQ — Application Configuration
Centralizes all environment-variable-based settings with
Pydantic Settings for validation and type safety.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    #  Google Cloud 
    gcp_project_id: str = "mock-project-id"
    gcp_region: str = "us-central1"
    gcp_location: str = "us-central1"

    #  Vertex AI 
    vertex_ai_model: str = "gemini-1.5-pro"
    google_application_credentials: str = ""

    #  BigQuery 
    bigquery_dataset: str = "policyiq_analytics"
    bigquery_interactions_table: str = "interactions"
    bigquery_metrics_table: str = "evaluation_metrics"
    bigquery_routing_table: str = "agent_routing_log"

    #  App 
    app_env: str = "development"
    log_level: str = "INFO"
    port: int = 8080

    #  Agent Config 
    supervisor_model: str = "gemini-1.5-pro"
    specialist_model: str = "gemini-1.5-flash"
    confidence_threshold: float = 0.75
    max_agent_iterations: int = 5

    #  RAGAS Quality Gates 
    ragas_faithfulness_threshold: float = 0.70
    ragas_relevancy_threshold: float = 0.70
    ragas_composite_threshold: float = 0.70

    #  Mock Flags (local dev without GCP) 
    use_mock_llm: bool = True
    use_mock_bigquery: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def bigquery_full_dataset(self) -> str:
        return f"{self.gcp_project_id}.{self.bigquery_dataset}"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
