# 🚀 Ambrosia Dashboard

[![Django](https://img.shields.io/badge/Django-5.2.1-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-2E8B57.svg)](https://postgis.net/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Project Structure](#-project-structure)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (Port 80)                      │
│                    Static Files + Reverse Proxy             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Django Application (Port 8000)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Dashboard  │  │  Risk Charts │  │  Climate Data API│   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │Vocabulary Mgr│  │  Simulation  │  │   User Auth      │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│           PostgreSQL 16 + PostGIS (Port 5432)               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │Climate Data  │  │ Simulations  │  │  Vocabularies    │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/ambrosia2024/dashboard.git
cd dashboard
```

### 2. Configure Environment

```bash
cp .env.sample .env
```

Edit `.env` with your configuration:

```bash
# Django
DJANGO_SECRET_KEY=your-secure-secret-key-here

# Database (PostgreSQL + PostGIS)
POSTGRES_DB=ambrosia
POSTGRES_USER=amb_admin
POSTGRES_PASSWORD=your-secure-db-password
POSTGRES_HOST=ambrosia_postgres
POSTGRES_PORT=5432

# pgAdmin (optional)
PGADMIN_DEFAULT_EMAIL=admin@yourdomain.com
PGADMIN_DEFAULT_PASSWORD=your-secure-password

# Feature Flags
EMAIL_VERIFICATION_ENABLED=false

# External APIs (optional)
SCIO_VOCAB_API_BASE=
```

> ⚠️ **Security Note**: Generate a strong `DJANGO_SECRET_KEY` using:
> ```python
> python -c "import secrets; print(secrets.token_urlsafe(50))"
> ```

### 3. Launch the Application

```bash
docker compose up -d
```

This will:
- 🐳 Pull and build required Docker images
- 🗄️ Initialize PostgreSQL with PostGIS extensions
- 🔧 Run Django migrations automatically
- 📦 Collect static files
- 🌐 Start Nginx reverse proxy

### 4. Access the Application

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost/ | Main web application |
| Admin Panel | http://localhost/admin/ | Django admin interface |
| pgAdmin | http://localhost:5050/ | Database management (optional) |
| Health Check | http://localhost/status | Service health endpoint |

### 5. Create Admin User

```bash
docker compose exec ambrosia_dashboard python manage.py createsuperuser
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | Yes | - | Django security key |
| `POSTGRES_DB` | Yes | ambrosia | Database name |
| `POSTGRES_USER` | Yes | amb_admin | Database user |
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `POSTGRES_HOST` | Yes | ambrosia_postgres | Database host |
| `POSTGRES_PORT` | No | 5432 | Database port |
| `EMAIL_VERIFICATION_ENABLED` | No | false | Enable email verification |
| `SCIO_VOCAB_API_BASE` | No | dev.api... | Vocabulary API endpoint |
| `ALLOWED_HOSTS` | No | localhost | Comma-separated allowed hosts |

### Dashboard View Modes

The application supports customizable dashboard layouts:

1. Access Django Admin: http://localhost/admin/
2. Navigate to **Lumenix** → **Dashboard view modes**
3. Create modes like "Farmer View", "Policy Advisor View", "Distributor View"
4. Assign charts to each mode via **Dashboard view charts**


---

## 🛠️ Development

### Local Development (Without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup local PostgreSQL with PostGIS
# Then configure DATABASES in config/settings.py

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic

# Start development server
python manage.py runserver
```

### Running Tests

```bash
docker compose exec ambrosia_dashboard python manage.py test
```

### Database Migrations

```bash
# Create migration
docker compose exec ambrosia_dashboard python manage.py makemigrations

# Apply migration
docker compose exec ambrosia_dashboard python manage.py migrate
```

### Vocabulary Synchronization

To sync plant and pathogen vocabularies from SCiO API:

```bash
docker compose exec ambrosia_dashboard python manage.py sync_vocabulary plants
docker compose exec ambrosia_dashboard python manage.py sync_vocabulary pathogens
```

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: Database connection failed
```bash
# Check database health
docker compose ps
docker compose logs ambrosia_postgres
```

**Issue**: Static files not loading
```bash
# Rebuild and collect static
docker compose down
docker compose up -d --build
```

**Issue**: Permission denied on volumes
```bash
# Fix volume permissions
docker compose down -v
docker volume prune  # ⚠️ Warning: Deletes all unused volumes
docker compose up -d
```

### Logs

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f ambrosia_dashboard
```
