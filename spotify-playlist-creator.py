import spotipy
from spotipy.oauth2 import SpotifyOAuth
import sys
import json
import os
from dotenv import load_dotenv
import re
import time

# Load environment variables
load_dotenv()

def setup_spotify():
    """Set up authentication with Spotify API"""
    print("🔑 Setting up Spotify authentication...")
    scope = "playlist-modify-public playlist-modify-private"
    
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Error: Missing Spotify credentials in .env file!")
        sys.exit(1)
    
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope=scope,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8888/callback"
    ))
    print("✅ Authentication successful!")
    return sp

def clean_song_title(title):
    """Normalize song title by removing common variations"""
    patterns = [
        r'\(ver[\s\.]?\d+\)',
        r'\(version\s?\d+\)',
        r'\(live\)',
        r'\([^)]*version[^)]*\)',
        r'\(feat.[^)]*\)',
        r'\(remaster(ed)?\s*\d*\)',
        r'\([^)]*mix[^)]*\)',
        r'\([^)]*edit[^)]*\)',
        r'-\s*remaster(ed)?\s*\d*',
        r'-\s*single\s*version',
    ]
    
    cleaned = title.lower()
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def build_song_maps(sp, playlist_id, songs_list):
    """Build efficient lookup maps for both playlist and desired songs"""
    print("\n📊 Analyzing current state...")
    
    # Build map of desired songs
    desired_songs = {}
    for i, song in enumerate(songs_list):
        try:
            artist, title = [x.strip() for x in song.split('-', 1)]
            key = f"{artist.lower()}-{clean_song_title(title)}"
            desired_songs[key] = {
                'position': i,
                'artist': artist,
                'title': title,
                'original': song
            }
        except ValueError:
            print(f"❌ Invalid format: {song}")
            continue

    # Build map of playlist songs
    playlist_songs = {}
    results = sp.playlist_tracks(playlist_id)
    position = 0
    while results:
        for item in results['items']:
            if item['track']:
                track = item['track']
                key = f"{track['artists'][0]['name'].lower()}-{clean_song_title(track['name'])}"
                playlist_songs[key] = {
                    'id': track['id'],
                    'position': position,
                    'name': track['name'],
                    'artist': track['artists'][0]['name']
                }
                position += 1
        if results['next']:
            results = sp.next(results)
        else:
            break

    return desired_songs, playlist_songs

def determine_required_actions(desired_songs, playlist_songs):
    """Determine what actions are needed to make playlist match desired songs"""
    actions = {
        'remove': [],    # Songs to remove (in playlist but not desired)
        'add': [],      # Songs to add (in desired but not playlist)
        'move': []      # Songs to move (wrong position)
    }

    # Find songs to remove
    for key, track in playlist_songs.items():
        if key not in desired_songs:
            actions['remove'].append(track)

    # Find songs to add or move
    for key, desired in desired_songs.items():
        if key not in playlist_songs:
            actions['add'].append(desired)
        else:
            current_pos = playlist_songs[key]['position']
            desired_pos = desired['position']
            if current_pos != desired_pos:
                actions['move'].append({
                    'id': playlist_songs[key]['id'],
                    'from_pos': current_pos,
                    'to_pos': desired_pos,
                    'name': playlist_songs[key]['name']
                })

    return actions

def normalize_artist_name(artist):
    """Normalize artist name to handle common variations"""
    replacements = {
        'blink-182': ['blink 182', 'blink182', 'blink'],
        'pete townshend': ['pete townsend'],
        'sir mix-a-lot': ['sir mix a lot', 'sir mixalot', 'sir mix alot'],
        'misc soundtrack': ['lady gaga', 'bradley cooper'],
        'a-ha': ['aha', 'a ha'],
        'the b-52\'s': ['b52s', 'the b52s', 'b 52s', 'the b 52s'],
        'cutting crew': ['cutting crew'],
    }
    
    # First try exact matches
    artist = artist.lower().strip()
    for correct, variations in replacements.items():
        if artist in variations or artist == correct:
            return correct
            
    # Then try removing special characters
    cleaned_artist = re.sub(r'[^\w\s]', ' ', artist)
    cleaned_artist = re.sub(r'\s+', ' ', cleaned_artist).strip()
    
    for correct, variations in replacements.items():
        if cleaned_artist in variations or cleaned_artist == correct.lower():
            return correct
    
    return cleaned_artist  # Return cleaned version if no match found

