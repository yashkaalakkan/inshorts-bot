# Inshorts → YouTube Shorts / Instagram Reels
## Complete Setup Guide — Zero Cost

---

## Folder structure
```
inshorts_bot/
├── main.py                  ← run this
├── requirements.txt
├── posted_history.json      ← auto-created, tracks duplicates
├── core/
│   ├── fetcher.py           ← pulls stories from Inshorts
│   ├── builder.py           ← assembles the 9:16 video
│   ├── music.py             ← picks royalty-free BGM
│   ├── poster.py            ← posts to YouTube + Instagram
│   └── history.py           ← dedup tracker
├── assets/
│   ├── music/               ← cached BGM tracks (auto-downloaded)
│   └── fonts/               ← optional: drop NotoSans .ttf files here
├── output/                  ← rendered MP4s (auto-cleaned)
└── .github/
    └── workflows/
        └── autopost.yml     ← GitHub Actions cron
```

---

## Step 1 — Local setup

```bash
# Clone / create the repo
cd inshorts_bot

# Install FFmpeg (required for video rendering)
# macOS:
brew install ffmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg fonts-noto

# Python deps
pip install -r requirements.txt
```

---

## Step 2 — YouTube API credentials (one-time)

1. Go to https://console.cloud.google.com/
2. Create a new project → **Enable YouTube Data API v3**
3. Create **OAuth 2.0 credentials** → Desktop App
4. Download the JSON — note `client_id` and `client_secret`
5. Run this once locally to get your refresh token:

```python
# run_once_get_yt_token.py
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file(
    'client_secret.json',
    scopes=['https://www.googleapis.com/auth/youtube.upload']
)
creds = flow.run_local_server(port=0)
print("REFRESH TOKEN:", creds.refresh_token)
```

Save the refresh token — you'll need it for Step 4.

---

## Step 3 — Instagram / Meta credentials (one-time)

Requirements:
- Instagram **Business or Creator** account
- Linked Facebook Page
- Meta Developer App with `instagram_basic` + `instagram_content_publish` permissions

Steps:
1. https://developers.facebook.com/ → Create App → Business
2. Add **Instagram Graph API** product
3. Get a **long-lived access token** (valid 60 days, can be refreshed):
   - Go to Graph API Explorer
   - Select your app → get User token
   - Exchange for long-lived: `GET /oauth/access_token?grant_type=fb_exchange_token&...`
4. Get your Instagram User ID:
   - `GET /me?fields=id,name&access_token=YOUR_TOKEN`

---

## Step 4 — GitHub Actions secrets

In your GitHub repo → **Settings → Secrets and variables → Actions**:

| Secret name        | Value                          |
|--------------------|--------------------------------|
| `YT_CLIENT_ID`     | From Google Console            |
| `YT_CLIENT_SECRET` | From Google Console            |
| `YT_REFRESH_TOKEN` | From Step 2 script             |
| `IG_ACCESS_TOKEN`  | Long-lived Meta token          |
| `IG_USER_ID`       | Your Instagram user ID         |

---

## Step 5 — Test locally

```bash
# Set env vars temporarily
export YT_CLIENT_ID=xxx
export YT_CLIENT_SECRET=xxx
export YT_REFRESH_TOKEN=xxx
export IG_ACCESS_TOKEN=xxx
export IG_USER_ID=xxx

python main.py
```

Check the `output/` folder for rendered MP4s before posting.

---

## Step 6 — Deploy to GitHub Actions

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/inshorts-bot.git
git push -u origin main
```

The workflow in `.github/workflows/autopost.yml` will run every 6 hours automatically.
You can also trigger it manually from the **Actions** tab in GitHub.

---

## Video layout (matches reference)

```
┌──────────────────────────────┐
│                              │
│   Image or video from        │  ← top 50% (960px)
│   the Inshorts story         │
│                              │
├──────────────────────────────┤
│ ████ HEADLINE HERE ████      │  ← yellow highlighted title
│                              │
│ Summary text in white...     │  ← summary (up to 6 lines)
│                              │
│ Source name         [LOGO]   │  ← source + logo bottom-right
└──────────────────────────────┘
```

Description format:
```
One-liner summary of the news story.

Source: https://source-url.com

#Shorts #Technology #News #Inshorts
```

---

## Music system

- Source: **Pixabay Music** (CC0, royalty-free, safe for YT + IG monetisation)
- Matching: category → mood → track (e.g. Technology → electronic/futuristic)
- Volume: 18% (subtle background, voiceover-friendly)
- Tracks are cached locally after first download

### To add your own music library:
Drop `.mp3` files into `assets/music/` — the picker will use those first.

---

## Free tier limits

| Service          | Free limit            | Our usage          |
|------------------|-----------------------|--------------------|
| GitHub Actions   | 2,000 min/month       | ~5 min per run     |
| YouTube API      | 10,000 units/day      | ~1,600 per video   |
| Meta Graph API   | Rate-limited          | Well within limits |
| Pixabay Music    | Unlimited             | Cached locally     |
| Clearbit Logos   | Unlimited (small use) | 1 per video        |

**Posting 3 videos/run × 4 runs/day = 12 videos/day — well within all limits.**

---

## Troubleshooting

**Video is silent**: No music cached yet — run once with internet, tracks will download.
**Logo not showing**: Clearbit couldn't find the domain — falls back to text badge automatically.
**Instagram 400 error**: Token expired — refresh your long-lived token (valid 60 days).
**YouTube quota exceeded**: Reduce `MAX_PER_RUN` in `main.py` or spread posts over more runs.
