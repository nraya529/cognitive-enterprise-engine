from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str

    extraction_model: str = "claude-opus-4-7"
    verification_model: str = "claude-sonnet-4-6"
    communications_model: str = "claude-sonnet-4-6"
    prospecting_model: str = "claude-sonnet-4-6"

    max_self_heal_attempts: int = 3
    fuzzy_match_threshold: int = 85

    database_url: str = "sqlite+aiosqlite:///./nexus_growth.db"

    tavily_api_key: str | None = None
    tavily_base_url: str = "https://api.tavily.com"
    tavily_search_depth: str = "advanced"

    resend_api_key: str | None = None
    resend_base_url: str = "https://api.resend.com"
    outbound_from_email: str = "Outbound <outreach@example.com>"
    outbound_reply_to_email: str | None = None
    outbound_daily_send_limit: int = 25
    outbound_run_send_limit: int = 10
    outbound_blocked_domains: str = "gmail.com,yahoo.com,hotmail.com,outlook.com,aol.com"

    default_prospecting_niche: str = "regional logistics companies"
    default_prospecting_geography: str = "New England"
    default_prospecting_max_results: int = 10
    minimum_qualification_score: float = 0.68

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    @property
    def blocked_domain_set(self) -> set[str]:
        return {
            domain.strip().lower()
            for domain in self.outbound_blocked_domains.split(",")
            if domain.strip()
        }


settings = Settings()
