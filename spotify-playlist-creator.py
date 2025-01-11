import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_spotify():
    """
    Set up authentication with Spotify API
    """
    print("🔑 Setting up Spotify authentication...")
    scope = "playlist-modify-public"
    
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Error: Missing Spotify credentials in .env file!")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file")
        sys.exit(1)
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope=scope,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8888/callback"
    ))
    print("✅ Authentication successful!")
    return sp

def create_playlist(sp, playlist_name, user_id):
    """
    Create a new playlist
    """
    print(f"\n📝 Creating new playlist: '{playlist_name}'...")
    playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
    print("✅ Playlist created!")
    return playlist['id']

def search_and_add_songs(sp, playlist_id, songs_list):
    """
    Search for songs and add them to the playlist
    """
    track_ids = []
    not_found = []
    total_songs = len(songs_list)
    
    print(f"\n🎵 Starting to add {total_songs} songs to your playlist...")
    
    for index, song in enumerate(songs_list, 1):
        print(f"📍 Processing ({index}/{total_songs}): {song}")
        # Search for the track
        result = sp.search(q=song, limit=1, type='track')
        
        if result['tracks']['items']:
            track_id = result['tracks']['items'][0]['id']
            track_ids.append(track_id)
            print(f"  ✅ Found: {result['tracks']['items'][0]['name']} by {result['tracks']['items'][0]['artists'][0]['name']}")
        else:
            not_found.append(song)
            print(f"  ❌ Could not find: {song}")
        
        # Spotify API has a limit of 100 songs per request
        if len(track_ids) == 100:
            print("\n💫 Adding batch of songs to playlist...")
            sp.playlist_add_items(playlist_id, track_ids)
            track_ids = []
    
    # Add any remaining tracks
    if track_ids:
        print("\n💫 Adding final batch of songs to playlist...")
        sp.playlist_add_items(playlist_id, track_ids)
    
    return not_found

def main():
    print("\n🎵 Welcome to Spotify Playlist Creator! 🎵\n")
    
    # Read songs from a text file (one song per line)
    print("📖 Reading songs from file...")
    try:
        with open('songs.txt', 'r', encoding='utf-8') as file:
            songs = [line.strip() for line in file if line.strip()]
        print(f"✅ Found {len(songs)} songs in file")
    except FileNotFoundError:
        print("❌ Error: songs.txt file not found!")
        sys.exit(1)

    # Initialize Spotify client
    sp = setup_spotify()
    
    # Get user ID
    print("\n🔍 Getting your Spotify user information...")
    user_id = sp.current_user()['id']
    
    # Create new playlist
    playlist_name = input("\n✨ Enter playlist name: ")
    playlist_id = create_playlist(sp, playlist_name, user_id)
    
    # Add songs to playlist
    not_found = search_and_add_songs(sp, playlist_id, songs)
    
    # Print results
    if not_found:
        print("\n⚠️ The following songs couldn't be found:")
        for song in not_found:
            print(f"  - {song}")
    
    print("\n🎉 Playlist created successfully! 🎉")
    playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
    print(f"🔗 Playlist URL: {playlist_url}")

if __name__ == "__main__":
    main()