def search_song(sp, artist, title, max_retries=3):
    """Search for a song on Spotify with retries"""
    for attempt in range(max_retries):
        try:
            # Clean up the title by removing version numbers and parentheses
            clean_title = re.sub(r'\s*\([^)]*\)', '', title)  # Remove anything in parentheses
            clean_title = re.sub(r'\s*-\s*.*$', '', clean_title)  # Remove anything after a dash
            
            # Try different search queries in order of specificity
            queries = [
                f'"{clean_title}" {artist}',         # Exact title match with artist
                clean_title + " " + artist,          # Title and artist without quotes
                f'track:"{clean_title}"',            # Just the exact title
                clean_title                          # Just the title without quotes
            ]
            
            for query in queries:
                print(f"  🔍 Trying: {query}")
                results = sp.search(q=query, type='track', limit=50)
                
                if results['tracks']['items']:
                    # Print first few results for debugging
                    print(f"\n  Found {len(results['tracks']['items'])} potential matches:")
                    for i, track in enumerate(results['tracks']['items'][:5]):
                        print(f"    {i+1}. {track['artists'][0]['name']} - {track['name']}")
                    
                    # Look for exact match first
                    for track in results['tracks']['items']:
                        track_title = re.sub(r'\s*\([^)]*\)', '', track['name'])
                        track_title = re.sub(r'\s*-\s*.*$', '', track_title)
                        track_artist = track['artists'][0]['name']
                        
                        # Check if both title and artist match (case insensitive)
                        if (track_title.lower() == clean_title.lower() and 
                            track_artist.lower() == artist.lower()):
                            print(f"\n  ✅ Found exact match: {track_artist} - {track['name']}")
                            return track['id']
                    
                    # If no exact match, return first result
                    first_match = results['tracks']['items'][0]
                    print(f"\n  ⚠️ Using closest match: {first_match['artists'][0]['name']} - {first_match['name']}")
                    return first_match['id']
            
            print(f"  ❌ No match found for: {title} by {artist}")
            return None

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"  ❌ Error searching for {title} by {artist}: {str(e)}")
                return None
            print(f"  ⚠️ Retry {attempt + 1}/{max_retries}")
            time.sleep(1)

def execute_actions(sp, playlist_id, actions, songs_list, max_retries=3):
    """Execute required actions in optimal order"""
    if actions:  # Only for mode 3
        return process_playlist(sp, playlist_id, songs_list)
    return []

def select_playlist(sp, user_id):
    """
    Let user select an existing playlist or create a new one
    """
    print("\n🎵 Choose an option:")
    print("1. Create new playlist")
    print("2. Update existing playlist")
    
    choice = input("\nEnter your choice (1 or 2): ")
    
    if choice == "1":
        playlist_name = input("\n✨ Enter new playlist name: ")
        playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
        print("✅ Playlist created!")
        return playlist['id']
    
    elif choice == "2":
        playlists = get_user_playlists(sp, user_id)
        
        print("\n📋 Your playlists:")
        for i, playlist in enumerate(playlists, 1):
            print(f"{i}. {playlist['name']}")
        
        while True:
            try:
                choice = int(input("\nEnter playlist number: ")) - 1
                if 0 <= choice < len(playlists):
                    return playlists[choice]['id']
                print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Please enter a number.")
    
    else:
        print("❌ Invalid choice. Creating new playlist...")
        playlist_name = input("\n✨ Enter playlist name: ")
        playlist = sp.user_playlist_create(user_id, playlist_name, public=True)
        print("✅ Playlist created!")
        return playlist['id']

def get_user_playlists(sp, user_id):
    """
    Get user's playlists
    """
    playlists = []
    results = sp.user_playlists(user_id)
    
    while results:
        playlists.extend(results['items'])
        if results['next']:
            results = sp.next(results)
        else:
            break
    
    return playlists

def select_update_mode():
    """
    Let user select how they want to update the playlist
    """
    print("\n📝 Choose update mode:")
    print("1. Add new songs only")
    print("2. Add new songs and replace covers with originals")
    print("3. Make playlist identical to songs.txt (will remove extra songs)")
    
    while True:
        choice = input("\nEnter your choice (1-3): ")
        if choice in ['1', '2', '3']:
            return int(choice)
        print("❌ Invalid choice. Please enter 1, 2, or 3.")

