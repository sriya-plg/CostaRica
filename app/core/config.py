from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TENANT_ID: str
    CLIENT_ID: str
    CLIENT_SECRET: str
    MAILBOX: str = Field(validation_alias=AliasChoices("MAILBOX", "BOT_EMAIL"))
    POLL_INTERVAL_SECONDS: int = 15
    INITIAL_LOOKBACK_HOURS: int = 48
    LOG_DIR: str = "logs"
    ATTACHMENTS_DIR: str = "downloads"
    TIMEZONE: str = "America/Chicago"
    CORE_DATA_BASE_URL: str = "https://plgtst.pegasuslogistics.com/api/orderentry"
    CORE_DATA_BILL_TO: int = 0
    AZURE_CONNECTION_STRING: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_CONNECTION_STRING", "AZURE_STORAGE_CONNECTION_STRING"),
    )
    AZURE_CONTAINER: str = Field(
        default="plgaiml1/cwdocs",
        validation_alias=AliasChoices("AZURE_CONTAINER", "AZURE_STORAGE_CONTAINER"),
    )

    @property
    def azure_container_name(self) -> str:
        return self.AZURE_CONTAINER.split("/")[-1].strip()


settings = Settings()
