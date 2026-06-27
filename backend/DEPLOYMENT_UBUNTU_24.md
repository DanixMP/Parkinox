# Parkinox Backend Deployment Guide - Ubuntu 24

Complete guide for deploying the Django REST API backend on Ubuntu 24.04 LTS.

## Prerequisites

- Ubuntu 24.04 LTS server
- Root or sudo access
- Domain name (optional, for production)
- SSL certificate (recommended for production)

## System Setup

### 1. Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Required Dependencies

```bash
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    supervisor \
    certbot \
    python3-certbot-nginx
```

## Database Setup (PostgreSQL)

### 1. Start PostgreSQL Service

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 2. Create Database and User

```bash
sudo -u postgres psql << EOF
CREATE DATABASE parkinox_db;
CREATE USER parkinox_user WITH PASSWORD 'your_secure_password_here';
ALTER ROLE parkinox_user SET client_encoding TO 'utf8';
ALTER ROLE parkinox_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE parkinox_user SET default_transaction_deferrable TO on;
ALTER ROLE parkinox_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE parkinox_db TO parkinox_user;
\q
EOF
```

**Important**: Replace `your_secure_password_here` with a strong password.

## Application Setup

### 1. Create Application Directory

```bash
sudo mkdir -p /var/www/parkinox
sudo chown $USER:$USER /var/www/parkinox
cd /var/www/parkinox
```

### 2. Clone Repository

```bash
git clone https://github.com/DanixMP/Parkinox.git .
cd backend
```

### 3. Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install gunicorn psycopg2-binary
```

### 5. Configure Environment Variables

```bash
cp .env.example .env
nano .env
```

Update the `.env` file with:

```env
DEBUG=False
SECRET_KEY=your_django_secret_key_here
ALLOWED_HOSTS=your_domain.com,www.your_domain.com,your_server_ip
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=parkinox_db
DATABASE_USER=parkinox_user
DATABASE_PASSWORD=your_secure_password_here
DATABASE_HOST=localhost
DATABASE_PORT=5432
ENVIRONMENT=production
```

**Generate SECRET_KEY**:
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 6. Run Migrations

```bash
python manage.py migrate
```

### 7. Create Superuser

```bash
python manage.py createsuperuser
```

### 8. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

## Gunicorn Setup

### 1. Create Gunicorn Service File

```bash
sudo nano /etc/systemd/system/parkinox.service
```

Add the following content:

```ini
[Unit]
Description=Parkinox Django Application
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/parkinox/backend
Environment="PATH=/var/www/parkinox/backend/venv/bin"
ExecStart=/var/www/parkinox/backend/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind unix:/run/gunicorn.sock \
    --timeout 120 \
    --access-logfile /var/log/parkinox/access.log \
    --error-logfile /var/log/parkinox/error.log \
    config.wsgi:application

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Create Log Directory

```bash
sudo mkdir -p /var/log/parkinox
sudo chown www-data:www-data /var/log/parkinox
```

### 3. Set Permissions

```bash
sudo chown -R www-data:www-data /var/www/parkinox
sudo chmod -R 755 /var/www/parkinox
```

### 4. Enable and Start Gunicorn

```bash
sudo systemctl daemon-reload
sudo systemctl enable parkinox
sudo systemctl start parkinox
sudo systemctl status parkinox
```

## Nginx Configuration

### 1. Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/parkinox
```

Add the following content:

```nginx
upstream parkinox_app {
    server unix:/run/gunicorn.sock fail_timeout=0;
}

