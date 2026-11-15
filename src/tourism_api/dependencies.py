"""Dépendances FastAPI partagées par les routes."""
import secrets
from typing import Annotated
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from tourism_agent.prompts.prompts import STAYS_PROPOSAL_PROMPT_DICT
from .schemas import ChatRequest
from .services.agent_service import AgentService


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Clé d'accès à l'API.")

def verify_api_key(request: Request, api_key: str | None = Security(api_key_header)) -> None:
    """Exige la clé d'API configurée (API_KEY) ; aucune vérification si elle n'est pas définie."""
    # A chaque requête :
    # - FastAPI appelle verify_api_key, mais pas directement. Il lit la signature de la fonction et voit que api_key dépend de Security(api_key_header).
    # - Il appelle alors api_key_header(request). APIKeyHeader est un objet appelable (__call__) qui lit le header X-API-Key dans la requête et renvoie sa valeur, ou None s'il est absent, grâce à auto_error=False.
    # - Cette valeur est ensuite passée à verify_api_key dans le paramètre api_key.
    expected = request.app.state.settings.api_key
    if expected and not (api_key and secrets.compare_digest(api_key.encode(), expected.encode())):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Clé d'API absente ou invalide.")


def get_agent_service(request: Request) -> AgentService:
    """Renvoie l'AgentService créé au démarrage (app.state.agent_service)."""
    return request.app.state.agent_service


def validate_model(body: ChatRequest) -> ChatRequest:
    """Refuse un modèle sans prompt système (évite une ConfigurationError en plein run)."""
    if body.model_name and body.model_name not in STAYS_PROPOSAL_PROMPT_DICT:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Modèle non pris en charge : {body.model_name}. "
            f"Modèles disponibles : {', '.join(STAYS_PROPOSAL_PROMPT_DICT)}",
        )
    return body


ValidChatRequest = Annotated[ChatRequest, Depends(validate_model)]
