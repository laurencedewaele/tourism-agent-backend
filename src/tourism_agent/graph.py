"""Graphe de l'agent de tourisme : assemblage uniquement (nœuds et conditions sont dans leurs modules)."""
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import tools_condition
from .schemas.context import Context
from .schemas.state import State
from .nodes.analyze_preferences_node import analyze_preferences_node
from .nodes.filter_matching_stays_node import filter_matching_stays_node
from .nodes.respond_with_proposal_node import respond_with_proposal_node
from .nodes.proposal_tools_node import proposal_tools_node
from .nodes.ask_for_details_node import ask_for_details_node
from .nodes.reject_input_node import reject_input_node
from .conditions.input_condition import input_condition
from .conditions.staytype_condition import staytype_condition

# Construction du graphe
workflow = StateGraph(State, context_schema=Context)

workflow.add_node("analyze_preferences", analyze_preferences_node)
workflow.add_node("filter_matching_stays", filter_matching_stays_node)
workflow.add_node("respond_with_proposal", respond_with_proposal_node)
workflow.add_node("tools", proposal_tools_node)
workflow.add_node("ask_for_details", ask_for_details_node)
workflow.add_node("reject_input", reject_input_node)

# Définition des transitions
workflow.add_conditional_edges(
    START,
    input_condition,
    {
        "valid_input": "analyze_preferences",
        "invalid_input": "reject_input"
    }
)
workflow.add_conditional_edges(
    "analyze_preferences",
    staytype_condition,
    {
        "criteria_detected": "filter_matching_stays",
        "need_details": "ask_for_details"
    }
)

workflow.add_edge("filter_matching_stays", "respond_with_proposal")
# Le modèle peut demander un outil (disponibilités) : exécution puis retour à la proposition
workflow.add_conditional_edges(
    "respond_with_proposal",
    tools_condition,
    {
        "tools": "tools",
        END: END
    }
)
workflow.add_edge("tools", "respond_with_proposal")
workflow.add_edge("ask_for_details", END)
workflow.add_edge("reject_input", END)


# Types propres à l'agent stockés dans l'état, donc dans les points de sauvegarde : ils doivent
# être explicitement autorisés à la désérialisation (bloqués sinon dans les versions à venir)
CHECKPOINT_ALLOWED_TYPES = [
    ("tourism_agent.schemas.criteria", "StayType"),
    ("tourism_agent.schemas.criteria", "CriterionOpinion"),
    ("tourism_agent.schemas.criteria", "CriteriaIdentificationResult"),
]


def checkpoint_serializer() -> JsonPlusSerializer:
    """Sérialiseur des checkpointers, limité aux types sûrs et à ceux de l'agent."""
    return JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_ALLOWED_TYPES)


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Compile le graphe, avec un checkpointer pour persister les conversations (API FastAPI)."""
    return workflow.compile(checkpointer=checkpointer)


# Graphe sans checkpointer pour `langgraph dev` / LangSmith Studio, qui gèrent eux-mêmes la persistance
graph = build_graph()
