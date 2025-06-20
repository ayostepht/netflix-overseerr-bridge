import requests
import os
import logging
from datetime import datetime, timedelta
import time
from urllib.parse import quote
import csv
import io
import sys
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NetflixOverseerrBridge:
    def __init__(self, dry_run=False):
        self.netflix_tsv_url = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
        self.dry_run = dry_run
        
        # Validate Overseerr configuration
        self.overseerr_url = os.getenv('OVERSEERR_URL')
        self.overseerr_api_key = os.getenv('OVERSEERR_API_KEY')
        country = os.getenv('NETFLIX_COUNTRY', 'United States')  # Default to United States
        # Strip any quotes from the country name
        self.country = country.strip('"\'')
        
        # Log environment variables for debugging
        logger.info(f"Environment variables:")
        logger.info(f"OVERSEERR_URL: {self.overseerr_url}")
        logger.info(f"NETFLIX_COUNTRY: {self.country}")
        logger.info(f"DRY_RUN: {os.getenv('DRY_RUN', 'not set')}")
        
        if not self.overseerr_url or not self.overseerr_api_key:
            logger.error("Missing required environment variables!")
            logger.error("Please set OVERSEERR_URL and OVERSEERR_API_KEY")
            logger.error("Example:")
            logger.error("export OVERSEERR_URL='http://192.168.0.115:5055'")
            logger.error("export OVERSEERR_API_KEY='your-api-key-here'")
            sys.exit(1)
            
        # Ensure URL has no trailing slash
        self.overseerr_url = self.overseerr_url.rstrip('/')
        
        # Configure retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[500, 502, 503, 504]  # retry on these status codes
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/tab-separated-values'
        }
        
        # Test Overseerr connection
        self._test_overseerr_connection()

    def _test_overseerr_connection(self):
        """Test the connection to Overseerr"""
        try:
            test_url = f"{self.overseerr_url}/api/v1/status"
            headers = {
                'X-Api-Key': self.overseerr_api_key,
                'Accept': 'application/json'
            }
            response = self.session.get(test_url, headers=headers)
            response.raise_for_status()
            logger.info("Successfully connected to Overseerr")
        except Exception as e:
            logger.error(f"Failed to connect to Overseerr: {str(e)}")
            logger.error("Please check your Overseerr URL and API key")
            sys.exit(1)

    def get_netflix_top10(self):
        try:
            response = self.session.get(self.netflix_tsv_url, headers=self.headers)
            response.raise_for_status()
            
            # Parse TSV data
            tsv_data = list(csv.DictReader(io.StringIO(response.text), delimiter='\t'))
            
            # Get unique country names for debugging
            available_countries = sorted(set(row['country_name'] for row in tsv_data))
            logger.info(f"Available countries in Netflix data: {', '.join(available_countries)}")
            
            # Filter for selected country data
            country_data = [row for row in tsv_data if row['country_name'] == self.country]
            
            if not country_data:
                logger.error(f"No data found for {self.country}")
                logger.error(f"Please use one of the available countries listed above")
                return [], []
            
            # Get the most recent week
            most_recent_week = max(row['week'] for row in country_data)
            logger.info(f"Processing data for {self.country} - week: {most_recent_week}")
            
            # Filter for most recent week
            recent_data = [row for row in country_data if row['week'] == most_recent_week]
            
            # Separate movies and TV shows
            movies = []
            tv_shows = []
            
            for row in recent_data:
                if row['category'] == 'Films':
                    movies.append(row['show_title'])
                elif row['category'] == 'TV':
                    tv_shows.append(row['show_title'])
            
            logger.info(f"Found {len(movies)} movies and {len(tv_shows)} TV shows for the most recent week")
            return movies[:10], tv_shows[:10]  # Return top 10 of each
            
        except Exception as e:
            logger.error(f"Error fetching Netflix top 10: {str(e)}")
            return [], []

    def request_in_overseerr(self, title, media_type):
        try:
            # Search for the title in Overseerr
            search_url = f"{self.overseerr_url}/api/v1/search"
            search_params = {
                'query': quote(title),
                'page': 1
            }
            search_headers = {
                'X-Api-Key': self.overseerr_api_key,
                'Accept': 'application/json'
            }
            
            search_response = self.session.get(
                search_url,
                params=search_params,
                headers=search_headers
            )
            
            if search_response.status_code == 200:
                search_results = search_response.json()
                if not search_results.get('results'):
                    logger.warning(f"No results found for {title} in TMDB")
                    return {'status': 'not_found', 'message': 'No results found in TMDB'}
                
                # Get all results and sort by release date
                results = search_results['results']
                if len(results) > 1:
                    # First, try to find exact title matches with correct media type
                    exact_matches = [r for r in results if r.get('title', r.get('name', '')).lower() == title.lower() and r.get('mediaType') == media_type]
                    if exact_matches:
                        # Use exact match with most recent date
                        exact_matches.sort(key=lambda x: x.get('releaseDate', '') or x.get('firstAirDate', ''), reverse=True)
                        results = exact_matches
                        logger.info(f"Found {len(results)} exact title matches for {title}, using most recent release from {results[0].get('releaseDate', '') or results[0].get('firstAirDate', '')}")
                    else:
                        # Fall back to sorting by release date (most recent first)
                        results.sort(key=lambda x: x.get('releaseDate', '') or x.get('firstAirDate', ''), reverse=True)
                        logger.info(f"Found {len(results)} matches for {title}, using most recent release from {results[0].get('releaseDate', '') or results[0].get('firstAirDate', '')}")
                else:
                    logger.info(f"Found 1 match for {title}")
                
                # Get the first (most recent) result
                media_item = results[0]
                media_id = media_item['id']
                
                # For TV shows, we need to get the first season
                if media_type == 'tv':
                    # First try requesting without specifying seasons
                    request_url = f"{self.overseerr_url}/api/v1/request"
                    request_data = {
                        'mediaId': media_id,
                        'mediaType': media_type,
                        'is4k': False
                    }
                else:
                    # For movies, use the original request format
                    request_url = f"{self.overseerr_url}/api/v1/request"
                    request_data = {
                        'mediaId': media_id,
                        'mediaType': media_type,
                        'is4k': False
                    }
                
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would request {title} ({media_type}) with ID {media_id}")
                    return {'status': 'dry_run', 'message': 'Dry run - would request'}
                
                request_response = self.session.post(
                    request_url,
                    json=request_data,
                    headers=search_headers
                )
                
                # For TV shows, if the first attempt fails, try with available seasons
                if media_type == 'tv' and request_response.status_code not in [201, 409]:
                    error_msg = request_response.json().get('message', 'Unknown error')
                    if 'Failed to fetch TV show details' in error_msg or '404' in error_msg or 'Cannot read properties of undefined' in error_msg:
                        # Try requesting season 1 first
                        logger.info(f"First attempt failed for {title}, trying with season 1...")
                        request_data['seasons'] = [1]
                        request_response = self.session.post(
                            request_url,
                            json=request_data,
                            headers=search_headers
                        )
                        
                        # If season 1 fails with "No seasons available", try season 2
                        if request_response.status_code not in [201, 409]:
                            error_msg = request_response.json().get('message', 'Unknown error')
                            if 'No seasons available to request' in error_msg:
                                logger.info(f"Season 1 not available for {title}, trying season 2...")
                                request_data['seasons'] = [2]
                                request_response = self.session.post(
                                    request_url,
                                    json=request_data,
                                    headers=search_headers
                                )
                                
                                # If season 2 fails with "No seasons available", try season 3
                                if request_response.status_code not in [201, 409]:
                                    error_msg = request_response.json().get('message', 'Unknown error')
                                    if 'No seasons available to request' in error_msg:
                                        logger.info(f"Season 2 not available for {title}, trying season 3...")
                                        request_data['seasons'] = [3]
                                        request_response = self.session.post(
                                            request_url,
                                            json=request_data,
                                            headers=search_headers
                                        )
                
                if request_response.status_code == 201:
                    logger.info(f"Successfully requested {title}")
                    return {'status': 'new_request', 'message': 'Successfully requested'}
                elif request_response.status_code == 409:
                    logger.info(f"Request for {title} already exists")
                    return {'status': 'existing_request', 'message': 'Request already exists'}
                else:
                    error_msg = request_response.json().get('message', 'Unknown error')
                    if 'Failed to fetch movie details' in error_msg:
                        logger.warning(f"Movie {title} not found in TMDB")
                        return {'status': 'not_found', 'message': 'Movie not found in TMDB'}
                    elif 'Failed to fetch TV show details' in error_msg:
                        logger.warning(f"TV show {title} not found in TMDB")
                        return {'status': 'not_found', 'message': 'TV show not found in TMDB'}
                    elif 'Could not find any entity of type "Media"' in error_msg:
                        logger.warning(f"Media {title} not found in Overseerr database")
                        return {'status': 'not_found', 'message': 'Media not found in Overseerr database'}
                    elif 'Cannot read properties of undefined' in error_msg:
                        logger.warning(f"TV show {title} not found in Overseerr database")
                        return {'status': 'not_found', 'message': 'TV show not found in Overseerr database'}
                    elif 'No seasons available to request' in error_msg:
                        logger.info(f"Season 1 of {title} is already available or requested")
                        return {'status': 'existing_request', 'message': 'Season already available or requested'}
                    else:
                        logger.warning(f"Failed to request {title}: {request_response.status_code} - {error_msg}")
                        return {'status': 'error', 'message': f'Request failed: {error_msg}'}
            else:
                logger.error(f"Search failed for {title}: {search_response.status_code} - {search_response.text}")
                return {'status': 'error', 'message': f'Search failed: {search_response.status_code}'}
        except Exception as e:
            logger.error(f"Error requesting {title} in Overseerr: {str(e)}")
            return {'status': 'error', 'message': f'Exception: {str(e)}'}

    def run(self, run_frequency_hours=None):
        while True:
            logger.info("Starting Netflix Top 10 to Overseerr bridge")
            
            # Initialize summary tracking
            summary = {
                'top_movies': [],
                'top_shows': [],
                'new_downloads': [],
                'existing_downloads': [],
                'errors': []
            }
            
            # Get top 10 titles for both movies and TV shows
            movies, tv_shows = self.get_netflix_top10()
            if not movies and not tv_shows:
                logger.error("Failed to fetch Netflix top 10")
                summary['errors'].append("Failed to fetch Netflix top 10")
            else:
                # Store top 10 lists
                summary['top_movies'] = movies
                summary['top_shows'] = tv_shows
                
                # Request each movie
                logger.info("Processing movies...")
                for title in movies:
                    logger.info(f"Processing movie: {title}")
                    try:
                        result = self.request_in_overseerr(title, 'movie')
                        if result['status'] == 'new_request':
                            summary['new_downloads'].append(f"{title} (Movie)")
                        elif result['status'] == 'existing_request':
                            summary['existing_downloads'].append(f"{title} (Movie)")
                        else:
                            summary['errors'].append(f"Failed to request movie: {title} - {result['message']}")
                    except Exception as e:
                        summary['errors'].append(f"Exception processing movie {title}: {str(e)}")
                    time.sleep(1)  # Be nice to the API

                # Request each TV show
                logger.info("Processing TV shows...")
                for title in tv_shows:
                    logger.info(f"Processing TV show: {title}")
                    try:
                        result = self.request_in_overseerr(title, 'tv')
                        if result['status'] == 'new_request':
                            summary['new_downloads'].append(f"{title} (TV)")
                        elif result['status'] == 'existing_request':
                            summary['existing_downloads'].append(f"{title} (TV)")
                        else:
                            summary['errors'].append(f"Failed to request TV show: {title} - {result['message']}")
                    except Exception as e:
                        summary['errors'].append(f"Exception processing TV show {title}: {str(e)}")
                    time.sleep(1)  # Be nice to the API

            # Display summary
            self._display_summary(summary)

            if run_frequency_hours is not None:
                # Use the specified run frequency
                sleep_seconds = run_frequency_hours * 3600
                next_run = datetime.now() + timedelta(seconds=sleep_seconds)
            else:
                # Calculate time until next run (tomorrow at 2 AM)
                now = datetime.now()
                next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                sleep_seconds = (next_run - now).total_seconds()
            
            logger.info(f"Next run scheduled for {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"Sleeping for {sleep_seconds/3600:.1f} hours")
            time.sleep(sleep_seconds)

    def _get_title_status(self, title, summary):
        """
        Determine the status of a title based on the summary data.
        
        Args:
            title (str): The title to check
            summary (dict): The summary dictionary containing new_downloads and existing_downloads
            
        Returns:
            str: Status string ('✓ New Request', '✓ Already Requested', or '✗ Failed')
        """
        # Check for exact matches in new_downloads and existing_downloads
        new_request = any(download.startswith(f"{title} (") for download in summary['new_downloads'])
        existing_request = any(download.startswith(f"{title} (") for download in summary['existing_downloads'])
        
        if new_request:
            return "✓ New Request"
        elif existing_request:
            return "✓ Already Requested"
        else:
            return "✗ Failed"

    def _display_summary(self, summary):
        """Display a summary of the processing results as a single log block with line breaks."""
        lines = []
        lines.append("=" * 60)
        lines.append("PROCESSING SUMMARY")
        lines.append("=" * 60)
        lines.append("Current Top 10 Shows:")
        lines.append("=== BEGIN SHOWS ===")
        if summary['top_shows']:
            for i, show in enumerate(summary['top_shows'], 1):
                status = self._get_title_status(show, summary)
                lines.append(f"  {i:2d}. {show} - {status}")
        else:
            lines.append("  No shows found")
        lines.append("=== END SHOWS ===\n")
        lines.append("Current Top 10 Movies:")
        lines.append("=== BEGIN MOVIES ===")
        if summary['top_movies']:
            for i, movie in enumerate(summary['top_movies'], 1):
                status = self._get_title_status(movie, summary)
                lines.append(f"  {i:2d}. {movie} - {status}")
        else:
            lines.append("  No movies found")
        lines.append("=== END MOVIES ===\n")
        lines.append("New Downloads:")
        if summary['new_downloads']:
            for download in summary['new_downloads']:
                lines.append(f"  ✓ {download}")
        else:
            lines.append("  No new downloads")
        lines.append("")
        lines.append("Existing Downloads:")
        if summary['existing_downloads']:
            for download in summary['existing_downloads']:
                lines.append(f"  ✓ {download}")
        else:
            lines.append("  No existing downloads")
        lines.append("")
        lines.append("Errors:")
        if summary['errors']:
            for error in summary['errors']:
                lines.append(f"  ✗ {error}")
        else:
            lines.append("  No errors")
        lines.append("")
        lines.append("Summary:")
        lines.append(f"  Total Shows Processed: {len(summary['top_shows'])}")
        lines.append(f"  Total Movies Processed: {len(summary['top_movies'])}")
        lines.append(f"  New Requests: {len(summary['new_downloads'])}")
        lines.append(f"  Existing Requests: {len(summary['existing_downloads'])}")
        lines.append(f"  Errors: {len(summary['errors'])}")
        lines.append("=" * 60)
        logger.info('\n'.join(lines))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Netflix Top 10 to Overseerr Bridge')
    parser.add_argument('--frequency', type=float, help='Run frequency in hours (e.g., 24 for daily, 168 for weekly)')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making actual requests')
    parser.add_argument('--country', type=str, help='Specify which country\'s Netflix top 10 list to sync (e.g., "United Kingdom")')
    args = parser.parse_args()
    
    # Check for frequency in environment variable first, then command line argument
    run_frequency = os.getenv('RUN_FREQUENCY')
    if run_frequency:
        try:
            run_frequency = float(run_frequency)
        except ValueError:
            logger.error("RUN_FREQUENCY environment variable must be a number")
            sys.exit(1)
    else:
        run_frequency = args.frequency
    
    # Override country from command line if specified
    if args.country:
        os.environ['NETFLIX_COUNTRY'] = args.country
        logger.info(f"Using country from command line: {args.country}")
    
    # Check for dry run in environment variable first, then command line argument
    dry_run = os.getenv('DRY_RUN', '').lower() in ('true', '1', 'yes')
    if dry_run:
        logger.info("Dry run mode enabled via environment variable")
    
    bridge = NetflixOverseerrBridge(dry_run=dry_run or args.dry_run)
    bridge.run(run_frequency) 