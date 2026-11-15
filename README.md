# Tourism Agent — API

FastAPI backend of a conversational LangGraph agent that finds stays in a catalogue from
the customer's wishes expressed in natural language. The user interface is a separate
Space (Gradio).

- Interactive API documentation: `/docs`
- Business routes under `/api/v1` (header `X-API-Key` required), probes `/health` and `/ready`
- Answers streamed as Server-Sent Events on `/api/v1/chat/stream`

## Space configuration

| Name | Type | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Secret | OpenRouter key used to call the LLM |
| `API_KEY` | Secret | Key expected in the `X-API-Key` header (shared with the frontend Space) |
| `MODEL_NAME` | Variable | Model used by default (must have a system prompt) |
| `DATABASE_URL` | Secret (optional) | PostgreSQL URL for conversation persistence (see below); empty = in-memory |
| `CORS_ORIGINS` | Variable (optional) | Allowed frontend origins, comma-separated (default `http://localhost:7860`) |
| `MAX_USER_MESSAGE_LENGTH` | Variable (optional) | Max length of a user message in characters (default `300`) |
| `LANGSMITH_API_KEY` | Secret (optional) | LangSmith tracing |
| `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | Variables (optional) | LangSmith tracing |

Without `DATABASE_URL`, conversations are kept in memory: they are lost when the service restarts or goes to sleep.
With it, they are stored in PostgreSQL (LangGraph checkpointer tables are created automatically at startup).

Full documentation (agent, graph, API, tests, local run): [README_doc.md](README_doc.md).

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

A local database cannot be reached from Render: use a Render PostgreSQL instance.

1. **Create the database**: Dashboard → New → PostgreSQL. Pick a name, a region (the same as the web service
   will use) and a plan. Once it is `available`, copy its **Internal Database URL**.
2. **Create the web service**: New → Web Service → connect the Git repository, language **Docker**
   (the [Dockerfile](Dockerfile) is used as is), same region as the database.
3. **Environment variables** (service → Environment):

   | Name | Value |
   |---|---|
   | `DATABASE_URL` | the database's Internal Database URL |
   | `OPENROUTER_API_KEY` | OpenRouter key |
   | `MODEL_NAME` | model used by default |
   | `API_KEY` | long random secret, shared with the frontend |
   | `CORS_ORIGINS` | public URL of the frontend (no trailing slash) |
   | `PORT` | `8000` (the container listens on 8000) |

4. **Health check**: Settings → Health Check Path → `/ready` (also verifies the database connection).
5. **Deploy**, then check `https://<service>.onrender.com/ready`: it must answer `{"status":"ok","checkpointer":"postgres"}`.
6. **Frontend**: set its `BACKEND_URL` to `https://<service>.onrender.com` and its `BACKEND_API_KEY` to the same `API_KEY`.

The *Internal* URL is only valid between Render services of the same region/account. To inspect the database from your
machine (DBeaver, psql), use the *External Database URL* and restrict access to your IP in the database's *Networking* settings.
