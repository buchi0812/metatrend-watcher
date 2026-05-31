from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    line_channel_access_token: str | None = None
    line_user_id: str | None = None
    database_url: str = "sqlite:///./metatrend.db"
    app_timezone: str = "Asia/Tokyo"
    enable_scheduler: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
