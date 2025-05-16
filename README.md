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
- `NETFLIX_COUNTRY`: (Optional) The country's Netflix top 10 list to sync (e.g., "United States", "United Kingdom", "Japan"). Defaults to "United States"

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
      - NETFLIX_COUNTRY=United States  # Optional: Set country for Netflix top 10 list
    restart: unless-stopped
```

2. Create a `.env` file in the same directory:
```bash
OVERSEERR_URL=http://your-overseerr-url:5055
OVERSEERR_API_KEY=your-api-key
RUN_FREQUENCY=24  # Optional: Set run frequency in hours
NETFLIX_COUNTRY="United States"  # Optional: Set country for Netflix top 10 list (use quotes for country names with spaces)
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
  -e NETFLIX_COUNTRY="United States" \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest
```

## Country Selection

The `NETFLIX_COUNTRY` environment variable allows you to specify which country's Netflix top 10 list to sync. Country names should be wrapped in quotes, especially when they contain spaces. Examples:

```bash
# In .env file:
NETFLIX_COUNTRY="United States"
NETFLIX_COUNTRY="United Kingdom"
NETFLIX_COUNTRY="New Zealand"
NETFLIX_COUNTRY="South Korea"
```

Common country values:
- "United States" (default)
- "United Kingdom"
- "Japan"
- "Germany"
- "France"
- "Brazil"
- "Australia"
- "South Korea"
- "India"
- "Canada"

Note: Make sure to use the exact country name as it appears in Netflix's data. The country name is case-sensitive.

## Manual Execution

You can manually trigger the script at any time by executing into the container:

```bash
# Execute into the container
docker exec -it netflix-overseerr-bridge /bin/bash

# Run the script with default settings
python src/scraper.py

# Run in dry run mode
python src/scraper.py --dry-run

# Run with a specific country
python src/scraper.py --country "United Kingdom"

# Run with both dry run and country
python src/scraper.py --dry-run --country "United Kingdom"
```

This is useful for testing different configurations or manually triggering a sync.

## Run Frequency

By default, the container runs once per day at 2 AM. You can customize the run frequency using the `RUN_FREQUENCY` environment variable:

```bash
# Run every 12 hours
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e RUN_FREQUENCY=12 \
  -e NETFLIX_COUNTRY="United States" \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest

# Run weekly (168 hours)
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e RUN_FREQUENCY=168 \
  -e NETFLIX_COUNTRY="United States" \
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

## Dry Run Mode

You can run the container in "dry run" mode to see what would be requested without actually making the requests. This is useful for testing and verifying the configuration. To enable dry run mode, add the `--dry-run` flag when running the container:

```bash
# Using Docker Compose
docker-compose run --rm netflix-overseerr-bridge --dry-run

# Using Docker directly
docker run --rm \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e NETFLIX_COUNTRY="United States" \
  stephtanner1/netflix-overseerr-bridge:latest --dry-run
```

In dry run mode, the script will:
- Fetch the Netflix top 10 list as normal
- Search for titles in Overseerr
- Log what would be requested without making actual requests
- Show the TMDB IDs that would be used for each request