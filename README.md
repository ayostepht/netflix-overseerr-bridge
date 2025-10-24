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
- `DRY_RUN`: (Optional) Set to "true", "1", or "yes" to enable dry run mode. Defaults to false.
- `KOMETA_ENABLED`: (Optional) Set to "true", "1", or "yes" to enable Kometa YAML file generation. Defaults to false.
- `KOMETA_OUTPUT_DIR`: (Optional) Base directory where Kometa YAML files will be saved. Defaults to "/config/kometa"
- `KOMETA_MOVIES_DIR`: (Optional) Specific directory for movie collection files. Defaults to KOMETA_OUTPUT_DIR
- `KOMETA_TV_DIR`: (Optional) Specific directory for TV collection files. Defaults to KOMETA_OUTPUT_DIR

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
      - NETFLIX_COUNTRY='United States'  # Optional: Set country for Netflix top 10 list
      - DRY_RUN=false  # Optional: Enable dry run mode, defaults to false
      - KOMETA_ENABLED=false  # Optional: Enable Kometa YAML file generation
      - KOMETA_OUTPUT_DIR=/config/kometa  # Optional: Base directory for Kometa YAML files
      - KOMETA_MOVIES_DIR=/config/kometa/movies  # Optional: Movie collections directory
      - KOMETA_TV_DIR=/config/kometa/tv  # Optional: TV collections directory
    volumes:
      - ./kometa:/config/kometa  # Optional: Mount directory for Kometa YAML files
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
  -e NETFLIX_COUNTRY='United States' \
  -e DRY_RUN=false \
  -e KOMETA_ENABLED=false \
  -e KOMETA_OUTPUT_DIR=/config/kometa \
  -e KOMETA_MOVIES_DIR=/config/kometa/movies \
  -e KOMETA_TV_DIR=/config/kometa/tv \
  -v ./kometa:/config/kometa \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest
```

## Kometa YAML Generation

The bridge can automatically generate Kometa YAML files for creating Netflix Top 10 collections in your media library. This optional feature (disabled by default) creates country-specific collection files that Kometa can use to build dynamic collections.

### Benefits

- **Automated Collection Management**: Keep your Netflix Top 10 collections automatically updated
- **Country-Specific Collections**: Generate separate collections for different Netflix regions
- **TMDb/TVDb Accuracy**: Uses TMDb IDs for movies and TVDb IDs for TV shows for precise media matching
- **Zero Maintenance**: Collections update automatically with fresh Netflix data
- **Library Organization**: Places Netflix collections at the top of your library for easy access

### Enabling Kometa Generation

Kometa YAML file generation is **disabled by default**. To enable it, set the `KOMETA_ENABLED` environment variable to `true` and configure the output directory:

```yaml
services:
  netflix-overseerr-bridge:
    container_name: netflix-overseerr-bridge
    image: stephtanner1/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - KOMETA_ENABLED=true                    # Enable Kometa YAML generation
      - KOMETA_OUTPUT_DIR=/config/kometa       # Base directory (default)
      - KOMETA_MOVIES_DIR=/config/kometa/movies # Movie collections directory
      - KOMETA_TV_DIR=/config/kometa/tv        # TV collections directory
      - NETFLIX_COUNTRY="United States"        # Country for collections
    volumes:
      - ./kometa:/config/kometa                # Mount directory for YAML files
    restart: unless-stopped
