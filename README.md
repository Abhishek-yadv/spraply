# Spraply

![Spraply Banner](assets/banner.png)

Spraply is a web crawling and search platform for extracting relevant web data.

> Backend update: the backend is built with FastAPI

## Quick Start

### Run with Docker

1. Clone the repository:

    ```bash
    git clone https://github.com/Abhishek-yadv/Spraply.git
    cd Spraply
    ```

2. Start services:

    ```bash
    cd docker
    cp .env.example .env
    docker compose up -d
    ```

3. Open the app:

    - [http://localhost](http://localhost)

## Project Structure

- `backend/` — FastAPI backend service
- `frontend/` — React + Vite frontend
- `docker/` — local and production compose files
- `docs/` — documentation site
- `tutorials/` — tutorial apps and notebooks

## Development

- Setup and development workflow: [DEV_SETUP.md](./DEV_SETUP.md)
- Deployment guide: [DEPLOYMENT.md](./DEPLOYMENT.md)

## Features

- Configurable web crawling and scraping
- Search and filtering workflows
- Async processing and job-based execution
- REST API with OpenAPI docs
- Self-hosted deployment with Docker
