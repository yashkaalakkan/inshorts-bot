"""
core/music.py
Picks a random MP3 from the assets/music/ folder.
No downloading, no API, no rate limits — just local files.
Add any royalty-free MP3s to assets/music/ and they'll be used automatically.
"""

import random
from pathlib import Path

MUSIC_DIR = Path(__file__).parent.parent / "assets" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

def pick_music(category: str) -> str | None:
    tracks = [f for f in MUSIC_DIR.glob("*.mp3") if f.stat().st_size > 10000]
    
    if not tracks:
        print("    [music] no MP3 files found in assets/music/ — video will be silent")
        return None
    
    chosen = random.choice(tracks)
    print(f"    [music] selected → {chosen.name}")
    return str(chosen)