```

**Important**: The volume mount (`./kometa:/config/kometa`) is required when Kometa generation is enabled. This maps a local directory to the container's output directory.

### Generated Files

When enabled, the bridge generates two YAML files per country:

- `netflix_movies_{country}.yml` - Contains TMDb IDs for top 10 movies (uses `tmdb_movie` builder)
- `netflix_tv_{country}.yml` - Contains TVDb IDs for top 10 TV shows (uses `tvdb_show` builder for better Plex matching)

#### TVDb Builder for Better Plex Matching

The bridge now uses the **TVDb builder** (`tvdb_show`) instead of the TMDb builder (`tmdb_show`) for TV shows. This change provides several benefits:

- **Better Plex Compatibility**: Plex primarily uses TVDb for TV show metadata, ensuring more accurate matching
- **Eliminates Conversion Warnings**: No more "Convert Warning: No TVDb ID Found for TMDb ID" messages in Kometa logs
- **Improved Collection Accuracy**: TV shows are more likely to be found and matched correctly in your Plex library
- **Automatic ID Resolution**: The bridge automatically converts TMDb IDs to TVDb IDs using Overseerr's API

For example, with `NETFLIX_COUNTRY="United States"`, these files will be generated:

- `netflix_movies_united_states.yml`
- `netflix_tv_united_states.yml`

### YAML File Structure

Each generated file contains a Kometa collection configuration:

```yaml
collections:
  Netflix Top 10 Movies - United States:
    tmdb_movie:
    - 550
    - 27205
    - 293660
    # ... more TMDb IDs
    sync_mode: sync
    sort_title: '!Netflix Netflix Top 10 Movies - United States'
    summary: Netflix Top 10 movies for United States as of 2025-10-23
    collection_mode: default

  Netflix Top 10 TV Shows - United States:
    tvdb_show:  # Uses TVDb IDs for better Plex matching
    - 123456
    - 789012
    - 345678
    # ... more TVDb IDs
    sync_mode: sync
    sort_title: '!Netflix Netflix Top 10 TV Shows - United States'
    summary: Netflix Top 10 TV shows for United States as of 2025-10-23
    collection_mode: default
```

### Key Features

- **Country-Specific Files**: Separate files for each country's Netflix data
- **TMDb/TVDb Integration**: Uses TMDb IDs for movies and TVDb IDs for TV shows for accurate media matching
- **Sync Mode**: Collections replace entirely on each update (sync_mode: sync)
- **Custom Sort**: Collections appear at the top of your library (!Netflix prefix)
- **Error Handling**: Continues processing even if some titles can't be matched
- **Automatic Updates**: Files are regenerated on each run with current Top 10 data

### Configuring Kometa

Once the bridge is generating YAML files, you need to configure your existing Kometa setup to use them. The bridge creates separate files for movies and TV shows that can be integrated into your current Kometa configuration.

#### Step-by-Step Integration

1. **Ensure Volume Mount**: Verify your Kometa container has access to the generated YAML files:

```yaml
# In your Kometa service
volumes:
  - ./kometa-config:/config           # Your existing Kometa config
  - ./kometa:/config/netflix-yaml     # Netflix YAML files from bridge
```

2. **Update Kometa Configuration**: Add the generated files to your existing `config.yml`:

```yaml
# config.yml - Add to existing libraries section
libraries:
  Movies:
    collection_files:
      - file: /config/existing-collections.yml    # Your existing collections
      - file: /config/netflix-yaml/netflix_movies_united_states.yml  # Netflix movies

  TV Shows:
    collection_files:
      - file: /config/existing-tv-collections.yml # Your existing TV collections
      - file: /config/netflix-yaml/netflix_tv_united_states.yml      # Netflix TV shows
```

3. **Multiple Countries**: For multiple country configurations:

```yaml
libraries:
  Movies:
    collection_files:
      - file: /config/existing-collections.yml
      - file: /config/netflix-yaml/netflix_movies_united_states.yml
      - file: /config/netflix-yaml/netflix_movies_united_kingdom.yml
      - file: /config/netflix-yaml/netflix_movies_japan.yml

  TV Shows:
    collection_files:
      - file: /config/existing-collections.yml
      - file: /config/netflix-yaml/netflix_tv_united_states.yml
      - file: /config/netflix-yaml/netflix_tv_united_kingdom.yml
      - file: /config/netflix-yaml/netflix_tv_japan.yml
