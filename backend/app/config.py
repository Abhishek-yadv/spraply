from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "spraply API"
    app_description: str = "FastAPI backend for spraply"
    app_version: str = "1.0.0"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_lifetime_minutes: int = 5
    refresh_token_lifetime_days: int = 30

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/spraply"
    auto_create_tables: bool = False

    frontend_url: str = "http://localhost:5173"
    is_enterprise_mode_active: bool = False
    is_login_active: bool = True
    is_signup_active: bool = True
    is_github_login_active: bool = True
    is_google_login_active: bool = True
    github_client_id: str = ""
    google_client_id: str = ""
    google_analytics_id: str = ""

    max_crawl_concurrency: int = 16
    mcp_server: str = ""
    api_version: str = "1.0.0"
    policy_url: str = ""
    terms_url: str = ""


settings = Settings()
