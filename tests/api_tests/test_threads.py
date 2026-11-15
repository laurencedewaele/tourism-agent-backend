"""Routes /threads (modèle simulé, sans réseau)."""
import logging
from uuid import UUID, uuid4

from langgraph.checkpoint.serde import jsonplus

THREADS = "/api/v1/threads"


def test_create_thread(client) -> None:
    response = client.post(THREADS)
    assert response.status_code == 201
    UUID(response.json()["thread_id"])


def test_unknown_thread_returns_404(client) -> None:
    assert client.get(f"{THREADS}/{uuid4()}/state").status_code == 404
    assert client.get(f"{THREADS}/{uuid4()}/messages").status_code == 404


def test_state_after_chat(client, thread_id) -> None:
    client.post("/api/v1/chat", json={"thread_id": thread_id, "message": "Je veux aller à la plage"})
    state = client.get(f"{THREADS}/{thread_id}/state").json()
    assert state["travel_period"] == "août"
    assert any(c["criterion"] == "plage" and c["avis"] for c in state["criteria"])


def test_blank_message_is_rejected(client, thread_id) -> None:
    response = client.post("/api/v1/chat", json={"thread_id": thread_id, "message": "   "})
    assert response.status_code == 422
    assert client.get(f"{THREADS}/{thread_id}/state").status_code == 404


def test_delete_thread(client, thread_id) -> None:
    client.post("/api/v1/chat", json={"thread_id": thread_id, "message": "Je veux aller à la plage"})
    assert client.delete(f"{THREADS}/{thread_id}").status_code == 204
    assert client.get(f"{THREADS}/{thread_id}/state").status_code == 404


def test_state_types_are_allowed_by_checkpointer(client, thread_id, caplog, monkeypatch) -> None:
    # Les types de l'agent relus depuis le checkpointer doivent être explicitement autorisés.
    # LangGraph n'avertit qu'une fois par type et par processus : on vide ce mémo.
    monkeypatch.setattr(jsonplus, "_warned_unregistered_types", set())
    with caplog.at_level(logging.WARNING, logger="langgraph.checkpoint.serde"):
        client.post("/api/v1/chat", json={"thread_id": thread_id, "message": "Je veux aller à la plage"})
        client.get(f"{THREADS}/{thread_id}/state")
    assert "unregistered type" not in caplog.text
