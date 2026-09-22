from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "HR Attendance + Payroll Management"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database (use postgresql+psycopg2://... with Supabase in production)
    DATABASE_URL: str = "sqlite:///./hrms.db"

    # Auth / Security
    JWT_SECRET: str = "CHANGE_ME_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    # eSSL/eTimeTrackLite
    ESSL_BASE_URL: str = "https://localhost/portal/api/essl/etimetracklite"
    ESSL_USERNAME: str = ""
    ESSL_PASSWORD: str = ""
    ESSL_API_KEY: str = ""
    ESSL_COMPANY_SHORT_NAME: str = ""
    ESSL_TIMEOUT_SECONDS: int = 30
    ESSL_SYNC_INTERVAL_SECONDS: int = 300
    ESSL_MOCK_MODE: bool = True

    # Device connector (local connector → cloud)
    DEVICE_CONNECTOR_API_KEY: str = "CHANGE_ME_connector_key"

    # Supabase (GoTrue auth sync)
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Company defaults
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    DEFAULT_LOP_POLICY: str = "WORKING_DAYS"
    DEFAULT_PF_RATE: float = 0.12
    DEFAULT_ESI_RATE_EMPLOYER: float = 0.0325
    DEFAULT_ESI_RATE_EMPLOYEE: float = 0.0075
    DEFAULT_ESI_THRESHOLD: float = 21000
    DEFAULT_PT_MAX: float = 200.0

    # Scheduling
    SCHEDULER_ENABLED: bool = True
    ATTENDANCE_PROCESS_INTERVAL_SECONDS: int = 900

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()