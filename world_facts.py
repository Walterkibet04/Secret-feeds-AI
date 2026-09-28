"""Current heads of state and government for every country, from Wikidata.

The AI models' training data is old, so they get titles wrong ("former President
Trump"). This module downloads who currently holds each country's top offices,
refreshes it once a day in the background, and hands the prompt only the
countries a story mentions (by name, demonym, capital, flag emoji or leader's
surname), so the prompt stays short.

If Wikidata can't be reached, the tool keeps working: the last saved copy is
used, or nothing, and current_facts.txt still applies.
"""
import json
import logging
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).with_name("world_leaders.json")
REFRESH_SECONDS = 24 * 60 * 60
MAX_COUNTRIES_PER_PROMPT = 6
MIN_COUNTRIES = 150  # a normal download has ~195; fewer means something went wrong
SPARQL_URL = "https://query.wikidata.org/sparql"
# Wikimedia asks automated clients to identify themselves.
USER_AGENT = "SecretFeedsRewriter/1.0 (personal news tool; python-requests)"

PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
"""

# Sovereign states (Q3624078) that are not historical countries (Q3024240),
# plus a few widely covered places Wikidata doesn't class as sovereign states:
# Palestine, Taiwan, Kosovo.
_COUNTRIES = """
  { ?c wdt:P31 wd:Q3624078 . FILTER NOT EXISTS { ?c wdt:P31 wd:Q3024240 } }
  UNION { VALUES ?c { wd:Q219060 wd:Q865 wd:Q1246 } }
"""

# One row per current statement: head of state (P35) or head of government (P6),
# without an end date (P582) and not deprecated.
LEADERS_QUERY = PREFIXES + """
SELECT ?c ?role ?name ?rank ?start WHERE {
""" + _COUNTRIES + """
  VALUES (?p ?ps ?role) { (p:P35 ps:P35 "hos") (p:P6 ps:P6 "hog") }
  ?c ?p ?st .
  ?st ?ps ?person .
  ?st wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  FILTER NOT EXISTS { ?st pq:P582 ?end }
  OPTIONAL { ?st pq:P580 ?start }
  ?person rdfs:label ?name . FILTER(LANG(?name) = "en")
}"""

# Names, codes, demonyms, capitals and office titles used for matching and wording.
COUNTRY_QUERY = PREFIXES + """
SELECT ?c ?label ?iso ?demonym ?capital ?hosOffice ?hogOffice WHERE {
""" + _COUNTRIES + """
  ?c rdfs:label ?label . FILTER(LANG(?label) = "en")
  OPTIONAL { ?c wdt:P297 ?iso }
  OPTIONAL { ?c wdt:P1549 ?demonym . FILTER(LANG(?demonym) = "en") }
  OPTIONAL { ?c wdt:P36 ?cap . ?cap rdfs:label ?capital . FILTER(LANG(?capital) = "en") }
  OPTIONAL { ?c wdt:P1906 ?hso . ?hso rdfs:label ?hosOffice . FILTER(LANG(?hosOffice) = "en") }
  OPTIONAL { ?c wdt:P1313 ?hgo . ?hgo rdfs:label ?hogOffice . FILTER(LANG(?hogOffice) = "en") }
}"""

# Common ways news copy refers to a country that Wikidata names don't cover.
# ALL-CAPS aliases are matched case-sensitively ("US" must not match "us").
ALIASES = {
    "US": ["US", "U.S.", "USA", "America", "American", "Americans", "White House", "Pentagon", "Washington"],
    "GB": ["UK", "U.K.", "Britain", "British", "Downing Street"],
    "RU": ["Kremlin"],
    "AE": ["UAE", "Emirati", "Emiratis"],
    "CD": ["DRC", "DR Congo"],
    "KR": ["South Korean"],
    "KP": ["North Korean"],
    "IL": ["IDF"],
    "IR": ["IRGC"],
    "PS": ["Gaza", "West Bank", "Palestinian", "Palestinians"],
    "TR": ["Türkiye", "Turkiye"],
    "CN": ["PRC"],
    "TW": ["Taiwanese"],
    "SA": ["Saudi"],
    "VA": ["Pope", "Holy See"],
}

_lock = threading.Lock()
_cache = {"countries": [], "fetched_at": None}


# ── FETCH + BUILD ─────────────────────────────────────────────────────────────
def _run_query(query: str) -> list[dict]:
    r = requests.post(
        SPARQL_URL,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def _val(row: dict, key: str):
    v = row.get(key)
    return v["value"] if v else None


def _pick_current(rows: list[dict]) -> list[str]:
    """From statements with no end date, pick who holds the office now.

    Preferred-rank statements win (Wikidata marks the current holder that way).
    Otherwise take the most recent start date, in case an old entry is missing
    its end date. Offices shared by several people keep all of them (max 3).
    """
    if not rows:
        return []
    preferred = [r for r in rows if r["rank"].endswith("PreferredRank")]
    pool = preferred or rows
    dated = [r for r in pool if r.get("start")]
    if not preferred and dated:
        latest = max(r["start"] for r in dated)
        pool = [r for r in dated if r["start"] == latest]
    names = []
    for r in pool:
        if r["name"] not in names:
            names.append(r["name"])
    return names[:3]


def build_records(leader_rows: list[dict], country_rows: list[dict]) -> list[dict]:
    """Turn raw SPARQL JSON bindings into one record per country."""
    countries: dict[str, dict] = {}
    for row in country_rows:
        cid = _val(row, "c")
        rec = countries.setdefault(cid, {
            "country": _val(row, "label"), "iso": None, "demonyms": [], "capitals": [],
            "hos_office": None, "hog_office": None, "hos": [], "hog": [],
        })
        if _val(row, "iso"):
            rec["iso"] = _val(row, "iso")
        for key, field in (("demonym", "demonyms"), ("capital", "capitals")):
            v = _val(row, key)
            if v and v not in rec[field]:
                rec[field].append(v)
        for key, field in (("hosOffice", "hos_office"), ("hogOffice", "hog_office")):
            if _val(row, key) and not rec[field]:
                rec[field] = _val(row, key)

    by_role: dict[tuple[str, str], list[dict]] = {}
    for row in leader_rows:
        key = (_val(row, "c"), _val(row, "role"))
        by_role.setdefault(key, []).append({
            "name": _val(row, "name"), "rank": _val(row, "rank") or "", "start": _val(row, "start"),
        })
    for (cid, role), rows in by_role.items():
        if cid in countries:
            countries[cid][role] = _pick_current(rows)

    return sorted(
        (r for r in countries.values() if r["country"] and (r["hos"] or r["hog"])),
        key=lambda r: r["country"],
    )


def refresh() -> bool:
    """Download fresh data and save it. Returns True on success."""
    try:
        records = build_records(_run_query(LEADERS_QUERY), _run_query(COUNTRY_QUERY))
        if len(records) < MIN_COUNTRIES:  # something is off; keep the old copy
            raise ValueError(f"only {len(records)} countries returned")
        data = {"fetched_at": datetime.now(timezone.utc).isoformat(), "countries": records}
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(CACHE_FILE)
        with _lock:
            _cache.update(data)
        log.info(f"🌍 World leaders refreshed: {len(records)} countries")
        return True
    except Exception as e:
        log.warning(f"⚠️  World leaders refresh failed ({str(e)[:120]}), keeping previous data")
        return False


def load_cache() -> None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        with _lock:
            _cache.update(data)
    except (OSError, ValueError):
        pass


def _cache_age_seconds() -> float:
    fetched = _cache.get("fetched_at")
    if not fetched:
        return float("inf")
    return (datetime.now(timezone.utc) - datetime.fromisoformat(fetched)).total_seconds()


def start_background_refresh() -> None:
    """Load the saved copy, then refresh now if it's stale and every 24 hours after."""
    load_cache()

    def loop():
        while True:
            if _cache_age_seconds() >= REFRESH_SECONDS or not _cache["countries"]:
                refresh()
            time.sleep(60 * 60)  # check hourly; refresh only when a day old

    threading.Thread(target=loop, daemon=True, name="world-leaders-refresh").start()


