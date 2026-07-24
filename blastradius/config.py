"""
BlastRadius Configuration Module.

Loads runtime settings and environment variables (DataHub endpoint URL, auth token,
GitHub credentials, logging options).
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()


@dataclass
class Config:
    """
    Application runtime configuration settings loaded from environment variables.
    """
    datahub_gms_url: str = os.getenv("DATAHUB_GMS_URL", "http://localhost:8080")
    datahub_pat_token: str = os.getenv("DATAHUB_PAT_TOKEN", "")
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    environment: str = os.getenv("ENVIRONMENT", "PROD")
    max_lineage_depth: int = int(os.getenv("MAX_LINEAGE_DEPTH", "5"))
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    def validate(self) -> None:
        """
        Validates critical configuration parameters.
        """
        if not self.datahub_gms_url:
            raise ValueError("DATAHUB_GMS_URL environment variable must be set.")


# Global configuration instance singleton
config = Config()