def verify_playlist(sp, playlist_id, songs_list):
    """
    Verify that playlist matches songs.txt exactly
    """
    print("\n🔍 Verifying playlist...")
    
    # Get all tracks from playlist
    playlist_tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            if item['track']:
                track = item['track']
                playlist_tracks.append({
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'id': track['id']
                })
        if results['next']:
            results = sp.next(results)
        else:
            break
    
    # Compare lengths
    if len(playlist_tracks) != len(songs_list):
        print(f"❌ Length mismatch: Playlist has {len(playlist_tracks)} songs, songs.txt has {len(songs_list)} songs")
        return False
    
    # Compare each song
    mismatches = []
    for i, (playlist_track, expected_song) in enumerate(zip(playlist_tracks, songs_list), 1):
        try:
            expected_artist, expected_title = [x.strip() for x in expected_song.split('-', 1)]
            
            # Clean up titles for comparison
            playlist_title = clean_song_title(playlist_track['name'])
            expected_title = clean_song_title(expected_title)
            
            # Compare
            title_match = playlist_title.lower() == expected_title.lower()
            artist_match = playlist_track['artist'].lower() == expected_artist.lower()
            
            if not (title_match and artist_match):
                mismatches.append({
                    'position': i,
                    'expected': expected_song,
                    'found': f"{playlist_track['artist']} - {playlist_track['name']}"
                })
        except ValueError:
            mismatches.append({
                'position': i,
                'expected': expected_song,
                'found': f"{playlist_track['artist']} - {playlist_track['name']}"
            })
    
    # Report results
    if not mismatches:
        print("✅ Playlist matches songs.txt exactly!")
        return True
    else:
        print("\n❌ Found mismatches:")
        for mismatch in mismatches:
            print(f"\nPosition {mismatch['position']}:")
            print(f"  Expected: {mismatch['expected']}")
            print(f"  Found:    {mismatch['found']}")
        return False

def reorder_playlist(sp, playlist_id, songs_list, max_retries=3):
    """
    Reorder playlist by placing each song before the position it needs to be in
    """
    print("\n📋 Reordering playlist...")
    
    # Go through each position in order (0 to n-1)
    for target_pos in range(len(songs_list)):
        desired_song = songs_list[target_pos]
        
        # Get current state
        results = sp.playlist_tracks(playlist_id)
        current_tracks = []
        for item in results['items']:
            if item['track']:
                current_tracks.append({
                    'id': item['track']['id'],
                    'name': item['track']['name'],
                    'artist': item['track']['artists'][0]['name']
                })
        
        # Check what's currently at our target position
        current_song = f"{current_tracks[target_pos]['artist']} - {current_tracks[target_pos]['name']}"
        
        if current_song != desired_song:
            # Find where our desired song currently is
            for current_pos, track in enumerate(current_tracks):
                if f"{track['artist']} - {track['name']}" == desired_song:
                    # Move it by inserting it before the target position
                    try:
                        sp.playlist_reorder_items(
                            playlist_id, 
                            range_start=current_pos,    # where the song is now
                            insert_before=target_pos    # where we want it to be
                        )
                        print(f"  ✅ Moved '{desired_song}' to position {target_pos + 1}")
                        time.sleep(0.1)  # Small delay between moves
                        break
                    except Exception as e:
                        print(f"  ❌ Error moving track: {e}")
        else:
            print(f"  ✅ '{desired_song}' already at position {target_pos + 1}")
    
    return True

def generate_validation_file(sp, playlist_id, songs_list):
    """
    Generate a validation file showing target vs actual order
    """
    print("\n📊 Generating validation file...")
    
    # Get current playlist state
    current_tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            if item['track']:
                current_tracks.append(f"{item['track']['artists'][0]['name']} - {item['track']['name']}")
        if results['next']:
            results = sp.next(results)
        else:
            break
    
    # Create validation file
    with open('playlist_validation.txt', 'w', encoding='utf-8') as f:
        f.write("Position | Expected | Current\n")
        f.write("-" * 100 + "\n")
        
        # Write each position
        for i in range(max(len(songs_list), len(current_tracks))):
            expected = songs_list[i] if i < len(songs_list) else "---"
            actual = current_tracks[i] if i < len(current_tracks) else "---"
            f.write(f"{i+1:3d} | {expected:50} | {actual}\n")
    
    print("✅ Validation file created: playlist_validation.txt")

