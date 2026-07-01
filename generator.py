import os
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── GEMINI SETUP ──────────────────────────────────────────────────────────────
try:
    from google import genai as google_genai
    gemini_client = google_genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    GEMINI_MODEL = "gemini-2.5-flash"
    GEMINI_AVAILABLE = bool(os.getenv("GEMINI_API_KEY"))
except Exception:
    GEMINI_AVAILABLE = False
    gemini_client = None

# ── GROQ SETUP (fallback) ─────────────────────────────────────────────────────
try:
    from groq import Groq
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    GROQ_AVAILABLE = bool(os.getenv("GROQ_API_KEY"))
except Exception:
    GROQ_AVAILABLE = False
    groq_client = None

SYSTEM_PROMPT = """You write tweets for Secret Feeds, a global news and geopolitics account on X.
Simple English. Direct and clear. Never vague or cryptic. Short sentences. Active voice.
Must NOT sound copy-pasted or AI-generated."""

REWRITE_PROMPT = """You are helping rewrite a tweet for Secret Feeds, a news account on X.

GOAL: Make the tweet look original to X's algorithm without changing what it says.

STRICT RULES:
1. Keep EVERY fact, number, name, and date exactly the same
2. Do NOT add new information
3. Do NOT remove any information
4. Do NOT change the meaning even slightly
5. Use simple everyday English
6. Just rearrange the sentence structure and swap some words with synonyms
7. Keep it under 4000 characters (X Premium account)
8. Do not add hashtags or emojis unless the original has them

If the original says "235 people died", your version must still say "235 people died" — not "hundreds died".

Original tweet:
"{tweet}"

Write ONLY the rewritten tweet. Nothing else."""


def call_ai(prompt: str) -> str:
    """Try Gemini first, fall back to Groq if Gemini fails or hits limits."""

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

    if GROQ_AVAILABLE and groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1500,
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


def rewrite_tweet(original: str) -> str:
    return call_ai(REWRITE_PROMPT.format(tweet=original))
