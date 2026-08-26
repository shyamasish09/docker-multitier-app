# TaskFlow — Dockerized Multi-Tier Application

A three-tier app containerized with Docker and orchestrated with Docker
Compose: a **React** frontend, a **Flask** REST API backend, and a
**PostgreSQL** database — wired together on a private Docker network with
environment-based configuration for local deployment.

```
┌─────────────┐      /api/*      ┌─────────────┐      SQL       ┌─────────────┐
│  frontend   │ ───────────────▶ │   backend   │ ──────────────▶│     db      │
│  React+nginx│  (proxy_pass)    │  Flask+gunicorn│              │  PostgreSQL │
│  :80 → :3000│                  │  :5000       │                │  :5432     │
└─────────────┘                  └─────────────┘                └─────────────┘
        all three on the "app-net" bridge network, DNS by container name
```

## Project structure

```
docker-multitier-app/
├── docker-compose.yml       # orchestrates all 3 services + network + volume
├── .env.example              # env-based config template (copy to .env)
├── frontend/
│   ├── Dockerfile            # multi-stage: node build → nginx serve
│   ├── nginx.conf            # serves the SPA, proxies /api/* to backend
│   └── src/App.jsx           # task list UI, calls the backend API
├── backend/
│   ├── Dockerfile
│   ├── app.py                 # Flask REST API (CRUD for tasks)
│   └── requirements.txt
└── db/
    └── init.sql               # seed data, runs once on first volume init
```

## How the tiers talk to each other

- **frontend → backend**: the browser calls same-origin `/api/*`; nginx
  (inside the frontend container) reverse-proxies those requests to
  `http://backend:5000/api/*`. `backend` resolves via Docker Compose's
  built-in DNS on the `app-net` bridge network — no hardcoded IPs.
- **backend → db**: the backend reads `DB_HOST=db`, `DB_PORT=5432`, etc.
  from environment variables injected by Compose, and connects to
  `db:5432`, again resolved by service name.
- **Compose startup ordering**: `depends_on: db: condition: service_healthy`
  makes the backend wait for Postgres's healthcheck (`pg_isready`) before
  starting, and the backend itself retries connecting for extra safety.
  `frontend` waits on `backend` similarly.

## Environment-based configuration

Nothing is hardcoded — `docker-compose.yml` reads everything from `.env`:

- `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` — db credentials,
  shared with the backend so both sides agree
- `DB_HOST` / `DB_PORT` — where the backend looks for Postgres
- `VITE_API_URL` — baked into the frontend's static build at build time
  (build arg), so you can point a build at a different backend URL per
  environment without touching source code
- `BACKEND_PORT` / `FRONTEND_PORT` — host-side port mappings, so you can
  run multiple environments side by side by changing just the `.env`

## Running it

```bash
cd docker-multitier-app
cp .env.example .env        # adjust values if needed
docker compose up --build
```

Then open:
- Frontend: http://localhost:3000
- Backend health check: http://localhost:5000/api/health
- Backend API directly: http://localhost:5000/api/tasks

Data persists across restarts via the `db-data` named volume. To wipe
everything and start fresh:

```bash
docker compose down -v
```

## Notes for the Termux / phone workflow

Docker itself doesn't run inside Termux (no container/cgroup support on
stock Android kernels) — this one needs a real Docker host: a laptop, a
cloud VM, or Termux's `proot-distro`/UserLAN Docker workarounds if you
want to try it on-device. If you just want to review or edit the code on
your phone, all the source files here are plain Python/JS/YAML and open
fine in any editor — only `docker compose up` needs an actual Docker
engine.
