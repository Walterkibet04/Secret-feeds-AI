import os
import time
import logging
from itertools import cycle
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── GEMINI SETUP (5 keys, round-robin) ───────────────────────────────────────
try:
    from google import genai as google_genai
    GEMINI_MODEL = "gemini-3.5-flash"

    gemini_keys = [
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
        os.getenv("GEMINI_API_KEY_4"),
        os.getenv("GEMINI_API_KEY_5"),
    ]

    gemini_clients = [
        {"client": google_genai.Client(api_key=k), "label": f"Gemini key {i}"}
        for i, k in enumerate(gemini_keys, 1) if k
    ]

    GEMINI_AVAILABLE = len(gemini_clients) > 0
    gemini_cycle = cycle(gemini_clients) if GEMINI_AVAILABLE else None

    if GEMINI_AVAILABLE:
        log.info(f"✅ Gemini ready — {len(gemini_clients)} key(s), round-robin, model: {GEMINI_MODEL}")
except Exception as e:
    GEMINI_AVAILABLE = False
    gemini_clients = []
    gemini_cycle = None
    log.warning(f"⚠️  Gemini not available: {e}")

# ── GROQ SETUP (5 keys, round-robin) ─────────────────────────────────────────
try:
    from groq import Groq

    groq_keys = [
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
        os.getenv("GROQ_API_KEY_4"),
        os.getenv("GROQ_API_KEY_5"),
    ]

    groq_clients = [
        {"client": Groq(api_key=k), "label": f"Groq key {i}"}
        for i, k in enumerate(groq_keys, 1) if k
    ]

    GROQ_AVAILABLE = len(groq_clients) > 0
    groq_cycle = cycle(groq_clients) if GROQ_AVAILABLE else None

    if GROQ_AVAILABLE:
        log.info(f"✅ Groq ready — {len(groq_clients)} key(s), round-robin")
except Exception as e:
    GROQ_AVAILABLE = False
    groq_clients = []
    groq_cycle = None
    log.warning(f"⚠️  Groq not available: {e}")

# ── PROMPTS ───────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You write for Secret Feeds, a neutral global news account on X reporting like AP, Reuters, or BBC.
Professional, factual, clear. Never vague. Never take sides. Short sentences. Active voice."""

REWRITE_PROMPT = """You are helping rewrite a tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Make the tweet look original to X's algorithm without changing what it says.

STRICT RULES:
1. Keep EVERY fact, number, name, and date exactly the same
2. Do NOT add new information
3. Do NOT remove any information
4. Do NOT change the meaning even slightly
5. Write as a neutral news reporter — REPORTING what others said or did, not speaking for them
6. If the original contains a quote or statement from a person/organization, frame it as their statement — attributed to THEM
7. Use correct grammar and professional news agency style (AP, Reuters, BBC)
8. Just rearrange the sentence structure and swap words with professional synonyms
9. Keep it under 4000 characters (X Premium account)
10. Do NOT add hashtags or emojis unless the original has them
11. Do NOT wrap the output in quotes — write the tweet text directly
12. Keep the same tense as the original
13. Never sound like you are taking a side or speaking on behalf of the source

Original tweet:
"{tweet}"

Write ONLY the rewritten tweet. No quotes around it. No explanation."""

SUMMARISE_PROMPT = """You are writing a summary tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Summarise the content into a punchy tweet AND rewrite it in your own words — do not copy the original wording.

STRICT RULES:
1. Keep ALL key facts, numbers, names, and dates — do not change or lose any
2. REWRITE completely in your own words — do not copy phrases or sentence structure from the original
3. Professional news agency style — formal, factual, neutral (AP, Reuters, BBC)
4. Report as a neutral observer — never take sides
5. Attribute quotes and statements clearly to their source
6. Lead with the most important fact
7. Keep it under 4000 characters (X Premium account)
8. Do NOT add hashtags or emojis unless the original has them
9. Do NOT wrap output in quotes — write the tweet text directly
10. Pick the 3-5 most important facts if content is very long
11. Use correct grammar and spelling
12. Never copy more than 3 consecutive words from the original

Content to summarise:
"{content}"

Write ONLY the summary tweet. No quotes around it. No explanation."""

HEADLINE_PROMPT = """You are writing a breaking news headline tweet for Secret Feeds, a global news account on X.

GOAL: Turn the content into a short, punchy breaking news style tweet — like DiscloseTV, Breaking911, or BNO News.

STRICT RULES:
1. Keep the key facts — who, what, where
2. Very short — ideally under 100 characters, maximum 280
3. Use relevant country flag emojis at the start if countries are involved (e.g. 🇺🇸🇮🇷)
4. Breaking news style — strip to the core news
5. Do NOT add hashtags
6. Do NOT wrap in quotes
7. Present tense or simple past — keep it punchy
8. If original starts with "JUST IN:" keep it

Examples:
- "🇺🇸🇮🇷 US launches new wave of strikes against Iran"
- "🇷🇺🇺🇦 Russia fires 47 drones at Kyiv overnight"
- "🇻🇪 Venezuela earthquake death toll rises to 310"

Content:
"{content}"

Write ONLY the headline tweet. No explanation."""


# ── ROUND-ROBIN AI CALLER ─────────────────────────────────────────────────────
def call_ai(prompt: str) -> str:
    """
    Round-robin rotation:
    - Each request picks the NEXT Gemini key in sequence
    - If that key fails (429/error), falls back to the next Groq key in sequence
    - Keys cycle evenly — no key is overloaded
    """

    # Pick next Gemini key (round-robin)
    if GEMINI_AVAILABLE and gemini_cycle:
        entry = next(gemini_cycle)
        label = entry["label"]
        try:
            response = entry["client"].models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
            log.info(f"  ✅ {label}")
            return response.text.strip()
        except Exception as e:
            err = str(e)
            log.warning(f"⚠️  {label} failed ({err[:60]}) — falling back to Groq")

    # Pick next Groq key (round-robin) as fallback
    if GROQ_AVAILABLE and groq_cycle:
        entry = next(groq_cycle)
        label = entry["label"]
        try:
            response = entry["client"].chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ],
            )
            log.info(f"  ✅ {label} (fallback)")
            return response.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"⚠️  {label} also failed: {e}")

    raise RuntimeError("All AI keys failed. Try again in a few minutes.")


def rewrite_tweet(original: str) -> str:
    return call_ai(REWRITE_PROMPT.format(tweet=original))

def summarise_content(content: str) -> str:
    return call_ai(SUMMARISE_PROMPT.format(content=content))

def make_headline(content: str) -> str:
    return call_ai(HEADLINE_PROMPT.format(content=content))
