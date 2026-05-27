from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_TITLE: str = "Partner System"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/partner_db"
    SECRET_KEY: str = "dev-secret-key-change-me"
    SESSION_COOKIE_NAME: str = "partner_session"
    SESSION_MAX_AGE: int = 60 * 60 * 8
    SESSION_SAME_SITE: str = "lax"
    SESSION_HTTPS_ONLY: bool = False
    SQL_ECHO: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
