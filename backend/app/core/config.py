from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """ORBITGUARD AI application configuration settings."""
    
    PROJECT_NAME: str = "ORBITGUARD AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*"
    ]
    
    # MongoDB Atlas settings
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "orbitguard"
    
    # External data sources
    CELESTRAK_BASE_URL: str = "https://celestrak.org/NORAD/elements/gp.php"
    AUTO_SYNC_ENABLED: bool = True
    AUTO_SYNC_INTERVAL_HOURS: float = 12.0
    AUTO_SYNC_GROUPS: List[str] = ["stations", "fengyun-1c-debris"]
    
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

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
