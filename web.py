import os
import threading
import logging
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from generator import call_ai, REWRITE_PROMPT

load_dotenv()

log = logging.getLogger(__name__)
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Secret Feeds — Tweet Rewriter</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0a; --surface: #111; --border: #1e1e1e;
    --accent: #e84e1b; --accent2: #ff6b35; --text: #f0ede8; --muted: #666;
    --green: #22c55e;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
  header { border-bottom: 1px solid var(--border); padding: 18px 28px; display: flex; align-items: center; justify-content: space-between; }
  .brand { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1rem; letter-spacing: 0.08em; text-transform: uppercase; background: linear-gradient(90deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .dot { width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);display:inline-block;margin-right:6px; }
  .status { font-size: 0.75rem; color: var(--muted); }
  main { max-width: 680px; margin: 0 auto; padding: 40px 20px; }
  h1 { font-family: 'Syne', sans-serif; font-size: 1.8rem; font-weight: 700; margin-bottom: 6px; }
  .sub { color: var(--muted); font-size: 0.88rem; margin-bottom: 32px; line-height: 1.5; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 20px; }
  label { display:block; font-size:0.72rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:8px; }
  textarea { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 0.9rem; padding: 12px 14px; outline: none; resize: vertical; min-height: 120px; line-height: 1.6; transition: border-color 0.2s; }
  textarea:focus { border-color: var(--accent); }
  .char-count { text-align: right; font-size: 0.72rem; color: var(--muted); margin-top: 5px; }
  .char-count.over { color: var(--accent); }
  .btn { width: 100%; padding: 13px; border: none; border-radius: 8px; margin-top: 14px; font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 700; letter-spacing: 0.05em; cursor: pointer; transition: opacity 0.2s; background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn:active { transform: scale(0.98); }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; margin-top: 20px; display: none; }
  .result-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 10px; }
  .result-text { font-size: 0.95rem; line-height: 1.65; color: var(--text); white-space: pre-wrap; }
  .result-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
  .result-chars { font-size: 0.72rem; color: var(--muted); }
  .copy-btn { padding: 7px 16px; border-radius: 6px; font-size: 0.78rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: transparent; color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif; }
  .copy-btn:hover { border-color: var(--accent); color: var(--accent2); }
  .copy-btn.copied { color: var(--green); border-color: var(--green); }
  .error { background: rgba(232,78,27,0.08); border: 1px solid rgba(232,78,27,0.2); border-radius: 8px; padding: 12px 16px; font-size: 0.85rem; color: #ff8c70; margin-top: 14px; display: none; }
  .spinner { display:none; text-align:center; padding: 16px 0; color: var(--muted); font-size: 0.85rem; }
  .tip { background: rgba(232,78,27,0.06); border: 1px solid rgba(232,78,27,0.12); border-radius: 8px; padding: 12px 16px; font-size: 0.82rem; color: #aaa; line-height: 1.6; margin-bottom: 20px; }
  .tip strong { color: var(--accent2); }
</style>
</head>
<body>
<header>
  <span class="brand">Secret Feeds</span>
  <span><span class="dot"></span><span class="status">Live</span></span>
</header>
<main>
  <h1>Tweet Rewriter</h1>
  <p class="sub">Paste any tweet. Get a rewritten version with the same meaning but different wording — safe from X's duplicate detection.</p>
  <div class="tip">
    <strong>How it works:</strong> Every fact, number, and name stays exactly the same. Only the sentence structure changes — just enough to pass X's duplicate filter.
  </div>
  <div class="card">
    <label>Original Tweet</label>
    <textarea id="original" placeholder="Paste the tweet you want to rewrite here..." oninput="countChars()"></textarea>
    <div class="char-count" id="charCount">0 / 4000</div>
    <button class="btn" id="rewriteBtn" onclick="rewriteTweet()">Rewrite for Secret Feeds</button>
  </div>
  <div class="spinner" id="spinner">⏳ Rewriting...</div>
  <div class="error" id="error"></div>
  <div class="result-card" id="resultCard">
    <div class="result-label">Rewritten Tweet</div>
    <div class="result-text" id="resultText"></div>
    <div class="result-meta">
      <span class="result-chars" id="resultChars"></span>
      <button class="copy-btn" id="copyBtn" onclick="copyResult()">Copy</button>
    </div>
  </div>
</main>
<script>
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
    document.getElementById('copyBtn').textContent = 'Copy';
    document.getElementById('copyBtn').className = 'copy-btn';
  } catch (e) {
    const el = document.getElementById('error');
    el.textContent = 'Error: ' + e.message;
    el.style.display = 'block';
  } finally {
    document.getElementById('rewriteBtn').disabled = false;
    document.getElementById('spinner').style.display = 'none';
  }
}

function copyResult() {
  const text = document.getElementById('resultText').textContent;
  const btn = document.getElementById('copyBtn');
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => { btn.textContent = 'Copied!'; btn.className = 'copy-btn copied'; setTimeout(() => { btn.textContent = 'Copy'; btn.className = 'copy-btn'; }, 2000); });
  } else {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand('copy'); btn.textContent = 'Copied!'; btn.className = 'copy-btn copied'; setTimeout(() => { btn.textContent = 'Copy'; btn.className = 'copy-btn'; }, 2000); } catch(e) { btn.textContent = 'Select & Copy'; }
    document.body.removeChild(ta);
  }
}

document.getElementById('original').addEventListener('keydown', e => { if (e.key === 'Enter' && e.ctrlKey) rewriteTweet(); });
</script>
</body>
</html>"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/rewrite", methods=["POST"])
def rewrite_endpoint():
    data = request.get_json()
    original = (data or {}).get("tweet", "").strip()
    if not original:
        return jsonify({"error": "No tweet provided"}), 400
    if len(original) > 5000:
        return jsonify({"error": "Text too long"}), 400
    try:
        rewritten = call_ai(REWRITE_PROMPT.format(tweet=original))
        return jsonify({"rewritten": rewritten})
    except Exception as e:
        log.error(f"Rewrite error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

def start_web():
    port = int(os.getenv("PORT", 5000))
    log.info(f"🌐 Web interface running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def run_web_in_background():
    thread = threading.Thread(target=start_web, daemon=True)
    thread.start()

