"""API complète avec PostgreSQL et appels réels au LLM.

Nécessite DATABASE_URL, OPENROUTER_API_KEY et MODEL_NAME (ex. `docker compose up db`).
"""
import os

import pytest
from fastapi.testclient import TestClient

from tourism_api.main import create_app

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL non défini"),
]


def test_conversation_persisted_in_postgres() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/ready").json() == {"status": "ok", "checkpointer": "postgres"}
        thread_id = client.post("/api/v1/threads").json()["thread_id"]
        body = client.post("/api/v1/chat", json={
            "thread_id": thread_id,
            "message": "Je cherche un séjour sportif à la montagne en juillet 2027.",
        }).json()
        assert "Lozère" in body["answer"]

    # Nouvelle application (redémarrage) : la conversation est relue depuis PostgreSQL
    with TestClient(create_app()) as client:
        state = client.get(f"/api/v1/threads/{thread_id}/state").json()
        assert "juillet" in (state["travel_period"] or "").lower()
        assert client.delete(f"/api/v1/threads/{thread_id}").status_code == 204
