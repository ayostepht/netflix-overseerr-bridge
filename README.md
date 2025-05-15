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

## Building and Running

1. Build the Docker image:
```bash
docker build -t netflix-overseerr-bridge .
```

2. Run the container:
```bash
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  --name netflix-overseerr-bridge \
  netflix-overseerr-bridge
```

## Running with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3'
services:
  netflix-overseerr-bridge:
    build: .
    environment:
      - OVERSEERR_URL=http://your-overseerr-url:5055
      - OVERSEERR_API_KEY=your-api-key
    restart: unless-stopped
```

Then run:
```bash
docker-compose up -d
```

## Scheduling

To run this container on a schedule (e.g., weekly), you can use Docker's restart policy or set up a cron job:

```bash
# Example cron job to run weekly
0 0 * * 0 docker restart netflix-overseerr-bridge
```

## Notes

- The container will fetch Netflix's top 10 content and attempt to request each item in Overseerr
- If a title is not found in Overseerr, it will be logged and skipped
- The script includes a 1-second delay between requests to be respectful to the Overseerr API
- All actions are logged for monitoring and debugging 