```

#### Important Configuration Notes

- **Non-Destructive**: The bridge generates separate YAML files and will never modify your existing Kometa configuration
- **File Naming**: Files are named based on country (e.g., `netflix_movies_united_states.yml`, `netflix_tv_united_kingdom.yml`)
- **Path Consistency**: Ensure the paths in your `config.yml` match your volume mount structure
- **Collection Ordering**: Netflix collections use `!Netflix` prefix to appear at the top of your library
- **Update Frequency**: Collections automatically update when the bridge runs (based on your `RUN_FREQUENCY`)

#### Alternative Library Setup

If you prefer dedicated Netflix libraries:

```yaml
libraries:
  Movies:
    collection_files:
      - file: /config/existing-collections.yml

  TV Shows:
    collection_files:
      - file: /config/existing-tv-collections.yml

  Netflix Movies:
    collection_files:
      - file: /config/netflix-yaml/netflix_movies_united_states.yml

  Netflix TV:
    collection_files:
      - file: /config/netflix-yaml/netflix_tv_united_states.yml
```

### Using with Kometa

1. **Mount the output directory** to your Kometa container
2. **Configure Kometa** to read from the generated YAML files
3. **Collections** will be automatically created/updated based on current Netflix Top 10 data

#### Complete Docker Compose Example with Kometa

```yaml
services:
  netflix-overseerr-bridge:
    container_name: netflix-overseerr-bridge
    image: stephtanner1/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - KOMETA_ENABLED=true
      - KOMETA_OUTPUT_DIR=/config/kometa
      - KOMETA_MOVIES_DIR=/config/kometa/movies
      - KOMETA_TV_DIR=/config/kometa/tv
      - NETFLIX_COUNTRY="United States"
    volumes:
      - ./kometa:/config/kometa
    restart: unless-stopped

  kometa:
    container_name: kometa
    image: kometateam/kometa:latest
    environment:
      - KOMETA_CONFIG=/config/config.yml
    volumes:
      - ./kometa-config:/config
      - ./kometa:/config/kometa  # Same mount as bridge
    restart: unless-stopped
```

#### Kometa Configuration Example

```yaml
# In your Kometa config.yml
libraries:
  Movies:
    collection_files:
      - file: /config/kometa/netflix_movies_united_states.yml
  TV Shows:
    collection_files:
      - file: /config/kometa/netflix_tv_united_states.yml
```

#### Multi-Country Example

To generate collections for multiple countries, run separate containers:

```yaml
services:
  netflix-bridge-us:
    container_name: netflix-bridge-us
    image: stephtanner1/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - KOMETA_ENABLED=true
      - NETFLIX_COUNTRY="United States"
    volumes:
      - ./kometa:/config/kometa
    restart: unless-stopped

  netflix-bridge-uk:
    container_name: netflix-bridge-uk
    image: stephtanner1/netflix-overseerr-bridge:latest
    environment:
      - OVERSEERR_URL=${OVERSEERR_URL}
      - OVERSEERR_API_KEY=${OVERSEERR_API_KEY}
      - KOMETA_ENABLED=true
      - NETFLIX_COUNTRY="United Kingdom"
    volumes:
      - ./kometa:/config/kometa
    restart: unless-stopped
```

This generates files for both countries:

- `netflix_movies_united_states.yml`
- `netflix_tv_united_states.yml`
- `netflix_movies_united_kingdom.yml`
- `netflix_tv_united_kingdom.yml`

## Country Selection

The `NETFLIX_COUNTRY` environment variable allows you to specify which country's Netflix top 10 list to sync. The country name must match exactly as it appears in Netflix's data. When you run the script, it will log the available countries in the Netflix data.

```yaml
environment:
  - NETFLIX_COUNTRY="United Kingdom"
  - NETFLIX_COUNTRY="Japan"
