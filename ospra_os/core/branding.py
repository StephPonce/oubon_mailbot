from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Branding(BaseSettings):
    """Brand configuration for OspraOS-facing applications."""

    OS_BRAND: str = Field(default="OspraOS")
    COMPANY_BRAND: str = Field(default="Ospra LLC")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )


@lru_cache(maxsize=1)
def get_branding() -> Branding:
    return Branding()
