"""Gestion des conversations (threads) persistées par le checkpointer."""
from uuid import UUID, uuid4
from typing import Annotated
from fastapi import APIRouter, HTTPException, status, Depends
from ..services.agent_service import AgentService
from ..dependencies import get_agent_service
from ..schemas import MessageOut, ThreadCreated, ThreadState

router = APIRouter(prefix="/threads", tags=["threads"])

NOT_FOUND = "Conversation introuvable."


@router.post("", response_model=ThreadCreated, status_code=status.HTTP_201_CREATED)
async def create_thread() -> ThreadCreated:
    """Crée un identifiant de conversation (la conversation est enregistrée au premier message)."""
    return ThreadCreated(thread_id=uuid4())


@router.get("/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(thread_id: UUID, service: Annotated[AgentService, Depends(get_agent_service)]) -> list[MessageOut]:
    """Historique visible de la conversation (sans les échanges avec les outils)."""
    messages = await service.get_messages(thread_id)
    if messages is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return messages


@router.get("/{thread_id}/state", response_model=ThreadState)
async def get_state(thread_id: UUID, service: Annotated[AgentService, Depends(get_agent_service)]) -> ThreadState:
    """Critères identifiés, période souhaitée et séjours correspondants."""
    state = await service.get_state(thread_id)
    if state is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return state


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(thread_id: UUID, service: Annotated[AgentService, Depends(get_agent_service)]) -> None:
    """Supprime la conversation et tous ses points de sauvegarde."""
    await service.delete_thread(thread_id)
