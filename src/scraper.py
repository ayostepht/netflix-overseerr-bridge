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
import yaml

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

        # Kometa configuration
        self.kometa_enabled = os.getenv('KOMETA_ENABLED', 'false').lower() in ('true', '1', 'yes')
        self.kometa_output_dir = os.getenv('KOMETA_OUTPUT_DIR', '/config/kometa')
        self.kometa_movies_dir = os.getenv('KOMETA_MOVIES_DIR', self.kometa_output_dir)
        self.kometa_tv_dir = os.getenv('KOMETA_TV_DIR', self.kometa_output_dir)

        # Log environment variables for debugging
        logger.info(f"Environment variables:")
        logger.info(f"OVERSEERR_URL: {self.overseerr_url}")
        logger.info(f"NETFLIX_COUNTRY: {self.country}")
        logger.info(f"DRY_RUN: {os.getenv('DRY_RUN', 'not set')}")
        logger.info(f"KOMETA_ENABLED: {self.kometa_enabled}")
        if self.kometa_enabled:
            logger.info(f"KOMETA_OUTPUT_DIR: {self.kometa_output_dir}")
            logger.info(f"KOMETA_MOVIES_DIR: {self.kometa_movies_dir}")
            logger.info(f"KOMETA_TV_DIR: {self.kometa_tv_dir}")
        
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
                    tv_shows.append({
                        'title': row['show_title'],
                        'season_title': row['season_title']
                    })
            
            logger.info(f"Found {len(movies)} movies and {len(tv_shows)} TV shows for the most recent week")
            return movies[:10], tv_shows[:10]  # Return top 10 of each
            
        except Exception as e:
            logger.error(f"Error fetching Netflix top 10: {str(e)}")
            return [], []

    def _extract_season_number(self, season_title):
        """Extract season number from season_title field.
        
        Args:
            season_title (str): The season_title field from Netflix data
            
        Returns:
            int or None: Season number if found, None if not found or Limited Series
        """
        if not season_title or season_title == 'N/A':
            return None
            
        # Handle Limited Series - these should be treated as season 1
        if 'Limited Series' in season_title:
            return 1
            
        # Extract season number from patterns like "Show Name: Season 3"
        import re
        season_match = re.search(r'Season (\d+)', season_title)
        if season_match:
            return int(season_match.group(1))
            
        return None

    def get_existing_tv_requests(self, media_id):
        """Get existing TV show requests and their seasons from Overseerr.

        Args:
            media_id (int): The TMDB media ID

        Returns:
            list: List of season numbers that are already requested or available
        """
        try:
            headers = {
                'X-Api-Key': self.overseerr_api_key,
                'Accept': 'application/json'
            }

            # Try to get requests for this specific media ID
            requests_url = f"{self.overseerr_url}/api/v1/request"
            requests_response = self.session.get(requests_url, headers=headers)

            if requests_response.status_code == 200:
                requests_data = requests_response.json()
                logger.info(f"Got requests data, checking for media ID {media_id}")
                existing_seasons = self._extract_seasons_from_requests(requests_data, media_id)
                if existing_seasons:
                    logger.info(f"Found existing seasons from requests API: {existing_seasons}")
                    return existing_seasons

            # Fallback: try the media endpoint which has request status info
            media_url = f"{self.overseerr_url}/api/v1/media/{media_id}"
            response = self.session.get(media_url, headers=headers)

            if response.status_code == 200:
                media_details = response.json()
                logger.info(f"Got media details via /api/v1/media/{media_id}")
                return self._extract_seasons_from_media(media_details)
            elif response.status_code == 404:
                logger.info(f"Media ID {media_id} not found in Overseerr database - this is a new media item")
                return []
            else:
                logger.info(f"Could not get media details for media ID {media_id}: {response.status_code}")
                # Fall back to TV endpoint
                tv_url = f"{self.overseerr_url}/api/v1/tv/{media_id}"
                tv_response = self.session.get(tv_url, headers=headers)
                if tv_response.status_code == 200:
                    tv_details = tv_response.json()
                    logger.info(f"Got TV details via /api/v1/tv/{media_id}")
                    logger.info(f"TV show API response keys: {list(tv_details.keys())}")
                    existing_seasons = []

                    # Check if there are any seasons in the response
                    if 'seasons' in tv_details:
                        logger.info(f"Found {len(tv_details['seasons'])} seasons in TV details")
                        for season in tv_details['seasons']:
                            season_number = season.get('seasonNumber', 0)
                            status = season.get('status')
                            logger.info(f"Season {season_number}: status={status}, available={season.get('available', 'unknown')}")
                            # Skip season 0 (specials) and check if season is requested or available
                            if season_number > 0:
                                # Check for any status that indicates the season exists/requested
                                # Status 1 = UNKNOWN, 2 = PENDING, 3 = APPROVED, 4 = DECLINED, 5 = AVAILABLE
                                # We want to include PENDING, APPROVED, and AVAILABLE
                                # But let's also check if 'available' field is true
                                is_available = season.get('available', False)
                                if status in [2, 3, 5] or is_available:
                                    existing_seasons.append(season_number)

                    logger.info(f"Found existing seasons for media ID {media_id}: {existing_seasons}")
                    return sorted(existing_seasons)
                elif tv_response.status_code == 404:
                    logger.info(f"TV show ID {media_id} not found in Overseerr database - this is a new media item")
                    return []
                return []

        except Exception as e:
            logger.info(f"Error checking existing requests for media ID {media_id}: {str(e)}")
            return []

    def _extract_seasons_from_media(self, media_details):
        """Extract existing seasons from media API response."""
        existing_seasons = []
        logger.info(f"Media API response keys: {list(media_details.keys())}")
        
        # Check different possible locations for season information
        if 'seasons' in media_details:
            logger.info(f"Found {len(media_details['seasons'])} seasons in media details")
            for season in media_details['seasons']:
                season_number = season.get('seasonNumber', 0)
                status = season.get('status')
                is_available = season.get('available', False)
                logger.info(f"Media Season {season_number}: status={status}, available={is_available}")
                if season_number > 0 and (status in [2, 3, 5] or is_available):
                    existing_seasons.append(season_number)
        
        # Check if there's a requests array - this is where actual request status lives
        if 'requests' in media_details:
            logger.info(f"Found {len(media_details['requests'])} requests in media details")
            for request in media_details['requests']:
                request_status = request.get('status')
                logger.info(f"Request status: {request_status}")
                if 'seasons' in request:
                    logger.info(f"Request has {len(request['seasons'])} seasons")
                    for season in request['seasons']:
                        season_number = season.get('seasonNumber', 0)
                        status = season.get('status')
                        is_available = season.get('available', False)
                        logger.info(f"Request Season {season_number}: status={status}, available={is_available}")
                        if season_number > 0 and (status in [2, 3, 5] or is_available):
                            existing_seasons.append(season_number)
                else:
                    # If no seasons specified in request, might be a "all seasons" request
                    logger.info(f"Request has no seasons array - might be requesting all seasons")
        
        # Also check for mediaInfo which might have download status
        if 'mediaInfo' in media_details:
            logger.info(f"Found mediaInfo in response")
            media_info = media_details['mediaInfo']
            if media_info and 'seasons' in media_info:
                logger.info(f"Found {len(media_info['seasons'])} seasons in mediaInfo")
                for season in media_info['seasons']:
                    season_number = season.get('seasonNumber', 0)
                    status = season.get('status')
                    is_available = season.get('available', False)
                    logger.info(f"MediaInfo Season {season_number}: status={status}, available={is_available}")
                    if season_number > 0 and (status in [2, 3, 5] or is_available):
                        existing_seasons.append(season_number)
        
        logger.info(f"Found existing seasons from media API: {sorted(list(set(existing_seasons)))}")
        return sorted(list(set(existing_seasons)))  # Remove duplicates

    def _extract_seasons_from_requests(self, requests_data, media_id):
        """Extract existing seasons from requests API response."""
        existing_seasons = []
        
        if 'results' in requests_data:
            logger.info(f"Found {len(requests_data['results'])} total requests")
            for request in requests_data['results']:
                # Check if this request is for our media ID
                if request.get('media', {}).get('tmdbId') == media_id:
                    request_status = request.get('status')
                    request_type = request.get('type')
                    logger.info(f"Found request for media {media_id}: status={request_status}, type={request_type}")
                    
                    # Only include approved/available requests
                    if request_status in [2, 3, 5]:  # PENDING, APPROVED, AVAILABLE
                        if 'seasons' in request and request['seasons']:
                            logger.info(f"Request has {len(request['seasons'])} specific seasons")
                            for season in request['seasons']:
                                season_number = season.get('seasonNumber', 0)
                                if season_number > 0:
                                    existing_seasons.append(season_number)
                                    logger.info(f"Found requested season: {season_number}")
                        else:
                            # If no specific seasons, might be requesting all seasons
                            logger.info(f"Request has no specific seasons - might be requesting all available")
        
        return sorted(list(set(existing_seasons)))

    def request_tv_show_seasons(self, title, max_season):
        """Request TV show seasons from 1 up to max_season.
        
        Args:
            title (str): The show title
            max_season (int): Maximum season number to request
            
        Returns:
            dict: Status and message about the request
        """
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
            
            if search_response.status_code != 200:
                logger.error(f"Search failed for {title}: {search_response.status_code} - {search_response.text}")
                return {'status': 'error', 'message': f'Search failed: {search_response.status_code}'}
            
            search_results = search_response.json()
            if not search_results.get('results'):
                logger.warning(f"No results found for {title} in TMDB")
                return {'status': 'not_found', 'message': 'No results found in TMDB'}
            
            # Get all results and find the best match
            results = search_results['results']
            tv_results = [r for r in results if r.get('mediaType') == 'tv']
            
            if not tv_results:
                logger.warning(f"No TV show results found for {title}")
                return {'status': 'not_found', 'message': 'No TV show results found'}
            
            # Find exact title match or use first result
            exact_matches = [r for r in tv_results if r.get('name', '').lower() == title.lower()]
            if exact_matches:
                # Use first exact match (likely ordered by relevance/popularity)
                media_item = exact_matches[0]
                logger.info(f"Found exact match for {title} (ID: {media_item.get('id')}) from {media_item.get('firstAirDate', '')}")
            else:
                tv_results.sort(key=lambda x: x.get('firstAirDate', ''), reverse=True)
                media_item = tv_results[0]
                logger.info(f"Using best match for {title} (ID: {media_item.get('id')}) from {media_item.get('firstAirDate', '')}")
            
            media_id = media_item['id']
            
            # Check what seasons are already requested/available
            existing_seasons = self.get_existing_tv_requests(media_id)
            
            # Determine which seasons we need to request
            all_seasons_needed = list(range(1, max_season + 1))
            seasons_to_request = [s for s in all_seasons_needed if s not in existing_seasons]
            
            if not seasons_to_request:
                logger.info(f"All seasons 1-{max_season} of {title} are already requested or available")
                return {'status': 'existing_request', 'message': f'All seasons 1-{max_season} already available or requested', 'tmdb_id': media_id}
            
            if existing_seasons:
                logger.info(f"{title}: Existing seasons {existing_seasons}, will request missing seasons {seasons_to_request}")
            else:
                logger.info(f"{title}: No existing seasons found, will request seasons {seasons_to_request}")
            
            request_url = f"{self.overseerr_url}/api/v1/request"
            request_data = {
                'mediaId': media_id,
                'mediaType': 'tv',
                'seasons': seasons_to_request,
                'is4k': False
            }
            
            if self.dry_run:
                if existing_seasons:
                    logger.info(f"[DRY RUN] {title}: Found existing seasons {existing_seasons}, would request missing seasons {seasons_to_request}")
                else:
                    logger.info(f"[DRY RUN] {title}: No existing seasons found, would request seasons {seasons_to_request}")
                return {'status': 'dry_run', 'message': f'Dry run - would request seasons {seasons_to_request}', 'tmdb_id': media_id}
            
            request_response = self.session.post(
                request_url,
                json=request_data,
                headers=search_headers
            )
            
            if request_response.status_code == 201:
                logger.info(f"Successfully requested {title} seasons {seasons_to_request}")
                if existing_seasons:
                    return {'status': 'new_request', 'message': f'Successfully requested missing seasons {seasons_to_request} (existing: {existing_seasons})', 'tmdb_id': media_id}
                else:
                    return {'status': 'new_request', 'message': f'Successfully requested seasons {seasons_to_request}', 'tmdb_id': media_id}
            elif request_response.status_code == 409:
                logger.info(f"Request for {title} seasons {seasons_to_request} already exists")
                return {'status': 'existing_request', 'message': f'Request already exists (existing: {existing_seasons})', 'tmdb_id': media_id}
            else:
                error_msg = request_response.json().get('message', 'Unknown error')

                # Check for Overseerr API bug first
                if "Cannot read properties of undefined (reading 'filter')" in error_msg:
                    logger.warning(f"Overseerr API bug detected for {title} (works in web UI but fails via API)")
                    return {'status': 'error', 'message': f'Overseerr API bug - try requesting via web UI'}
                
                # If requesting multiple seasons fails, try one by one
                if 'No seasons available to request' in error_msg:
                    logger.info(f"Multiple seasons request failed for {title}, trying individual missing seasons...")
                    requested_seasons = []
                    
                    for season_num in seasons_to_request:
                        request_data['seasons'] = [season_num]
                        season_response = self.session.post(
                            request_url,
                            json=request_data,
                            headers=search_headers
                        )
                        
                        if season_response.status_code == 201:
                            requested_seasons.append(season_num)
                            logger.info(f"Successfully requested {title} season {season_num}")
                        elif season_response.status_code == 409:
                            logger.info(f"{title} season {season_num} already requested")
                        else:
                            season_error = season_response.json().get('message', 'Unknown error')
                            if 'No seasons available to request' in season_error:
                                logger.info(f"{title} season {season_num} already available or not found")
                            else:
                                logger.warning(f"Failed to request {title} season {season_num}: {season_error}")
                    
                    if requested_seasons:
                        if existing_seasons:
                            return {'status': 'new_request', 'message': f'Successfully requested missing seasons {requested_seasons} (existing: {existing_seasons})', 'tmdb_id': media_id}
                        else:
                            return {'status': 'new_request', 'message': f'Successfully requested seasons {requested_seasons}', 'tmdb_id': media_id}
                    else:
                        # All seasons were already available - this is the correct behavior
                        return {'status': 'existing_request', 'message': f'All seasons already available or requested', 'tmdb_id': media_id}
                elif 'Could not find any entity of type "Media"' in error_msg:
                    # This happens when media ID exists in TMDB search but not in Overseerr's database yet
                    # Try a simple request without season checking to let Overseerr import the media
                    logger.info(f"Media {media_id} not found in Overseerr database for {title}, trying simple request to import media...")
                    simple_request_data = {
                        'mediaId': media_id,
                        'mediaType': 'tv',
                        'is4k': False
                    }

                    simple_response = self.session.post(
                        request_url,
                        json=simple_request_data,
                        headers=search_headers
                    )

                    if simple_response.status_code == 201:
                        logger.info(f"Successfully requested {title} via simple request (media imported)")
                        return {'status': 'new_request', 'message': f'Successfully requested (media imported)', 'tmdb_id': media_id}
                    elif simple_response.status_code == 409:
                        logger.info(f"Request for {title} already exists")
                        return {'status': 'existing_request', 'message': f'Request already exists', 'tmdb_id': media_id}
                    else:
                        simple_error = simple_response.json().get('message', 'Unknown error')
                        logger.warning(f"Simple request also failed for {title}: {simple_response.status_code} - {simple_error}")
                        return {'status': 'error', 'message': f'Request failed: {simple_error}'}
                elif "Cannot read properties of undefined (reading 'filter')" in error_msg:
                    # Known Overseerr bug in version 1.34.0 affecting TV show requests via API
                    # The web UI works but API calls fail with this JavaScript error
                    logger.warning(f"Overseerr API bug detected for {title} (works in web UI but fails via API)")
                    return {'status': 'error', 'message': f'Overseerr API bug - try requesting via web UI'}
                else:
                    logger.warning(f"Failed to request {title}: {request_response.status_code} - {error_msg}")
                    return {'status': 'error', 'message': f'Request failed: {error_msg}'}
                    
        except Exception as e:
            logger.error(f"Error requesting {title} in Overseerr: {str(e)}")
            return {'status': 'error', 'message': f'Exception: {str(e)}'}

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
                        # Use first exact match (likely ordered by relevance/popularity)
                        results = exact_matches
                        logger.info(f"Found {len(results)} exact title matches for {title}, using first result (ID: {results[0].get('id')}) from {results[0].get('releaseDate', '') or results[0].get('firstAirDate', '')}")
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
                    return {'status': 'dry_run', 'message': 'Dry run - would request', 'tmdb_id': media_id}
                
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
                    return {'status': 'new_request', 'message': 'Successfully requested', 'tmdb_id': media_id}
                elif request_response.status_code == 409:
                    logger.info(f"Request for {title} already exists")
                    return {'status': 'existing_request', 'message': 'Request already exists', 'tmdb_id': media_id}
                else:
                    error_msg = request_response.json().get('message', 'Unknown error')
                    if 'Failed to fetch movie details' in error_msg:
                        logger.warning(f"Movie {title} not found in TMDB")
                        return {'status': 'not_found', 'message': 'Movie not found in TMDB'}
                    elif 'Failed to fetch TV show details' in error_msg:
                        logger.warning(f"TV show {title} not found in TMDB")
                        return {'status': 'not_found', 'message': 'TV show not found in TMDB'}
                    elif 'Could not find any entity of type "Media"' in error_msg:
                        # Try a simple request to import the media into Overseerr's database
                        logger.info(f"Media {media_id} not found in Overseerr database for {title}, trying simple request to import media...")
                        simple_request_data = {
                            'mediaId': media_id,
                            'mediaType': media_type,
                            'is4k': False
                        }

                        simple_response = self.session.post(
                            request_url,
                            json=simple_request_data,
                            headers=search_headers
                        )

                        if simple_response.status_code == 201:
                            logger.info(f"Successfully requested {title} via simple request (media imported)")
                            return {'status': 'new_request', 'message': 'Successfully requested (media imported)', 'tmdb_id': media_id}
                        elif simple_response.status_code == 409:
                            logger.info(f"Request for {title} already exists")
                            return {'status': 'existing_request', 'message': 'Request already exists', 'tmdb_id': media_id}
                        else:
                            simple_error = simple_response.json().get('message', 'Unknown error')
                            if "Cannot read properties of undefined (reading 'filter')" in simple_error:
                                logger.warning(f"Overseerr API bug detected for {title} (works in web UI but fails via API)")
                                return {'status': 'error', 'message': f'Overseerr API bug - try requesting via web UI'}
                            else:
                                logger.warning(f"Simple request also failed for {title}: {simple_response.status_code} - {simple_error}")
                                return {'status': 'error', 'message': f'Media not found in Overseerr database'}
                    elif 'Cannot read properties of undefined' in error_msg:
                        logger.warning(f"TV show {title} not found in Overseerr database")
                        return {'status': 'not_found', 'message': 'TV show not found in Overseerr database'}
                    elif 'No seasons available to request' in error_msg:
                        logger.info(f"Season 1 of {title} is already available or requested")
                        return {'status': 'existing_request', 'message': 'Season already available or requested', 'tmdb_id': media_id}
                    else:
                        logger.warning(f"Failed to request {title}: {request_response.status_code} - {error_msg}")
                        return {'status': 'error', 'message': f'Request failed: {error_msg}'}
            else:
                logger.error(f"Search failed for {title}: {search_response.status_code} - {search_response.text}")
                return {'status': 'error', 'message': f'Search failed: {search_response.status_code}'}
        except Exception as e:
            logger.error(f"Error requesting {title} in Overseerr: {str(e)}")
            return {'status': 'error', 'message': f'Exception: {str(e)}'}

    def _sanitize_filename(self, country):
        """
        Sanitize country name for use in filenames.

        Args:
            country (str): Country name

        Returns:
            str: Sanitized filename safe country name
        """
        # Convert to lowercase and replace spaces and special characters with underscores
        import re
        sanitized = re.sub(r'[^\w\s-]', '', country.lower())
        sanitized = re.sub(r'[-\s]+', '_', sanitized)
        return sanitized.strip('_')

    def generate_kometa_files(self, summary):
        """
        Generate Kometa YAML files for Netflix Top 10 collections.

        Args:
            summary (dict): Summary data containing TMDb IDs and titles
        """
        if not self.kometa_enabled:
            logger.info("Kometa generation disabled, skipping YAML file creation")
            return

        try:
            # Create output directories if they don't exist
            os.makedirs(self.kometa_movies_dir, exist_ok=True)
            os.makedirs(self.kometa_tv_dir, exist_ok=True)

            # Test write permissions
            try:
                test_movie_file = os.path.join(self.kometa_movies_dir, '.write_test')
                with open(test_movie_file, 'w') as f:
                    f.write('test')
                os.remove(test_movie_file)
                logger.info(f"Movie directory is writable: {self.kometa_movies_dir}")
            except Exception as e:
                logger.error(f"Movie directory is not writable: {self.kometa_movies_dir} - {e}")
                return

            try:
                test_tv_file = os.path.join(self.kometa_tv_dir, '.write_test')
                with open(test_tv_file, 'w') as f:
                    f.write('test')
                os.remove(test_tv_file)
                logger.info(f"TV directory is writable: {self.kometa_tv_dir}")
            except Exception as e:
                logger.error(f"TV directory is not writable: {self.kometa_tv_dir} - {e}")
                return

            # Sanitize country name for filename
            country_safe = self._sanitize_filename(self.country)

            # Process movies
            movie_tmdb_ids = []
            if summary.get('top_movies'):
                logger.info("Collecting TMDb IDs for movies...")
                for movie in summary['top_movies']:
                    try:
                        # Search for the movie to get its TMDb ID
                        result = self._get_tmdb_id_for_title(movie, 'movie')
                        if result and result.get('tmdb_id'):
                            movie_tmdb_ids.append(result['tmdb_id'])
                            logger.info(f"Found TMDb ID {result['tmdb_id']} for movie: {movie}")
                        else:
                            logger.warning(f"Could not find TMDb ID for movie: {movie}")
                    except Exception as e:
                        logger.error(f"Error getting TMDb ID for movie {movie}: {str(e)}")

            # Process TV shows
            tv_tmdb_ids = []
            if summary.get('top_shows'):
                logger.info("Collecting TMDb IDs for TV shows...")
                for show in summary['top_shows']:
                    try:
                        title = show['title'] if isinstance(show, dict) else show
                        # Search for the TV show to get its TMDb ID
                        result = self._get_tmdb_id_for_title(title, 'tv')
                        if result and result.get('tmdb_id'):
                            tv_tmdb_ids.append(result['tmdb_id'])
                            logger.info(f"Found TMDb ID {result['tmdb_id']} for TV show: {title}")
                        else:
                            logger.warning(f"Could not find TMDb ID for TV show: {title}")
                    except Exception as e:
                        logger.error(f"Error getting TMDb ID for TV show {title}: {str(e)}")

            # Generate movie YAML file
            if movie_tmdb_ids:
                movie_filename = f"netflix_movies_{country_safe}.yml"
                movie_filepath = os.path.join(self.kometa_movies_dir, movie_filename)
                movie_yaml = self._create_kometa_yaml(
                    collection_name=f"Netflix Top 10 Movies - {self.country}",
                    tmdb_ids=movie_tmdb_ids,
                    builder_type="tmdb_movie",
                    summary=f"Netflix Top 10 movies for {self.country} as of {datetime.now().strftime('%Y-%m-%d')}"
                )

                with open(movie_filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(movie_yaml, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

                # Verify file was actually created and has content
                if os.path.exists(movie_filepath):
                    file_size = os.path.getsize(movie_filepath)
                    logger.info(f"✓ Generated Kometa movie file: {movie_filepath} with {len(movie_tmdb_ids)} movies ({file_size} bytes)")
                else:
                    logger.error(f"✗ Failed to create movie file: {movie_filepath}")
                    return
            else:
                logger.warning("No movie TMDb IDs found, skipping movie YAML generation")

            # Generate TV show YAML file
            if tv_tmdb_ids:
                tv_filename = f"netflix_tv_{country_safe}.yml"
                tv_filepath = os.path.join(self.kometa_tv_dir, tv_filename)
                tv_yaml = self._create_kometa_yaml(
                    collection_name=f"Netflix Top 10 TV Shows - {self.country}",
                    tmdb_ids=tv_tmdb_ids,
                    builder_type="tmdb_show",
                    summary=f"Netflix Top 10 TV shows for {self.country} as of {datetime.now().strftime('%Y-%m-%d')}"
                )

                with open(tv_filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(tv_yaml, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

                # Verify file was actually created and has content
                if os.path.exists(tv_filepath):
                    file_size = os.path.getsize(tv_filepath)
                    logger.info(f"✓ Generated Kometa TV file: {tv_filepath} with {len(tv_tmdb_ids)} shows ({file_size} bytes)")
                else:
                    logger.error(f"✗ Failed to create TV file: {tv_filepath}")
                    return
            else:
                logger.warning("No TV show TMDb IDs found, skipping TV YAML generation")

            # Log summary
            total_generated = (1 if movie_tmdb_ids else 0) + (1 if tv_tmdb_ids else 0)
            if total_generated > 0:
                movies_msg = f"Movies: {self.kometa_movies_dir}" if movie_tmdb_ids else ""
                tv_msg = f"TV: {self.kometa_tv_dir}" if tv_tmdb_ids else ""
                dirs_msg = ", ".join(filter(None, [movies_msg, tv_msg]))
                logger.info(f"✅ Successfully generated {total_generated} Kometa YAML file(s) - {dirs_msg}")
            else:
                logger.warning("No Kometa YAML files were generated due to missing TMDb IDs")

        except Exception as e:
            logger.error(f"Error generating Kometa files: {str(e)}")

    def _get_tmdb_id_for_title(self, title, media_type):
        """
        Get TMDb ID for a title by searching Overseerr.

        Args:
            title (str): Title to search for
            media_type (str): 'movie' or 'tv'

        Returns:
            dict: Result with tmdb_id if found
        """
        try:
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
                    return None

                # Filter by media type and find best match
                results = [r for r in search_results['results'] if r.get('mediaType') == media_type]
                if not results:
                    return None

                # Find exact title match or use first result
                exact_matches = [r for r in results if r.get('title', r.get('name', '')).lower() == title.lower()]
                if exact_matches:
                    # Use first exact match (likely ordered by relevance/popularity)
                    media_item = exact_matches[0]
                else:
                    results.sort(key=lambda x: x.get('releaseDate', '') or x.get('firstAirDate', ''), reverse=True)
                    media_item = results[0]

                return {'tmdb_id': media_item['id']}

            return None

        except Exception as e:
            logger.error(f"Error searching for {title}: {str(e)}")
            return None

    def _create_kometa_yaml(self, collection_name, tmdb_ids, builder_type, summary):
        """
        Create Kometa YAML structure for a collection.

        Args:
            collection_name (str): Name of the collection
            tmdb_ids (list): List of TMDb IDs
            builder_type (str): Type of builder ('tmdb_movie' or 'tmdb_show')
            summary (str): Collection summary description

        Returns:
            dict: YAML structure for Kometa
        """
        return {
            'collections': {
                collection_name: {
                    builder_type: tmdb_ids,
                    'sync_mode': 'sync',
                    'collection_order': 'custom',
                    'sort_title': f"!Netflix {collection_name}",
                    'summary': summary,
                    'collection_mode': 'default',
                    'visible_home': True,
                    'visible_shared': True
                }
            }
        }

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
                for tv_show in tv_shows:
                    title = tv_show['title']
                    season_title = tv_show['season_title']
                    max_season = self._extract_season_number(season_title)
                    
                    logger.info(f"Processing TV show: {title} (season_title: {season_title})")
                    
                    try:
                        if max_season:
                            # Use new logic to request all seasons up to max_season
                            logger.info(f"Requesting {title} seasons 1-{max_season}")
                            result = self.request_tv_show_seasons(title, max_season)
                        else:
                            # Fall back to original logic for shows without clear season info
                            logger.info(f"No clear season info for {title}, using original logic")
                            result = self.request_in_overseerr(title, 'tv')
                        
                        if result['status'] == 'new_request':
                            summary['new_downloads'].append(f"{title} (TV) - {result['message']}")
                        elif result['status'] == 'existing_request':
                            summary['existing_downloads'].append(f"{title} (TV) - {result['message']}")
                        else:
                            summary['errors'].append(f"Failed to request TV show: {title} - {result['message']}")
                    except Exception as e:
                        summary['errors'].append(f"Exception processing TV show {title}: {str(e)}")
                    time.sleep(1)  # Be nice to the API

            # Generate Kometa files if enabled
            if self.kometa_enabled:
                logger.info("Generating Kometa YAML files...")
                self.generate_kometa_files(summary)

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
                if isinstance(show, dict):
                    title = show['title']
                    season_title = show['season_title']
                    season_num = self._extract_season_number(season_title)
                    season_info = f" (Season {season_num})" if season_num else ""
                    status = self._get_title_status(title, summary)
                    lines.append(f"  {i:2d}. {title}{season_info} - {status}")
                else:
                    # Handle old format for backward compatibility
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