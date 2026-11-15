"""Contrat d'échange de l'API (corps des requêtes et des réponses)."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, Field, StringConstraints
# Même limite que la garde d'entrée du graphe (variable d'environnement MAX_USER_MESSAGE_LENGTH)
from tourism_agent.services.input_validation import MAX_USER_MESSAGE_LENGTH

# Classe représentant une requête de chat
class ChatRequest(BaseModel):
    thread_id: UUID = Field(description="Identifiant de la conversation (POST /threads).",
                            examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_USER_MESSAGE_LENGTH)
    ] = Field(description="Message du client (espaces de début et de fin retirés).",
              examples={"je recherche un séjour à la montagne"})
    model_name: str | None = Field(default=None, description="Modèle à utiliser (défaut : MODEL_NAME).",
                                   examples=["gemini-3.5-flash-lite"])

# Classe représentant un critère de séjour détecté
class CriterionOut(BaseModel):
    criterion: str = Field(description="Identifiant technique du type de séjour (ex. « plage »).")
    label: str = Field(description="Libellé lisible du type de séjour.")
    avis: bool | None = Field(description="True souhaité, False à éviter, None non mentionné.")
    justification: str | None = None

# Classe représentant un séjour détecté
class StayOut(BaseModel):
    nom: str
    match: str = Field(description="« parfait » ou « partiel ».")
    score: str = Field(description="Critères satisfaits / critères souhaités (ex. « 2/3 »).")

# Classe représentant l'état d'une conversation (thread)
class ThreadState(BaseModel):
    criteria: list[CriterionOut] = []
    travel_period: str | None = None
    matching_stays: list[StayOut] = []

# Classe représentant la réponse à une requête de chat
class ChatResponse(ThreadState):
    thread_id: UUID
    answer: str

# Classe représentant la création d'un thread (conversation)
class ThreadCreated(BaseModel):
    thread_id: UUID

# Classe représentant un message sortant (du système vers le client)
class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str

# Classe représentant le statut de santé de l'API
class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    checkpointer: str | None = None
