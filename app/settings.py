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

    # AI Providers
    openai_api_key: str = ""
    claude_api_key: str = ""  # Anthropic Claude API key

    # Other services
    database_url: str = "sqlite+aiosqlite:///./data/mailbot.db"
    slack_webhook_url: str = ""

    # Shopify
    SHOPIFY_API_TOKEN: str = ""
    SHOPIFY_STORE: str = ""          # e.g., "oubonshop.myshopify.com"
    SHOPIFY_MODE: str = "safe"       # "safe" or "live"

    # Google Cloud Pub/Sub (for Gmail push notifications)
    GOOGLE_CLOUD_PROJECT_ID: str = ""     # Your GCP project ID
    GMAIL_PUBSUB_TOPIC: str = "gmail-notifications"  # Pub/Sub topic name

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env variables
    )

def get_settings() -> "Settings":
    return Settings()
