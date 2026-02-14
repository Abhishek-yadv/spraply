# Troubleshooting Guide

This guide covers common issues and their solutions when running Spraply self-hosted with Docker.

## Common Issues

### Services Not Starting

#### Symptoms
- Services fail to start
- Docker containers exit immediately
- Error messages in docker logs

#### Solutions
1. Check container logs:
   ```bash
   docker compose logs [service_name]
   ```

2. Verify Docker Compose configuration:
   ```bash
   docker compose config
   ```

3. Check system resources:
   ```bash
   docker stats
   ```

4. Ensure all required ports are available:
   ```bash
   netstat -tulpn | grep LISTEN
   ```

5. Check for proper environment variables in .env:
   ```bash
   cat docker/.env | grep -v "^#" | grep -v "^$"
   ```

### Database Connection Issues

#### Symptoms
- App fails to connect to database
- Database-related error messages
- Slow database operations

#### Solutions
1. Verify PostgreSQL is running:
   ```bash
   docker compose ps db
   ```

2. Check database logs:
   ```bash
   docker compose logs db
   ```

3. Ensure database credentials in .env match:
   ```bash
   grep -E "POSTGRES_|DATABASE" docker/.env
   ```

4. Restart the database service:
   ```bash
   docker compose restart db
   ```

5. Check if the database is healthy:
   ```bash
   docker compose exec db pg_isready -U postgres
   ```

### File Upload/Download Issues

#### Symptoms
- Unable to upload or download files
- MinIO-related errors
- Broken links to files

#### Solutions
1. Check MinIO configuration in .env:
   ```bash
   grep "MINIO_" docker/.env
   ```

2. Verify MinIO service is running:
   ```bash
   docker compose ps minio
   ```

3. Check MinIO logs:
   ```bash
   docker compose logs minio
   ```

4. **Important**: Ensure MinIO external endpoint is properly configured when running on non-localhost environments:
   ```bash
   # These settings MUST match your domain
   MINIO_EXTERNAL_ENDPOINT=your-domain.com
   MINIO_BROWSER_REDIRECT_URL=https://your-domain.com/minio-console/
   MINIO_SERVER_URL=https://your-domain.com/
   ```

5. Test MinIO connectivity:
   ```bash
   docker compose exec app python -c "import socket; socket.create_connection(('minio', 9000), 5); print('Connection successful: True')"
   ```

### Background Processing Issues

#### Symptoms
- Crawl/search tasks not progressing
- Requests stay in `new` or `running`
- App worker restarts repeatedly

#### Solutions
1. Check app logs:
   ```bash
   docker compose logs app
   ```

2. Verify Redis is running properly:
   ```bash
   docker compose ps redis
   docker compose logs redis
   ```

3. Restart the app service:
   ```bash
   docker compose restart app
   ```

4. Check current crawl/search/sitemap statuses through the API:
   ```bash
   curl http://localhost/api/v1/core/crawl-requests/
   curl http://localhost/api/v1/core/search/
   curl http://localhost/api/v1/core/sitemaps/
   ```

### Nginx Configuration Issues

#### Symptoms
- 502 Bad Gateway errors
- Cannot access web interface
- Routing problems between services

#### Solutions
1. Check Nginx logs:
   ```bash
   docker compose logs nginx
   ```

2. Verify Nginx configuration generated from template:
   ```bash
   docker compose exec nginx cat /etc/nginx/conf.d/default.conf
   ```

3. Restart Nginx:
   ```bash
   docker compose restart nginx
   ```

4. Test connectivity to app service:
   ```bash
   docker compose exec nginx curl -I http://app:9000
   ```

### Permission Issues

#### Symptoms
- Permission denied errors
- Cannot write to volumes
- File access problems

#### Solutions
1. Check volume permissions:
   ```bash
   ls -la docker/volumes/
   ```

2. Fix permissions if needed:
   ```bash
   chmod -R 777 docker/volumes/
   ```

3. Restart affected services:
   ```bash
   docker compose restart
   ```

## Rebuilding and Upgrading

If you're experiencing persistent issues, you might need to rebuild the services:

1. Stop all containers:
   ```bash
   docker compose down
   ```

2. Optionally backup data:
   ```bash
   cp -r docker/volumes docker/volumes_backup
   cp docker/.env docker/.env.backup
   ```

3. Pull the latest images:
   ```bash
   docker compose pull
   ```

4. Start services:
   ```bash
   docker compose up -d
   ```

5. Apply migrations:
   ```bash
   docker compose exec app alembic upgrade head
   ```

## Advanced Debugging

### Database Inspection
```bash
docker compose exec db psql -U postgres -d postgres
```

### Python Shell Access
```bash
docker compose exec app python
```

### Container Shell Access
```bash
docker compose exec [service_name] sh
```

### Docker Logs with Time
```bash
docker compose logs --timestamps [service_name]
```

### Check Environment Variables in Container
```bash
docker compose exec [service_name] env
```

### Memory Usage Issues
If you're experiencing out-of-memory errors:

```bash
# View memory usage
docker stats

# Increase memory limits in your container orchestration
# Edit docker-compose.yml to add:
#   deploy:
#     resources:
#       limits:
#         memory: 2G
```

## Getting Help

If you're unable to resolve an issue using this guide, you can:

1. Check the [GitHub Issues](https://github.com/Abhishek-yadv/Spraply/issues) for similar problems
2. Open a new issue with details about your problem
3. Contact support at support@spraply.dev
