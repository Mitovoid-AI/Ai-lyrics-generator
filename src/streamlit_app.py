import streamlit as st
import os
from pathlib import Path
from lyrics_generate import setup_groq_client, create_prompt, generate_new_lyrics, save_generated_lyrics
from lyrics_dwn_from_genius import get_song_lyrics

st.set_page_config(
    page_title="AI Lyrics Generator",
    page_icon="🎵",
    layout="wide"
)

st.title("🎵 AI Lyrics Generator")
st.markdown("""
This app generates new lyrics in the style of your favorite songs. 
Enter a song title and artist name to get started!
""")

# Sidebar with examples
with st.sidebar:
    st.header("Example Songs")
    examples = {
        "Bohemian Rhapsody - Queen": {"title": "Bohemian Rhapsody", "artist": "Queen"},
        "Yesterday - The Beatles": {"title": "Yesterday", "artist": "The Beatles"},
        "Shape of You - Ed Sheeran": {"title": "Shape of You", "artist": "Ed Sheeran"}
    }
    
    for example_name, example_data in examples.items():
        if st.button(example_name):
            st.session_state.song_title = example_data["title"]
            st.session_state.artist_name = example_data["artist"]

# Initialize session state
if 'song_title' not in st.session_state:
    st.session_state.song_title = ""
if 'artist_name' not in st.session_state:
    st.session_state.artist_name = ""
if 'generated_lyrics' not in st.session_state:
    st.session_state.generated_lyrics = None
if 'genre' not in st.session_state:
    st.session_state.genre = None
if 'original_title' not in st.session_state:
    st.session_state.original_title = None
if 'show_results' not in st.session_state:
    st.session_state.show_results = False
if 'original_lyrics' not in st.session_state:
    st.session_state.original_lyrics = None
if 'seed' not in st.session_state:
    st.session_state.seed = 42  # Default seed value

# Input fields
col1, col2 = st.columns(2)
with col1:
    song_title = st.text_input("Song Title", value=st.session_state.song_title, placeholder="Enter the song title...")
with col2:
    artist_name = st.text_input("Artist Name", value=st.session_state.artist_name, placeholder="Enter the artist name...")

# Add theme selection after input fields
st.subheader("🎨 Choose Generation Theme")
theme = st.radio(
    "Select the mood/theme for the generated lyrics:",
    ["Same as Original", "Happy", "Sad", "Angry", "Romantic", "Motivational"],
    horizontal=True
)

# Add seed input
st.subheader("🌱 Generation Seed")
seed = st.number_input(
    "Enter a seed value (same seed will generate the same lyrics):",
    min_value=1,
    max_value=1000000,
    value=st.session_state.seed,
    help="Using the same seed value will generate the same lyrics. Change the seed to get different variations."
)

# Generate button
if st.button("Generate Lyrics", type="primary"):
    if not song_title or not artist_name:
        st.error("Please enter both song title and artist name.")
    else:
        with st.spinner("Generating lyrics..."):
            # Get original lyrics
            song_info = get_song_lyrics(song_title, artist_name)
            if not song_info:
                st.error("Could not find lyrics for the given song.")
            else:
                original_lyrics = song_info['raw_lyrics']
                original_title = song_info['title']
                
                # Set up Groq client
                try:
                    client = setup_groq_client()
                except Exception as e:
                    st.error(f"Failed to set up Groq client: {e}")
                    st.stop()
                
                # Create prompt and generate new lyrics
                prompt = create_prompt(original_lyrics, theme)
                genre, generated_lyrics = generate_new_lyrics(client, prompt, seed=seed)
                
                if generated_lyrics:
                    # Save to files
                    save_generated_lyrics(original_title, genre, generated_lyrics)
                    
                    # Update session state
                    st.session_state.generated_lyrics = generated_lyrics
                    st.session_state.genre = genre
                    st.session_state.original_title = original_title
                    st.session_state.show_results = True
                    st.session_state.original_lyrics = original_lyrics
                    st.session_state.seed = seed
                    
                    # Display results
                    st.success("Lyrics generated successfully!")
                else:
                    st.error("Failed to generate new lyrics.")

# Display results if available
if st.session_state.show_results and st.session_state.generated_lyrics:
    # Create three columns for results
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.subheader("Original Lyrics")
        st.text_area("", st.session_state.original_lyrics, height=400)
        
        st.download_button(
            label="📥 Download Original Lyrics",
            data=st.session_state.original_lyrics,
            file_name=f"original_{st.session_state.original_title}_lyrics.txt",
            mime="text/plain"
        )
    
    with col2:
        st.subheader("Generated Lyrics")
        st.text_area("", st.session_state.generated_lyrics, height=400)
        
        st.download_button(
            label="📥 Download Generated Lyrics",
            data=st.session_state.generated_lyrics,
            file_name=f"generated_{st.session_state.original_title}_lyrics.txt",
            mime="text/plain"
        )
    
    with col3:
        st.subheader("Song Information")
        st.info(f"Genre: {st.session_state.genre}")
        st.info(f"Theme: {theme}")
        
        st.subheader("Original Song")
        st.write(f"Title: {st.session_state.original_title}")
        st.write(f"Artist: {artist_name}")
        
        st.download_button(
            label="📥 Download Genre",
            data=st.session_state.genre,
            file_name=f"generated_{st.session_state.original_title}_genre.txt",
            mime="text/plain"
        )

# Footer
st.markdown("---")
st.markdown("Made with ❤️ using Streamlit")