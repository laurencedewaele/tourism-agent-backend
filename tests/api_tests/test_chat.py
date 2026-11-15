"""Routes /chat et /chat/stream (modèle simulé, sans réseau)."""
from .conftest import PROPOSAL, parse_sse

CHAT = "/api/v1/chat"


def test_health(client) -> None:
    assert client.get("/health").json() == {"status": "ok", "checkpointer": None}
    assert client.get("/ready").json() == {"status": "ok", "checkpointer": "memory"}


def test_chat_returns_answer_and_state(client, thread_id) -> None:
    response = client.post(CHAT, json={"thread_id": thread_id, "message": "Je veux aller à la plage"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == PROPOSAL
    assert body["travel_period"] == "août"
    assert [c["criterion"] for c in body["criteria"] if c["avis"]] == ["plage"]
    assert body["matching_stays"][0]["nom"] == "Palavas de paillotes en paillotes"


def test_conversation_is_persisted_across_turns(client, thread_id) -> None:
    for message in ("Je veux aller à la plage", "Et en août"):
        client.post(CHAT, json={"thread_id": thread_id, "message": message})
    messages = client.get(f"/api/v1/threads/{thread_id}/messages").json()
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[2]["content"] == "Et en août"


def test_message_too_long_is_rejected_by_api(client, thread_id) -> None:
    response = client.post(CHAT, json={"thread_id": thread_id, "message": "x" * 301})
    assert response.status_code == 422


def test_unknown_model_is_rejected(client, thread_id) -> None:
    response = client.post(CHAT, json={"thread_id": thread_id, "message": "plage", "model_name": "inconnu"})
    assert response.status_code == 422
    assert "inconnu" in response.json()["detail"]


def test_chat_stream_events(client, thread_id) -> None:
    with client.stream("POST", f"{CHAT}/stream", json={"thread_id": thread_id, "message": "La plage !"}) as response:
        assert response.status_code == 200
        events = parse_sse(response.read().decode("utf-8"))

    names = [name for name, _ in events]
    assert names[0] == "status" and names[-1] == "final"
    assert {"analyze_preferences", "filter_matching_stays", "respond_with_proposal"} <= {
        data["node"] for name, data in events if name == "status"
    }
    tokens = "".join(data["content"] for name, data in events if name == "token")
    assert tokens == PROPOSAL
    assert events[-1][1]["answer"] == PROPOSAL
