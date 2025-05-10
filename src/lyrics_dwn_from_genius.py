import time
import re
import logging
import json
from pathlib import Path
from typing import Dict, Optional, List, Any
from functools import lru_cache
import requests
import streamlit as st
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    GENIUS_TOKEN = "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"
    CACHE_DIR = Path("cache")
    TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_DELAY = 5

# Ensure cache directory exists
Config.CACHE_DIR.mkdir(exist_ok=True)

def get_cache_path(song_title: str, artist_name: str) -> Path:
    """Generate cache file path for a song."""
    safe_title = re.sub(r'[^\w\s-]', '', song_title.lower())
    safe_artist = re.sub(r'[^\w\s-]', '', artist_name.lower())
    return Config.CACHE_DIR / f"{safe_artist}_{safe_title}.json"

def load_from_cache(cache_path: Path) -> Optional[Dict[str, Any]]:
    """Load song data from cache if available and not expired."""
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if time.time() - data.get('timestamp', 0) < 86400:
                return data
    except Exception as e:
        logger.warning(f"Error reading cache: {e}")
    return None

def save_to_cache(cache_path: Path, data: Dict[str, Any]) -> None:
    """Save song data to cache."""
    try:
        data['timestamp'] = time.time()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")

def clean_metadata(lyrics: str) -> str:
    """Remove metadata and translations information from lyrics."""
    contributors_pattern = re.compile(r'Contributors.*?Read More', re.DOTALL)
    lyrics = contributors_pattern.sub('', lyrics)
    lines = lyrics.split('\n')
    if lines and lyrics.startswith(lines[0]):
        lyrics = '\n'.join(lines[1:])
    lyrics = lyrics.strip().replace('\\n', '\n').replace('\\', '')
    lyrics = re.sub(r'\n{3,}', '\n\n', lyrics)
    return lyrics

def get_song_lyrics(song_title: str, artist_name: str) -> Optional[Dict[str, Any]]:
    """Get lyrics for a specific song with caching and retry mechanism."""
    logger.info(f"Getting lyrics for: {song_title} by {artist_name}")
    cache_path = get_cache_path(song_title, artist_name)
    cached_data = load_from_cache(cache_path)
    if cached_data:
        logger.info("Retrieved lyrics from cache")
        return cached_data

    headers = {
        "Authorization": f"Bearer {Config.GENIUS_TOKEN}",
        "User-Agent": "Mozilla/5.0"
    }

    for attempt in range(Config.MAX_RETRIES):
        try:
            logger.info(f"Attempt {attempt + 1} of {Config.MAX_RETRIES}")
            query = f"{song_title} {artist_name}"
            search_url = "https://api.genius.com/search"
            response = requests.get(search_url, headers=headers, params={"q": query}, timeout=Config.TIMEOUT)
            
            if response.status_code != 200:
                raise Exception(f"Genius API error: {response.status_code} {response.text}")
            
            hits = response.json()["response"]["hits"]
            if not hits:
                logger.warning("No results found from Genius search")
                return None

            song_data = hits[0]["result"]
            song_title_result = song_data["title"]
            song_artist_result = song_data["primary_artist"]["name"]
            song_url = song_data["url"]
            song_id = song_data["id"]

            # Scrape lyrics from the page
            logger.info(f"Found song: {song_title_result} by {song_artist_result}")
            logger.info(f"Scraping lyrics from: {song_url}")

            page = requests.get(song_url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(page.text, "html.parser")
            lyrics_divs = soup.select("div[data-lyrics-container=true]")
            raw_lyrics = "\n".join([div.get_text(separator="\n") for div in lyrics_divs]).strip()
            raw_lyrics = clean_metadata(raw_lyrics)

            genres = []
            try:
                song_detail_url = f"https://api.genius.com/songs/{song_id}"
                detail_response = requests.get(song_detail_url, headers=headers)
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    tags = detail_data.get("response", {}).get("song", {}).get("tags", [])
                    genres = [
                        tag["name"] if isinstance(tag, dict) else tag
                        for tag in tags
                        if isinstance(tag, (str, dict))
                    ]
            except Exception as e:
                logger.warning(f"Error getting genres: {e}")

            result = {
                'title': song_title_result,
                'artist': song_artist_result,
                'raw_lyrics': raw_lyrics,
                'url': song_url,
                'genres': genres
            }

            save_to_cache(cache_path, result)
            return result

        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            if attempt < Config.MAX_RETRIES - 1:
                logger.info(f"Retrying in {Config.RETRY_DELAY} seconds...")
                time.sleep(Config.RETRY_DELAY)

    logger.error("All retry attempts failed")
    return None

def get_safe_filename(title: str) -> str:
    """Convert song title to a safe filename."""
    return re.sub(r'[^\w\s-]', '', title.lower())

def save_lyrics_files(song_info: Dict[str, Any]) -> None:
    """Save lyrics and genre information to files."""
    try:
        genre_text = " ".join(song_info['genres']) if song_info['genres'] else "romantic ballad pop vocal emotional"
        with open('genre.txt', 'w', encoding='utf-8') as f:
            f.write(genre_text)
        logger.info(f"Genre file created with: {genre_text}")

        safe_title = get_safe_filename(song_info['title'])
        folder_name = "lyrics_dwnloaded_genius"
        os.makedirs(folder_name, exist_ok=True)
        raw_lyric_filename = f"{folder_name}/Raw_{safe_title}_lyric.txt"
        with open(raw_lyric_filename, 'w', encoding='utf-8') as f:
            f.write(song_info['raw_lyrics'])
        logger.info(f"Raw lyrics file created: {raw_lyric_filename}")

    except Exception as e:
        logger.error(f"Error saving files: {e}")

if __name__ == "__main__":
    logger.info("=== Starting Lyrics Search ===")
    song_info = get_song_lyrics("Kiss Me Now", "Pierce The Veil")
    if song_info:
        logger.info("\n=== Results ===")
        logger.info(f"Title: {song_info['title']}")
        logger.info(f"Artist: {song_info['artist']}")
        logger.info(f"URL: {song_info['url']}")
        save_lyrics_files(song_info)
    logger.info("=== Search Complete ===")
