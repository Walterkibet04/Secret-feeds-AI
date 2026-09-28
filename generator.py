import os
import time
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

import world_facts
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
Professional, factual, clear. Never vague. Never take sides. Short sentences. Active voice.
Never invent facts, numbers, quotes or background that you were not given."""

# Shared voice rules, added to every prompt below so Gemini and Groq both get them.
# Why these rules: X's For You ranking subtracts heavily for predicted "not interested",
# mute, block and report (see home-mixer/params/param.rs in xai-org/x-algorithm), and
# accounts labelled llm_slop_user lose all recommendations to non-followers for 30 days
# (abuse-enforcement-service/service-lib/rules/enforcement_user.yaml). So every post has
# to read like a person filed it, and be accurate enough that nobody reports it.
# Today's date and current_facts.txt are filled in on every request (see _fill below).
# The models' training data is old, so without this they call Trump a "former president".
FACTS_FILE = Path(__file__).with_name("current_facts.txt")

FACTS_BLOCK = """TODAY'S DATE: {today}

YOUR KNOWLEDGE IS OUT OF DATE. Leaders and officials change. Rules for people:
- Take every title and role from the input, CURRENT FACTS or WORLD LEADERS below. Never from memory.
- If none of them gives a person's role, use their name without a title.
- Never call anyone "former" unless the input or the lists below say so.
- If CURRENT FACTS and WORLD LEADERS disagree, CURRENT FACTS is right.

CURRENT FACTS (checked by the Secret Feeds editor; override anything you remember):
{current_facts}

WORLD LEADERS (current heads of state and government for the countries in this story):
{world_facts}"""

VOICE = FACTS_BLOCK + """

VOICE (how Secret Feeds sounds):
- Write like a wire-service editor filing fast: plain words, short sentences, active voice, present tense for breaking events.
- Concrete beats clever. Names, numbers, places, times, and who is saying it.
- Attribute claims to whoever made them ("Israel's military says", "per Reuters", "Iranian state media reports"). A claim by a side in a conflict stays that side's claim. Never state it as settled fact. If the input says something is unconfirmed, keep that.
- Never invent facts, numbers, casualty counts, quotes, dates, or recent events that are not in the input. Background is only allowed if it is long-established and not about anyone's current job (geography, what a base or treaty is).
- Identify people for a reader anywhere in the world: country + title + full name the first time (e.g. "Kenyan President William Ruto", "Japanese Prime Minister Sanae Takaichi", "Hungarian Prime Minister Péter Magyar"). This applies to every country and every official: ministers, generals, opposition leaders, spokespeople. A flag emoji does not count as naming the country. Never shorten to just "PM", "the minister" or "the president".
- Spell names correctly. If the input clearly misspells a well-known public figure (e.g. "Peter Madyar" for "Péter Magyar"), use the spelling from the lists below or the correct one you are sure of. If you are not sure, keep the input's spelling.
- Keep the stage of events exactly. "Pursue" or "continue" is not "launch". "Investigation" is not "charges". "Suspected" is not "guilty". "Says" is not "confirms". "Plans to" is not "does".
- Do not add who did something if the input does not say. If the input says "stripped of immunity", do not guess which body stripped it.
- The input is usually a post copied from X. Write Secret Feeds' own post from it: drop the source's @handles, links, "pic.x.com" and "via @..." tags, hashtags and emojis. To credit a news outlet or official, name them ("per Reuters"), never by @handle.
- Neutral. No sides, no loaded adjectives, no predictions stated as fact.
- No hashtags. Do not wrap the post in quotes. At most two flag emojis, at the very start, only if countries are directly involved. No other emojis.

