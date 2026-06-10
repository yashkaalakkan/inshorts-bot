"""
core/fetcher.py
Fetches news from Currents API (free tier, 600 req/day, works from servers).
Requires NEWS_API_KEY environment variable.

Category is used only for internal tagging/routing — NOT sent to the API.
We fetch all Hindi news in one call and distribute stories across categories.
"""

import os, time, requests

API_KEY = os.environ.get("NEWS_API_KEY", "")

def fetch_stories(category: str = "general", limit: int = 10, offset: int = 0) -> list:
    timeouts = [15, 30, 45]   # retry up to 3 times with increasing timeouts
    last_err = None

    for attempt, timeout in enumerate(timeouts, 1):
        try:
            r = requests.get(
                "https://api.currentsapi.services/v1/latest-news",
                params={
                    "language": "hi",
                    "apiKey":   API_KEY,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            articles = r.json().get("news", [])[offset:offset+limit]

            stories = []
            for a in articles:
                title   = a.get("title", "").strip()
                summary = a.get("description") or title
                if not title or not summary:
                    continue

                story_id = f"{abs(hash(title)):08x}"

                api_cats = a.get("category") or []
                tag = api_cats[0] if api_cats else category

                stories.append({
                    "id":        story_id,
                    "title":     title,
                    "summary":   summary[:300],
                    "one_liner": summary[:100],
                    "source":    a.get("author", ""),
                    "src_url":   a.get("url", ""),
                    "img_url":   a.get("image", ""),
                    "vid_url":   None,
                    "category":  tag,
                })

            print(f"  [fetcher] hindi news → {len(stories)} stories")
            return stories

        except requests.exceptions.Timeout as e:
            last_err = e
            print(f"  [fetcher] timeout on attempt {attempt}/{len(timeouts)} (limit={timeout}s), retrying...")
            time.sleep(3)
        except Exception as e:
            print(f"  [fetcher] error: {e}")
            return []

    print(f"  [fetcher] all retries failed: {last_err}")
    return []