```

When running manually from the command line, any type of quotes will work:

```bash
# All of these work:
python src/scraper.py --country "United Kingdom"
python src/scraper.py --country 'United Kingdom'
python src/scraper.py --country United\ Kingdom
```

Common country values (exact names from Netflix data):

- "United States"
- "United Kingdom"
- "Japan"
- "Germany"
- "France"
- "Brazil"
- "Australia"
- "South Korea"
- "India"
- "Canada"

Note: The country name is case-sensitive and must match exactly as it appears in Netflix's data. If you're unsure of the exact name, run the script once and check the logs for the list of available countries.

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
  -e NETFLIX_COUNTRY='United States' \
  -e KOMETA_ENABLED=false \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest

# Run weekly (168 hours)
docker run -d \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e RUN_FREQUENCY=168 \
  -e NETFLIX_COUNTRY='United States' \
  -e KOMETA_ENABLED=false \
  --name netflix-overseerr-bridge \
  stephtanner1/netflix-overseerr-bridge:latest
```

Common frequency values:

- 24: Daily
- 168: Weekly
- 720: Monthly (30 days)
- 8760: Yearly

## Dry Run Mode

You can run the container in "dry run" mode to see what would be requested without actually making the requests. This is useful for testing and verifying the configuration. To enable dry run mode, add the `--dry-run` flag when running the container:

```bash
# Using Docker Compose
docker-compose run --rm netflix-overseerr-bridge --dry-run

# Using Docker directly
docker run --rm \
  -e OVERSEERR_URL="http://your-overseerr-url:5055" \
  -e OVERSEERR_API_KEY="your-api-key" \
  -e NETFLIX_COUNTRY='United States' \
  -e KOMETA_ENABLED=false \
  stephtanner1/netflix-overseerr-bridge:latest --dry-run
```

In dry run mode, the script will:

- Fetch the Netflix top 10 list as normal
- Search for titles in Overseerr
- Log what would be requested without making actual requests
- Show the TMDB IDs that would be used for each request

## Notes

- The container will fetch Netflix's top 10 content and attempt to request each item in Overseerr
- If a title is not found in Overseerr, it will be logged and skipped
- The script includes a 1-second delay between requests to be respectful to the Overseerr API
- All actions are logged for monitoring and debugging
- The container uses Python 3.11 and runs the scraper script automatically on startup

## Recent Improvements

The bridge has been enhanced with intelligent content matching and error handling:

### Smart Title Matching

- **Exact Title Matching**: Prioritizes exact title matches with correct media type (movie vs TV)
- **Fallback Logic**: If exact matches aren't found, falls back to most recent releases
- **Media Type Detection**: Automatically distinguishes between movies and TV shows

### Intelligent Season Selection for TV Shows

- **Progressive Season Requests**: Tries season 1 first, then season 2, then season 3
- **Already Requested Detection**: Properly identifies when seasons are already requested or downloading
- **Smart Fallbacks**: Handles cases where earlier seasons are unavailable

### Enhanced Error Handling

- **500 Error Elimination**: Fixed connection issues with TV show requests
- **Proper Error Categorization**: Distinguishes between "not found" vs "error" status
- **TMDB Integration**: Better handling of shows not found in TMDB database

### Expected Success Rates

- **Movies**: ~95-100% success rate (most movies are found and requested successfully)
- **TV Shows**: ~85-95% success rate (some shows may not be in Overseerr database)
- **Overall**: ~90-95% success rate across all content types

## Troubleshooting

### Common Issues and Solutions

#### "TV show not found in Overseerr database"

- This is normal for shows that haven't been imported into your Overseerr instance
- The show exists in TMDB but not in your local Overseerr database
- No action needed - this is expected behavior

#### "Season 1 already available or requested"

- The show is already being downloaded or is available in your media library
- The bridge correctly identifies this and skips the request
- This is working as designed

#### "No seasons available to request"

- All seasons of the show are already requested or available
- The bridge will try the next available season automatically
- No action needed

#### High error count in summary

- Check that your `OVERSEERR_URL` and `OVERSEERR_API_KEY` are correct
- Verify your Overseerr instance is running and accessible
- Ensure your API key has request permissions

### Performance Notes

- The bridge processes ~20 titles (10 movies + 10 TV shows) per run
- Each request includes a 1-second delay to be respectful to the API
- Total processing time is typically 20-30 seconds per run
- The bridge runs automatically based on your `RUN_FREQUENCY` setting
