"""Quick checks on a generated post before you copy it.

These don't call any AI. They flag the things that make a post read as
machine-written or break the Secret Feeds voice, so you can fix them by hand.
"""
import re
import unicodedata
from pathlib import Path

STOCK_PHRASES = [
    "this is no longer",
    "sends a clear message",
    "a stark reminder",
    "raises questions",
    "it remains to be seen",
    "the question is whether",
    "in a significant move",
    "marks a turning point",
    "game-changer",
    "game changer",
    "here's why",
    "let that sink in",
    "make no mistake",
    "what happens next?",
]

GENERIC_QUESTIONS = [
    "thoughts?",
    "agree?",
    "what do you think?",
    "your thoughts?",
    "do you agree?",
    "what's your take?",
]

THREAD_MARKERS = ["🧵", "thread below", "more below", "a thread", "see reply", "in the replies"]
_THREAD_COUNTER = re.compile(r"\(?\b1/\d*\)?\s*$")  # "1/", "1/2" or "(1/2)" at the end of the post

_HASHTAG = re.compile(r"(?<![\w&])#[^\W\d]\w*")
_REGIONAL_INDICATOR = re.compile("[\U0001F1E6-\U0001F1FF]")
# Characters some models (gpt-oss especially) put in place of plain ones. They look
# odd on X, break search, and are an easy "written by AI" tell.
_CHAR_FIXES = {
    "\u2010": "-",   # hyphen
    "\u2011": "-",   # non-breaking hyphen, e.g. "phone\u2011theft"
    "\u2012": "-",   # figure dash
    "\u00a0": " ",   # no-break space
    "\u202f": " ",   # narrow no-break space
    "\u2009": " ",   # thin space
    "\u200b": "",    # zero-width space
    "\u2060": "",    # word joiner
}

_FORMER_TITLE = re.compile(
    r"\bformer\s+(?:US\s+|U\.S\.\s+)?(president|prime minister|pm|chancellor|leader|supreme leader|premier)\b",
    re.I,
)
# Titles that should come with a country ("Hungarian Prime Minister", "Kenya's President").
_TITLES = ["Prime Minister", "Foreign Minister", "Defence Minister", "Defense Minister",
           "President", "Chancellor", "Premier", "PM"]
_BARE_TITLE = re.compile(r"(?<![\w'’])(" + "|".join(_TITLES) + r")\s+(?=[A-ZÀ-Þ])")

_NOT_X_BUT_Y = re.compile(r"\b(?:it's|it is|this is|that's|that is)\s+not\s+[^.?!\n]{1,60}[,;]\s*(?:it's|it is|but)\b", re.I)


def clean_text(text: str) -> str:
    """Swap look-alike characters for plain ones. Used on every AI result."""
    for bad, good in _CHAR_FIXES.items():
        text = text.replace(bad, good)
    return text


def _bare_titles(text: str) -> list[str]:
    """Titles used without a country in front, e.g. "revokes PM Peter ..."."""
    found = []
    for m in _BARE_TITLE.finditer(text):
        before = text[:m.start()].rstrip()
        prev = re.split(r"\s+", before)[-1] if before else ""
        prev = prev.strip(",.:;!?\"()")
        # A capitalised word just before ("Hungarian", "US", "Kenya's") names the country.
        # A flag emoji, the start of the post or a lowercase word does not.
        if prev[:1].isupper() and prev[:1].isalpha():
            continue
        name = text[m.end():].split()[0] if text[m.end():].split() else ""
        found.append(f"{m.group(1)} {name}".strip())
    return found


FACTS_FILE = Path(__file__).with_name("current_facts.txt")


def _plain(word: str) -> str:
    """Lowercase and strip accents, so "Péter" and "Peter" compare equal."""
    return "".join(c for c in unicodedata.normalize("NFKD", word.lower()) if not unicodedata.combining(c))


def _known_name_words() -> set[str]:
    """Words from the names in current_facts.txt ("Title: Name" lines and "X is the current ...")."""
    try:
        lines = FACTS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    names = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for sentence in re.split(r"(?<=\.)\s+", line):
            sentence = re.sub(r"\(.*?\)", "", sentence).strip(" .")
            if ":" in sentence:
                names.append(sentence.split(":", 1)[1])
            else:
                m = re.match(r"(.+?) is (?:the current|a former)", sentence)
                if m:
                    names.append(m.group(1))
    return {w for n in names for w in n.split() if len(w) >= 4 and w[0].isupper()}


