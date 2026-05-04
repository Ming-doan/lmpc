from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    jwt_secret: str
    session_cookie_name: str = "llmbench_session"
    session_ttl_hours: int = 24
    worker_secret: str
    hf_token: str = ""
    log_format: str = "console"  # "json" in prod

settings = Settings()
