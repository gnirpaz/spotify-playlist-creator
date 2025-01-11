# 🎵 Spotify Playlist Creator

A command-line tool that creates Spotify playlists from a text file. Simply provide a list of songs, and this tool will create a Spotify playlist for you with real-time progress updates.

## ✨ Features

- Create Spotify playlists from a text file
- Real-time progress updates with emoji indicators
- Batch processing (handles Spotify API limits)
- Clear error reporting for songs that couldn't be found
- User-friendly command line interface

## 🚀 Setup

1. **Install Requirements**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Spotify Credentials**
   - Create an app at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Set redirect URI to `http://localhost:8888/callback`
   - Copy `.env.example` to `.env`
   - Add your Spotify client ID and secret to `.env`

## 📝 Usage

1. **Prepare Your Songs**
   Create a `songs.txt` file with your songs, one per line in the format:
   ```
   Artist - Song Name
   ```
   Example:
   ```
   The Beatles - Yesterday
   Queen - Bohemian Rhapsody
   Eagles - Hotel California
   ```

2. **Run the Script**
   ```bash
   python spotify-playlist-creator.py
   ```

3. **Follow the Prompts**
   - The script will authenticate with Spotify (first time only)
   - Enter a name for your playlist
   - Watch as your playlist is created!

## 🔍 What to Expect

The script will:
- Read your songs list
- Create a new playlist
- Search for each song on Spotify
- Add found songs to your playlist
- Show progress for each step
- Report any songs that couldn't be found
- Provide the URL to your new playlist

## ⚠️ Notes

- Songs should be in the format "Artist - Song Name"
- Some songs might not be found if the exact title/artist doesn't match Spotify's database
- The script uses the first search result for each song

## 📄 License

MIT License - feel free to modify and reuse this code! 