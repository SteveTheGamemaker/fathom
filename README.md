<p align="center">
  <img src="logo.svg" alt="Fathom logo" width="400">
</p>

# Fathom

A lightweight Python alternative to Sonarr + Radarr, built from scratch with LLM-powered media matching.

## What is this?

Fathom combines TV and movie library workflows into a single app. Instead of relying only on brittle regex for release parsing, it uses an **OpenAI-compatible-endpoint LLM** to interpret release names, qualities, and matches—while still fitting the familiar *arr-style model: indexers, download clients, quality profiles, and a web UI.

## What you get

- **Web UI** — Jinja2 + HTMX dashboard for library, search, indexers, downloads, and settings-oriented flows
- **REST API** — Versioned under `/api/v1` (movies, series, indexers, search, quality profiles, download clients, queue/history, system/scheduler)
- **OpenAPI** — Interactive docs at `/docs` and `/redoc`
- **SQLite** — Async SQLAlchemy + `aiosqlite`; database path configurable via YAML or environment
- **Background jobs** — APScheduler-driven RSS sync, search, and import checks (intervals in config)
- **Indexers** — Torznab / Newznab (including Jackett-style endpoints)
- **Download clients** — Add, test, and send grabs to configured clients
- **Notifications** — Webhook-friendly hooks for grab/import events
- **Optional API auth** — HTTP `X-Api-Key` when `auth.api_key` is set

## Goals

- **Unified** — One tool for TV and movies
- **Lightweight** — Small footprint; no .NET runtime
- **Python-native** — FastAPI, Pydantic, clear module layout under `src/fathom`
- **LLM-assisted matching** — OpenAI-compatible APIs (OpenRouter, LiteLLM, local gateways, etc.)
- **Familiar automation** — Indexers, clients, quality profiles, renaming templates, calendar-oriented workflows where implemented
- **API-first** — Same backend powers the UI and integrations

## Stack

| Area | Choice |
|------|--------|
| Runtime | Python **3.12+** |
| Web | **FastAPI**, Uvicorn |
| DB | **SQLite** (async), **Alembic** for migrations |
| Config | **YAML** + **pydantic-settings** (env overrides) |
| LLM | **openai** client → any OpenAI-compatible `base_url` |
| UI | **Jinja2**, **HTMX**, static assets under `/static` |

## Requirements

- Python 3.12 or newer (for local installs)
- An OpenAI-compatible API key and endpoint (for LLM parsing/matching)
- A TMDB API key for metadata lookup (`tmdb.api_key` in config)

## Quick start (local)

From the repository root (so `config.yaml` is found):

```bash
git clone https://github.com/SteveTheGamemaker/fathom.git
cd fathom

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -e .

cp config.example.yaml config.yaml
# Edit config.yaml: llm.api_key, tmdb.api_key, media paths, indexers, etc.

# Run (uses server.host / server.port from config)
fathom
```

Equivalent explicit Uvicorn command:

```bash
python -m uvicorn fathom.app:create_app --factory --host 0.0.0.0 --port 8989
```

Then open **http://localhost:8989** (or the port you set under `server.port`).

### Optional: alternate config file

```bash
set FATHOM_CONFIG=C:\path\to\config.yaml
fathom
```

On macOS/Linux use `export FATHOM_CONFIG=/path/to/config.yaml`.

## Configuration

Default file names: `config.yaml` or `config.yml` in the current working directory. See **`config.example.yaml`** for all keys.

**Nested settings** can be overridden with environment variables: prefix **`FATHOM_`**, use **`__`** between nesting levels (pydantic-settings).

| YAML path | Example environment variable |
|-----------|------------------------------|
| `database.path` | `FATHOM_DATABASE__PATH` |
| `llm.api_key` | `FATHOM_LLM__API_KEY` |
| `llm.base_url` | `FATHOM_LLM__BASE_URL` |
| `llm.model` | `FATHOM_LLM__MODEL` |
| `tmdb.api_key` | `FATHOM_TMDB__API_KEY` |
| `auth.api_key` | `FATHOM_AUTH__API_KEY` |
| `server.base_url` | `FATHOM_SERVER__BASE_URL` |

`media.root_folders_movies` and `media.root_folders_series` must point at paths **your runtime can access** (host paths for local install; container paths plus volume mounts for Docker).

## Docker

The image installs the app from `pyproject.toml`, copies `src/`, and runs Uvicorn on port **8989**. The Compose file persists SQLite under **`./data`** and mounts **`./config.yaml`** read-only.

### 1. Prepare config on the host

```bash
cp config.example.yaml config.yaml
# Edit config.yaml (API keys, LLM, TMDB, media paths as seen *inside* the container)
```

### 2. Build and run

```bash
docker compose up -d --build
```

- **UI / API:** http://localhost:8989  
- **Logs:** `docker compose logs -f fathom`  
- **Stop:** `docker compose down` (data in `./data` is kept)

### 3. Data and database

- Host directory **`./data`** is mounted at **`/app/data`** in the container.
- Compose sets `FATHOM_DATABASE__PATH=/app/data/fathom.db` so the DB stays on the volume.

### 4. Media libraries inside Docker

Paths in `media.root_folders_movies` / `media.root_folders_series` must exist **inside the container**. Mount your libraries and point config at those mount points, for example:

```yaml
media:
  root_folders_movies:
    - /media/movies
  root_folders_series:
    - /media/tv
```

And extend `docker-compose.yml` (example):

```yaml
services:
  fathom:
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
      - /path/on/host/movies:/media/movies:ro
      - /path/on/host/tv:/media/tv:ro
```

Adjust host paths and read-only (`:ro`) to match your setup.

### 5. Rebuild after pulling changes

```bash
git pull
docker compose up -d --build
```

## API

- Base path: **`/api/v1`**
- Examples: `/api/v1/movie`, `/api/v1/series`, `/api/v1/indexer`, `/api/v1/search`, `/api/v1/system/health`
- With `auth.api_key` set, send header **`X-Api-Key: <your key>`** (or query parameter **`apikey`**) on API requests

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```

Tests live under **`tests/`**.

## Status

Built entirely via vibe coding with Claude Code.

## License

TBD
