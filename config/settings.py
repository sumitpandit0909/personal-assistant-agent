from pydantic import ConfigDict
from pydantic_settings import BaseSettings,SettingsConfigDict

class env_settings(BaseSettings):
    OPENROUTER_API_KEY :str
    CLOUDFLARE_TOKEN :str
    CLOUDFLARE_ACCESS_KEY_ID :str
    CLOUDFLARE_SECRET_ACCESS_KEY_ID :str
    CLOUDFLARE_R2_ENDPOINT :str
    CLOUDFLARE_R2_BUCKET: str | None = None
    CLOUDFLARE_R2_PUBLIC_URL: str | None = None

    model_config=SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

setting = env_settings()


