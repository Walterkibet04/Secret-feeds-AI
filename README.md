# Secret Feeds Bot — Python Version

Automatically fetches breaking news, trending topics, and X account posts,
generates tweet drafts in your Secret Feeds voice, and emails them 5x per day.

Powered by: Groq AI (free) · Gmail · Render (free hosting)

---

## Adding Your Own X Accounts

Open `fetcher.py` and find the `X_ACCOUNTS` list:

```python
X_ACCOUNTS = [
    {"handle": "BBCBreaking",    "label": "BBC Breaking (X)"},
    {"handle": "Reuters",        "label": "Reuters (X)"},
    # Add yours below:
    {"handle": "AnyXHandle",     "label": "Any Display Name (X)"},
]
```

Just add a new line with the handle (without @) and a label. Save. Done.

---

## Full Setup Guide

### What You Need (All Free)
- GitHub account — github.com
- Render account — render.com
- Groq API key — console.groq.com
- Gmail App Password

---

### Step 1 — Get Your Groq API Key (Free)
1. Go to console.groq.com
2. Sign up with your Gmail — no credit card needed
3. Click API Keys → Create API Key
4. Copy and save it

---

### Step 2 — Get Gmail App Password
1. Go to myaccount.google.com
2. Security → 2-Step Verification → turn it ON
3. Security → App Passwords → Create
4. Name it "Secret Feeds Bot"
5. Copy the 16-character password shown

---

### Step 3 — Upload to GitHub
1. Go to github.com → New repository
2. Name it: secret-feeds-bot
3. Set it to Private
4. Upload all files from this folder

---

### Step 4 — Deploy on Render (Free)
1. Go to render.com → sign up with GitHub
2. Click New → Web Service → connect your repo
3. Settings:
   - Runtime: Python
   - Build Command: pip install -r requirements.txt
   - Start Command: python main.py
   - Instance Type: Free
4. Click Environment → add these 4 variables:

| Key                  | Value                          |
|----------------------|-------------------------------|
| GROQ_API_KEY         | your key from Step 1          |
| EMAIL_FROM           | your Gmail address             |
| EMAIL_APP_PASSWORD   | 16-char password from Step 2  |
| EMAIL_TO             | walterkibet1997@gmail.com     |

5. Click Deploy

---

## What Happens After Deployment

- Bot runs immediately and sends your first batch of drafts to your Gmail
- Then runs every 4 hours: 7am, 11am, 3pm, 7pm, 11pm
- Each email contains 5 ready-to-post drafts
- Each draft shows source, format type, and character count

---

## Sources

| Type | Sources |
|------|---------|
| 🌍 News | BBC, Reuters, Al Jazeera, Guardian, NY Times, DW, France 24, Sky News |
| 🔥 Trending | Reddit, Google Trends, ESPN, USGS Earthquakes, BBC Sport |
| 𝕏 From X | 10 top geopolitics/intelligence accounts via Nitter (free) |

---

## Troubleshooting

- **No emails received** — check your spam/junk folder first
- **Groq error** — regenerate your API key at console.groq.com
- **Gmail auth error** — regenerate App Password at myaccount.google.com
- **Nitter not fetching** — normal occasionally, bot auto-tries 4 backup servers
- **Render bot stopped** — free tier sleeps after inactivity; redeploy from dashboard