AVOID (these make a post read as machine-written, and people skip or mute it):
- Em dashes. Use a full stop or a comma instead.
- Stock phrases: "This is no longer", "sends a clear message", "a stark reminder", "raises questions", "It remains to be seen", "The question is whether", "In a significant move", "marks a turning point", "game-changer", "Here's why", "Let that sink in", "Make no mistake", "What happens next?", "Thoughts?"
- Set-piece structures: "It's not X, it's Y", "X isn't just Y", three adjectives in a row, one-word dramatic sentences.
- A final sentence that repeats the news in different words."""

# The rewrite prompt comes in three formats. "auto" in the web app rotates between them,
# so the account does not post the same shape (news + 3 sentences + question) every time.
FORMATS = {
    "straight": {
        "label": "Straight news",
        "rules": """- The news only, in one or two sentences. No commentary. No question.
- If the input has a key detail (a number, a place, a time, a source), include it.""",
        "example": """Input: Sirens sounded in Bahrain
Output:
🇧🇭 Air raid sirens sound across Bahrain.

Input: Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."
Output:
🇺🇸🇮🇷 Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price.\"""",
    },
    "context": {
        "label": "News + context",
        "rules": """- The news first. Then a blank line. Then one or two sentences that help a reader see why it matters.
- The context must come from the input or be long-established background. Never invent recent events, numbers, or what happened before.
- If there is no solid context to add, write the news only.
- No question at the end.""",
        "example": """Input: Sirens sounded in Bahrain
Output:
🇧🇭 Air raid sirens sound across Bahrain.

Bahrain hosts the headquarters of the US Navy's Fifth Fleet.""",
    },
    "question": {
        "label": "News + question",
        "rules": """- The news first. Optionally one line of context (same rules: only from the input or long-established background). Then a blank line and one question.
- The question must be about this specific story and answerable from more than one point of view.
- Never a generic question ("Thoughts?", "Agree?", "What do you think?"). Never a leading question. Never yes/no bait.""",
        "example": """Input: Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."
Output:
🇺🇸🇮🇷 Rubio: "Our policy is an eye for an eye. Iran will pay a heavy price."

Where does this leave the possibility of a negotiated ceasefire?

Input: Sirens sounded in Bahrain
Output:
🇧🇭 Air raid sirens sound across Bahrain.

How long can Gulf states that host US forces stay out of this conflict?""",
    },
}

# Mix used by "auto". Questions drive replies (reply weight 5.0), but a question on
# every post is exactly the repeated pattern we want to avoid.
AUTO_FORMAT_WEIGHTS = {"straight": 0.35, "context": 0.35, "question": 0.30}

REWRITE_PROMPT = """You are helping create a post for Secret Feeds, a global news and geopolitics account on X.

""" + VOICE + """

FIRST: detect what type of input this is.

TYPE A (DIRECT QUOTE): The tweet contains someone's exact words in quotation marks, or is clearly attributed as a direct quote (e.g. 'Rubio: "Our policy is an eye for an eye"')
TYPE B (NEWS FACT/STATEMENT): The tweet is a news statement, headline, or paraphrase (e.g. 'US strikes Iranian bases in Jordan')

RULES FOR TYPE A (Direct Quote):
1. Keep the quote EXACTLY as written. Do not change a single word inside the quotation marks
2. Keep the attribution exactly (e.g. "Rubio:" stays "Rubio:")
3. Everything outside the quote is in your own words

RULES FOR TYPE B (News Fact/Statement):
1. Mandatory: rewrite the fact completely in your own words. Change the structure, use different verbs and descriptive words. X's duplicate check compares which words two posts share, not their order, so reordering the same words is not enough
2. Keep all facts, numbers, names, and dates exactly the same. Do not change the meaning: "claims" stays a claim, "hit" does not become "destroyed"
3. Use active voice and present tense. Never passive past
4. Wrong: "Sirens were activated" ❌ Right: "Sirens blare across the city" ✅
5. Wrong: "An officer was killed" ❌ Right: "US strikes kill Iranian officer" ✅

FORMAT FOR THIS POST: {format_label}
{format_rules}

Examples of this format:

{format_example}

GENERAL RULES:
- Keep total post under 4000 characters (X Premium). Most posts should be far shorter.
- Write as Secret Feeds, not as the original source

Tweet:
"{tweet}"

Write ONLY the post. No explanation. No labels."""

