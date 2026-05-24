# Parkinox Backend

Django backend for the Parkinox Smart University Parking System.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and update the values:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials and other settings.

### 3. Database Setup

**Development:** The project is configured to use SQLite by default for easier development setup. No additional database setup is required.

**Production:** For production, configure PostgreSQL:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE parkinox;

# Exit psql
\q
```

Then update your `.env` file with PostgreSQL credentials and set `DJANGO_SETTINGS_MODULE=config.settings.production`.

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 6. Run Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/`

## Settings

The project uses a settings package with three modules:

- `config/settings/base.py` - Common settings for all environments
- `config/settings/development.py` - Development-specific settings
- `config/settings/production.py` - Production-specific settings

By default, `manage.py` uses `development` settings. For production, set:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

## Environment Variables

Required environment variables (see `.env.example`):

- `SECRET_KEY` - Django secret key (change in production!)
- `DEBUG` - Debug mode (True/False)
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts
- `DB_NAME` - PostgreSQL database name
- `DB_USER` - PostgreSQL username
- `DB_PASSWORD` - PostgreSQL password
- `DB_HOST` - PostgreSQL host (default: localhost)
- `DB_PORT` - PostgreSQL port (default: 5432)
- `CORS_ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins

## Testing Database Connection

To test the database connection:

```bash
python manage.py check --database default
```

To test migrations:

```bash
python manage.py showmigrations
```
