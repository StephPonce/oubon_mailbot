sed -n '1,12p' app/settings.py

from dotenv import load_dotenv
load_dotenv(".env")  # force load env file into os.environ

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App
    app_host: str = "localhost"
    app_port: int = 8001
    app_debug: bool = True

    # Google
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8001/oauth2callback"
    google_scopes: str = "https://www.googleapis.com/auth/gmail.modify"
    google_credentials_file: str = ".secrets/credentials.json"
    google_token_file: str = ".secrets/gmail_token.json"

    # OpenAI / DB / Slack
    openai_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/mailbot.db"
    slack_webhook_url: str = ""

    # Shopify
    SHOPIFY_API_TOKEN: str = ""
    SHOPIFY_STORE: str = ""          # e.g., "oubonshop.myshopify.com"
    SHOPIFY_MODE: str = "safe"       # "safe" or "live"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

def get_settings() -> "Settings":
    return Settings()
