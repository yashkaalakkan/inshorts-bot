"""
core/history.py
Simple JSON file tracking which stories have been posted.
Stored in project root — commit to repo or keep in Google Drive.
"""

import json
from pathlib import Path
from datetime import datetime

HISTORY_FILE = Path(__file__).parent.parent / "posted_history.json"

def _load() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {}

def _save(data: dict):
    HISTORY_FILE.write_text(json.dumps(data, indent=2))

def already_posted(story_id: str) -> bool:
    return story_id in _load()

def mark_posted(story_id: str, title: str):
    data = _load()
    data[story_id] = {"title": title[:80], "posted_at": datetime.utcnow().isoformat()}
    _save(data)
    # keep last 500 entries only
    if len(data) > 500:
        keys = list(data.keys())
        for k in keys[:-500]:
            del data[k]
        _save(data)
