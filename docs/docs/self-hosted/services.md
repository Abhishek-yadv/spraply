# Services Documentation

Spraply consists of several services working together in a Docker Compose environment. Here's a detailed overview of each service.

## Core Services

### App (FastAPI Application)

- **Image**: Built from `backend/Dockerfile`
- **Purpose**: Main application server
- **Tech Stack**: FastAPI + SQLAlchemy + Alembic
- **Default Port**: 9000 (internal)
- **Dependencies**: PostgreSQL, Redis
- **Key Features**:
  - REST API endpoints
  - User authentication
  - Crawl job management
  - Plugin system
  - Data processing
- **Command**: `uvicorn app.main:app --host 0.0.0.0 --port 9000 --workers 2`

### Frontend

- **Image**: `Spraply/frontend:v0.12.1`
- **Purpose**: Web interface
- **Tech Stack**: React/Vite
- **Dependencies**: App (Core API)
- **Key Features**:
  - User interface
  - Interactive dashboard
  - Job management interface
- **Environment Variables**:
  - `VITE_API_BASE_URL`: API endpoint URL
- **Command**: `npm run serve`

### Nginx

- **Image**: `nginx:alpine`
- **Purpose**: Web server and reverse proxy
- **Default Port**: 80 (configurable via `NGINX_PORT`)
- **Dependencies**: App, Frontend, MinIO
- **Volumes**:
  - `./nginx/nginx.conf:/etc/nginx/conf.d/default.conf.template`
  - `./nginx/entrypoint.sh:/entrypoint.sh`
- **Command**: Runs an entrypoint script that configures and starts Nginx

## Supporting Services

### PostgreSQL

- **Image**: `postgres:17.2-alpine3.21`
- **Purpose**: Main database
- **Default Port**: 5432 (internal)
- **Volumes**: `./volumes/postgres-db:/var/lib/postgresql/data`
- **Environment Variables**:
  - `POSTGRES_PASSWORD`: Database password
  - `POSTGRES_USER`: Database username
  - `POSTGRES_DB`: Database name
- **Health Check**: Ensures database is ready before dependent services start

### Redis

- **Image**: `redis:latest`
- **Purpose**: Cache and shared runtime state
- **Used For**:
  - Application caching
  - Rate limiting
  - Locks

### MinIO

- **Image**: `minio/minio:RELEASE.2024-11-07T00-52-20Z`
- **Purpose**: Object storage (S3-compatible)
- **Volumes**: `./volumes/minio-data:/data`
- **Environment Variables**:
  - `MINIO_BROWSER_REDIRECT_URL`: URL for MinIO console
  - `MINIO_SERVER_URL`: URL for MinIO server
  - `MINIO_ROOT_USER`: MinIO username (same as `MINIO_ACCESS_KEY`)
  - `MINIO_ROOT_PASSWORD`: MinIO password (same as `MINIO_SECRET_KEY`)
- **Command**: `server /data --console-address ":9001"`

### Playwright

- **Image**: `Spraply/playwright:1.1`
- **Purpose**: Headless browser for JavaScript rendering
- **Default Port**: 8000 (internal)
- **Environment Variables**:
  - `AUTH_API_KEY`: API key for authentication
  - `PORT`: Service port
  - `HOST`: Service host

## Service Interaction

The services interact as follows:

1. **User Flow**:
   - Users access the application through Nginx (port 80)
   - Nginx routes requests to Frontend or App based on the URL path
   - API requests are sent to the App
   - Static assets are served by Frontend

1. **Crawl Job Flow**:
   - App receives crawl/search requests from users
   - App processes jobs through the FastAPI backend runtime
   - Redis supports caching/state when enabled
   - Results are stored in PostgreSQL and file assets in MinIO
   - Users can monitor job status through the Frontend

1. **Storage Flow**:
   - Media files are stored in MinIO
   - MinIO provides S3-compatible API for file operations
   - Nginx proxies MinIO requests for simplified access

## Scaling Considerations

When scaling the application, consider:

1. **App Workers**: Increase Uvicorn worker count for API throughput
1. **PostgreSQL**: Consider using a managed database service for production
1. **Redis**: Scale for larger cache/state workloads
1. **Storage**: MinIO can be configured for cluster mode or replaced with S3

## Monitoring

Monitor your services using:

```bash
# Check service status
docker compose ps

# View logs for all services
docker compose logs

# View logs for a specific service
docker compose logs app

# Follow logs in real-time
docker compose logs -f

# View resource usage
docker stats
```
