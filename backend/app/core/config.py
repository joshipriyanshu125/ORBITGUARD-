from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List, Union
import json


class Settings(BaseSettings):
    """ORBITGUARD AI application configuration settings."""
    
    PROJECT_NAME: str = "ORBITGUARD AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: Union[List[str], str] = [
        "https://orbitguard-one.vercel.app",
    ]
    
    # MongoDB Atlas settings
    MONGODB_URI: str = ""
    MONGODB_DB_NAME: str = "orbitguard"
    
    # External data sources
    CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements/gp.php"
    AUTO_SYNC_ENABLED: bool = False
    AUTO_SYNC_INTERVAL_HOURS: float = 12.0
    AUTO_SYNC_GROUPS: Union[List[str], str] = ["stations", "fengyun-1c-debris"]
    
    # AI / LLM Orchestration
    LLM_PROVIDER: str = "custom"
    LLM_BASE_URL: str = "https://platform.experientiallabs.ai/"
    LLM_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    
    # Cesium Token
    CESIUM_ION_TOKEN: str = ""
    
    # Safety Disclaimer
    SYSTEM_DISCLAIMER: str = (
        "ORBITGUARD AI provides analytical and illustrative orbital assessments based on "
        "publicly available TLE/OMM ephemeris data. This platform does not provide certified "
        "operational flight-dynamics commands. Explicit human-in-the-loop authorization is required "
        "for all recommended maneuvers."
    )

    @field_validator("CORS_ORIGINS", "AUTO_SYNC_GROUPS", mode="after")
    @classmethod
    def assemble_string_list(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip().rstrip("/") for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [origin.strip().rstrip("/") for origin in v.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(origin).strip().rstrip("/") for origin in v if str(origin).strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
