"""
core/poster.py
Posts to YouTube Shorts using YouTube Data API v3 (OAuth2).
Handles 429 rate limiting gracefully — skips instead of crashing.
"""

import os, time, requests

def _yt_refresh_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type":    "refresh_token",
    })
    r.raise_for_status()
    return r.json()["access_token"]

def _yt_description(story: dict) -> str:
    return (
        f"{story['one_liner']}\n\n"
        f"Source: {story['src_url']}\n\n"
        f"#Shorts #{story['category'].replace('_',' ').title().replace(' ','')} "
        f"#News #Inshorts"
    )

def post_youtube(story: dict, video_path: str) -> str | None:
    """Upload video to YouTube as a Short. Returns video ID or None on rate limit."""
    try:
        token = _yt_refresh_token()
    except Exception as e:
        print(f"    [poster] token refresh failed: {e}")
        return None

    title = f"{story['title'][:90]} #Shorts"
    meta  = {
        "snippet": {
            "title":       title,
            "description": _yt_description(story),
            "tags":        ["shorts", "news", "inshorts", story["category"]],
            "categoryId":  "25",
        },
        "status": {"privacyStatus": "public"},
    }

    try:
        init = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos"
            "?uploadType=resumable&part=snippet,status",
            headers={
                "Authorization":  f"Bearer {token}",
                "Content-Type":   "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/mp4",
            },
            json=meta,
        )

        # handle 429 gracefully — don't crash, just skip this story
        if init.status_code == 429:
            print("    [poster] YouTube rate limited (429) — skipping this story")
            return None

        init.raise_for_status()
        upload_url = init.headers["Location"]

        file_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            upload_resp = requests.put(
                upload_url,
                headers={
                    "Content-Length": str(file_size),
                    "Content-Type":   "video/mp4",
                },
                data=f,
            )
        upload_resp.raise_for_status()
        video_id = upload_resp.json()["id"]

        # wait between uploads to avoid rate limiting
        print("    [poster] waiting 60s before next upload...")
        time.sleep(60)

        return video_id

    except Exception as e:
        print(f"    [poster] upload error: {e}")
        return None


def post_instagram(story: dict, video_path: str) -> str:
    raise NotImplementedError("Instagram posting is disabled.")
