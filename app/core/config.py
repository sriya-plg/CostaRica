from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    TENANT_ID: str
    CLIENT_ID: str
    CLIENT_SECRET: str
    MAILBOX: str = Field(validation_alias=AliasChoices("MAILBOX", "BOT_EMAIL"))
    NOTIFICATION_URL: str
    CLIENT_STATE: str
    DB_PATH: str = "data/processed_emails.db"
    SUBSCRIPTION_FILE: str = "data/subscription.json"
    LOG_DIR: str = "logs"
    APP_PORT: int = 8000


settings = Settings()
