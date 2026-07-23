from typing import Optional
from pydantic_settings import BaseSettings,SettingsConfigDict
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

class env_settings(BaseSettings):
    OPENROUTER_API_KEY :str
    CLOUDFLARE_TOKEN :str
    CLOUDFLARE_ACCESS_KEY_ID :str
    CLOUDFLARE_SECRET_ACCESS_KEY_ID :str
    CLOUDFLARE_R2_ENDPOINT :str
    CLOUDFLARE_R2_BUCKET: str | None = None
    CLOUDFLARE_R2_PUBLIC_URL: str | None = None
    DATABASE_URL: str   # Fallback to SQLite if Supabase URL is not set
    REDIS_URL: str
    QDRANT_URL: str
    QDRANT_API_KEY: str | None = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None 

    model_config=SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

setting = env_settings()


model = OpenRouterModel(
    "deepseek/deepseek-v4-flash",
    provider=OpenRouterProvider(api_key=setting.OPENROUTER_API_KEY)
)

# model = OllamaModel(
#     'mistral:latest', provider=OllamaProvider(base_url='http://localhost:11434/v1')
# )