def _one_edit_apart(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _possible_misspellings(text: str) -> list[tuple[str, str]]:
    known = _known_name_words()
    known_plain = {_plain(k): k for k in known}
    out = []
    for raw in re.findall(r"[^\W\d_][\w'’-]*", text):
        word = re.sub(r"['’]s$", "", raw)
        if len(word) < 4 or not word[0].isupper() or _plain(word) in known_plain:
            continue
        for kp, k in known_plain.items():
            if len(kp) >= 5 and _one_edit_apart(_plain(word), kp):
                out.append((word, k))
                break
    return out


def check_post(text: str, limit: int | None = None, standalone: bool = False) -> list[str]:
    """Return a list of human-readable warnings for one post."""
    warnings = []
    lower = text.lower()

    if "—" in text:
        warnings.append("Has an em dash (—). Readers spot it as an AI tell. Swap it for a full stop or comma.")

    found = [p for p in STOCK_PHRASES if p in lower]
    if found:
        warnings.append("Stock phrase: " + ", ".join(f'"{p}"' for p in found) + ". Cut or say it plainly.")

    if _NOT_X_BUT_Y.search(text):
        warnings.append('"It\'s not X, it\'s Y" structure. A common AI pattern; state the point directly.')

    generic = [q for q in GENERIC_QUESTIONS if lower.rstrip().endswith(q)]
    if generic:
        warnings.append(f'Ends with a generic question ("{generic[0]}"). Ask something specific to the story, or drop it.')

    former = _FORMER_TITLE.search(text)
    if former:
        warnings.append(f'Says "{former.group(0)}". AI models often have outdated officeholders; check it\'s still true.')

    for word, known in _possible_misspellings(text):
        warnings.append(f'"{word}" looks like a misspelling of "{known}" (from current_facts.txt).')

    bare = _bare_titles(text)
    if bare:
        warnings.append("Title without a country: " + ", ".join(f'"{t}"' for t in bare) + ". Say which country so every reader knows who.")

    if _HASHTAG.search(text):
        warnings.append("Has a hashtag. Secret Feeds posts don't use them.")

    flags = len(_REGIONAL_INDICATOR.findall(text)) // 2
    if flags > 2:
        warnings.append(f"{flags} flag emojis. Keep it to two at most.")

    if limit and len(text) > limit:
        warnings.append(f"{len(text)} characters, over the {limit} target.")

    if standalone:
        markers = [m for m in THREAD_MARKERS if m in lower]
        if _THREAD_COUNTER.search(text.strip()):
            markers.append("1/")
        if markers:
            warnings.append("Points to the reply (" + ", ".join(markers) + "). Non-followers never see the reply, so Post 1 must stand alone.")

    return warnings


# ── DUPLICATE CHECK ───────────────────────────────────────────────────────────
# X's copypasta detector (botmaker-rules/scarecrow/bot/BBQDuplicateTextProd.bot in
# xai-org/x-algorithm) clusters posts by the words they share ("unigrams"), not by
# word order. So what matters is how many of the same words the rewrite uses.
# X doesn't publish its threshold; these limits are deliberately cautious.
OVERLAP_WARN = 0.60      # share of distinct words in common (Jaccard)
COPIED_RUN_WARN = 6      # words in a row copied from the original

_QUOTED = re.compile(r"[\"“”]([^\"“”]{12,})[\"“”]")


def _tokens(text: str) -> list[str]:
    text = _plain(text)
    text = re.sub(r"https?://\S+|pic\.x\.com/\S+|@\w+", " ", text)
    text = re.sub(r"['’]s\b", "", text)
    return re.findall(r"[^\W_]+", text)


def word_overlap(original: str, rewrite: str) -> dict:
    """How close the rewrite is to the pasted original.

    Exact quotes are left out of the comparison, because quotes are kept word for word
    on purpose.
    """
    quotes = [q.strip() for q in _QUOTED.findall(original)]
    strip = lambda t: _QUOTED.sub(" ", t)
    a, b = _tokens(strip(original)), _tokens(strip(rewrite))
    sa, sb = set(a), set(b)
    jaccard = len(sa & sb) / len(sa | sb) if sa | sb else 0.0

    # Longest run of consecutive words that appears in both.
    best, end = 0, 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, end = cur[j], i
        prev = cur
    return {
        "percent": round(jaccard * 100),
        "longest_run": best,
        "longest_phrase": " ".join(a[end - best:end]) if best else "",
        "quotes_excluded": bool(quotes),
    }


def overlap_warnings(o: dict) -> list[str]:
    out = []
    if o["percent"] >= OVERLAP_WARN * 100:
        out.append(f"{o['percent']}% of words are shared with the original. X's duplicate check compares words, "
                   "not word order: change more words, or regenerate.")
    if o["longest_run"] >= COPIED_RUN_WARN:
        out.append(f"Copies {o['longest_run']} words in a row from the original: \"{o['longest_phrase']}\".")
    return out


# ── PASTED TEXT CLEANUP ───────────────────────────────────────────────────────
# Lines that come along when you copy a post from X, not part of the post itself.
_JUNK_LINES = [
    r"show more", r"show less", r"translate post", r"show translation", r"rate this translation",
    r"translated from .{1,40}", r"quote", r"pinned", r"promoted", r"ad", r"·",
    r"replying to (@\w+[ ,]*(and )?)+", r"@\w{1,15}",
    r"\d{1,2}:\d{2}\s?(am|pm)\s?·\s?\w{3,9}\.? \d{1,2},? \d{4}(\s?·.*)?",   # 12:30 PM · Sep 28, 2026
    r"[\d.,]+\s?[kmb]?\s+views?",                                           # 1.2M Views
    r"[\d.,]+\s?[kmb]?",                                                     # lone counts (likes, reposts)
    r"\d{1,2}[smhd]", r"\w{3} \d{1,2}(, \d{4})?",                            # 2h, Sep 28
]
_JUNK = re.compile(r"^\s*(?:" + "|".join(_JUNK_LINES) + r")\s*$", re.I)


def clean_pasted(text: str) -> str:
    """Drop X's interface text from a pasted post and tidy blank lines."""
    lines = [l for l in clean_text(text).splitlines() if not _JUNK.match(l)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