def sort_playlist(sp, playlist_id, songs_list):
    """Sort playlist one position at a time"""
    print("\n📋 Sorting playlist...")
    
    # Get initial playlist state
    current_tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            if item['track']:
                current_tracks.append({
                    'id': item['track']['id'],
                    'name': item['track']['name'],
                    'artist': item['track']['artists'][0]['name'],
                    'full_name': f"{item['track']['artists'][0]['name']} - {item['track']['name']}"
                })
        if results['next']:
            results = sp.next(results)
        else:
            break

    missing_songs = []
    sorted_count = 0  # Keep track of how many songs we've successfully sorted
    
    # Go through each position in order
    for target_pos in range(len(songs_list)):
        desired_song = songs_list[target_pos]
        print(f"\nProcessing position {target_pos + 1}: {desired_song}")
        
        # Find this exact song in the playlist
        found = False
        for current_pos, track in enumerate(current_tracks):
            if track['full_name'] == desired_song:
                found = True
                try:
                    # If it's not already in the right position
                    if current_pos != sorted_count:
                        # Move it to where it should be
                        sp.playlist_reorder_items(playlist_id, current_pos, sorted_count)
                        print(f"  ✅ Moved to position {sorted_count + 1}")
                        
                        # Update our local state
                        track = current_tracks.pop(current_pos)
                        current_tracks.insert(sorted_count, track)
                    else:
                        print(f"  ✅ Already in correct position {sorted_count + 1}")
                    
                    sorted_count += 1  # Increment our sorted count
                except Exception as e:
                    print(f"  ❌ Error moving track: {e}")
                break
        
        if not found:
            missing_songs.append(desired_song)
            print(f"  ⚠️ Not found in playlist")
            # Don't increment sorted_count for missing songs
    
    # Remove everything after our last sorted song
    if sorted_count < len(current_tracks):
        extra_tracks = current_tracks[sorted_count:]
        if extra_tracks:
            try:
                track_ids = [track['id'] for track in extra_tracks]
                sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
                print(f"\n🗑️ Removed {len(extra_tracks)} songs after position {sorted_count}")
                for track in extra_tracks:
                    print(f"  ✅ Removed: {track['full_name']}")
            except Exception as e:
                print(f"❌ Error removing extra tracks: {e}")
    
    return missing_songs

def add_missing_songs(sp, playlist_id, missing_songs):
    """Add songs that weren't found in the playlist, avoiding duplicates"""
    print("\n➕ Adding missing songs...")
    
    # First get current playlist tracks to check for duplicates
    current_tracks = []
    results = sp.playlist_tracks(playlist_id)
    while results:
        for item in results['items']:
            if item['track']:
                current_tracks.append({
                    'name': item['track']['name'],
                    'artist': item['track']['artists'][0]['name'],
                    'id': item['track']['id'],
                    'full_name': f"{item['track']['artists'][0]['name']} - {item['track']['name']}"
                })
        if results['next']:
            results = sp.next(results)
        else:
            break

    not_found = []
    tracks_to_add = []
    
    for song in missing_songs:
        # Skip if song is already in playlist
        if any(track['full_name'] == song for track in current_tracks):
            print(f"  ⚠️ Already in playlist: {song}")
            continue
            
        try:
            artist, title = [x.strip() for x in song.split('-', 1)]
            track_id = search_song(sp, artist, title)
            if track_id:
                tracks_to_add.append(track_id)
                print(f"  ✅ Found and will add: {song}")
            else:
                not_found.append(song)
                print(f"  ❌ Could not find: {song}")
        except ValueError:
            print(f"  ❌ Invalid format: {song}")
            not_found.append(song)
    
    if tracks_to_add:
        try:
            sp.playlist_add_items(playlist_id, tracks_to_add)
            print(f"  ✅ Added {len(tracks_to_add)} songs")
        except Exception as e:
            print(f"  ❌ Error adding songs: {e}")
    
    return not_found

def add_and_verify_song(sp, playlist_id, track_id, desired_song, target_position):
    """Add a song and verify it was added correctly"""
    try:
        # Add the song (it will be added at the end)
        sp.playlist_add_items(playlist_id, [track_id])
        time.sleep(1)  # Wait for add to complete
        
        # Get the playlist state
        results = sp.playlist_tracks(playlist_id)
        current_tracks = []
        for item in results['items']:
            if item['track']:
                current_tracks.append({
                    'id': item['track']['id'],
                    'position': len(current_tracks)
                })
        
        # Find where our song was added
        for pos, track in enumerate(current_tracks):
            if track['id'] == track_id:
                # Move it to the target position if needed
                if pos != target_position:
                    sp.playlist_reorder_items(playlist_id, pos, target_position)
                    print(f"  ✅ Added and moved to position {target_position + 1}")
                else:
                    print(f"  ✅ Added at position {target_position + 1}")
                return True
        
        print("  ❌ Added song not found in playlist")
        return False
        
    except Exception as e:
        print(f"  ❌ Error adding/moving song: {e}")
        return False

