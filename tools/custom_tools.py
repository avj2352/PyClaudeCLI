from azapi import AZlyrics
from strands import tool
from typing import Optional

@tool
def get_songs_lyrics(title: str, artist: Optional[str] = None) -> Optional[str]:
    """Custom tool to fetch lyrics using azapi"""
    try:
        api = AZlyrics('google')
        api.title = title
        if artist is not None:
            api.artist = artist
        api.getLyrics(save=True)
    except Exception as err:
        print(f"Error! calling AZlyrics API: {err.__class__} - {str(err)}")
        return None
    
