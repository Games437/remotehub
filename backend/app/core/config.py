"""
Central configuration. All values are read from environment variables so the
same image can be deployed to dev/staging/prod without code changes.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General -------------------------------------------------------
    APP_NAME: str = "RemoteHub"
    ENV: str = "development"

    # --- Database --------------------------------------------------------
    DATABASE_URL: str = "postgresql+psycopg://remotehub:remotehub@postgres:5432/remotehub"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """
        Managed Postgres providers (Render, Railway, Heroku, ...) hand out
        connection strings starting with postgres:// or postgresql://, but
        our SQLAlchemy engine needs the psycopg3 driver explicitly named
        (postgresql+psycopg://) — otherwise SQLAlchemy tries to load
        psycopg2, which isn't installed. Rewrite it automatically so no one
        has to remember to hand-edit the DATABASE_URL env var per platform.
        """
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://") and "+psycopg" not in v.split("://", 1)[0]:
            v = v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    # --- Redis (optional cache / pub-sub for scaling websockets) --------
    REDIS_URL: str = "redis://redis:6379/0"
    USE_REDIS: bool = False

    # --- JWT (Layer 2) ---------------------------------------------------
    JWT_SECRET: str = "CHANGE_ME_dev_only_secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Agent tokens (Layer 3) ------------------------------------------
    AGENT_SECRET_BYTES: int = 32  # 256-bit secret per agent

    # --- Device pairing (Layer 4) ----------------------------------------
    PAIR_CODE_TTL_SECONDS: int = 600  # pairing code valid for 10 minutes

    # --- Command signature (Layer 5) --------------------------------------
    COMMAND_TIMESTAMP_SKEW_SECONDS: int = 30  # reject if timestamp drifts more than this
    COMMAND_NONCE_TTL_SECONDS: int = 300      # how long we remember a nonce, to reject replays

    # --- Rate limiting (Layer 8) -------------------------------------------
    RATE_LIMIT_PER_MINUTE: int = 20

    # --- CORS --------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()