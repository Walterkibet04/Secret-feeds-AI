import feedparser
import logging
import random
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

log = logging.getLogger(__name__)

# ── NEWS FEEDS ────────────────────────────────────────────────────────────────
NEWS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",               "source": "BBC World",         "type": "news"},
    {"url": "https://feeds.bbci.co.uk/news/rss.xml",                     "source": "BBC Top",           "type": "news"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",                  "source": "Al Jazeera",        "type": "news"},
    {"url": "https://feeds.reuters.com/reuters/worldNews",                "source": "Reuters",           "type": "news"},
    {"url": "https://rss.france24.com/rss/en/news",                       "source": "France 24",         "type": "news"},
    {"url": "https://feeds.skynews.com/feeds/rss/world.xml",              "source": "Sky News",          "type": "news"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",     "source": "NY Times World",    "type": "news"},
    {"url": "https://www.theguardian.com/world/rss",                      "source": "The Guardian",      "type": "news"},
    {"url": "https://rss.dw.com/rdf/rss-en-world",                       "source": "DW World",          "type": "news"},
    {"url": "https://feeds.bbci.co.uk/news/politics/rss.xml",             "source": "BBC Politics",      "type": "news"},
    {"url": "https://foreignpolicy.com/feed/",                            "source": "Foreign Policy",    "type": "news"},
    {"url": "https://www.cfr.org/rss/publications.xml",                   "source": "CFR",               "type": "news"},
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",             "source": "BBC Business",      "type": "news"},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml",  "source": "NYT Politics",      "type": "news"},
    # X-like breaking sources
    {"url": "https://bnonews.com/index.php/feed/",                        "source": "BNO News",          "type": "news"},
    {"url": "https://breaking911.com/feed/",                              "source": "Breaking911",       "type": "news"},
    {"url": "https://insiderpaper.com/feed/",                             "source": "Insider Paper",     "type": "news"},
    {"url": "https://nypost.com/feed/",                                   "source": "NY Post",           "type": "news"},
    {"url": "https://nypost.com/world/feed/",                             "source": "NY Post World",     "type": "news"},
    {"url": "https://moxie.foxnews.com/google-publisher/world.xml",       "source": "Fox News World",    "type": "news"},
    {"url": "https://moxie.foxnews.com/google-publisher/latest.xml",      "source": "Fox News Latest",   "type": "news"},
    {"url": "https://www.newsmax.com/rss/World/16/",                      "source": "Newsmax World",     "type": "news"},
    {"url": "https://thehill.com/feed/",                                  "source": "The Hill",          "type": "news"},
    {"url": "https://rss.politico.com/politics-news.xml",                 "source": "Politico",          "type": "news"},
    # Conflict & defense
    {"url": "https://www.defenseone.com/rss/all/",                        "source": "Defense One",       "type": "news"},
    {"url": "https://warontherocks.com/feed/",                            "source": "War on Rocks",      "type": "news"},
    {"url": "https://breakingdefense.com/feed/",                          "source": "Breaking Defense",  "type": "news"},
    {"url": "https://www.understandingwar.org/rss.xml",                   "source": "ISW",               "type": "news"},
    {"url": "https://www.bellingcat.com/feed/",                           "source": "Bellingcat",        "type": "news"},
    # Regional & intelligence
    {"url": "https://www.middleeasteye.net/rss",                          "source": "Middle East Eye",   "type": "news"},
    {"url": "https://theintercept.com/feed/?rss",                         "source": "The Intercept",     "type": "news"},
    {"url": "https://english.alarabiya.net/tools/rss",                    "source": "Al Arabiya",        "type": "news"},
    {"url": "https://www.voanews.com/api/epiqq",                          "source": "VOA News",          "type": "news"},
    {"url": "https://rferl.org/api/epiqq",                                "source": "Radio Free Europe", "type": "news"},
    {"url": "https://www.euronews.com/rss?format=mrss&level=vertical&name=news", "source": "Euronews",   "type": "news"},
    {"url": "https://feeds.washingtonpost.com/rss/world",                 "source": "Washington Post",   "type": "news"},
    {"url": "https://www.scmp.com/rss/91/feed",                           "source": "SCMP World",        "type": "news"},
    {"url": "https://tass.com/rss/v2.xml",                                "source": "TASS",              "type": "news"},
    {"url": "https://www.rt.com/rss/news/",                               "source": "RT News",           "type": "news"},
    {"url": "https://thesoufancenter.org/feed/",                          "source": "Soufan Center",     "type": "news"},
    {"url": "https://acleddata.com/feed/",                                "source": "ACLED Conflict",    "type": "news"},
    {"url": "https://www.africanews.com/feed/",                           "source": "Africa News",       "type": "news"},
    {"url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf", "source": "AllAfrica",     "type": "news"},
    {"url": "https://www.straitstimes.com/RSS/global.xml",                "source": "Straits Times",     "type": "news"},
]

