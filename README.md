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
- `RUN_FREQUENCY`: (Optional) Run frequency in hours (e.g., 24 for daily, 168 for weekly)

## Quick Start with Docker Compose

1. Create a `docker-compose.yml` file:

```yaml
services:
  netflix-overseerr-bridge:
    container_name: netflix-overseerr-bridge
    image: stephtanner1/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - RUN_FREQUENCY=24  # Optional: Set run frequency in hours (e.g., 24 for daily)
    restart: unless-stopped
```

2. Create a `.env` file in the same directory:
```bash
OVERSEERR_URL=http://your-overseerr-url:5055
OVERSEERR_API_KEY=your-api-key
RUN_FREQUENCY=24  # Optional: Set run frequency in hours
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
  -e RUN_FREQUENCY=24 \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest
```

## Run Frequency

By default, the container runs once per day at 2 AM. You can customize the run frequency using the `RUN_FREQUENCY` environment variable:

```bash
# Run every 12 hours
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e RUN_FREQUENCY=12 \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest

# Run weekly (168 hours)
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e RUN_FREQUENCY=168 \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest
```

Common frequency values:
- 24: Daily
- 168: Weekly
- 720: Monthly (30 days)
- 8760: Yearly

## Notes

- The container will fetch Netflix's top 10 content and attempt to request each item in Overseerr
- If a title is not found in Overseerr, it will be logged and skipped
- The script includes a 1-second delay between requests to be respectful to the Overseerr API
- All actions are logged for monitoring and debugging
- The container uses Python 3.11 and runs the scraper script automatically on startup