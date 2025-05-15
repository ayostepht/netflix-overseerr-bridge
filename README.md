# Netflix Top 10 to Overseerr Bridge

This Docker container automatically fetches Netflix's top 10 shows and movies in the US and requests them in your Overseerr instance.

## Prerequisites

- Docker installed on your system
- An Overseerr instance with API access
- Overseerr API key

## Environment Variables

The container requires the following environment variables:

- `OVERSEERR_URL`: The URL of your Overseerr instance (e.g., `http://overseerr:5055`)
- `OVERSEERR_API_KEY`: Your Overseerr API key

## Quick Start with Docker Compose

1. Create a `docker-compose.yml` file:

```yaml
version: '3'
services:
  netflix-overseerr-bridge:
    container_name: netflix-overseerr-bridge
    image: stephtanner/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
    restart: unless-stopped
```

2. Create a `.env` file in the same directory:
```bash
OVERSEERR_URL=http://your-overseerr-url:5055
OVERSEERR_API_KEY=your-api-key
```

3. Run the container:
```bash
docker-compose up -d
```

## Manual Docker Run

Alternatively, you can run the container directly with Docker:

```bash
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  --name netflix-overseerr-bridge \
  stephtanner/netflix-overseerr-bridge:latest
```

## Image Versions

The Docker image is automatically built and published using GitHub Actions. The following tags are available:

- `latest`: The most recent stable version
- `v1.0.0`, `v1.1.0`, etc.: Specific version releases
- `sha-abc123`: Git commit SHA for specific builds

To use a specific version, replace `latest` with the desired tag in your `docker-compose.yml` or `docker run` command.

## Scheduling

The container is configured to restart automatically unless explicitly stopped (`restart: unless-stopped`). This ensures the container will run after system reboots.

To run this container on a specific schedule (e.g., weekly), you can use a cron job:

```bash
# Example cron job to run weekly
0 0 * * 0 docker restart netflix-overseerr-bridge
```

## Notes

- The container will fetch Netflix's top 10 content and attempt to request each item in Overseerr
- If a title is not found in Overseerr, it will be logged and skipped
- The script includes a 1-second delay between requests to be respectful to the Overseerr API
- All actions are logged for monitoring and debugging
- The container uses Python 3.11 and runs the scraper script automatically on startup 