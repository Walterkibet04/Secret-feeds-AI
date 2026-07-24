import os
import threading
import logging
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from dotenv import load_dotenv
from generator import call_ai, REWRITE_PROMPT, THREAD_PROMPT, SUMMARISE_PROMPT, HEADLINE_PROMPT

load_dotenv()

log = logging.getLogger(__name__)
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Secret Feeds — Tools</title>
<link rel="icon" type="image/png" href="/favicon.png">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0a0a0a; --surface: #111; --border: #1e1e1e;
    --accent: #e84e1b; --accent2: #ff6b35; --text: #f0ede8; --muted: #666;
    --green: #22c55e;
  }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
  header {
    border-bottom: 1px solid var(--border); padding: 14px 24px;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; background: var(--bg); z-index: 10;
  }
  .brand { font-family: 'Syne', sans-serif; font-weight: 800; font-size: 1rem; letter-spacing: 0.08em; text-transform: uppercase; background: linear-gradient(90deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .dot { width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);display:inline-block;margin-right:6px; }
  .status { font-size: 0.73rem; color: var(--muted); }
  nav { display: flex; gap: 5px; }
  .nav-btn { padding: 7px 16px; border-radius: 6px; font-size: 0.76rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: transparent; color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif; white-space: nowrap; }
  .nav-btn.active, .nav-btn:hover { border-color: var(--accent); color: var(--accent2); background: rgba(232,78,27,0.06); }
  main { max-width: 680px; margin: 0 auto; padding: 32px 20px; }
  .tab { display: none; }
  .tab.active { display: block; }
  .page-title { font-family: 'Syne', sans-serif; font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; }
  .page-sub { color: var(--muted); font-size: 0.86rem; margin-bottom: 24px; line-height: 1.55; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 14px; }
  label { display:block; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:8px; }
  textarea { width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 0.9rem; padding: 11px 13px; outline: none; resize: vertical; min-height: 110px; line-height: 1.6; transition: border-color 0.2s; }
  textarea:focus { border-color: var(--accent); }
  textarea.tall { min-height: 160px; }
  .char-count { text-align: right; font-size: 0.7rem; color: var(--muted); margin-top: 5px; }
  .char-count.over { color: var(--accent); }

  /* Toggle */
  .toggle-row { display: flex; align-items: center; gap: 10px; margin-top: 14px; margin-bottom: 2px; }
  .toggle-label { font-size: 0.8rem; color: var(--muted); }
  .toggle { position: relative; display: inline-block; width: 40px; height: 22px; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #222; border-radius: 22px; transition: .3s; border: 1px solid var(--border); }
  .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 2px; bottom: 2px; background: var(--muted); border-radius: 50%; transition: .3s; }
  input:checked + .slider { background: rgba(232,78,27,0.2); border-color: var(--accent); }
  input:checked + .slider:before { transform: translateX(18px); background: var(--accent2); }

  .btn { width: 100%; padding: 12px; border: none; border-radius: 8px; margin-top: 12px; font-family: 'Syne', sans-serif; font-size: 0.88rem; font-weight: 700; letter-spacing: 0.05em; cursor: pointer; background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff; transition: opacity 0.2s; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn:active { transform: scale(0.98); }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin-top: 14px; display: none; }
  .result-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); margin-bottom: 10px; }
  .result-text { font-size: 0.93rem; line-height: 1.7; color: var(--text); white-space: pre-wrap; }

  /* Thread result */
  .thread-container { display: none; margin-top: 14px; }
  .thread-post { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 18px; margin-bottom: 10px; }
  .thread-post-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent2); margin-bottom: 8px; }
  .thread-post-text { font-size: 0.93rem; line-height: 1.7; color: var(--text); white-space: pre-wrap; margin-bottom: 10px; }
  .thread-connector { text-align: center; color: var(--border); font-size: 1.2rem; margin: 2px 0; }

  .result-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
  .result-chars { font-size: 0.7rem; color: var(--muted); }
  .copy-btn { padding: 6px 14px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: transparent; color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif; }
  .copy-btn:hover { border-color: var(--accent); color: var(--accent2); }
  .copy-btn.copied { color: var(--green); border-color: var(--green); }
  .error { background: rgba(232,78,27,0.08); border: 1px solid rgba(232,78,27,0.2); border-radius: 8px; padding: 11px 14px; font-size: 0.83rem; color: #ff8c70; margin-top: 12px; display: none; }
  .spinner { display:none; text-align:center; padding: 14px 0; color: var(--muted); font-size: 0.83rem; }
  .tip { background: rgba(232,78,27,0.05); border: 1px solid rgba(232,78,27,0.1); border-radius: 8px; padding: 11px 14px; font-size: 0.8rem; color: #888; line-height: 1.6; margin-bottom: 18px; }
  .tip strong { color: var(--accent2); }
</style>
</head>
<body>
<header>
  <span class="brand">Secret Feeds</span>
  <nav>
    <button class="nav-btn active" id="nav-rewrite" onclick="switchTab('rewrite')">Rewrite</button>
    <button class="nav-btn" id="nav-summarise" onclick="switchTab('summarise')">Summarise</button>
    <button class="nav-btn" id="nav-headline" onclick="switchTab('headline')">Headline</button>
  </nav>
  <span><span class="dot"></span><span class="status">Live</span></span>
</header>

<main>
  <!-- REWRITE TAB -->
  <div class="tab active" id="tab-rewrite">
    <div class="page-title">Rewrite</div>
    <p class="page-sub">Paste any news tweet or quote. Direct quotes are kept exactly — news facts are rewritten. Both get Secret Feeds commentary added.</p>
    <div class="tip">
      <strong>Smart detection:</strong> If you paste a direct quote (e.g. <em>Rubio: "Our policy is an eye for an eye"</em>), it's kept word-for-word. News facts are rewritten in a fresh voice. Commentary and a question are added to both.
    </div>
    <div class="card">
      <label>Original Tweet or Quote</label>
      <textarea id="rewrite-input" placeholder='Paste a news tweet or direct quote...' oninput="countChars('rewrite-input','rewrite-count',4000)"></textarea>
      <div class="char-count" id="rewrite-count">0 / 4000</div>

      <div class="toggle-row">
        <label class="toggle">
          <input type="checkbox" id="thread-toggle">
          <span class="slider"></span>
        </label>
        <span class="toggle-label">Generate as thread (2 posts — gets more algorithmic push)</span>
      </div>

      <button class="btn" id="rewrite-btn" onclick="doRewrite()">Rewrite for Secret Feeds</button>
    </div>
    <div class="spinner" id="rewrite-spinner">⏳ Writing...</div>
    <div class="error" id="rewrite-error"></div>

    <!-- Single post result -->
    <div class="result-card" id="rewrite-result">
      <div class="result-label">Rewritten Post</div>
      <div class="result-text" id="rewrite-output"></div>
      <div class="result-meta">
        <span class="result-chars" id="rewrite-chars"></span>
        <button class="copy-btn" onclick="copyText('rewrite-output', this)">Copy</button>
      </div>
    </div>

    <!-- Thread result -->
    <div class="thread-container" id="thread-result">
      <div class="thread-post">
        <div class="thread-post-label">Post 1 — Main Post</div>
        <div class="thread-post-text" id="thread-post1"></div>
        <div class="result-meta">
          <span class="result-chars" id="thread-chars1"></span>
          <button class="copy-btn" onclick="copyText('thread-post1', this)">Copy</button>
        </div>
      </div>
      <div class="thread-connector">↓ reply to your own post</div>
      <div class="thread-post">
        <div class="thread-post-label">Post 2 — Your Analysis</div>
        <div class="thread-post-text" id="thread-post2"></div>
        <div class="result-meta">
          <span class="result-chars" id="thread-chars2"></span>
          <button class="copy-btn" onclick="copyText('thread-post2', this)">Copy</button>
        </div>
      </div>
    </div>
  </div>

  <!-- SUMMARISE TAB -->
  <div class="tab" id="tab-summarise">
    <div class="page-title">Summarise</div>
    <p class="page-sub">Paste a long tweet, thread, or article. Get a single punchy tweet with all key facts.</p>
    <div class="tip">
      <strong>How it works:</strong> Picks the 2-3 most important facts and condenses into one clear tweet in Secret Feeds voice.
    </div>
    <div class="card">
      <label>Content to Summarise</label>
      <textarea class="tall" id="summarise-input" placeholder="Paste a long tweet, thread, or article text here..." oninput="countChars('summarise-input','summarise-count',10000)"></textarea>
      <div class="char-count" id="summarise-count">0 / 10000</div>
      <button class="btn" id="summarise-btn" onclick="doSummarise()">Summarise</button>
    </div>
    <div class="spinner" id="summarise-spinner">⏳ Summarising...</div>
    <div class="error" id="summarise-error"></div>
    <div class="result-card" id="summarise-result">
      <div class="result-label">Summary Tweet</div>
      <div class="result-text" id="summarise-output"></div>
      <div class="result-meta">
        <span class="result-chars" id="summarise-chars"></span>
        <button class="copy-btn" onclick="copyText('summarise-output', this)">Copy</button>
      </div>
    </div>
  </div>

  <!-- HEADLINE TAB -->
  <div class="tab" id="tab-headline">
    <div class="page-title">Headline</div>
    <p class="page-sub">Paste any tweet or news text. Get a short punchy breaking news headline.</p>
    <div class="tip">
      <strong>Example:</strong> 🇺🇸🇮🇷 US forces target Iranian air defence systems in overnight strikes
    </div>
    <div class="card">
      <label>Original Tweet or Text</label>
      <textarea id="headline-input" placeholder="Paste the tweet or news text here..." oninput="countChars('headline-input','headline-count',5000)"></textarea>
      <div class="char-count" id="headline-count">0 / 5000</div>
      <button class="btn" id="headline-btn" onclick="doHeadline()">Make Headline</button>
    </div>
    <div class="spinner" id="headline-spinner">⏳ Writing headline...</div>
    <div class="error" id="headline-error"></div>
    <div class="result-card" id="headline-result">
      <div class="result-label">Headline Tweet</div>
      <div class="result-text" id="headline-output"></div>
      <div class="result-meta">
        <span class="result-chars" id="headline-chars"></span>
        <button class="copy-btn" onclick="copyText('headline-output', this)">Copy</button>
      </div>
    </div>
  </div>
</main>

<script>
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');
}

function countChars(inputId, countId, max) {
  const len = document.getElementById(inputId).value.length;
  const el = document.getElementById(countId);
  el.textContent = len + ' / ' + max;
  el.className = 'char-count' + (len > max ? ' over' : '');
}

function copyText(sourceId, btn) {
  const text = document.getElementById(sourceId).textContent;
  const orig = btn.textContent;
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => flash(btn, orig));
  } else {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand('copy'); flash(btn, orig); } catch(e) { btn.textContent = 'Select & Copy'; }
    document.body.removeChild(ta);
  }
}

