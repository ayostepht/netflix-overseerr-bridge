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
    def __init__(self):
        self.netflix_tsv_url = "https://www.netflix.com/tudum/top10/data/all-weeks-countries.tsv"
        
        # Validate Overseerr configuration
        self.overseerr_url = os.getenv('OVERSEERR_URL')
        self.overseerr_api_key = os.getenv('OVERSEERR_API_KEY')
        
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
            
            # Filter for US data
            us_data = [row for row in tsv_data if row['country_name'] == 'United States']
            
            if not us_data:
                logger.error("No data found for United States")
                return [], []
            
            # Get the most recent week
            most_recent_week = max(row['week'] for row in us_data)
            logger.info(f"Processing data for week: {most_recent_week}")
            
            # Filter for most recent week
            recent_data = [row for row in us_data if row['week'] == most_recent_week]
            
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
                    return False
                
                # Get the first result
                media_item = search_results['results'][0]
                media_id = media_item['id']
                
                # For TV shows, we need to get the first season
                if media_type == 'tv':
                    # Get TV show details to find the first season
                    tv_url = f"{self.overseerr_url}/api/v1/tv/{media_id}"
                    tv_response = self.session.get(tv_url, headers=search_headers)
                    
                    if tv_response.status_code != 200:
                        error_msg = tv_response.json().get('message', 'Unknown error')
                        if 'Unable to retrieve series' in error_msg:
                            logger.warning(f"TV show {title} not found in TMDB")
                        else:
                            logger.warning(f"Failed to get TV details for {title}: {tv_response.status_code} - {error_msg}")
                        return False
                        
                    tv_data = tv_response.json()
                    if not tv_data.get('seasons'):
                        logger.warning(f"No seasons found for {title}")
                        return False
                        
                    # Request the first season
                    request_url = f"{self.overseerr_url}/api/v1/request"
                    request_data = {
                        'mediaId': media_id,
                        'mediaType': media_type,
                        'is4k': False,
                        'seasons': [1]  # Request first season
                    }
                else:
                    # For movies, use the original request format
                    request_url = f"{self.overseerr_url}/api/v1/request"
                    request_data = {
                        'mediaId': media_id,
                        'mediaType': media_type,
                        'is4k': False
                    }
                
                request_response = self.session.post(
                    request_url,
                    json=request_data,
                    headers=search_headers
                )
                
                if request_response.status_code == 201:
                    logger.info(f"Successfully requested {title}")
                    return True
                elif request_response.status_code == 409:
                    logger.info(f"Request for {title} already exists")
                    return True  # Consider this a success
                else:
                    error_msg = request_response.json().get('message', 'Unknown error')
                    if 'Failed to fetch movie details' in error_msg:
                        logger.warning(f"Movie {title} not found in TMDB")
                    elif 'Could not find any entity of type "Media"' in error_msg:
                        logger.warning(f"Media {title} not found in Overseerr database")
                    elif 'No seasons available to request' in error_msg:
                        logger.info(f"Season 1 of {title} is already available or requested")
                        return True  # Consider this a success
                    else:
                        logger.warning(f"Failed to request {title}: {request_response.status_code} - {error_msg}")
                    return False
            else:
                logger.error(f"Search failed for {title}: {search_response.status_code} - {search_response.text}")
                return False
        except Exception as e:
            logger.error(f"Error requesting {title} in Overseerr: {str(e)}")
            return False

    def run(self, run_frequency_hours=None):
        while True:
            logger.info("Starting Netflix Top 10 to Overseerr bridge")
            
            # Get top 10 titles for both movies and TV shows
            movies, tv_shows = self.get_netflix_top10()
            if not movies and not tv_shows:
                logger.error("Failed to fetch Netflix top 10")
            else:
                # Request each movie
                logger.info("Processing movies...")
                for title in movies:
                    logger.info(f"Processing movie: {title}")
                    self.request_in_overseerr(title, 'movie')
                    time.sleep(1)  # Be nice to the API

                # Request each TV show
                logger.info("Processing TV shows...")
                for title in tv_shows:
                    logger.info(f"Processing TV show: {title}")
                    self.request_in_overseerr(title, 'tv')
                    time.sleep(1)  # Be nice to the API

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Netflix Top 10 to Overseerr Bridge')
    parser.add_argument('--frequency', type=float, help='Run frequency in hours (e.g., 24 for daily, 168 for weekly)')
    args = parser.parse_args()
    
    bridge = NetflixOverseerrBridge()
    bridge.run(args.frequency) 