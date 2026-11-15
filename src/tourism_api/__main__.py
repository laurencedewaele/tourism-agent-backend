"""Point d'entrée : `uv run python -m tourism_api` (ou `uv run tourism-api`).
   -> pour tests en local
"""
import asyncio
import sys
import uvicorn
from .config import get_settings


def main() -> None:
    settings = get_settings()
    config = uvicorn.Config(
        "tourism_api.main:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
    server = uvicorn.Server(config)
    if sys.platform == "win32":
        # psycopg (asynchrone) ne fonctionne pas avec la boucle Proactor par défaut sous Windows
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()


if __name__ == "__main__":
    main()
