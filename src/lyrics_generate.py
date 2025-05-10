import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import json
from groq import Groq
import re
from lyrics_dwn_from_genius import get_song_lyrics

class Config:
    GROQ_API_KEY = "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"
    MODEL_NAME = "llama3-70b-8192"
    MAX_TOKENS = 2048
    TEMPERATURE = 0.7
    TOP_P = 0.9
    DEFAULT_SEED = 42

def setup_groq_client() -> Groq:
    """Set up connection to Groq API."""
    if not Config.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    
    print("Setting up Groq API connection...")
    client = Groq(api_key=Config.GROQ_API_KEY)
    print("Groq API connection successful!")
    return client

def read_lyrics_and_title():
    song_title = input("Enter the song title: ")
    artist_name = input("Enter the artist name: ")
    song_info = get_song_lyrics(song_title, artist_name)
    if song_info:
        lyrics = song_info['raw_lyrics']
        title = song_info['title']
        return lyrics, title
    else:
        return None, None

def create_prompt(original_lyrics: str, theme: str = "Same as Original", generation_mode: str = "Replace Original Lyrics") -> str:
    """Create a prompt for the LLaMA model."""
    theme_instruction = ""
    if theme != "Same as Original":
        theme_instruction = f"\nAdditionally, modify the emotional tone to be {theme.lower()} while maintaining the core message."
    
    generation_instruction = ""
    if generation_mode == "Extend Original Lyrics":
        generation_instruction = """
Your task is to extend the original lyrics by adding new verses and sections while maintaining the same style and theme.
ONLY provide the new sections that you create - do not include the original lyrics in your response.
Make sure the new sections maintain the same emotional energy and style as the original."""
    else:
        generation_instruction = """
Your task is to create new lyrics that maintain the same emotional energy, style, and theme, but use different words and expressions.
The new lyrics should be in the same language as the original."""
    
    return f"""You are a creative songwriter. I will provide you with original lyrics. 
{generation_instruction}{theme_instruction}

First, analyze the lyrics and determine their genre based on the style, themes, and language used.
Then, create new lyrics that match that genre while:
1. Maintaining the same emotional tone and energy
2. Keeping the same general theme and message
3. Using different words and expressions
4. Maintaining similar length and structure
5. Keeping the same language style

Format your response exactly like this:
GENRE: [genre name]

[Verse 1]
[your lyrics here]

[Chorus]
[your lyrics here]

[Verse 2]
[your lyrics here]

[etc...]

Original Lyrics:
{original_lyrics}

Please first identify the genre, then generate new lyrics in that style."""

def extract_genre_and_lyrics(text: str) -> Tuple[str, str]:
    """Extract genre and formatted lyrics from the model's response."""
    # Extract genre
    genre_match = re.search(r'GENRE:\s*(.*?)(?:\n|$)', text)
    genre = genre_match.group(1).strip() if genre_match else "Unknown"
    
    # Extract lyrics (everything after the genre line)
    lyrics = re.sub(r'^.*?GENRE:.*?\n', '', text, flags=re.DOTALL).strip()
    
    # Remove any analysis or explanation text
    lyrics = re.sub(r'^.*?\[Verse 1\]', '[Verse 1]', lyrics, flags=re.DOTALL)
    
    # Remove the analysis text at the end (more comprehensive pattern)
    lyrics = re.sub(r'\n\nIn this rewritten version.*$', '', lyrics, flags=re.DOTALL)
    lyrics = re.sub(r'\n\nI maintained.*$', '', lyrics, flags=re.DOTALL)
    
    # Remove any trailing whitespace and ensure proper ending
    lyrics = lyrics.strip()
    if not lyrics.endswith(']'):
        # Find the last section header
        last_section = re.findall(r'\[.*?\]', lyrics)[-1]
        # Keep everything up to and including the last section
        lyrics = lyrics[:lyrics.rindex(last_section) + len(last_section)]
    
    return genre, lyrics

def generate_new_lyrics(client: Groq, prompt: str, seed: int = Config.DEFAULT_SEED) -> Tuple[str, str]:
    """Generate new lyrics using the LLaMA model."""
    try:
        print("Generating new lyrics...")
        response = client.chat.completions.create(
            model=Config.MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a creative songwriter who can rewrite lyrics while maintaining their essence."},
                {"role": "user", "content": prompt}
            ],
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
            top_p=Config.TOP_P,
            seed=seed
        )
        
        generated_text = response.choices[0].message.content.strip()
        genre, lyrics = extract_genre_and_lyrics(generated_text)
        print("Successfully generated new lyrics!")
        return genre, lyrics
    
    except Exception as e:
        print(f"Error generating lyrics: {e}")
        return "Unknown", ""

def save_generated_lyrics(original_title: str, genre: str, generated_lyrics: str) -> None:
    """Save the generated lyrics to a file."""
    try:
        safe_title = re.sub(r'[^\w\s-]', '', original_title.lower())
        folder_name = "new_lyrics_downlaoded"
        Path(folder_name).mkdir(exist_ok=True)
        
        # Save lyrics
        output_filename = f"{folder_name}/generated_{safe_title}_lyrics.txt"
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(generated_lyrics)
        print(f"Generated lyrics saved to: {output_filename}")
        
        genre = genre
        print(genre)
        # Save genre
        genre_filename = f"{folder_name}/generated_{safe_title}_genre.txt"
        with open(genre_filename, 'w', encoding='utf-8') as f:
            f.write(genre)
        print(f"Genre saved to: {genre_filename}")
    
    except Exception as e:
        print(f"Error saving files: {e}")

def main():
    """Main function to generate new lyrics."""
    print("=== Starting Lyrics Generation ===")
    
    # Read the original lyrics
    original_lyrics, original_title = read_lyrics_and_title()
    if not original_lyrics:
        return
    
    # Set up Groq client
    try:
        client = setup_groq_client()
    except Exception as e:
        print(f"Failed to set up Groq client: {e}")
        return
    
    # Create prompt and generate new lyrics
    prompt = create_prompt(original_lyrics)
    genre, generated_lyrics = generate_new_lyrics(client, prompt)
    
    if generated_lyrics:
        save_generated_lyrics(original_title, genre, generated_lyrics)
    
    print("=== Lyrics Generation Complete ===")

if __name__ == "__main__":
    main()
