# Docker Deployment Guide for LLTeacher v2

This guide explains how to deploy LLTeacher v2 using Docker.

## Files Created

- **`Dockerfile`** - Multi-stage Docker build optimized for LLTeacher v2 UV workspace
- **`docker-entrypoint.sh`** - Startup script that handles database migrations and superuser creation
- **`.dockerignore`** - Optimizes build context by excluding unnecessary files
- **`src/llteacher/production.py`** - Production Django settings

## Quick Start

### Build the Image

```bash
docker build -t llteacher:latest .
```

### Run the Container

```bash
# Create a data volume for database persistence
docker volume create llteacher_data

# Run the container
docker run -d \
  --name llteacher-app \
  -p 8000:8000 \
  -v llteacher_data:/data \
  -e SECRET_KEY="your-secret-key-here" \
  llteacher:latest
```

### Access the Application

- **Web Interface**: http://localhost:8000
- **Admin Interface**: http://localhost:8000/admin
- **Default Admin Credentials**: admin / admin123 (created automatically)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `django-insecure-change-this-in-production` | Django secret key |
| `DATABASE_PATH` | `/data/llteacher.sqlite` | SQLite database path |
| `DJANGO_SETTINGS_MODULE` | `llteacher.production` | Django settings module |
| `SQLITE_VECTOR_ENABLED` | `true` | Load the sqlite-vector extension for SQLite connections |
| `SQLITE_VECTOR_REQUIRED` | `true` | Fail startup if sqlite-vector cannot be loaded |

## Production Deployment

### Security Considerations

1. **Change the default admin password** immediately after first login
2. **Set a secure SECRET_KEY** environment variable
3. **Configure ALLOWED_HOSTS** in production settings if needed
4. **Use HTTPS** in production with a reverse proxy

### Example Production Run

```bash
docker run -d \
  --name llteacher-prod \
  -p 8000:8000 \
  -v /path/to/persistent/data:/data \
  -e SECRET_KEY="$(openssl rand -base64 32)" \
  --restart unless-stopped \
  llteacher:latest
```

## Container Features

- **UV Package Manager**: Fast dependency resolution and installation
- **Non-root User**: Runs as `app` user for security
- **Health Checks**: Built-in health monitoring
- **Static Files**: Pre-collected during build
- **Database Migrations**: Automatic on startup
- **Volume Persistence**: Database stored in `/data` volume

## Troubleshooting

### Check Container Logs

```bash
docker logs llteacher-app
```

### Access Container Shell

```bash
docker exec -it llteacher-app bash
```

### Rebuild After Changes

```bash
docker build --no-cache -t llteacher:latest .
```

### Reset Database

```bash
# Stop container
docker stop llteacher-app

# Remove volume (WARNING: This deletes all data)
docker volume rm llteacher_data

# Recreate volume and restart
docker volume create llteacher_data
docker start llteacher-app
```

## Architecture Notes

- **Base Image**: Python 3.12 slim
- **Package Manager**: UV for fast dependency management
- **Web Server**: Gunicorn with 8 workers
- **Database**: SQLite (suitable for small to medium deployments)
- **Static Files**: Served from `/app/staticfiles`
- **Workspace Structure**: Supports UV workspace with multiple apps

## Development vs Production

The Docker setup uses production settings by default. For development:

1. Use the local development server: `python manage.py runserver`
2. The Docker container is optimized for production deployment
3. Database migrations run automatically on container startup
4. Static files are pre-collected during the build process

## Support

For issues related to the LLTeacher application itself, refer to the main project documentation. For Docker-specific issues, check the container logs and ensure proper volume mounting and environment variable configuration.
