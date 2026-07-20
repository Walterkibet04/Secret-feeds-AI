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
SYSTEM_PROMPT = """You are a senior news editor for Secret Feeds, a neutral global wire service (like AP, Reuters, or BBC). 
Your specialty is taking wire reports and completely restructuring them into original, punchy, AP-style breaking news posts for X while preserving 100% of the facts."""

REWRITE_PROMPT = """Rewrite the following news tweet into an entirely fresh, original reporting format for X.

GOAL: Maximally alter the sentence order, clause structure, and phrasing to prevent algorithmic duplication flags while maintaining absolute factual accuracy.

STRICT ACCURACY RULES:
1. Preserve 100% of all numbers, names, locations, dates, and core facts.
2. Maintain exact semantic meaning and tense — zero factual additions, omissions, or side-taking.
3. Consistently frame claims or statements with neutral attribution (e.g., "according to," "officials reported," "stated").

RESTRUCTURING & ANTI-DUPLICATION RULES:
1. INVERT THE STRUCTURE: If the original starts with [Who did What], begin your version with [Where/Why/The Result], or vice-versa.
2. TRANSFORM CLAUSES: Convert active clauses to passive (or passive to active) where natural. Shift direct quotes into indirect attributions.
3. SYNONYM REPLACEMENT: Replace key non-proper nouns and verbs with strong, professional newsroom synonyms.
4. FORMATTING: 
   - Add relevant flag emojis (e.g., 🇺🇸 🇮🇷) at the start ONLY if specific nations are central to the report.
   - Do NOT add external hashtags or decorative emojis.
   - Do NOT wrap output in quotation marks or provide commentary.
   - Length limit: 4,000 characters.

EXAMPLES OF BAD vs. GOOD RESTRUCTURING:

Original: "The UN announced today that over 100,000 people have fled the region following heavy shelling on Monday."
BAD (Too close): "The United Nations announced today that more than 100,000 residents fled the area after heavy shelling on Monday."
GOOD (Fully restructured): "Heavy shelling on Monday has displaced more than 100,000 people from the region, according to a UN announcement on Tuesday."

Original tweet to rewrite:
"{tweet}"

Output ONLY the rewritten text:"""

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

GOAL: Turn the content into a short, punchy breaking news headline — AND rewrite it enough that it does not look like a copy of the original.

STRICT RULES:
1. Keep the key facts — who, what, where
2. Short — ideally under 100 characters, maximum 280
3. Use relevant country flag emojis at the start if countries are involved (e.g. 🇺🇸🇮🇷)
4. Breaking news style — strip to the core news
5. Do NOT add hashtags
6. Do NOT wrap in quotes
7. Keep the same tense as the original
8. If original starts with "JUST IN:" keep it
9. REWRITE the wording — do not just swap one word. Change the sentence structure completely
10. Never use the same verb as the original (e.g. if original says "strikes", use "attacks", "targets", "bombs", "launches assault on" etc.)
11: Use relevant country flag emojis before if countries are involved (e.g. 🇺🇸🇮🇷)

Examples of good rewriting:
- Original: "🇮🇷🇺🇸 Iran strikes US military fuel terminal in Kuwait"
- Good: "🇮🇷🇺🇸 Iranian forces target US fuel depot in Kuwait" ✅
- Good: "🇮🇷🇺🇸 Kuwait: Iran attacks American military fuel site" ✅
- Bad: "🇮🇷🇺🇸 Iran hits US military fuel terminal in Kuwait" ❌ (too similar)

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
