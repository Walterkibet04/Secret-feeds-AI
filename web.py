import os
import threading
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from generator import call_ai, REWRITE_PROMPT

load_dotenv()

log = logging.getLogger(__name__)
app = Flask(__name__)

# ── IN-MEMORY DRAFT STORE ─────────────────────────────────────────────────────
# Stores all generated drafts in memory — visible on the web UI
_drafts = []
MAX_DRAFTS = 100  # keep last 100 drafts


def store_drafts(drafts: list):
    """Called by main.py after each generation cycle."""
    global _drafts
    now = datetime.now().strftime("%b %d, %I:%M %p")
    for d in drafts:
        _drafts.insert(0, {**d, "generated_at": now})
    # Keep only last MAX_DRAFTS
    _drafts = _drafts[:MAX_DRAFTS]
    log.info(f"📋 {len(drafts)} drafts stored in UI ({len(_drafts)} total)")


# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Secret Feeds — Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0a; --surface: #111; --border: #1e1e1e;
    --accent: #e84e1b; --accent2: #ff6b35; --text: #f0ede8; --muted: #666;
    --green: #22c55e; --blue: #818cf8; --yellow: #fbbf24;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
  header {
    border-bottom: 1px solid var(--border); padding: 16px 28px;
    display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; background: var(--bg); z-index: 10;
  }
  .brand {
    font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1rem;
    letter-spacing: 0.08em; text-transform: uppercase;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  }
  .dot { width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);display:inline-block;margin-right:6px; }
  .status { font-size: 0.73rem; color: var(--muted); }
  nav { display: flex; gap: 6px; }
  .nav-btn {
    padding: 7px 16px; border-radius: 6px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; border: 1px solid var(--border); background: transparent;
    color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif;
  }
  .nav-btn.active, .nav-btn:hover { border-color: var(--accent); color: var(--accent2); background: rgba(232,78,27,0.06); }
  main { max-width: 720px; margin: 0 auto; padding: 32px 20px; }

  /* TABS */
  .tab { display: none; }
  .tab.active { display: block; }

  /* DRAFTS TAB */
  .drafts-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
  .drafts-title { font-family: 'Syne', sans-serif; font-size: 1.4rem; font-weight: 700; }
  .refresh-btn {
    padding: 8px 16px; border-radius: 6px; font-size: 0.78rem; font-weight: 600;
    cursor: pointer; border: 1px solid var(--border); background: transparent;
    color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif;
  }
  .refresh-btn:hover { border-color: var(--accent); color: var(--accent2); }
  .draft-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 18px 20px; margin-bottom: 12px; transition: border-color 0.2s;
  }
  .draft-card:hover { border-color: #2a2a2a; }
  .draft-meta { display: flex; align-items: center; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
  .badge {
    border-radius: 4px; padding: 2px 8px; font-size: 0.68rem;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em;
  }
  .badge-format { background: rgba(232,78,27,0.15); color: #ff6b35; }
  .badge-source { background: rgba(232,78,27,0.1); color: #cc4a1a; }
  .badge-news { background: rgba(99,102,241,0.15); color: var(--blue); }
  .badge-sports { background: rgba(34,197,94,0.15); color: var(--green); }
  .badge-trending { background: rgba(251,191,36,0.15); color: var(--yellow); }
  .badge-x { background: rgba(255,255,255,0.06); color: #888; }
  .draft-time { font-size: 0.68rem; color: var(--muted); margin-left: auto; }
  .draft-text { font-size: 0.92rem; line-height: 1.65; color: var(--text); margin-bottom: 12px; }
  .draft-footer { display: flex; align-items: center; justify-content: space-between; }
  .draft-chars { font-size: 0.7rem; color: var(--muted); }
  .draft-chars.over { color: var(--accent); }
  .copy-btn {
    padding: 6px 14px; border-radius: 6px; font-size: 0.75rem; font-weight: 600;
    cursor: pointer; border: 1px solid var(--border); background: transparent;
    color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif;
  }
  .copy-btn:hover { border-color: var(--accent); color: var(--accent2); }
  .copy-btn.copied { color: var(--green); border-color: var(--green); }
  .source-link { font-size: 0.7rem; color: #444; text-decoration: none; }
  .source-link:hover { color: var(--muted); }
  .empty-state { text-align: center; padding: 60px 20px; color: var(--muted); font-size: 0.88rem; line-height: 1.7; }
  .empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }
  .cycle-divider {
    text-align: center; font-size: 0.68rem; color: #333;
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 20px 0 12px; display: flex; align-items: center; gap: 10px;
  }
  .cycle-divider::before, .cycle-divider::after { content:''; flex:1; height:1px; background: var(--border); }

  /* REWRITE TAB */
  .rewrite-title { font-family: 'Syne', sans-serif; font-size: 1.4rem; font-weight: 700; margin-bottom: 6px; }
  .rewrite-sub { color: var(--muted); font-size: 0.85rem; margin-bottom: 24px; line-height: 1.5; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 22px; margin-bottom: 16px; }
  label { display:block; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:8px; }
  textarea {
    width: 100%; background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; color: var(--text); font-family: 'Inter', sans-serif;
    font-size: 0.88rem; padding: 11px 13px; outline: none; resize: vertical;
    min-height: 95px; line-height: 1.6; transition: border-color 0.2s;
  }
  textarea:focus { border-color: var(--accent); }
  .char-count { text-align: right; font-size: 0.7rem; color: var(--muted); margin-top: 5px; }
  .char-count.over { color: var(--accent); }
  .btn {
    width: 100%; padding: 12px; border: none; border-radius: 8px; margin-top: 12px;
    font-family: 'Syne', sans-serif; font-size: 0.88rem; font-weight: 700;
    letter-spacing: 0.05em; cursor: pointer;
    background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff;
  }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin-top: 16px; display: none; }
  .result-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 8px; }
  .result-text { font-size: 0.92rem; line-height: 1.65; color: var(--text); white-space: pre-wrap; margin-bottom: 10px; }
  .result-meta { display: flex; align-items: center; justify-content: space-between; }
  .result-chars { font-size: 0.7rem; color: var(--muted); }
  .spinner { display:none; text-align:center; padding: 14px 0; color: var(--muted); font-size: 0.83rem; }
  .error-box { background: rgba(232,78,27,0.08); border: 1px solid rgba(232,78,27,0.2); border-radius: 8px; padding: 11px 14px; font-size: 0.83rem; color: #ff8c70; margin-top: 12px; display: none; }
  .tip { background: rgba(232,78,27,0.05); border: 1px solid rgba(232,78,27,0.1); border-radius: 8px; padding: 11px 14px; font-size: 0.8rem; color: #888; line-height: 1.6; margin-bottom: 18px; }
  .tip strong { color: var(--accent2); }
  .count-badge { background: rgba(232,78,27,0.15); color: var(--accent2); border-radius: 10px; padding: 1px 8px; font-size: 0.7rem; font-weight: 700; margin-left: 8px; }
</style>
</head>
<body>
<header>
  <span class="brand">Secret Feeds</span>
  <nav>
    <button class="nav-btn active" onclick="switchTab('drafts', this)">Drafts <span class="count-badge" id="draftCount">0</span></button>
    <button class="nav-btn" onclick="switchTab('rewrite', this)">Rewriter</button>
  </nav>
  <span><span class="dot"></span><span class="status">Live</span></span>
</header>

<main>
  <!-- DRAFTS TAB -->
  <div class="tab active" id="tab-drafts">
    <div class="drafts-header">
      <span class="drafts-title">Generated Drafts</span>
      <button class="refresh-btn" onclick="loadDrafts()">↻ Refresh</button>
    </div>
    <div id="draftsList">
      <div class="empty-state">
        <div class="empty-icon">🌍</div>
        No drafts yet. Bot runs every 30 minutes.<br>Check back soon or wait for the next cycle.
      </div>
    </div>
  </div>

  <!-- REWRITE TAB -->
  <div class="tab" id="tab-rewrite">
    <div class="rewrite-title">Tweet Rewriter</div>
    <p class="rewrite-sub">Paste any tweet. Get a rewritten version with the same meaning — safe from X's duplicate filter.</p>

    <div class="tip">
      <strong>How it works:</strong> Every fact, number, and name stays exactly the same. Only the sentence structure changes — just enough to pass X's duplicate detection.
    </div>

    <div class="card">
      <label>Original Tweet</label>
      <textarea id="original" placeholder="Paste the tweet you want to rewrite..." oninput="countChars()"></textarea>
      <div class="char-count" id="charCount">0 / 4000</div>
      <button class="btn" id="rewriteBtn" onclick="rewriteTweet()">Rewrite for Secret Feeds</button>
    </div>

    <div class="spinner" id="spinner">⏳ Rewriting...</div>
    <div class="error-box" id="error"></div>

    <div class="result-card" id="resultCard">
      <div class="result-label">Rewritten Tweet</div>
      <div class="result-text" id="resultText"></div>
      <div class="result-meta">
        <span class="result-chars" id="resultChars"></span>
        <button class="copy-btn" id="copyRewriteBtn" onclick="copyText('resultText', 'copyRewriteBtn')">Copy</button>
      </div>
    </div>
  </div>
</main>

<script>
// ── TAB SWITCHING ─────────────────────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  if (name === 'drafts') loadDrafts();
}

// ── COPY UTILITY (works on HTTP and HTTPS) ────────────────────────────────────
function copyText(sourceId, btnId) {
  const text = document.getElementById(sourceId).textContent;
  const btn = document.getElementById(btnId);

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => flashCopied(btn));
  } else {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus(); ta.select();
    try { document.execCommand('copy'); flashCopied(btn); } catch(e) { btn.textContent = 'Select & Copy'; }
    document.body.removeChild(ta);
  }
}

function flashCopied(btn) {
  const orig = btn.textContent;
  btn.textContent = 'Copied!';
  btn.classList.add('copied');
  setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
}

// ── LOAD DRAFTS ───────────────────────────────────────────────────────────────
async function loadDrafts() {
  try {
    const resp = await fetch('/drafts');
    const data = await resp.json();
    renderDrafts(data.drafts || []);
    document.getElementById('draftCount').textContent = data.drafts?.length || 0;
  } catch(e) {
    console.error('Failed to load drafts:', e);
  }
}

function typeBadge(type) {
  const map = {
    news:     '<span class="badge badge-news">🌍 Geo</span>',
    sports:   '<span class="badge badge-sports">⚽ Sports</span>',
    trending: '<span class="badge badge-trending">🔥 Trending</span>',
    x:        '<span class="badge badge-x">𝕏 X</span>',
  };
  return map[type] || map.news;
}

function renderDrafts(drafts) {
  const list = document.getElementById('draftsList');
  if (!drafts.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-icon">🌍</div>No drafts yet. Bot runs every 30 minutes.<br>Check back soon.</div>';
    return;
  }

  // Group by generated_at time
  const groups = {};
  drafts.forEach(d => {
    const key = d.generated_at || 'Unknown';
    if (!groups[key]) groups[key] = [];
    groups[key].push(d);
  });

  let html = '';
  Object.entries(groups).forEach(([time, items]) => {
    html += `<div class="cycle-divider">${time}</div>`;
    items.forEach((d, i) => {
      const over = d.chars > 4000;
      const id = `draft-${time.replace(/\W/g,'')}-${i}`;
      html += `
      <div class="draft-card">
        <div class="draft-meta">
          <span class="badge badge-format">${d.format}</span>
          <span class="badge badge-source">${d.source}</span>
          ${typeBadge(d.type)}
          <span class="draft-time">${d.generated_at || ''}</span>
        </div>
        <div class="draft-text" id="${id}">${escHtml(d.text)}</div>
        <div class="draft-footer">
          <div>
            <span class="draft-chars ${over ? 'over' : ''}">${d.chars}/4000</span>
            ${d.link ? `<a href="${d.link}" target="_blank" class="source-link" style="margin-left:10px;">Source →</a>` : ''}
          </div>
          <button class="copy-btn" onclick="copyText('${id}', this.id)" id="btn-${id}">Copy</button>
        </div>
      </div>`;
    });
  });

  list.innerHTML = html;
}

function escHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── REWRITER ──────────────────────────────────────────────────────────────────
function countChars() {
  const text = document.getElementById('original').value;
  const el = document.getElementById('charCount');
  el.textContent = text.length + ' / 4000';
  el.className = 'char-count' + (text.length > 4000 ? ' over' : '');
}

async function rewriteTweet() {
  const original = document.getElementById('original').value.trim();
  if (!original) return;

  document.getElementById('rewriteBtn').disabled = true;
  document.getElementById('spinner').style.display = 'block';
  document.getElementById('resultCard').style.display = 'none';
  document.getElementById('error').style.display = 'none';

  try {
    const resp = await fetch('/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tweet: original })
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    document.getElementById('resultText').textContent = data.rewritten;
    document.getElementById('resultChars').textContent = data.rewritten.length + ' / 4000 chars';
    document.getElementById('resultCard').style.display = 'block';
  } catch(e) {
    const el = document.getElementById('error');
    el.textContent = 'Error: ' + e.message;
    el.style.display = 'block';
  } finally {
    document.getElementById('rewriteBtn').disabled = false;
    document.getElementById('spinner').style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', loadDrafts);

// Auto-refresh drafts every 5 minutes
setInterval(loadDrafts, 5 * 60 * 1000);
</script>
</body>
</html>"""


# ── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/drafts")
def get_drafts():
    return jsonify({"drafts": _drafts, "total": len(_drafts)})


@app.route("/rewrite", methods=["POST"])
def rewrite_endpoint():
    data = request.get_json()
    original = (data or {}).get("tweet", "").strip()
    if not original:
        return jsonify({"error": "No tweet provided"}), 400
    if len(original) > 1000:
        return jsonify({"error": "Text too long"}), 400
    try:
        rewritten = call_ai(REWRITE_PROMPT.format(tweet=original))
        return jsonify({"rewritten": rewritten})
    except Exception as e:
        log.error(f"Rewrite error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "drafts_stored": len(_drafts)})


def start_web():
    port = int(os.getenv("PORT", 5000))
    log.info(f"🌐 Web interface running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_web_in_background():
    thread = threading.Thread(target=start_web, daemon=True)
    thread.start()