server {
    listen 80;
    server_name your_domain.com www.your_domain.com;
    client_max_body_size 100M;

    access_log /var/log/nginx/parkinox_access.log;
    error_log /var/log/nginx/parkinox_error.log;

    location /static/ {
        alias /var/www/parkinox/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/parkinox/backend/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://parkinox_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://parkinox_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Enable Nginx Site

```bash
sudo ln -s /etc/nginx/sites-available/parkinox /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
```

### 3. Test Nginx Configuration

```bash
sudo nginx -t
```

### 4. Start Nginx

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
sudo systemctl status nginx
```

## SSL Certificate Setup (Let's Encrypt)

### 1. Obtain SSL Certificate

```bash
sudo certbot certonly --nginx -d your_domain.com -d www.your_domain.com
```

### 2. Update Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/parkinox
```

Replace the server block with:

```nginx
server {
    listen 80;
    server_name your_domain.com www.your_domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your_domain.com www.your_domain.com;
    client_max_body_size 100M;

    ssl_certificate /etc/letsencrypt/live/your_domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your_domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    access_log /var/log/nginx/parkinox_access.log;
    error_log /var/log/nginx/parkinox_error.log;

    location /static/ {
        alias /var/www/parkinox/backend/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/parkinox/backend/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://parkinox_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /ws/ {
        proxy_pass http://parkinox_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3. Reload Nginx

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Auto-Renewal Setup

```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

## Monitoring and Maintenance

### 1. Check Service Status

```bash
sudo systemctl status parkinox
sudo systemctl status nginx
sudo systemctl status postgresql
```

### 2. View Logs

```bash
# Application logs
tail -f /var/log/parkinox/error.log
tail -f /var/log/parkinox/access.log

# Nginx logs
tail -f /var/log/nginx/parkinox_error.log
tail -f /var/log/nginx/parkinox_access.log

# System logs
sudo journalctl -u parkinox -f
```

### 3. Database Backup

```bash
# Create backup script
sudo nano /usr/local/bin/backup_parkinox.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/parkinox"
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
sudo -u postgres pg_dump parkinox_db | gzip > $BACKUP_DIR/parkinox_db_$TIMESTAMP.sql.gz
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
```

Make it executable:

```bash
sudo chmod +x /usr/local/bin/backup_parkinox.sh
```

Add to crontab:

```bash
sudo crontab -e
```

Add line:

```
0 2 * * * /usr/local/bin/backup_parkinox.sh
```

## Troubleshooting

### Application Won't Start

```bash
# Check service status
sudo systemctl status parkinox

# View detailed logs
sudo journalctl -u parkinox -n 50

# Test Django app directly
cd /var/www/parkinox/backend
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U parkinox_user -d parkinox_db

# Check PostgreSQL status
sudo systemctl status postgresql

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-*.log
```

### Nginx Issues

```bash
# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Check Nginx status
sudo systemctl status nginx
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R www-data:www-data /var/www/parkinox

# Fix permissions
sudo chmod -R 755 /var/www/parkinox
sudo chmod -R 755 /var/log/parkinox
```

## Performance Optimization

### 1. Increase Gunicorn Workers

Edit `/etc/systemd/system/parkinox.service` and adjust:

```ini
ExecStart=/var/www/parkinox/backend/venv/bin/gunicorn \
    --workers 8 \
    ...
```

Formula: `workers = (2 × CPU_cores) + 1`

### 2. Enable Gzip Compression

Add to Nginx configuration:

```nginx
gzip on;
gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml+rss;
gzip_min_length 1000;
```

### 3. Database Connection Pooling

Install pgbouncer:

```bash
sudo apt install pgbouncer
```

## Security Hardening

### 1. Firewall Setup

```bash
sudo ufw enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### 2. Fail2Ban Installation

```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. Update Django Settings

Ensure in `config/settings/production.py`:

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

## Deployment Checklist

- [ ] System updated and dependencies installed
- [ ] PostgreSQL database created and configured
- [ ] Application cloned and virtual environment set up
- [ ] Environment variables configured
- [ ] Database migrations completed
- [ ] Superuser created
- [ ] Static files collected
- [ ] Gunicorn service configured and running
- [ ] Nginx configured and running
- [ ] SSL certificate installed
- [ ] Firewall configured
- [ ] Backup script set up
- [ ] Monitoring configured
- [ ] Domain DNS records updated
- [ ] Application tested and verified

## Useful Commands

```bash
# Restart application
sudo systemctl restart parkinox

# Restart Nginx
sudo systemctl restart nginx

# Restart PostgreSQL
sudo systemctl restart postgresql

# Check disk usage
df -h

# Check memory usage
free -h

# Monitor processes
top

# View active connections
sudo netstat -tulpn | grep LISTEN
```

## Support and Troubleshooting

For issues or questions:
1. Check logs in `/var/log/parkinox/`
2. Review Django error logs
3. Check Nginx error logs
4. Verify database connectivity
5. Ensure all services are running

## Additional Resources

- Django Documentation: https://docs.djangoproject.com/
- Gunicorn Documentation: https://gunicorn.org/
- Nginx Documentation: https://nginx.org/
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Let's Encrypt: https://letsencrypt.org/

---

**Last Updated**: May 2026
**Version**: 1.0