def process_playlist(sp, playlist_id, songs_list):
    """Process playlist according to songs list"""
    print("\n📋 Processing playlist...")
    
    for target_pos, desired_song in enumerate(songs_list):
        print(f"\nProcessing position {target_pos + 1}: {desired_song}")
        
        # Get fresh playlist state each time
        current_tracks = []
        results = sp.playlist_tracks(playlist_id)
        while results:
            for item in results['items']:
                if item['track']:
                    current_tracks.append({
                        'id': item['track']['id'],
                        'name': item['track']['name'],
                        'artist': item['track']['artists'][0]['name'],
                        'full_name': f"{item['track']['artists'][0]['name']} - {item['track']['name']}"
                    })
            if results['next']:
                results = sp.next(results)
            else:
                break

        # First try to find and move existing song
        found = False
        for current_pos, track in enumerate(current_tracks):
            if track['full_name'] == desired_song:
                if current_pos != target_pos:
                    try:
                        # Move directly to target position
                        sp.playlist_reorder_items(playlist_id, current_pos, target_pos)
                        print(f"  ✅ Moved to position {target_pos + 1}")
                        time.sleep(1)  # Wait after move
                    except Exception as e:
                        print(f"  ❌ Error moving track: {e}")
                else:
                    print(f"  ✅ Already in position {target_pos + 1}")
                found = True
                break
        
        # If not found, search and add
        if not found:
            try:
                artist, title = [x.strip() for x in desired_song.split('-', 1)]
                track_id = search_song(sp, artist, title)
                if track_id:
                    # Add to end
                    sp.playlist_add_items(playlist_id, [track_id])
                    time.sleep(1)  # Wait after add
                    
                    # Then move to correct position
                    results = sp.playlist_tracks(playlist_id)
                    last_pos = len([x for x in results['items'] if x['track']]) - 1
                    sp.playlist_reorder_items(playlist_id, last_pos, target_pos)
                    print(f"  ✅ Added and moved to position {target_pos + 1}")
                    time.sleep(1)  # Wait after move
                else:
                    print(f"  ❌ Could not find on Spotify")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        
        time.sleep(0.5)  # General operation delay
    
    # Finally remove any extra tracks
    results = sp.playlist_tracks(playlist_id)
    current_tracks = [item['track']['id'] for item in results['items'] if item['track']]
    if len(current_tracks) > len(songs_list):
        try:
            track_ids = current_tracks[len(songs_list):]
            sp.playlist_remove_all_occurrences_of_items(playlist_id, track_ids)
            print(f"\n🗑️ Removed {len(track_ids)} extra songs")
        except Exception as e:
            print(f"❌ Error removing extra tracks: {e}")

def main():
    print("\n🎵 Welcome to Spotify Playlist Creator! 🎵\n")
    
    # Read songs file
    try:
        with open('songs.txt', 'r', encoding='utf-8') as file:
            songs = [line.strip() for line in file if line.strip()]
        print(f"📖 Found {len(songs)} songs in songs.txt")
    except FileNotFoundError:
        print("❌ Error: songs.txt file not found!")
        sys.exit(1)

    # Setup Spotify
    sp = setup_spotify()
    user_id = sp.current_user()['id']
    
    # Select or create playlist
    playlist_id = select_playlist(sp, user_id)
    
    # If updating existing playlist, get update mode
    update_mode = 1  # Default for new playlist
    if playlist_id:
        update_mode = select_update_mode()
    
    # Build maps and determine required actions
    desired_songs, playlist_songs = build_song_maps(sp, playlist_id, songs)
    actions = determine_required_actions(desired_songs, playlist_songs)
    
    # Show summary of changes
    print("\n📝 Required changes:")
    print(f"  • Songs to remove: {len(actions['remove'])}")
    print(f"  • Songs to add: {len(actions['add'])}")
    print(f"  • Songs to reorder: {len(actions['move'])}")
    
    # Execute actions
    not_found = execute_actions(sp, playlist_id, actions, songs, max_retries=3)
    
    # Generate validation file
    generate_validation_file(sp, playlist_id, songs)
    
    # Show results
    if not_found:
        print("\n⚠️ The following songs couldn't be found:")
        for song in not_found:
            print(f"  • {song}")
    
    # Verify playlist if in mode 3 (exact match)
    if update_mode == 3:
        if verify_playlist(sp, playlist_id, songs):
            print("\n🎉 Playlist verified and matches exactly! 🎉")
        else:
            print("\n⚠️ Playlist verification failed - some differences found")
    else:
        print("\n🎉 Playlist update completed!")
    
    print(f"🔗 Playlist URL: https://open.spotify.com/playlist/{playlist_id}")

if __name__ == "__main__":
    main()