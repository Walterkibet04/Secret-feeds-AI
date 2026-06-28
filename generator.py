import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── GEMINI SETUP ──────────────────────────────────────────────────────────────
try:
    from google import genai as google_genai
    gemini_client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    GEMINI_MODEL = "gemini-1.5-flash"  # 1.5-flash has higher free limits than 2.0-flash
    GEMINI_AVAILABLE = bool(os.getenv("GEMINI_API_KEY"))
except Exception:
    GEMINI_AVAILABLE = False
    gemini_client = None

# ── GROQ SETUP (fallback) ─────────────────────────────────────────────────────
try:
    from groq import Groq
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False
    groq_client = None

FORMATS = ["single", "thread", "sharp"]

FORMAT_INSTRUCTIONS = {
    "single": """Write one tweet under 280 characters.
- Start with the most important specific fact: a number, name, country, or event
- Use simple English that anyone can understand
- Be direct and clear — no metaphors, no vague language
- End with one short insight or question to drive replies
- Good: "235 people died in Venezuela after a 7.3 earthquake. Rescue teams from 12 countries have arrived. The government took 6 hours to ask for help."
- Bad: "Venezuela trembles as chaos looms" — too vague, never write this""",

    "thread": """Write a thread opener under 280 characters. End with 🧵
- Start with a bold specific fact that surprises people
- Use simple English
- Make people want to read more
- Good: "Russia moved 40,000 troops to Finland's border this week. NATO has not responded publicly. Here is what is actually happening 🧵"
- Bad: "The wheels of geopolitics are turning silently" — meaningless, never write this""",

    "sharp": """Write one short tweet under 200 characters.
- Must be based on a real specific fact from the story
- Simple English, direct, clear
- Good: "235 dead in Venezuela. The earthquake hit a region where hospitals were already out of supplies."
- Bad: "Silence speaks volumes in the corridors of power" — too vague, never write this""",
}

SYSTEM_PROMPT = """You write tweets for Secret Feeds, a global news and geopolitics account on X.

Your style:
- Simple English that anyone can understand
- Always lead with a specific fact: a number, name, place, or event
- Direct and clear — never vague or cryptic
- Short sentences. Active voice.
- Must NOT sound copy-pasted or AI-generated

If the source is an RSS error or unrelated garbage, respond with only: SKIP"""

REWRITE_PROMPT = """You are helping rewrite a tweet for Secret Feeds, a news account on X.

GOAL: Make the tweet look original to X's algorithm without changing what it says.

STRICT RULES:
1. Keep EVERY fact, number, name, and date exactly the same
2. Do NOT add new information
3. Do NOT remove any information
4. Do NOT change the meaning even slightly
5. Use simple everyday English
6. Just rearrange the sentence structure and swap some words with synonyms
7. Keep it under 280 characters
8. Do not add hashtags or emojis unless the original has them

If the original says "235 people died", your version must still say "235 people died" — not "hundreds died".

Original tweet:
"{tweet}"

Write ONLY the rewritten tweet. Nothing else."""


# ── AI CALL WITH FALLBACK ─────────────────────────────────────────────────────
def call_ai(prompt: str) -> str:
    """Try Gemini first, fall back to Groq if Gemini fails or hits limits."""

    # Try Gemini
    if GEMINI_AVAILABLE and gemini_client:
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                log.warning("⚠️  Gemini quota hit — switching to Groq fallback")
            elif "API_KEY" in err or "api_key" in err.lower():
                log.warning("⚠️  Gemini API key issue — switching to Groq fallback")
            else:
                log.warning(f"⚠️  Gemini error — switching to Groq: {err[:80]}")

    # Groq fallback
    if GROQ_AVAILABLE and groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=350,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
            )
            log.info("  ✅ Used Groq fallback")
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"Groq also failed: {e}")

    raise RuntimeError("Both Gemini and Groq failed. Check your API keys.")


# ── PROMPT BUILDERS ───────────────────────────────────────────────────────────
def build_prompt(headline: dict, fmt: str) -> str:
    source_type = headline.get("type", "news")

    if source_type == "sports":
        tone = "This is a sports story. State the key result or fact clearly. Add why it matters — record broken, upset, political angle, or global significance."
    elif source_type == "trending":
        tone = "This is a trending event. Lead with the key facts. Add what it means — who is affected, what happens next."
    else:
        tone = "This is a world news or geopolitics story. Lead with the most important specific fact. Then explain what it means in one sentence."

    return f"""{SYSTEM_PROMPT}

Source headline: "{headline['title']}"
From: {headline['source']}

{tone}

{FORMAT_INSTRUCTIONS[fmt]}

Write ONLY the tweet. No labels, no quotes around it, no explanation."""


# ── PUBLIC FUNCTIONS ──────────────────────────────────────────────────────────
def rewrite_tweet(original: str) -> str:
    return call_ai(REWRITE_PROMPT.format(tweet=original))


def generate_draft(headline: dict, fmt: str) -> str:
    return call_ai(build_prompt(headline, fmt))


def generate_drafts(headlines: list) -> list:
    drafts = []
    for i, headline in enumerate(headlines):
        fmt = FORMATS[i % len(FORMATS)]
        try:
            text = generate_draft(headline, fmt)

            if text.upper().startswith("SKIP"):
                log.info(f"  ⏭️  Skipped: {headline['title'][:60]}")
                continue

            drafts.append({
                "text": text,
                "format": fmt,
                "source": headline["source"],
                "type": headline.get("type", "news"),
                "original_title": headline["title"],
                "link": headline.get("link", ""),
                "chars": len(text),
            })
            log.info(f"  ✍️  Draft {len(drafts)}: {text[:70]}...")
            time.sleep(1)  # Rate limit buffer for both APIs
        except Exception as e:
            log.error(f"Failed for: {headline['title'][:50]} — {e}")

    return drafts
