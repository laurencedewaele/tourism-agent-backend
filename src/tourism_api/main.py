"""Application FastAPI : cycle de vie (checkpointer, graphe), middlewares et routes."""
import logging
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from tourism_agent.exceptions import ConfigurationError, TourismAgentError
from tourism_agent.graph import build_graph, checkpoint_serializer

from .config import Settings, get_settings
from .dependencies import verify_api_key
from .routers import chat, health, threads
from .services.agent_service import AgentService

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"


async def open_postgres_checkpointer(stack: AsyncExitStack, app: FastAPI, settings: Settings) -> BaseCheckpointSaver:
    """Ouvre le pool de connexions et crée au besoin les tables du checkpointer."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    # Création du pool de connexions PostgreSQL
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        max_size=settings.database_pool_max_size,
        # Réglages requis par AsyncPostgresSaver
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False, # le pool n'est pas ouvert à la construction, car l'ouverture doit être "awaitée"
    )

    # Ouverture du pool
    await pool.open(wait=True, timeout=30)
    # On attend que les connexions soient établies, avec 30 secondes maximum. Sinon une erreur est levée et le démarrage échoue, ce qui évite de lancer une API sans base

    # Enregistrement de la fermeture du pool dans la pile de ressources à libérer
    stack.push_async_callback(pool.close)

    # Partage du pool de connexions dans l'état de l'application pour qu'il soit accessible ailleurs
    app.state.db_pool = pool

    # Création du checkpointer PostgreSQL avec sérialisation personnalisée
    checkpointer = AsyncPostgresSaver(pool, serde=checkpoint_serializer())

    # Initialisation du checkpointer (création des tables si nécessaire)
    await checkpointer.setup()

    return checkpointer


def create_app(checkpointer: BaseCheckpointSaver | None = None, settings: Settings | None = None) -> FastAPI:
    """Construit l'application.

    Args:
        checkpointer: checkpointer imposé (tests) ; sinon PostgreSQL si DATABASE_URL est
            défini, mémoire du processus à défaut.
        settings: configuration ; par défaut lue dans l'environnement.
    """
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

    @asynccontextmanager # transforme une fonction génératrice asynchrone (avec un seul yield) en un gestionnaire de contexte asynchrone, utilisable avec async with
    # Avant le yield : initialisation des ressources au démarrage du serveur (ex. : créer le graphe LangGraph, ouvrir une connexion à la base de données / checkpointer, charger la config).
    # Le yield : l'application tourne et traite les requêtes.
    # Après le yield : libération propre des ressources à l'arrêt (fermer les connexions, etc.).
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Gestion du cycle de vie de l'application (ouverture/fermeture des ressources)

        async with AsyncExitStack() as stack: # pile de ressources à fermer à l'arrêt
            # Choix du type de checkpointer à utiliser
            saver = checkpointer

            # Si aucun checkpointer n'est fourni, on choisit entre PostgreSQL et mémoire selon la config
            if saver is None and settings.database_url:
                # Création d'un pool de connexions PostgreSQL
                saver = await open_postgres_checkpointer(stack, app, settings)
                logger.info("Checkpointer PostgreSQL prêt")
            elif saver is None:
                saver = InMemorySaver(serde=checkpoint_serializer())
                logger.warning("DATABASE_URL absent : conversations conservées en mémoire uniquement")

            # Vérification de la présence de la clé API
            if not settings.api_key:
                logger.warning("API_KEY absent : l'API est accessible sans clé")

            # Initialisation du service agent avec le graphe construit et le modèle spécifié
            app.state.agent_service = AgentService(build_graph(saver))

            yield

    app = FastAPI(
        title="Tourism Agent API",
        version="0.1.0",
        description="Agent conversationnel de recherche de séjours (LangGraph).",
        lifespan=lifespan,
    )

    app.state.settings = settings
    # Le state va servir à partager des ressources uniques, créées une seule fois au démarrage, avec tous les handlers de l'API, sans variables globales
    # Ici il va contenir :
    # - settings : les paramètres de configuration (clé API, nom du modèle)
    # - db_pool : le pool de connexions PostgreSQL (si utilisé)
    # - agent_service : le service agent (AgentService) avec le graphe et le modèle spécifié

    # Création du middleware CORS pour gérer les requêtes cross-origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    # Gestionnaire d'exceptions pour les erreurs spécifiques à l'agent touristique
    @app.exception_handler(TourismAgentError)
    async def agent_error_handler(request: Request, exc: TourismAgentError) -> JSONResponse:
        logger.exception("Erreur de l'agent", exc_info=exc)
        # Choix dumessage renvoyé au client.
        # Pour une ConfigurationError (ex. clé API manquante), le vrai message de l'exception est exposé, ce qui aide à diagnostiquer.
        # Pour toute autre erreur de l'agent, un message générique est renvoyé, afin de ne pas divulguer de détails internes
        detail = str(exc) if isinstance(exc, ConfigurationError) else "Erreur interne de l'agent."
        return JSONResponse(status_code=500, content={"detail": detail})

    # Ajout des endpoints définis dans routers
    app.include_router(health.router)
    for router in (chat.router, threads.router):
        # Routes métier protégées par la clé d'API ; les sondes /health et /ready restent ouvertes
        app.include_router(router, prefix=API_PREFIX, dependencies=[Depends(verify_api_key)])
        # Les fonctions des dépendances sont appelées automatiquement par FastAPI à chaque requête HTTP avant l'exécution des routes.
    return app
