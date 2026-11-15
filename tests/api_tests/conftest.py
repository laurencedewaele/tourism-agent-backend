"""Fixtures des tests d'API : application avec checkpointer en mémoire et modèle simulé."""
import json
from itertools import repeat

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from sse_starlette.sse import AppStatus

from tourism_agent.graph import checkpoint_serializer
from tourism_agent.nodes import analyze_preferences_node as analyze_module
from tourism_agent.nodes import respond_with_proposal_node as proposal_module
from tourism_agent.schemas.criteria import CriteriaIdentificationResult, CriterionOpinion, StayType
from tourism_api.main import create_app

PROPOSAL = "Je vous propose Palavas de paillotes en paillotes, au bord de la mer."
BEACH_CRITERIA = CriteriaIdentificationResult(
    criteria=[CriterionOpinion(criterion=StayType.BEACH, avis=True, justification="Veut la plage")],
    travel_period="août",
)


class FakeAgentModel(GenericFakeChatModel):
    """Modèle simulé : analyse fixe des préférences et proposition diffusée mot à mot."""

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        return RunnableLambda(lambda _: BEACH_CRITERIA)


@pytest.fixture
def fake_model(monkeypatch):
    # Un nouveau message à chaque appel (un même id serait remplacé par add_messages)
    model = FakeAgentModel(messages=(AIMessage(content=PROPOSAL) for _ in repeat(None)))
    for module in (analyze_module, proposal_module):
        monkeypatch.setattr(module, "get_model", lambda model_name, **kwargs: model)
    return model


@pytest.fixture
def client(fake_model):
    # sse-starlette garde un Event global lié à la première boucle : on le réinitialise
    AppStatus.should_exit_event = None
    with TestClient(create_app(checkpointer=InMemorySaver(serde=checkpoint_serializer()))) as test_client:
        yield test_client


@pytest.fixture
def thread_id(client) -> str:
    return client.post("/api/v1/threads").json()["thread_id"]


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """Découpe un flux SSE en (événement, données JSON)."""
    events = []
    for block in body.replace("\r\n", "\n").strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.split("\n") if ": " in line)
        if "event" in fields:
            events.append((fields["event"], json.loads(fields.get("data", "{}"))))
    return events
