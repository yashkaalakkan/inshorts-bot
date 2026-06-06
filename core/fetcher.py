"""
core/fetcher.py
Fetches news from Currents API (free tier, 600 req/day, works from servers).
Requires CURRENTS_API_KEY environment variable.
"""

import os, requests

API_KEY = os.environ.get("NEWS_API_KEY", "")

CATEGORY_MAP = {
    "human_interest":             "human_interest",
    "lifestyle_leisure":          "lifestyle_leisure",
    "arts_culture_entertainment": "arts_culture_entertainment",
    "economy_business_finance":   "economy_business_finance",
    "politics_government":        "politics_government",
    "science_technology":         "science_technology",
    "society":                    "society",
    "general":                    "general",    
}

def fetch_stories(category: str, limit: int = 10, offset: int = 0) -> list:
    api_category = CATEGORY_MAP.get(category, category)
    try:
        r = requests.get(
            "https://api.currentsapi.services/v1/latest-news",
            params={
                "category": api_category,
                "language": "en",
                "apiKey":   API_KEY,
            },
            timeout=15,
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

            stories.append({
                "id":        story_id,
                "title":     title,
                "summary":   summary[:300],
                "one_liner": summary[:100],
                "source":    a.get("author", ""),
                "src_url":   a.get("url", ""),
                "img_url":   a.get("image", ""),
                "vid_url":   None,
                "category":  category,
            })

        print(f"  [fetcher] {category} → {len(stories)} stories")
        return stories

    except Exception as e:
        print(f"  [fetcher] error for {category}: {e}")
        return []