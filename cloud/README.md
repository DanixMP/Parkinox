# Parkinox Cloud — Remote Management & Reporting Replica

Local parking system remains the **operational source of truth**.
This `cloud/` project is a **reporting replica** plus HTML management dashboard.

## Quick start (dev)

```bash
cd cloud
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # optional
python manage.py migrate
python manage.py runserver 8010
```

Open http://127.0.0.1:8010/login/

Default pilot login (override via env):

- `DASHBOARD_USERNAME=admin`
- `DASHBOARD_PASSWORD=changeme-pilot`

Site ingest token (must match on-site `CLOUD_SITE_INGEST_TOKEN`):

- `CLOUD_SITE_INGEST_TOKEN=dev-site-ingest-token`

## On-site sync

In the operational Django (`backend/`):

```env
CLOUD_SYNC_ENABLED=true
CLOUD_BASE_URL=http://YOUR_CLOUD_HOST:8010
CLOUD_SITE_ID=pilot-main
CLOUD_SITE_INGEST_TOKEN=dev-site-ingest-token
```

Drain outbox:

```bash
cd backend
python manage.py sync_to_cloud --once
# or loop:
python manage.py sync_to_cloud --sleep 5
```

## End Season from dashboard

Optional LAN proxy to the local SoR (does **not** redesign sync direction):

```env
LOCAL_SITE_API_URL=http://127.0.0.1:8001
LOCAL_SITE_OPERATOR_PHONE=0912...
LOCAL_SITE_OPERATOR_PASSWORD=...
```

The Overview / Sync pages show **پایان فصل و شروع مجدد**, which posts to local `POST /api/parking/season/reset/` after confirming the dashboard password.

## Architecture

```
Local GateEvent/Session commit
  → SyncOutbox (+ success images under Core/parking_media)
  → POST /api/ingest/events/ and /api/ingest/images/
  → Cloud replica DB + HTML dashboard
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for VPS + domain + nginx + TLS.
