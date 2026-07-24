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

REWRITE_PROMPT = """You are helping create a post for Secret Feeds, a global news and geopolitics account on X.

FIRST — detect what type of input this is:

TYPE A — DIRECT QUOTE: The tweet contains someone's exact words in quotation marks, or is clearly attributed as a direct quote (e.g. 'Rubio: "Our policy is an eye for an eye"')
TYPE B — NEWS FACT/STATEMENT: The tweet is a news statement, headline, or paraphrase (e.g. 'US strikes Iranian bases in Jordan')

RULES FOR TYPE A (Direct Quote):
1. Keep the quote EXACTLY as written — do not change a single word inside the quotation marks
2. Keep the attribution exactly (e.g. "Rubio:" stays "Rubio:")
3. Add 1-3 sentences of Secret Feeds commentary below the quote
4. End with a short question to drive replies
5. Use flag emojis at the start if countries are involved

RULES FOR TYPE B (News Fact/Statement):
1. Rewrite the fact completely in your own words — different structure, different verbs
2. Keep all facts, numbers, names, and dates exactly the same
3. Use active voice and present/active tense — never passive past
4. Wrong: "Sirens were activated" ❌ Right: "Sirens blare across the city" ✅
5. Wrong: "An officer was killed" ❌ Right: "US strikes kill Iranian officer" ✅
6. Add 2-3 sentences of Secret Feeds commentary below
7. End with a short question to drive replies
8. Use flag emojis at the start if countries are involved

COMMENTARY STYLE (for both types):
- Sharp, geopolitically aware, informed
- Add context: what led to this, why it matters, historical parallel, or what happens next
- Neutral — do not take sides but highlight significance
- Never more than 3 sentences of commentary
- Question at the end should spark genuine debate

GENERAL RULES:
- No hashtags
- Do NOT wrap output in quotes
- Keep total post under 4000 characters (X Premium)
- Write as Secret Feeds, not as the original source

Examples:

TYPE A example:
Input: Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."
Output:
🇺🇸🇮🇷 Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."

The sharpest public warning from a US official since the conflict began. This is no longer diplomatic language — it is a policy statement. Washington is signalling that every Iranian strike will be met with equal or greater force.

Where does this leave the possibility of a negotiated ceasefire?

TYPE B example:
Input: Sirens sounded in Bahrain
Output:
🇧🇭 Air raid sirens blare across Bahrain.

A nation hosting the US Navy's 5th Fleet is now inside the conflict's reach. If Bahrain is being targeted, the war has expanded well beyond Iran's immediate neighbours — and US naval assets are now directly in the crosshairs.

Is this an escalation or a warning shot?

Tweet:
"{tweet}"

Write ONLY the post. No explanation. No labels."""

THREAD_PROMPT = """You are helping create a 2-post thread for Secret Feeds, a global news and geopolitics account on X.

GOAL: Generate a thread that gets maximum algorithmic push — X favors threads for news topics.

FIRST — detect what type of input this is:
TYPE A — DIRECT QUOTE: Contains exact words in quotation marks or clearly attributed direct quote
TYPE B — NEWS FACT/STATEMENT: A news statement, headline, or paraphrase

POST 1 rules:
- TYPE A: Keep the quote EXACTLY as written, attribution intact. Add one short hook sentence. End with a question.
- TYPE B: Rewrite the fact in your own words (active voice, present tense). Add one short hook. End with a question.
- Keep Post 1 under 280 characters if possible
- Use flag emojis if countries are involved

POST 2 rules:
- Add deeper context: what led to this, historical parallel, implications, or what happens next
- 2-4 sentences max
- No emojis on Post 2
- No question needed — this is the analysis layer

GENERAL RULES:
- No hashtags
- Do NOT wrap in quotes
- Separate the two posts with exactly: ---THREAD---
- Do not label them "Post 1" or "Post 2"

Example output:

🇺🇸🇮🇷 Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."

This is Washington's clearest signal yet that retaliation is policy, not rhetoric. How does Iran respond?
---THREAD---
This statement follows the fifth consecutive night of US strikes on Iranian territory. Rubio is drawing a direct line — every Iranian action will be met with equal or greater force. The MOU that briefly paused hostilities is now officially dead. The question is whether Tehran escalates or signals a willingness to negotiate under pressure.

Tweet:
"{tweet}"

Write the two posts separated by ---THREAD--- only. No labels. No explanation."""

SUMMARISE_PROMPT = """You are writing a summary tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Condense the content into ONE short punchy tweet — not multiple paragraphs.

STRICT RULES:
1. OUTPUT must be a SINGLE TWEET — maximum 280 characters for the core message
2. Pick only the 2-3 most important facts — do not include everything
3. Lead with the biggest fact first
4. Rewrite completely in your own words — do not copy phrasing from the original
5. Never copy more than 3 consecutive words from the original
6. Professional news style — factual, neutral, clear
7. Attribute statements to their source (e.g. "per NYT", "Pentagon says")
8. Use relevant country flag emojis at the start if countries are involved
9. Do NOT add hashtags
10. Do NOT wrap in quotes
11. Do NOT write multiple paragraphs — one tweet only

Content to summarise:
"{content}"

Write ONLY the single summary tweet. No quotes around it. No explanation. No paragraphs."""

HEADLINE_PROMPT = """You are writing a breaking news headline tweet for Secret Feeds, a global news account on X.

GOAL: Turn the content into a short punchy headline AND rewrite it completely — never copy the original wording.

STRICT RULES:
1. Keep the key facts — who, what, where
2. Very short — ideally under 100 characters, maximum 280
3. Use relevant country flag emojis at the start if countries are involved
4. Do NOT add hashtags
5. Do NOT wrap in quotes
6. Keep nationalities correct — "Iranian" stays "Iranian", never substitute
7. MANDATORY REWRITE — change structure, verb, word order completely
8. Never copy more than 2 consecutive words from the original
9. Never use the same verb as the original
10. If original starts with "JUST IN:" keep it

Examples:
- Original: "Iranian ballistic missiles fly past Patriot interceptors and hit targets in Jordan"
  Good: "🇮🇷🇯🇴 Patriot defences fail to stop Iranian ballistic missiles striking Jordan" ✅
- Original: "🇮🇷🇺🇸 Iran strikes US military fuel terminal in Kuwait"
  Good: "🇮🇷🇺🇸 Iranian forces target US fuel depot in Kuwait" ✅

Content:
"{content}"

Write ONLY the headline tweet. No explanation."""


# ── ROUND-ROBIN AI CALLER ─────────────────────────────────────────────────────
def call_ai(prompt: str) -> str:
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
            log.warning(f"⚠️  {label} failed ({str(e)[:60]}) — falling back to Groq")

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


def rewrite_tweet(tweet: str) -> str:
    return call_ai(REWRITE_PROMPT.format(tweet=tweet))

def summarise_content(content: str) -> str:
    return call_ai(SUMMARISE_PROMPT.format(content=content))

def make_headline(content: str) -> str:
    return call_ai(HEADLINE_PROMPT.format(content=content))

def make_thread(tweet: str) -> str:
    return call_ai(THREAD_PROMPT.format(tweet=tweet))
