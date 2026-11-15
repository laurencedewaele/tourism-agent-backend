"""Protection des routes /api/v1 par la clé d'API (en-tête X-API-Key)."""
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from tourism_agent.graph import checkpoint_serializer
from tourism_api.config import get_settings
from tourism_api.main import create_app

API_KEY = "cle-de-test"


@pytest.fixture
def secured_client(fake_model):
    settings = get_settings().model_copy(update={"api_key": API_KEY})
    app = create_app(checkpointer=InMemorySaver(serde=checkpoint_serializer()), settings=settings)
    with TestClient(app) as client:
        yield client


def test_missing_or_wrong_key_is_rejected(secured_client) -> None:
    assert secured_client.post("/api/v1/threads").status_code == 401
    response = secured_client.post("/api/v1/threads", headers={"X-API-Key": "mauvaise"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Clé d'API absente ou invalide."


def test_valid_key_is_accepted(secured_client) -> None:
    headers = {"X-API-Key": API_KEY}
    thread_id = secured_client.post("/api/v1/threads", headers=headers).json()["thread_id"]
    response = secured_client.post(
        "/api/v1/chat", headers=headers, json={"thread_id": thread_id, "message": "La plage"}
    )
    assert response.status_code == 200


def test_probes_stay_open(secured_client) -> None:
    # Le frontend interroge /ready sans clé pour détecter le réveil du backend
    assert secured_client.get("/health").status_code == 200
    assert secured_client.get("/ready").status_code == 200