# ── MATCHING ──────────────────────────────────────────────────────────────────
def _plain(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
    )


def _flag_codes(text: str) -> set[str]:
    """ISO codes from flag emojis: 🇭🇺 → HU."""
    ri = [ord(c) - 0x1F1E6 for c in text if 0x1F1E6 <= ord(c) <= 0x1F1FF]
    return {chr(65 + ri[i]) + chr(65 + ri[i + 1]) for i in range(0, len(ri) - 1, 2)}


def _has_phrase(plain_text: str, phrase: str) -> bool:
    p = _plain(phrase)
    return bool(p) and re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", plain_text) is not None


def _surnames(rec: dict) -> list[str]:
    out = []
    for name in rec["hos"] + rec["hog"]:
        last = name.split()[-1] if name.split() else ""
        if len(last) >= 4 and last[0].isupper():
            out.append(last)
    return out


def countries_in(text: str) -> list[dict]:
    """Countries a piece of text refers to, most mentions first."""
    with _lock:
        records = list(_cache["countries"])
    if not records or not text:
        return []
    plain = _plain(text)
    flags = _flag_codes(text)
    scored = []
    for rec in records:
        hits = 0
        if rec.get("iso") in flags:
            hits += 2
        for phrase in [rec["country"]] + rec["demonyms"] + rec["capitals"] + _surnames(rec):
            if _has_phrase(plain, phrase):
                hits += 1
        for alias in ALIASES.get(rec.get("iso") or "", []):
            if alias.isupper() or "." in alias:
                if re.search(r"(?<![\w.])" + re.escape(alias) + r"(?![\w])", text):
                    hits += 1
            elif _has_phrase(plain, alias):
                hits += 1
        if hits:
            scored.append((hits, rec))
    scored.sort(key=lambda x: -x[0])
    return [rec for _, rec in scored[:MAX_COUNTRIES_PER_PROMPT]]


def describe(rec: dict) -> str:
    """One line for the prompt, e.g.
    Hungary (Hungarian): President of Hungary: András Baka. Prime Minister of Hungary: Péter Magyar."""
    demonym = f" ({rec['demonyms'][0]})" if rec["demonyms"] else ""
    parts = []
    same = rec["hos"] and rec["hos"] == rec["hog"]
    if rec["hos"]:
        office = rec["hos_office"] or "Head of state"
        if same:
            office += " (head of state and government)"
        parts.append(f"{office}: {', '.join(rec['hos'])}.")
    if rec["hog"] and not same:
        office = rec["hog_office"] or "Head of government"
        parts.append(f"{office}: {', '.join(rec['hog'])}.")
    return f"{rec['country']}{demonym}: " + " ".join(parts)


def facts_for(text: str) -> str:
    """Prompt lines for the countries in this text, or a note if none matched."""
    recs = countries_in(text)
    if not recs:
        return "(no country list available for this story)"
    fetched = (_cache.get("fetched_at") or "")[:10]
    return "\n".join(f"- {describe(r)}" for r in recs) + f"\n(Source: Wikidata, updated {fetched})"
