"""Conversion de l'état LangGraph vers les objets du contrat d'API."""
from typing import Any
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from tourism_agent.schemas.criteria import CriteriaIdentificationResult
from ..schemas import CriterionOut, MessageOut, StayOut, ThreadState

# Fonction de formatage des critères vers l'objet de sortie API
def criteria_to_out(criteria: CriteriaIdentificationResult | None) -> list[CriterionOut]:
    if not criteria or not criteria.criteria:
        return []
    return [
        CriterionOut(
            criterion=c.criterion.value,
            label=c.criterion.label,
            avis=c.avis,
            justification=c.justification,
        )
        for c in criteria.criteria
    ]


# Fonction de formatage de l'état du thread vers l'objet de sortie API
def state_to_out(values: dict[str, Any]) -> ThreadState:
    stays = [StayOut(**{k: str(stay.get(k, "")) for k in ("nom", "match", "score")})
             for stay in values.get("matching_stays") or []]
    return ThreadState(
        criteria=criteria_to_out(values.get("criteria")),
        travel_period=values.get("travel_period"),
        matching_stays=stays,
    )

# Fonction de filtrage des messages visibles par le client
def is_visible(message: BaseMessage) -> bool:
    """Messages montrés au client : ni résultats d'outil, ni demandes d'appel d'outil."""
    if isinstance(message, HumanMessage):
        return True
    return isinstance(message, AIMessage) and not message.tool_calls and bool(message.text)

# Fonction de conversion des messages en objets de sortie API
def messages_to_out(messages: list[BaseMessage]) -> list[MessageOut]:
    return [
        MessageOut(role="user" if isinstance(m, HumanMessage) else "assistant", content=m.text)
        for m in messages
        if is_visible(m)
    ]

# Fonction de récupération de la dernière réponse de l'agent
def last_answer(values: dict[str, Any]) -> str:
    """Dernière réponse de l'agent du tour écoulé."""
    for message in reversed(values.get("messages") or []):
        if isinstance(message, HumanMessage):
            # On ne remonte que jusqu'au dernier message humain, pas au tout début de la conversation
            break
        if is_visible(message):
            return message.text
    return ""
