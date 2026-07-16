import os
import time
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

# ── GEMINI SETUP ──────────────────────────────────────────────────────────────
try:
    from google import genai as google_genai
    GEMINI_MODEL = "gemini-2.5-flash"

    gemini_key1 = os.getenv("GEMINI_API_KEY")
    gemini_key2 = os.getenv("GEMINI_API_KEY_2")

    gemini_clients = []
    if gemini_key1:
        gemini_clients.append(google_genai.Client(api_key=gemini_key1))
    if gemini_key2:
        gemini_clients.append(google_genai.Client(api_key=gemini_key2))

    GEMINI_AVAILABLE = len(gemini_clients) > 0
    if GEMINI_AVAILABLE:
        log.info(f"✅ Gemini ready — {len(gemini_clients)} key(s) loaded, model: {GEMINI_MODEL}")
except Exception as e:
    GEMINI_AVAILABLE = False
    gemini_clients = []
    log.warning(f"⚠️  Gemini not available: {e}")

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
Must NOT sound copy-pasted or AI-generated. Never wrap output in quotation marks."""

REWRITE_PROMPT = """You are helping rewrite a tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Make the tweet look original to X's algorithm without changing what it says.

STRICT RULES:
1. Keep EVERY fact, number, name, and date exactly the same
2. Do NOT change the meaning even slightly
3. Write as a neutral news reporter — you are REPORTING what others said or did, not speaking for them
4. If the original contains a quote or statement from a person/organization, frame it clearly as their statement — use "says", "states", "announces", "condemns" attributed to THEM, not as your own view
5. Use correct grammar and professional news agency style (AP, Reuters, BBC)
6. Just rearrange the sentence structure and swap words with professional synonyms
7. Keep it under 4000 characters (X Premium account)
8. Do NOT add hashtags or emojis unless the original has them
9. Do NOT wrap the output in quotes — write the tweet text directly
10. Keep the same tense as the original
11. Never sound like you are taking a side or speaking on behalf of the source
12. You can summarize long tweets 

Attribution examples:
- Original: Iranian army: "We condemn X" → Rewrite: "Iran's military has condemned X, calling it..." ✅
- Wrong: "We strongly condemn X" or "Iran condemns X" without attribution ❌
- Original: "Russia says troops have withdrawn" → Rewrite: "Russian officials report that troops have pulled back" ✅

Original tweet:
"{tweet}"

Write ONLY the rewritten tweet. No quotes around it. No explanation."""


def call_ai(prompt: str) -> str:
    """Try each Gemini key in turn, then fall back to Groq."""

    if GEMINI_AVAILABLE and gemini_clients:
        for key_index, client in enumerate(gemini_clients):
            key_label = f"Gemini key {key_index + 1}"
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=prompt
                    )
                    log.info(f"  ✅ {key_label} succeeded")
                    return response.text.strip()
                except Exception as e:
                    err = str(e)
                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        if attempt == 0:
                            log.warning(f"⚠️  {key_label} 429 — retrying in 10s")
                            time.sleep(10)
                            continue
                        else:
                            log.warning(f"⚠️  {key_label} 429 again — trying next key")
                            break
                    else:
                        log.warning(f"⚠️  {key_label} error — trying next key: {err[:80]}")
                        break

    if GROQ_AVAILABLE and groq_client:
        for attempt in range(2):
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
                err = str(e)
                if "429" in err and attempt == 0:
                    log.warning("⚠️  Groq 429 — retrying in 60s")
                    time.sleep(60)
                    continue
                log.error(f"Groq failed: {e}")
                break

    raise RuntimeError("All AI keys exhausted. Try again in a few minutes.")


def rewrite_tweet(original: str) -> str:
    return call_ai(REWRITE_PROMPT.format(tweet=original))

