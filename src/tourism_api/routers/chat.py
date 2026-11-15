"""Échanges avec l'agent : réponse complète ou diffusée en Server-Sent Events."""
import json
import logging
from typing import Annotated
from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from tourism_agent.exceptions import TourismAgentError
from ..services.agent_service import AgentService
from ..dependencies import ValidChatRequest, get_agent_service
from ..schemas import ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
# Depends(fonction) dit à FastAPI : « pour remplir ce paramètre, appelle cette fonction et donne-moi son résultat »
async def chat(body: ValidChatRequest,
               service: Annotated[AgentService,Depends(get_agent_service)]
) -> ChatResponse:
    """Envoie un message et renvoie la réponse de l'agent avec l'état de la conversation."""
    return await service.chat(body.thread_id, body.message, body.model_name)


@router.post("/stream", response_class=EventSourceResponse)
# Depends(fonction) dit à FastAPI : « pour remplir ce paramètre, appelle cette fonction et donne-moi son résultat »
async def chat_stream(body: ValidChatRequest,
                      service: Annotated[AgentService, Depends(get_agent_service)]
) -> EventSourceResponse:
    """Envoie un message et diffuse la réponse (événements status, token, final, error)."""

    async def events():
        try:
            async for event, data in service.chat_stream(body.thread_id, body.message, body.model_name):
                yield {"event": event, "data": json.dumps(data, ensure_ascii=False)}
        except TourismAgentError as e:
            logger.exception("Erreur de l'agent pendant le streaming")
            yield {"event": "error", "data": json.dumps({"detail": str(e)}, ensure_ascii=False)}
        except Exception:
            # Le statut HTTP est déjà parti : l'erreur est signalée dans le flux
            logger.exception("Erreur inattendue pendant le streaming")
            yield {"event": "error", "data": json.dumps({"detail": "Erreur interne de l'agent."})}

    return EventSourceResponse(events())
