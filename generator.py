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

COMMENTARY_PROMPT = """You are helping create an original post for Secret Feeds, a global news and geopolitics account on X.

GOAL: Take the news tweet and turn it into a high-value post that X rewards — keep the original quote/fact, then add Secret Feeds commentary that makes it original.

FORMAT (always follow this structure):
Line 1: The original quote or fact — kept exactly as-is or as a direct attribution
Line 2-3: Your sharp commentary — context, analysis, implications, or historical parallel
Last line: A short question to spark replies (optional but recommended)

STRICT RULES:
1. ALWAYS keep the original quote or core fact on the first line — do not rewrite or paraphrase it
2. If it is a direct quote from an official, use attribution format: Name: "Quote"
3. Add 1-3 sentences of genuine insight below — what it means, why it matters, historical context, or what happens next
4. End with a question if it fits naturally — questions drive replies which boost the algorithm
5. Write in Secret Feeds voice — sharp, informed, geopolitically aware
6. Be neutral — do not take sides, but you can highlight significance
8. Keep total post under 4000 characters (X Premium)
9. Do NOT wrap anything in quotes except actual direct quotes from people

Examples of good output:

Example 1:
Original: "Sec. of State Marco Rubio: Our policy is a head for an eye. Iran will pay a heavy price."
Output:
Sec. of State Marco Rubio: "Our policy is a head for an eye. Iran will pay a heavy price."

The strongest public threat from a US official since the war began. This language signals military retaliation is no longer a warning — it is a policy.

What does this mean for the next 48 hours?

Example 2:
Original: "Sirens sounded in Bahrain"
Output:
🇧🇭 Sirens sound across Bahrain.

A small island nation hosting the US Navy's 5th Fleet. If Bahrain is being targeted, the conflict has expanded beyond Iran's immediate neighbours.

Is this an escalation or a warning shot?

Example 3:
Original: "Pentagon concealed Iranian attacks on US bases in Jordan — 16 killed, 400+ wounded"
Output:
🇺🇸🇯🇴🇮🇷 The Pentagon concealed multiple Iranian strikes on US bases in Jordan. 16 troops killed. 400+ wounded.

The public was kept in the dark for operational security — but the scale of casualties suggests this war is far deadlier than officially acknowledged.

What else aren't we being told?

News tweet:
"{tweet}"

Write ONLY the post. No explanation. No labels."""

SUMMARISE_PROMPT = """You are writing a summary tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Condense the content into ONE short, punchy tweet — not multiple paragraphs, not multiple sentences if avoidable. One tweet.

STRICT RULES:
1. OUTPUT must be a SINGLE TWEET — maximum 280 characters for the core message (up to 4000 if truly needed but always aim for under 280)
2. Pick only the 2-3 most important facts — do not include everything
3. Lead with the biggest fact first
4. Rewrite completely in your own words — do not copy phrasing from the original
5. Never copy more than 3 consecutive words from the original
6. Professional news style — factual, neutral, clear
7. Attribute statements to their source (e.g. "per NYT", "Pentagon says")
9. Do NOT add hashtags
10. Do NOT wrap in quotes

Example of good summarising:
Original: 3 paragraphs about Pentagon hiding Iranian attacks in Jordan that killed 16 and injured 400+
Good: "🇺🇸🇮🇷🇯🇴 Pentagon concealed multiple Iranian strikes on US bases in Jordan — 16 troops killed, 400+ wounded since Feb 28, per NYT." ✅
Bad: 3 reworded paragraphs that repeat all the details ❌

Content to summarise:
"{content}"

Write ONLY the single summary tweet. No quotes around it. No explanation. No paragraphs."""

HEADLINE_PROMPT = """You are writing a breaking news headline tweet for Secret Feeds, a global news account on X.

GOAL: Turn the content into a short punchy headline AND rewrite it completely — it must NEVER look like a copy of the original.

STRICT RULES:
1. Keep the key facts — who, what, where, numbers
2. Very short — ideally under 120 characters, maximum 280
3. Use relevant country flag emojis at the start if countries are involved (e.g. 🇺🇸🇮🇷)
4. Do NOT add hashtags
5. Do NOT wrap in quotes
6. Keep nationalities correct — "Iranian" stays "Iranian", never change to "Tehran's" or any substitute
7. MANDATORY REWRITE — you MUST change the sentence structure completely:
   - Change the verb (e.g. "strikes" → "targets", "hit" → "struck", "fly past" → "evade", "bypass")
   - Change the word order
   - Rephrase — never copy the original sentence as-is
8. Never copy more than 2 consecutive words from the original
9. If the original is already a short headline, still restructure it differently
10. If original starts with "JUST IN:" keep it

Rewriting examples:
- Original: "Iranian ballistic missiles fly past Patriot interceptors and hit targets in Jordan"
  Good: "🇮🇷🇯🇴 Iran's ballistic missiles evade Patriot defences, striking targets inside Jordan" ✅
  Good: "🇮🇷🇯🇴 Patriot missiles fail to intercept Iranian ballistic strikes over Jordan" ✅
  Bad: "Iranian ballistic missiles fly past Patriot interceptor missiles and hit their targets in Jordan" ❌ (identical)
  Bad: "Tehran's ballistic missiles fly past Patriot interceptors" ❌ (changed nationality word)

- Original: "🇮🇷🇺🇸 Iran strikes US military fuel terminal in Kuwait"
  Good: "🇮🇷🇺🇸 Iranian forces target US fuel depot in Kuwait" ✅
  Bad: "🇮🇷🇺🇸 Iran hits US military fuel terminal in Kuwait" ❌ (only one word changed)

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
