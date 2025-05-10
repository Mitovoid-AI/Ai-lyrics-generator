import lyricsgenius
import time
import re
import logging
import json
from pathlib import Path
from typing import Dict, Optional, List, Any
from functools import lru_cache
import os
import streamlit as st

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    GENIUS_TOKEN = st.secrets["GENIUS_ACCESS_TOKEN"]
    # # .streamlit/secrets.toml
    # GENIUS_ACCESS_TOKEN = "t2sg5lrj9UtM8iVhYuLVjdBmOIa5r6ObE3ps8OzwL1xc49nwGmRk1bqY9oxh2NPQ"

    # GENIUS_TOKEN = "t2sg5lrj9UtM8iVhYuLVjdBmOIa5r6ObE3ps8OzwL1xc49nwGmRk1bqY9oxh2NPQ"
    CACHE_DIR = Path("cache")
    TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_DELAY = 5

# Ensure cache directory exists
Config.CACHE_DIR.mkdir(exist_ok=True)

@lru_cache(maxsize=100)
def setup_genius() -> lyricsgenius.Genius:
    """Set up connection to Genius API with caching."""
    logger.info("Setting up Genius API connection...")
    genius = lyricsgenius.Genius(
        Config.GENIUS_TOKEN,
        timeout=Config.TIMEOUT,
        retries=Config.MAX_RETRIES
    )
    genius.remove_section_headers = False
    logger.info("Genius API connection successful!")
    return genius

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
            # Check if cache is less than 24 hours old
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
    # Compile regex patterns once
    contributors_pattern = re.compile(r'Contributors.*?Read More', re.DOTALL)
    
    # Remove metadata and translations
    lyrics = contributors_pattern.sub('', lyrics)
    
    # Remove the song title and artist from the beginning
    lines = lyrics.split('\n')
    if lines and lyrics.startswith(lines[0]):
        lyrics = '\n'.join(lines[1:])
    
    # Clean up whitespace and special characters
    lyrics = lyrics.strip()
    lyrics = lyrics.replace('\\n', '\n').replace('\\', '')
    
    # Remove multiple consecutive empty lines
    lyrics = re.sub(r'\n{3,}', '\n\n', lyrics)
    
    return lyrics

# def clean_lyrics(lyrics: str) -> str:
#     """Clean up the lyrics by removing unwanted elements."""
#     logger.info("Starting lyrics cleaning...")
#     logger.debug(f"Original lyrics length: {len(lyrics)} characters")
    
#     # Compile regex patterns once
#     section_pattern = re.compile(r'\[.*?\]\s*')
#     bracket_pattern = re.compile(r'\(.*?\)\s*')
    
#     # Clean lyrics
#     lyrics = clean_metadata(lyrics)
#     lyrics = section_pattern.sub('', lyrics)
#     lyrics = bracket_pattern.sub('', lyrics)
#     lyrics = lyrics.strip()
    
#     logger.debug(f"Cleaned lyrics length: {len(lyrics)} characters")
#     logger.info("Lyrics cleaning complete!")
#     return lyrics

def get_song_lyrics(song_title: str, artist_name: str) -> Optional[Dict[str, Any]]:
    """Get lyrics for a specific song with caching and retry mechanism."""
    logger.info(f"Getting lyrics for: {song_title} by {artist_name}")
    
    # Check cache first
    cache_path = get_cache_path(song_title, artist_name)
    cached_data = load_from_cache(cache_path)
    if cached_data:
        logger.info("Retrieved lyrics from cache")
        return cached_data
    
    # Set up Genius API
    genius = setup_genius()
    
    for attempt in range(Config.MAX_RETRIES):
        try:
            logger.info(f"Attempt {attempt + 1} of {Config.MAX_RETRIES}")
            song = genius.search_song(song_title, artist_name)
            
            if not song:
                logger.warning(f"Could not find lyrics for {song_title} by {artist_name}")
                return None
            
            logger.info(f"Found song: {song.title} by {song.artist}")
            
            # Process lyrics
            raw_lyrics = clean_metadata(song.lyrics)
            # cleaned_lyrics = clean_lyrics(raw_lyrics)
            
            # Get genre information
            genres = []
            try:
                song_data = genius.song(song.id)
                if 'song' in song_data and 'tags' in song_data['song']:
                    genres = [
                        tag['name'] if isinstance(tag, dict) else tag
                        for tag in song_data['song']['tags']
                        if isinstance(tag, (str, dict))
                    ]
            except Exception as e:
                logger.warning(f"Error getting genres: {e}")
            
            result = {
                'title': song.title,
                'artist': song.artist,
                'raw_lyrics': raw_lyrics,
                # 'cleaned_lyrics': cleaned_lyrics,
                'url': song.url,
                'genres': genres
            }
            
            # Save to cache
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
        # Save genre information
        genre_text = " ".join(song_info['genres']) if song_info['genres'] else "romantic ballad pop vocal emotional"
        with open('genre.txt', 'w', encoding='utf-8') as f:
            f.write(genre_text)
        logger.info(f"Genre file created with: {genre_text}")
        
        # Save raw lyrics
        safe_title = get_safe_filename(song_info['title'])
        folder_name = "lyrics_dwnloaded_genius"
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