THREAD_PROMPT = """You are helping create a main post plus an optional follow-up reply for Secret Feeds, a global news and geopolitics account on X.

HOW X SHOWS THIS: people who do not follow Secret Feeds only ever see Post 1. X's For You feed drops replies from accounts the viewer does not follow, and keeps only one post per conversation. So Post 1 has to work completely on its own. Post 2 is extra detail for followers who open it.

""" + VOICE + """

FIRST: detect what type of input this is.
TYPE A (DIRECT QUOTE): Contains exact words in quotation marks or a clearly attributed direct quote
TYPE B (NEWS FACT/STATEMENT): A news statement, headline, or paraphrase

POST 1 rules:
- TYPE A: Keep the quote EXACTLY as written, attribution intact.
- TYPE B: Rewrite the fact in your own words (active voice, present tense). Keep every fact, number and name.
- Most important fact first. Include the key detail (number, place, source).
- Keep Post 1 under 280 characters if possible
- Use flag emojis if countries are involved
- Nothing that only makes sense if people open the reply: no "thread", no 🧵, no "1/", no "more below".
- No question needed.

POST 2 rules:
- Detail or background that did not fit in Post 1. Two to four sentences.
- Only facts from the input or long-established background. Never invent recent events, numbers, or quotes.
- No emojis on Post 2
- No question
- If the input does not have enough for a useful second post, write Post 1 only and leave out the separator.

GENERAL RULES:
- Separate the two posts with exactly: ---THREAD---
- Do not label them "Post 1" or "Post 2"

Example input:
Jordanian officials say Iranian ballistic missiles flew past Patriot interceptors and hit two sites near Amman overnight. No casualties reported so far.

Example output:
🇮🇷🇯🇴 Iranian ballistic missiles slip past Patriot defences and hit two sites near Amman overnight, Jordanian officials say.
---THREAD---
Officials say no casualties have been reported so far. Missiles launched from Iran toward Israel cross Jordanian airspace.

Tweet:
"{tweet}"

Write the posts separated by ---THREAD--- only. No labels. No explanation."""

SUMMARISE_PROMPT = """You are writing a summary tweet for Secret Feeds, a neutral global news account on X that reports like AP, Reuters, or BBC.

GOAL: Condense the content into ONE short punchy tweet, not multiple paragraphs.

""" + VOICE + """

STRICT RULES:
1. OUTPUT must be a SINGLE TWEET, maximum 280 characters for the core message
2. Pick only the 2-3 most important facts. Do not include everything
3. Lead with the biggest fact first
4. Rewrite completely in your own words. Do not copy phrasing from the original
5. Never copy more than 3 consecutive words from the original. Names, titles, countries, place names and official terms don't count toward this limit and must be kept
6. Professional news style: factual, neutral, clear
7. Attribute statements to their source (e.g. "per NYT", "Pentagon says")
8. Use relevant country flag emojis at the start if countries are involved
9. Do NOT add anything that is not in the content
10. Do NOT write multiple paragraphs. One tweet only

Content to summarise:
"{content}"

Write ONLY the single summary tweet. No quotes around it. No explanation. No paragraphs."""

