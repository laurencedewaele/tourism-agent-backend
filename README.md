# Tourism Agent — API

FastAPI backend of a conversational LangGraph agent that finds stays in a catalogue from
the customer's wishes expressed in natural language. The user interface is a separate
Gradio application (repository `tourism-agent-frontend`).

- Interactive API documentation: `/docs`
- Business routes under `/api/v1` (header `X-API-Key` required), probes `/health` and `/ready`
- Answers streamed as Server-Sent Events on `/api/v1/chat/stream`

## Configuration

Environment variables (`.env` locally, service *Environment* on Render):

| Name | Type | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Secret | OpenRouter key used to call the LLM |
| `API_KEY` | Secret | Key expected in the `X-API-Key` header (shared with the frontend) |
| `MODEL_NAME` | Variable | Model used by default (must have a system prompt) |
| `DATABASE_URL` | Secret (optional) | PostgreSQL URL for conversation persistence (see below); empty = in-memory |
| `CORS_ORIGINS` | Variable (optional) | Allowed frontend origins, comma-separated (default `http://localhost:7860`) |
| `DATABASE_POOL_MAX_SIZE` | Variable (optional) | Max size of the PostgreSQL connection pool (default `10`) |
| `MAX_USER_MESSAGE_LENGTH` | Variable (optional) | Max length of a user message in characters (default `300`) |
| `PORT` | Variable (optional) | Port the container listens on (default `8000`; set by Render automatically) |
| `LANGSMITH_API_KEY` | Secret (optional) | LangSmith tracing |
| `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | Variables (optional) | LangSmith tracing |

Without `DATABASE_URL`, conversations are kept in memory: they are lost when the service restarts or goes to sleep.
With it, they are stored in PostgreSQL (LangGraph checkpointer tables are created automatically at startup).

## Local PostgreSQL

The database must only be reachable from your machine.

- **Installed on Windows** (e.g. `winget install PostgreSQL.PostgreSQL.16`): check that `listen_addresses = 'localhost'`
  in `postgresql.conf` (restart the service after a change), then create the role and database:
  ```sql
  CREATE USER tourism WITH PASSWORD '<password>';
  CREATE DATABASE tourism OWNER tourism;
  ```
  and set `DATABASE_URL=postgresql://tourism:<password>@localhost:5432/tourism` in `.env`.
  Run the API directly (`python -m tourism_api`), not in a container: a container cannot reach the host's `localhost`.
- **With Docker**: `docker compose up db -d`, same `DATABASE_URL` as above (user, password and database `tourism`
  by default).

## Deploying on Render

The infrastructure is described in [render.yaml](render.yaml) (Render Blueprint, free plan): a PostgreSQL
database `tourism-db` and a Docker web service `tourism-agent-backend`, both in the Frankfurt region.
A local database cannot be reached from Render: the Blueprint creates a Render PostgreSQL instance and wires
its *Internal Database URL* into `DATABASE_URL`.

1. **Push** the repository to GitHub/GitLab (the Blueprint deploys the `main` branch and redeploys on every push).
2. **Create the Blueprint**: Dashboard → New → Blueprint → select the repository. Render reads `render.yaml`
   and asks for the values marked `sync: false`:

   | Name | Value |
   |---|---|
   | `OPENROUTER_API_KEY` | OpenRouter key |
   | `MODEL_NAME` | model used by default |
   | `CORS_ORIGINS` | public URL of the frontend (no trailing slash) |
   | `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` | optional, can stay empty |

   `DATABASE_URL` comes from the database, `API_KEY` is generated randomly, `PORT` is set by Render
   (the [Dockerfile](Dockerfile) listens on `${PORT:-8000}`). The health check path is `/ready`, which also
   verifies the database connection.
3. **Check** `https://tourism-agent-backend.onrender.com/ready`: it must answer
   `{"status":"ok","checkpointer":"postgres"}`. The API documentation is on `/docs`.
4. **Frontend**: set its `BACKEND_URL` to `https://tourism-agent-backend.onrender.com` and its `BACKEND_API_KEY`
   to the generated `API_KEY` (service → Environment). Give its HTTP client a timeout of at least 60 s (cold start).

**Free plan limits**

- The web service sleeps after 15 min without traffic; the next request wakes it up in about a minute.
- The free database expires 30 days after its creation: recreate it (conversations are lost) or switch to a paid plan.
- 512 MB of RAM: the container runs a single uvicorn worker.

The *Internal* URL is only valid between Render services of the same region/account. To inspect the database from
your machine (DBeaver, psql), add your IP to `ipAllowList` in [render.yaml](render.yaml) (or in the database's
*Networking* settings) and use the *External Database URL*.
