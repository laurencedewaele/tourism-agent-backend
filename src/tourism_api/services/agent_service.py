"""Exécution de l'agent pour un tour de conversation, en mode complet ou en streaming."""
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from tourism_agent.schemas.context import Context

from ..schemas import ChatResponse, MessageOut, ThreadState
from .mappers import last_answer, messages_to_out, state_to_out

logger = logging.getLogger(__name__)

# Nœud dont la réponse est diffusée token par token
STREAMED_NODE = "respond_with_proposal"

# Étapes annoncées au client pendant le traitement (événement SSE « status »)
NODE_STATUS = {
    "analyze_preferences": "Analyse de vos préférences…",
    "filter_matching_stays": "Recherche des séjours correspondants…",
    "tools": "Vérification des disponibilités…",
    "respond_with_proposal": "Rédaction de la proposition…",
}

class AgentService:
    """Façade de l'API sur le graphe compilé (avec checkpointer)."""

    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph

    @staticmethod # n'utilise pas l'état de l'instance
    def _config(thread_id: UUID) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(thread_id)}}

    # Fonction d'assemblage des arguments pour l'appel au graphe
    def _run_args(self, thread_id: UUID, message: str, model_name: str | None) -> dict[str, Any]:
        # Seul le nouveau message est envoyé : le checkpointer restitue l'historique
        # et le reducer add_messages l'ajoute à la conversation
        return {
            "input": {"messages": [HumanMessage(content=message)]},
            "config": self._config(thread_id),
            # Sans modèle demandé, Context applique le défaut (variable d'environnement MODEL_NAME)
            "context": Context(model_name=model_name) if model_name else Context(),
        }

    # Fonction de récupération de l'état du graphe pour un thread donné
    async def _values(self, thread_id: UUID) -> dict[str, Any]:
        snapshot = await self.graph.aget_state(self._config(thread_id))
        return snapshot.values or {}

    # Fonction d'encapsulation de la réponse finale du graphe
    async def _response(self, thread_id: UUID) -> ChatResponse:
        values = await self._values(thread_id)
        return ChatResponse(thread_id=thread_id, answer=last_answer(values),
                            **state_to_out(values).model_dump())

    # Fonction de conversation simple (un tour)
    async def chat(self, thread_id: UUID, message: str, model_name: str | None = None) -> ChatResponse:
        await self.graph.ainvoke(**self._run_args(thread_id, message, model_name))
        return await self._response(thread_id)

    # Fonction de conversation en streaming (un tour)
    async def chat_stream(
        self, thread_id: UUID, message: str, model_name: str | None = None
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Diffuse les événements (type, données) d'un tour de conversation.

        - « status » : étape en cours ; le client repart d'une réponse vide à chaque étape ;
        - « token » : fragment de la proposition rédigée par le modèle ;
        - « final » : réponse complète et état de la conversation (même contenu que /chat).
        """
        async for mode, chunk in self.graph.astream(
            **self._run_args(thread_id, message, model_name), stream_mode=["tasks", "messages"]
        ):
            if mode == "tasks":
                # Début de tâche : pas encore de clé « result »
                if "result" not in chunk and chunk.get("name") in NODE_STATUS:
                    yield "status", {"node": chunk["name"], "label": NODE_STATUS[chunk["name"]]}
            elif mode == "messages":
                message_chunk, metadata = chunk
                if (
                    metadata.get("langgraph_node") == STREAMED_NODE
                    and isinstance(message_chunk, AIMessageChunk)
                    and message_chunk.text
                ):
                    yield "token", {"content": message_chunk.text}
        final = await self._response(thread_id)
        yield "final", final.model_dump(mode="json")

    # Fonction de récupération de l'état d'un thread
    async def get_state(self, thread_id: UUID) -> ThreadState | None:
        values = await self._values(thread_id)
        return state_to_out(values) if values else None

    # Fonction de récupération des messages d'un thread
    async def get_messages(self, thread_id: UUID) -> list[MessageOut] | None:
        values = await self._values(thread_id)
        return messages_to_out(values.get("messages") or []) if values else None

    # Fonction de suppression d'un thread
    async def delete_thread(self, thread_id: UUID) -> None:
        await self.graph.checkpointer.adelete_thread(str(thread_id))
