"""Secret Feeds: find who is speaking in a pasted post, and their exact words.

The AI prompt is SPEAKER_PROMPT in generator.py; the /speaker route is in web.py.

The rule this file enforces: a quote card only shows words in quote marks if those
words appear, word for word, in the text you pasted. The AI picks the speaker and the
best passage; it never supplies the words. Every quote it returns is checked against
your text here, and anything that doesn't match is thrown away.

A headline like "Zelensky says Russia fired North Korean missiles..." is a journalist's
summary, so it has no exact words to take. In that case you get a reported line (no
quote marks) and links to find the speaker's own post.
"""
import json
import logging
import re
import unicodedata

log = logging.getLogger(__name__)

MAX_TEXT = 6000
MIN_QUOTE_WORDS = 4
MAX_OPTIONS = 5

# Opening/closing pairs used for quotations in English-language news.
# Straight and curly single quotes need extra care because they double as apostrophes.
_QUOTE_PATTERNS = [
    re.compile(r"“([^”]+)”"),
    re.compile(r"„([^“”]+)[“”]"),
    re.compile(r"«\s*([^»]+?)\s*»"),
    re.compile(r'"([^"]+)"'),
    re.compile(r"(?<![\w’'])‘(.+?)’(?![\w])", re.S),
    re.compile(r"(?<![\w'’])'(.+?)'(?![\w])", re.S),
]

_STOP = set("""a an and are as at be been but by for from had has have he her his i if in into is it its
of on or our over says said say she so than that the their them they this to was we were what when where
which who will with would you your about after against amid also any before being between both can could
did does during each just more most new not now off only other out over own same should some such then
there these those through under until very while why how all says told tells claims claimed warned warns
added accused accuses""".split())


# ── text helpers ─────────────────────────────────────────────────────────────
_CHAR_MAP = {
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "‚": "'",
    "–": "-", "—": "-", "‑": "-", "−": "-", " ": " ", " ": " ",
}


def _normalise_with_map(text):
    """Return (normalised, index_map). index_map[i] is the position in `text` of normalised char i.

    Normalising: NFKC, curly quotes to straight, dashes to '-', runs of whitespace to one space,
    lower case. Lets the AI's copy match even if it straightened a quote mark or a dash.
    """
    out, index = [], []
    prev_space = True
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", _CHAR_MAP.get(ch, ch)):
            if c.isspace():
                if prev_space:
                    continue
                c, prev_space = " ", True
            else:
                prev_space = False
            out.append(c.lower())
            index.append(i)
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def _trim_quote(q):
    """Strip the quote marks, ellipses and spaces the AI may wrap around a passage."""
    q = (q or "").strip()
    q = re.sub(r"^[\s\"'“”‘’«»„]+|[\s\"'“”‘’«»„]+$", "", q)
    q = re.sub(r"^(?:\.\.\.|…)\s*|\s*(?:\.\.\.|…)$", "", q)
    return q.strip()


def words(s):
    return re.findall(r"[\w’']+", s or "")


def find_quoted_spans(text):
    """Every passage of 4+ words inside quotation marks, as (start, end, exact_text), in order."""
    spans = []
    for pat in _QUOTE_PATTERNS:
        for m in pat.finditer(text):
            inner = m.group(1).strip()
            if len(words(inner)) < MIN_QUOTE_WORDS:
                continue
            s, e = m.start(1), m.end(1)
            if any(s < e2 and s2 < e for s2, e2, _ in spans):   # overlaps one already found
                continue
            spans.append((s, e, text[s:e].strip()))
    spans.sort()
    return spans


def verify_quote(candidate, text, own_words=False):
    """Return the exact passage from `text` that `candidate` copies, or '' if it isn't there.

    The returned string is cut from your text (original spelling, case and punctuation), so
    the card shows what was really written even if the AI changed a quote mark.
    If own_words is False, the passage must also sit inside quotation marks in your text:
    words outside quote marks were written by a reporter, not said by the speaker.
    """
    cand = _trim_quote(candidate)
    if len(words(cand)) < MIN_QUOTE_WORDS:
        return ""
    norm_text, index = _normalise_with_map(text)
    norm_cand, _ = _normalise_with_map(cand)
    pos = norm_text.find(norm_cand)
    if pos < 0 or not norm_cand:
        return ""
    start, end = index[pos], index[pos + len(norm_cand) - 1] + 1
    if not own_words:
        inside = any(s <= start and end <= e for s, e, _ in find_quoted_spans(text))
        if not inside:
            return ""
    return text[start:end].strip()


def search_terms(text, speaker="", limit=6):
    """The story's key words, in order, for a news search that finds the speaker's statement."""
    skip = {w.lower() for w in words(speaker)}
    seen, terms = set(), []
    for w in words(text):
        lw = w.lower().strip("'’")
        if len(lw) < 3 or lw in _STOP or lw in skip or lw in seen or lw.isdigit():
            continue
        seen.add(lw)
        terms.append(w.strip("'’"))
    return terms[:limit]


# ── the AI reply ─────────────────────────────────────────────────────────────
def parse_reply(reply):
    """Pull the JSON object out of the AI's reply. Tolerates code fences and chatter around it."""
    if not reply:
        return {}
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(data.get(k) or "").strip() for k in ("speaker", "role", "where", "quote", "reported")}


def analyse(text, ai_reply, own_words=False):
    """Combine the AI's answer with the checks. This is what the /speaker endpoint returns."""
    data = parse_reply(ai_reply)
    spans = find_quoted_spans(text)
    quote = verify_quote(data.get("quote", ""), text, own_words)
    ai_quote_rejected = bool(data.get("quote")) and not quote
    # Quoted passages the AI didn't pick are offered, never used automatically: a story
    # often quotes someone else too (a spokesman, a rival), and the card must not
    # put their words under the speaker's photo.
    chosen = _normalise_with_map(quote)[0] if quote else None
    options = [s[2] for s in spans if not (chosen and chosen in _normalise_with_map(s[2])[0])][:MAX_OPTIONS]
    speaker = data.get("speaker", "")
    reported = re.sub(r'^["“]+|["”]+$', "", data.get("reported", "")).strip()

    if quote:
        status, note = "exact", "Exact words, found in your text."
    elif options:
        status = "choose"
        note = ("Your text has quoted words, but I couldn't tell which are the speaker's. "
                "Tap the one they said, or paste their own post.")
    else:
        status = "none"
        note = ("Your text doesn't contain the speaker's own words, only a summary of what they said. "
                "Find their post or statement and paste it here, or use the reported line without quote marks.")
    if ai_quote_rejected:
        log.info("speaker: AI quote not found in the text, dropped")

    return {
        "speaker": speaker,
        "role": data.get("role", ""),
        "where": data.get("where", ""),
        "quote": quote,
        "status": status,
        "options": options,
        "reported": reported,
        "terms": search_terms(reported or text, speaker),
        "note": note,
    }
