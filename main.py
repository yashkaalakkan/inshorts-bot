"""
Inshorts → YouTube Shorts / Instagram Reels
Auto-posting pipeline — 100% free tier
Run manually or via GitHub Actions cron
"""

import os, json, sys
from core.fetcher   import fetch_stories
from core.builder   import build_video
from core.music     import pick_music
from core.poster    import post_youtube, post_instagram
from core.history   import already_posted, mark_posted

# ── config ────────────────────────────────────────────────────────────────────
CATEGORIES = ["human_interest", "lifestyle_leisure", "arts_culture_entertainment", "economy_business_finance", "politics_government", "science_technolog", "society", "general"]
MAX_PER_RUN  = 3         # videos to produce & post per run
FETCH_OFFSET = 0         # bot 1 takes the first 3 stories
POST_YT      = True
POST_IG      = False
# ──────────────────────────────────────────────────────────────────────────────

def run():
    print("=== Inshorts Bot starting ===")
    stories = []
    for cat in CATEGORIES:
        stories += fetch_stories(cat, limit=MAX_PER_RUN * 2, offset=FETCH_OFFSET)

    produced = 0
    for story in stories:
        if produced >= MAX_PER_RUN:
            break
        if already_posted(story["id"]):
            print(f"  skip (duplicate): {story['id']}")
            continue

        print(f"\n→ Processing: {story['title'][:60]}")

        music_path = pick_music(story["category"])
        video_path = build_video(story, music_path)

        if video_path is None:
            print("  ✗ video build failed, skipping")
            continue

        if POST_YT:
            yt_id = post_youtube(story, video_path)
            print(f"  ✓ YouTube: https://youtube.com/shorts/{yt_id}")
        if POST_IG:
            ig_id = post_instagram(story, video_path)
            print(f"  ✓ Instagram reel posted: {ig_id}")

        mark_posted(story["id"], story["title"])
        produced += 1

    print(f"\n=== Done. {produced} video(s) posted. ===")

if __name__ == "__main__":
    run()