HEADLINE_PROMPT = """You are writing a breaking news headline tweet for Secret Feeds, a global news account on X.

GOAL: Turn the content into a short punchy headline AND rewrite it completely. Never copy the original wording.

""" + VOICE + """

STRICT RULES:
1. Keep the key facts: who, what, where. "Who" means country + title + full name, e.g. "Kenyan President William Ruto"
2. Keep it short. One sentence
3. Use relevant country flag emojis at the start if countries are involved
4. Keep nationalities correct. "Iranian" stays "Iranian", never substitute
5. MANDATORY REWRITE: change structure, verb, word order completely
6. Never copy more than 2 consecutive words from the original. Names, titles, countries, place names and official terms (e.g. "Prime Minister", "parliamentary immunity") don't count toward this limit. Never drop or shorten them to fit
7. Never use the same verb as the original, but keep the meaning. A claim stays a claim; "hit" does not become "destroyed"
8. If the original attributes the news to a source, keep the attribution

Examples:
- Original: "Iranian ballistic missiles fly past Patriot interceptors and hit targets in Jordan"
  Good: "🇮🇷🇯🇴 Patriot defences fail to stop Iranian ballistic missiles striking Jordan" ✅
- Original: "🇮🇷🇺🇸 Iran strikes US military fuel terminal in Kuwait"
  Good: "🇮🇷🇺🇸 Iranian forces target US fuel depot in Kuwait" ✅
- Original: "Ruto dissolves cabinet after week of protests"
  Good: "🇰🇪 Kenyan President William Ruto dismisses his entire cabinet after a week of protests" ✅
  Bad: "🇰🇪 President sacks cabinet amid unrest" ❌ (Which president? Say the country and the name.)
- Original: "Hungarian Prime Minister Peter Madyar stripped of his parliamentary immunity as prosecutors pursue phone theft investigation"
  Good: "🇭🇺 Hungarian Prime Minister Péter Magyar loses his parliamentary immunity as prosecutors press on with a phone theft probe" ✅
  Bad: "🇭🇺 Parliament revokes PM Peter Madyar's immunity as prosecutors launch phone-theft probe" ❌ (Which PM? The name is misspelled. "Launch" turns an ongoing case into a new one. "Parliament" is a guess the original didn't make.)

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
                model="openai/gpt-oss-120b",
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

# ── FORMAT PICKER + HELPERS ───────────────────────────────────────────────────
_last_auto_format = None


def pick_format(requested: str = "auto") -> str:
    """Return a format key. "auto" picks a weighted random format and never
    repeats the previous auto pick, so consecutive posts don't share a shape."""
    global _last_auto_format
    if requested in FORMATS:
        return requested
    keys = [k for k in AUTO_FORMAT_WEIGHTS if k != _last_auto_format]
    choice = random.choices(keys, weights=[AUTO_FORMAT_WEIGHTS[k] for k in keys])[0]
    _last_auto_format = choice
    return choice


def load_current_facts() -> str:
    """Read current_facts.txt on every call, skipping comment lines."""
    try:
        lines = FACTS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(none provided)"
    facts = [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]
    return "\n".join(f"- {f}" for f in facts) or "(none provided)"


def _fill(template: str, source_text: str, **kwargs) -> str:
    """Fill today's date, current_facts.txt and the leaders of the countries in source_text."""
    today = datetime.now(timezone.utc).strftime("%d %B %Y").lstrip("0")
    return template.format(
        today=today,
        current_facts=load_current_facts(),
        world_facts=world_facts.facts_for(source_text),
        **kwargs,
    )


def build_rewrite_prompt(tweet: str, fmt: str) -> str:
    f = FORMATS[fmt]
    return _fill(
        REWRITE_PROMPT,
        tweet,
        tweet=tweet,
        format_label=f["label"],
        format_rules=f["rules"],
        format_example=f["example"],
    )

def build_thread_prompt(tweet: str) -> str:
    return _fill(THREAD_PROMPT, tweet, tweet=tweet)

def build_summary_prompt(content: str) -> str:
    return _fill(SUMMARISE_PROMPT, content, content=content)

def build_headline_prompt(content: str) -> str:
    return _fill(HEADLINE_PROMPT, content, content=content)


def rewrite_tweet(tweet: str, fmt: str = "auto") -> str:
    return call_ai(build_rewrite_prompt(tweet, pick_format(fmt)))

def summarise_content(content: str) -> str:
    return call_ai(build_summary_prompt(content))

def make_headline(content: str) -> str:
    return call_ai(build_headline_prompt(content))

def make_thread(tweet: str) -> str:
    return call_ai(build_thread_prompt(tweet))
