# Parkinox Cloud — VPS / domain deployment (Ubuntu 24)

This deploys the **reporting replica + dashboard only**. Operational parking
Django and FastAPI stay on-site.

## 1. Server packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx
```

Optional PostgreSQL:

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres createuser -P parkinox
sudo -u postgres createdb -O parkinox parkinox_cloud
```

## 2. App install

```bash
sudo mkdir -p /opt/parkinox-cloud
sudo chown $USER:$USER /opt/parkinox-cloud
# copy cloud/ contents here
cd /opt/parkinox-cloud
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — set CLOUD_SECRET_KEY, DASHBOARD_*, CLOUD_SITE_INGEST_TOKEN,
# CLOUD_ALLOWED_HOSTS=your.domain.com
# CLOUD_CSRF_TRUSTED_ORIGINS=https://your.domain.com
nano .env
python manage.py migrate
python manage.py collectstatic --noinput
```

## 3. Gunicorn systemd unit

`/etc/systemd/system/parkinox-cloud.service`:

```ini
[Unit]
Description=Parkinox Cloud Dashboard
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/parkinox-cloud
EnvironmentFile=/opt/parkinox-cloud/.env
ExecStart=/opt/parkinox-cloud/.venv/bin/gunicorn config.wsgi:application \
  --bind unix:/run/parkinox-cloud.sock --workers 3 --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now parkinox-cloud
```

## 4. Nginx + TLS

`/etc/nginx/sites-available/parkinox-cloud`:

```nginx
server {
    listen 80;
    server_name your.domain.com;
    client_max_body_size 50M;

    location /static/ {
        alias /opt/parkinox-cloud/staticfiles/;
    }
    # Dashboard images use Django auth proxy at /files/<id>/ (proxied via location /).
    # Do NOT alias all of /media/ — that steals /media/<id>/ style paths from Django.
    location /media/events/ {
        alias /opt/parkinox-cloud/media/events/;
    }
    location / {
        proxy_pass http://unix:/run/parkinox-cloud.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/parkinox-cloud /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your.domain.com
```

Set `CLOUD_DEBUG=false` after TLS works.

## 5. On-site sync worker

On the parking PC (operational `backend/`):

```env
CLOUD_SYNC_ENABLED=true
CLOUD_BASE_URL=https://your.domain.com
CLOUD_SITE_ID=pilot-main
CLOUD_SITE_INGEST_TOKEN=<same as cloud>
```

Systemd / Task Scheduler loop:

```bash
python manage.py sync_to_cloud --sleep 5
```

## 6. Pilot E2E checklist

1. Disconnect internet on site PC
2. Process several entries/exits — gates and local reports still work
3. Confirm outbox pending grows (`GET /api/parking/sync/status/`)
4. Restore internet and run `sync_to_cloud`
5. Confirm cloud dashboard totals match local (no duplicate UUIDs)
6. Confirm images appear after metadata (may lag)

## Security notes (pilot)

- Dashboard login = env username/password only
- Ingest = shared site token (`X-Site-Ingest-Token`)
- Keep tokens separate
- Rotate `DASHBOARD_PASSWORD` and ingest token before production hardening
- Extension points for roles / 2FA / retention are intentional stubs for later
