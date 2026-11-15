"""Configuration de l'API, lue dans les variables d'environnement (et le fichier .env).

Ce module charge le .env dès son import : `tourism_agent.schemas.context` lit MODEL_NAME
au moment de son propre import, il doit donc toujours être importé APRÈS ce module.
"""
from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Les variables déjà définies (Docker, CI) restent prioritaires sur le .env
load_dotenv()


class Settings(BaseSettings):
    # A l'instanciation, chaque champ est rempli avec la variable d'environnement du même nom, sans tenir compte de la casse
    model_config = SettingsConfigDict(extra="ignore")

    # MODEL_NAME (modèle par défaut) n'est pas ici : il est lu uniquement par l'agent
    # (tourism_agent.schemas.context) dans la variable d'environnement.
    openrouter_api_key: str
    # URL PostgreSQL du checkpointer ; vide → mémoire du processus (développement, tests)
    database_url: str | None = None
    database_pool_max_size: int = 10
    # Clé exigée dans l'en-tête X-API-Key des routes /api/v1 ; vide → API ouverte (développement)
    api_key: str | None = None
    # Origines autorisées (frontend), séparées par des virgules
    cors_origins: str = "http://localhost:7860"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