function flash(btn, orig) {
  btn.textContent = 'Copied!'; btn.classList.add('copied');
  setTimeout(() => { btn.textContent = orig; btn.classList.remove('copied'); }, 2000);
}

async function doRewrite() {
  const tweet = document.getElementById('rewrite-input').value.trim();
  const asThread = document.getElementById('thread-toggle').checked;
  if (!tweet) return;

  document.getElementById('rewrite-btn').disabled = true;
  document.getElementById('rewrite-spinner').style.display = 'block';
  document.getElementById('rewrite-result').style.display = 'none';
  document.getElementById('thread-result').style.display = 'none';
  document.getElementById('rewrite-error').style.display = 'none';

  try {
    const resp = await fetch('/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tweet, thread: asThread })
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    if (data.is_thread && data.post1 && data.post2) {
      document.getElementById('thread-post1').textContent = data.post1;
      document.getElementById('thread-post2').textContent = data.post2;
      document.getElementById('thread-chars1').textContent = data.post1.length + ' chars';
      document.getElementById('thread-chars2').textContent = data.post2.length + ' chars';
      document.getElementById('thread-result').style.display = 'block';
    } else {
      document.getElementById('rewrite-output').textContent = data.result;
      document.getElementById('rewrite-chars').textContent = data.result.length + ' / 4000 chars';
      document.getElementById('rewrite-result').style.display = 'block';
    }
  } catch(e) {
    const el = document.getElementById('rewrite-error');
    el.textContent = 'Error: ' + e.message;
    el.style.display = 'block';
  } finally {
    document.getElementById('rewrite-btn').disabled = false;
    document.getElementById('rewrite-spinner').style.display = 'none';
  }
}

async function callEndpoint(endpoint, payload, btnId, spinnerId, errorId, resultId, outputId, charsId) {
  document.getElementById(btnId).disabled = true;
  document.getElementById(spinnerId).style.display = 'block';
  document.getElementById(resultId).style.display = 'none';
  document.getElementById(errorId).style.display = 'none';
  try {
    const resp = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    document.getElementById(outputId).textContent = data.result;
    document.getElementById(charsId).textContent = data.result.length + ' / 4000 chars';
    document.getElementById(resultId).style.display = 'block';
  } catch(e) {
    const el = document.getElementById(errorId);
    el.textContent = 'Error: ' + e.message;
    el.style.display = 'block';
  } finally {
    document.getElementById(btnId).disabled = false;
    document.getElementById(spinnerId).style.display = 'none';
  }
}

function doSummarise() {
  const content = document.getElementById('summarise-input').value.trim();
  if (!content) return;
  callEndpoint('/summarise', { content }, 'summarise-btn', 'summarise-spinner', 'summarise-error', 'summarise-result', 'summarise-output', 'summarise-chars');
}

function doHeadline() {
  const content = document.getElementById('headline-input').value.trim();
  if (!content) return;
  callEndpoint('/headline', { content }, 'headline-btn', 'headline-spinner', 'headline-error', 'headline-result', 'headline-output', 'headline-chars');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) {
    const active = document.querySelector('.tab.active').id;
    if (active === 'tab-rewrite') doRewrite();
    else if (active === 'tab-summarise') doSummarise();
    else doHeadline();
  }
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/favicon.png")
def favicon():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "favicon.png",
        mimetype="image/png"
    )