# ── SPORTS FEEDS ──────────────────────────────────────────────────────────────
SPORTS_FEEDS = [
    {"url": "https://feeds.bbci.co.uk/sport/rss.xml",                    "source": "BBC Sport",         "type": "sports"},
    {"url": "https://www.espn.com/espn/rss/news",                        "source": "ESPN",              "type": "sports"},
    {"url": "https://www.reddit.com/r/soccer/top/.rss?t=day",            "source": "Reddit Soccer",     "type": "sports"},
    {"url": "https://www.reddit.com/r/sports/top/.rss?t=day",            "source": "Reddit Sports",     "type": "sports"},
    {"url": "https://www.skysports.com/rss/12040",                        "source": "Sky Sports",        "type": "sports"},
    {"url": "https://www.goal.com/feeds/en/news",                         "source": "Goal.com",          "type": "sports"},
]

# ── TRENDING FEEDS ────────────────────────────────────────────────────────────
TRENDING_FEEDS = [
    {"url": "https://www.reddit.com/r/worldnews/top/.rss?t=day",         "source": "Reddit WorldNews",  "type": "trending"},
    {"url": "https://www.reddit.com/r/geopolitics/top/.rss?t=day",       "source": "Reddit Geopolitics","type": "trending"},
    {"url": "https://www.reddit.com/r/news/top/.rss?t=day",              "source": "Reddit News",       "type": "trending"},
    {"url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom",
                                                                          "source": "USGS Earthquakes",  "type": "trending"},
    {"url": "https://trends.google.com/trending/rss?geo=US",             "source": "Google Trends US",  "type": "trending"},
    {"url": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml","source": "BBC Science",    "type": "trending"},
]

# ── KEYWORDS ──────────────────────────────────────────────────────────────────
GEO_KEYWORDS = [
    "war", "conflict", "military", "troops", "sanctions", "nato", "nuclear",
    "coup", "president", "prime minister", "election", "government", "crisis",
    "intelligence", "missile", "border", "invasion", "protest", "regime",
    "geopolitics", "alliance", "weapon", "attack", "terror", "summit",
    "united nations", "assassination", "drone", "ceasefire", "hostage",
    "refugee", "famine", "pandemic", "diplomat", "treaty", "airstrike",
    "bombing", "offensive", "foreign minister", "secretary of state",
    "blockade", "militia", "warship", "captured", "sentenced", "jailed",
    "earthquake", "tsunami", "flood", "hurricane", "volcano", "wildfire",
    "disaster", "dead", "killed", "arrested", "economy", "inflation",
    "collapse", "debt", "oil", "billion", "trillion", "recession",
    "breaking", "urgent", "alert", "developing", "official", "minister",
    "brics", "g7", "g20", "imf", "world bank", "zelensky", "putin",
    "trump", "xi jinping", "modi", "visegrad", "un security council",
]

SPORTS_KEYWORDS = [
    "world cup", "fifa", "champions league", "premier league", "la liga",
    "bundesliga", "serie a", "europa", "euro", "olympics", "championship",
    "final", "semifinal", "quarter", "tournament", "won", "defeated",
    "champion", "title", "trophy", "goal", "scored", "nba", "nfl",
    "mlb", "nhl", "wimbledon", "grand slam", "formula 1", "f1", "ufc", "boxing",
]

TRENDING_KEYWORDS = [
    "breaking", "record", "historic", "first ever", "unprecedented",
    "arrested", "convicted", "sentenced", "charged", "billion", "trillion",
    "spacex", "nasa", "discovery", "strike", "riot", "rally",
    "earthquake", "tsunami", "flood", "hurricane", "disaster",
    "killed", "dead", "crash", "explosion", "developing",
]

# ── DUPLICATE MEMORY — remembers sent titles for 6 hours ─────────────────────
# Stores (title_key, sent_at) so we can expire old entries automatically
_sent_titles: dict = {}  # key -> datetime sent
MAX_AGE_HOURS = 6
MEMORY_EXPIRY_HOURS = 6


def _clean_memory():
    """Remove entries older than MEMORY_EXPIRY_HOURS."""
    now = datetime.now(timezone.utc)
    expired = [k for k, t in _sent_titles.items() if (now - t).total_seconds() / 3600 > MEMORY_EXPIRY_HOURS]
    for k in expired:
        del _sent_titles[k]


def _title_key(title: str) -> str:
    """Normalize title to a short key for comparison."""
    return " ".join(title.lower().split()[:6])


def is_fresh(title: str) -> bool:
    _clean_memory()
    return _title_key(title) not in _sent_titles


def mark_sent(headlines: list):
    now = datetime.now(timezone.utc)
    for h in headlines:
        _sent_titles[_title_key(h["title"])] = now
    log.info(f"  Memory: {len(_sent_titles)} titles stored (auto-expires after {MEMORY_EXPIRY_HOURS}h)")


# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_pub_datetime(entry):
    for field in ["published", "updated"]:
        val = entry.get(field)
        if val:
            try:
                return parsedate_to_datetime(val).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def is_recent(entry):
    pub = get_pub_datetime(entry)
    if pub is None:
        return True
    return (datetime.now(timezone.utc) - pub).total_seconds() / 3600 <= MAX_AGE_HOURS


def is_geo_relevant(title):
    return any(kw in title.lower() for kw in GEO_KEYWORDS)

def is_sports_relevant(title):
    return any(kw in title.lower() for kw in SPORTS_KEYWORDS)

def is_trending_relevant(title):
    return any(kw in title.lower() for kw in TRENDING_KEYWORDS)


# ── FETCH ─────────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_feed(feed):
    try:
        req = urllib.request.Request(feed["url"], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        return feedparser.parse(content)
    except Exception:
        try:
            return feedparser.parse(feed["url"])
        except Exception:
            return None


def fetch_from_feeds(feeds, relevance_fn):
    headlines = []
    for feed in feeds:
        parsed = fetch_feed(feed)
        if not parsed:
            continue
        try:
            for entry in parsed.entries[:12]:
                title = (entry.get("title") or "").strip()
                if title and relevance_fn(title) and is_fresh(title) and is_recent(entry):
                    headlines.append({
                        "title": title,
                        "source": feed["source"],
                        "type": feed["type"],
                        "link": entry.get("link", ""),
                        "pubDate": entry.get("published", ""),
                        "pub_dt": get_pub_datetime(entry),
                    })
        except Exception as e:
            log.warning(f"Parse error {feed['source']}: {e}")
    return headlines


def sort_by_recency(headlines):
    return sorted(
        headlines,
        key=lambda h: h.get("pub_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )


def deduplicate(headlines):
    """Deduplicate by first 5 words — catches same story from multiple sources."""
    seen = set()
    unique = []
    for h in headlines:
        key = " ".join(h["title"].lower().split()[:5])
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique


# ── MAIN ─────────────────────────────────────────────────────────────────────
def fetch_headlines():
    log.info("Fetching news feeds...")
    news = sort_by_recency(deduplicate(fetch_from_feeds(NEWS_FEEDS, is_geo_relevant)))

    log.info("Fetching sports feeds...")
    sports = sort_by_recency(deduplicate(fetch_from_feeds(SPORTS_FEEDS, is_sports_relevant)))

    log.info("Fetching trending feeds...")
    trending = sort_by_recency(deduplicate(fetch_from_feeds(TRENDING_FEEDS, is_trending_relevant)))

    # Target 8 drafts: 5 news + 2 sports + 1 trending
    TARGET = 8
    selected_news     = news[:5]
    selected_sports   = sports[:2]
    selected_trending = trending[:1]
    combined = selected_news + selected_sports + selected_trending

    # Fill shortfall with more news if any category came up short
    shortfall = TARGET - len(combined)
    if shortfall > 0:
        picked = {h["title"] for h in combined}
        extra = [h for h in news if h["title"] not in picked]
        combined += extra[:shortfall]
        if shortfall > 0:
            log.info(f"  ℹ️  Filled {min(shortfall, len(extra))} extra slots from news")

    log.info(f"📰 News: {len([h for h in combined if h['type']=='news'])} | ⚽ Sports: {len([h for h in combined if h['type']=='sports'])} | 🔥 Trending: {len([h for h in combined if h['type']=='trending'])} | Total: {len(combined)}")
    for h in combined:
        age = ""
        if h.get("pub_dt"):
            mins = int((datetime.now(timezone.utc) - h["pub_dt"]).total_seconds() / 60)
            age = f" [{mins}m ago]"
        log.info(f"  [{h['source']}]{age} {h['title'][:75]}")

    mark_sent(combined)
    return combined
