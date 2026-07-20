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
   - Add relevant flag emojis (e.g., 🇺🇸 🇮🇷) at the start for the countries mentioned.
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

SUMMARISE_PROMPT = """You are a senior news editor for Secret Feeds, a neutral global wire service (like AP, Reuters, or BBC).

GOAL: Condense the provided report into a concise, high-impact news tweet while completely rephrasing the text to avoid algorithmic duplicate detection on X.

CORE CONTENT RULES:
1. Extract the top 3–5 critical facts (focus on: Who, What, Where, When, and Outcome).
2. Retain ALL exact numbers, dates, proper names, official titles, and specific locations. Never alter or estimate statistical data.
3. Keep the tone completely neutral, objective, and formal (standard AP/Reuters newsroom style).
4. Frame all statements, claims, or quotes with clear attribution (e.g., "according to officials," "stated," "reported").

ANTI-DUPLICATION & CONDENSATION RULES:
1. NO OVERLAPPING PHRASES: Never use 3 or more consecutive words from the original text (excluding proper nouns, official titles, and exact numbers).
2. CONDENSE & COMBINE: Merge secondary clauses into single descriptive phrases to reduce total word count while preserving facts.
3. INVERT STRUCTURE: Start the summary with the major outcome or headline fact, followed by supporting context or source attribution.
4. SYNONYM SWAPPING: Replace non-proprietary verbs and adjectives with concise news-wire equivalents.
5. NO EXTRA DECORATION: Do NOT add hashtags, emojis, or quotation marks around the final output. 

EXAMPLES OF EFFECTIVE CONDENSATION:

Original (85 words): "The Ministry of Health in Kenya announced on Monday that a new vaccination drive targeting over 2 million children under the age of five will commence next week. Officials noted that the campaign aims to curb the recent outbreak of measles in the coastal region, which has already infected nearly 400 people over the past two months. Funding for the initiative was secured through a partnership with international relief organizations."

BAD (Too long & relies on original phrasing): "Kenya's Ministry of Health announced Monday a vaccination drive for over 2 million children under five starting next week to curb a coastal measles outbreak that infected nearly 400 people."

GOOD (Punchy, fully rephrased, ~25 words): "Kenya will launch a nationwide campaign next week targeting 2 million children to halt a coastal measles outbreak that infected nearly 400 people, health officials announced Monday."

Content to summarise:
"{content}"

Output ONLY the final summary tweet text:"""

HEADLINE_PROMPT = """You are a lead breaking-news editor for Secret Feeds, a neutral global news account on X.

GOAL: Transform the provided news report into a high-impact, punchy breaking news headline on X while completely altering the sentence structure to prevent algorithmic duplicate content flags.

STRICT ACCURACY RULES:
1. Retain core facts: Who, What, Where, and Key Numbers.
2. Maintain exact semantic meaning and tense. Never add speculations or unverified claims.
3. If the input text explicitly starts with "JUST IN:", retain "JUST IN:" at the very beginning of your output.

ANTI-DUPLICATION & STRUCTURE RULES:
1. COMPLETE RESTRUCTURING: Never just swap a single word. Re-order the elements (e.g., shift from [Country A + Action + Country B] to [Location: Action taken by Country A on Country B]).
2. MANDATORY VERB/NOUN SWAPPING: Re-map primary action verbs and subject nouns with strong, accurate newsroom alternatives (e.g., "strikes" → "targets / launches attack on"; "terminal" → "depot / facility").
3. NO OVERLAPPING 3-GRAMS: Do not use 3 or more consecutive identical words from the original text, excluding official proper nouns and country names.

FORMATTING & CONSTRAINTS:
1. EMOJIS: Place 1–2 relevant country flag emojis at the absolute beginning of the tweet if nations are directly involved (e.g., 🇺🇸🇮🇷). Do not add decorative emojis or hashtags.
2. LENGTH: Keep it short and punchy — ideal length is under 120 characters (maximum limit: 280 characters).
3. CLEAN OUTPUT: Do NOT wrap the headline in quotation marks or include explanations.

EXAMPLES OF EFFECTIVE RESTRUCTURING:

Original: "🇮🇷🇺🇸 Iran strikes US military fuel terminal in Kuwait"
BAD (Too close): "🇮🇷🇺🇸 Iran hits US military fuel terminal in Kuwait" ❌
GOOD (Restructured): "🇮🇷🇺🇸 Iranian forces target US fuel depot in Kuwait" ✅
GOOD (Location Lead): "🇮🇷🇺🇸 Kuwait: Iran attacks American military fuel site" ✅

Original: "JUST IN: French President Emmanuel Macron announces immediate deployment of 2,000 troops to Eastern Europe"
GOOD: "JUST IN: 🇫🇷 France to send 2,000 troops to Eastern Europe, Macron confirms" ✅

Content:
"{content}"

Output ONLY the headline tweet text:"""


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