@app.route("/rewrite", methods=["POST"])
def rewrite_endpoint():
    data = request.get_json()
    tweet = (data or {}).get("tweet", "").strip()
    as_thread = (data or {}).get("thread", False)
    if not tweet:
        return jsonify({"error": "No tweet provided"}), 400
    if len(tweet) > 5000:
        return jsonify({"error": "Text too long"}), 400
    try:
        if as_thread:
            result = call_ai(THREAD_PROMPT.format(tweet=tweet))
            if "---THREAD---" in result:
                parts = result.split("---THREAD---")
                return jsonify({
                    "result": result,
                    "post1": parts[0].strip(),
                    "post2": parts[1].strip(),
                    "is_thread": True
                })
        result = call_ai(REWRITE_PROMPT.format(tweet=tweet))
        return jsonify({"result": result, "is_thread": False})
    except Exception as e:
        log.error(f"Rewrite error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/summarise", methods=["POST"])
def summarise_endpoint():
    data = request.get_json()
    content = (data or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "No content provided"}), 400
    if len(content) > 15000:
        return jsonify({"error": "Content too long — paste a shorter section"}), 400
    try:
        result = call_ai(SUMMARISE_PROMPT.format(content=content))
        return jsonify({"result": result})
    except Exception as e:
        log.error(f"Summarise error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/headline", methods=["POST"])
def headline_endpoint():
    data = request.get_json()
    content = (data or {}).get("content", "").strip()
    if not content:
        return jsonify({"error": "No content provided"}), 400
    if len(content) > 10000:
        return jsonify({"error": "Content too long"}), 400
    try:
        result = call_ai(HEADLINE_PROMPT.format(content=content))
        return jsonify({"result": result})
    except Exception as e:
        log.error(f"Headline error: {e}")
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
