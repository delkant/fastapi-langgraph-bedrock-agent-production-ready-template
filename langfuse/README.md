# Langfuse Docker Setup

This directory contains the Docker configuration for running Langfuse locally alongside the main application stack.

## Overview

Langfuse is an open-source LLM engineering platform for tracing, evaluation, prompt management, and analytics. This setup provides:

- **Langfuse Server**: Web interface and API running on port 3001
- **Dedicated PostgreSQL**: Separate database for Langfuse data on port 5433
- **Environment-specific configurations**: Support for local, development, staging, and production

## Quick Start

### Option 1: Run with main docker-compose (Recommended)

The Langfuse service is included in the main `docker-compose.yml`. Simply run:

```bash
# Start the entire stack including Langfuse
make docker-compose-up ENV=local

# Or manually:
docker-compose --env-file .env.local up -d
```

### Option 2: Run Langfuse standalone

If you want to run only Langfuse:

```bash
cd langfuse
docker-compose -f docker-compose.langfuse.yml up -d
```

## Accessing Langfuse

Once running, access Langfuse at:
- **Web UI**: http://localhost:3001
- **API**: http://localhost:3001/api

### First-time Setup

1. Open http://localhost:3001 in your browser
2. Create an admin account
3. Generate API keys for your application
4. Update your application's `.env` file with the Langfuse configuration:

```bash
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=http://localhost:3001
```

## Configuration

### Environment Files

- `config/local.env` - Local development settings
- `config/production.env` - Production settings
- `config/langfuse.env` - Default/fallback settings

### Port Configuration

- **Langfuse Web UI**: 3001 (avoids collision with Grafana on 3000)
- **Langfuse Database**: 5433 (avoids collision with main PostgreSQL on 5432)

### Database

Langfuse uses its own PostgreSQL database to avoid conflicts with your main application database. The database is automatically initialized on first startup.

## Management Commands

### View Logs
```bash
docker-compose logs -f langfuse-server
```

### Restart Services
```bash
docker-compose restart langfuse-server
```

### Reset Database (⚠️ This will delete all data)
```bash
docker-compose down -v
docker-compose up -d
```

### Backup Database
```bash
docker exec langfuse-postgres pg_dump -U langfuse langfuse > langfuse_backup.sql
```

### Restore Database
```bash
cat langfuse_backup.sql | docker exec -i langfuse-postgres psql -U langfuse -d langfuse
```

## Integration with Your Application

Once Langfuse is running, update your application configuration:

1. **Environment Variables** (in your `.env.local`):
```bash
LANGFUSE_PUBLIC_KEY=pk_...  # Get from Langfuse UI
LANGFUSE_SECRET_KEY=sk_...  # Get from Langfuse UI
LANGFUSE_HOST=http://localhost:3001
```

2. **Application Code**: The existing LangGraph integration should automatically start sending traces to your local Langfuse instance.

## Troubleshooting

### Common Issues

1. **Port 3001 already in use**:
   - Check what's using the port: `lsof -i :3001`
   - Stop the conflicting service or change the port in `docker-compose.yml`

2. **Database connection errors**:
   - Ensure PostgreSQL container is healthy: `docker-compose ps`
   - Check logs: `docker-compose logs langfuse-db`

3. **Langfuse won't start**:
   - Ensure database is ready: `docker-compose logs langfuse-db`
   - Check Langfuse logs: `docker-compose logs langfuse-server`

### Health Checks

Check if services are running:
```bash
curl http://localhost:3001/api/public/health
```

## Production Considerations

When deploying to production:

1. **Security**:
   - Change all default passwords and secrets
   - Use environment variables for sensitive data
   - Enable HTTPS and proper CORS settings

2. **Database**:
   - Use managed PostgreSQL service
   - Set up proper backups
   - Configure connection pooling

3. **Scaling**:
   - Consider using external database
   - Set up load balancing if needed
   - Monitor resource usage

## Useful Links

- [Langfuse Documentation](https://langfuse.com/docs)
- [Langfuse GitHub](https://github.com/langfuse/langfuse)
- [Langfuse Docker Hub](https://hub.docker.com/r/langfuse/langfuse)