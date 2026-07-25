from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    GOOGLE_API_KEY: str = ""         # legacy / ya no usado en el agente
    GROQ_API_KEY: str = ""           # fallback LLM: llama-3.3-70b-versatile (free tier)
    CEREBRAS_API_KEY: str = ""       # primary LLM: gpt-oss-120b (cloud.cerebras.ai)
    OPENAI_API_KEY: str = ""        # embeddings RAG (text-embedding-3-small)
    VOYAGE_API_KEY: str = ""        # embeddings RAG (voyage-multilingual-2, free tier)
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""          # nombre que usa Vercel
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SENTINEL_CLIENT_ID: Optional[str] = None
    SENTINEL_CLIENT_SECRET: Optional[str] = None
    GEE_CREDENTIALS_PATH: Optional[str] = None
    GEE_CLIENT_EMAIL: Optional[str] = None
    GEE_PRIVATE_KEY_B64: Optional[str] = None
    GEE_PROJECT_ID: Optional[str] = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",          # ignora variables de Vercel que no usamos
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
