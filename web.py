import os
import threading
import logging
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from dotenv import load_dotenv
from generator import (
    call_ai, FORMATS, pick_format, build_rewrite_prompt,
    build_thread_prompt, build_summary_prompt, build_headline_prompt, retry_prompt,
    QUOTE_ANGLES, pick_angle, build_quote_prompt,
)
from checks import (
    check_post, clean_text, clean_pasted, unwrap_quotes,
    word_overlap, overlap_warnings, too_similar,
)
import world_facts

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
  @import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Inter:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    /* Light theme taken from the Secret Feeds logo */
    --bg: #FFF6F0; --surface: #FFFFFF; --field: #FFFCFA; --border: #F1DDD1; --border-strong: #E8CBBB;
    --brand: #FF4500;            /* logo orange: fills, borders, focus */
    --accent: #D93A00;           /* darker orange for small text, readable on white */
    --accent-soft: #FFF0E8;      /* tinted backgrounds */
    --line: #FF9A73;             /* logo divider line */
    --text: #1A1A1A; --muted: #75655D;
    --green: #15803D;
    --warn-bg: #FFF8E6; --warn-border: #F3D68C; --warn-text: #7A4B00;
    --err-bg: #FEEDE9; --err-border: #F7C3B7; --err-text: #B42318;
  }
  body { background: radial-gradient(circle at 50% -10%, #FFFFFF 0%, var(--bg) 55%) fixed; background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }
  header {
    border-bottom: 1px solid var(--border); padding: 10px 24px;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    position: sticky; top: 0; background: rgba(255,255,255,0.92); backdrop-filter: blur(8px); z-index: 10;
  }
  .logo { height: 60px; width: auto; display: block; }
  .dot { width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 0 3px rgba(21,128,61,0.15);display:inline-block;margin-right:6px; }
  .status { font-size: 0.73rem; color: var(--muted); white-space: nowrap; }
  nav { display: flex; gap: 6px; }
  .nav-btn { padding: 7px 16px; border-radius: 999px; font-size: 0.78rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: var(--surface); color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif; white-space: nowrap; }
  .nav-btn:hover { border-color: var(--line); color: var(--accent); }
  .nav-btn.active { border-color: var(--brand); color: var(--accent); background: var(--accent-soft); }
  main { max-width: 680px; margin: 0 auto; padding: 32px 20px 48px; }
  .tab { display: none; }
  .tab.active { display: block; }
  .page-title { font-family: 'Syne', sans-serif; font-size: 1.6rem; font-weight: 800; margin-bottom: 6px; color: var(--text); }
  .page-sub { color: var(--muted); font-size: 0.88rem; margin-bottom: 20px; line-height: 1.55; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 20px; margin-bottom: 14px; box-shadow: 0 1px 2px rgba(120,60,20,0.04), 0 6px 20px rgba(120,60,20,0.05); }
  label { display:block; font-size:0.7rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--muted); margin-bottom:8px; }
  textarea { width: 100%; background: var(--field); border: 1px solid var(--border-strong); border-radius: 10px; color: var(--text); font-family: 'Inter', sans-serif; font-size: 0.92rem; padding: 11px 13px; outline: none; resize: vertical; min-height: 110px; line-height: 1.6; transition: border-color 0.2s, box-shadow 0.2s; }
  textarea::placeholder { color: #A8978E; }
  textarea:focus { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(255,69,0,0.12); }
  textarea.tall { min-height: 160px; }
  .char-count { text-align: right; font-size: 0.7rem; color: var(--muted); margin-top: 5px; }
  .char-count.over { color: var(--err-text); font-weight: 600; }

  /* Toggle */
  .toggle-row { display: flex; align-items: center; gap: 10px; margin-top: 14px; margin-bottom: 2px; }
  .toggle-label { font-size: 0.8rem; color: var(--muted); }
  .toggle { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
  .toggle input { opacity: 0; width: 0; height: 0; }
  .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background: #EADCD3; border-radius: 22px; transition: .3s; border: 1px solid var(--border-strong); }
  .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 2px; bottom: 2px; background: #FFFFFF; border-radius: 50%; transition: .3s; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
  input:checked + .slider { background: var(--brand); border-color: var(--brand); }
  input:checked + .slider:before { transform: translateX(18px); }
  .toggle input:focus-visible + .slider { box-shadow: 0 0 0 3px rgba(255,69,0,0.25); }

  .btn { width: 100%; padding: 12px; border: none; border-radius: 10px; margin-top: 12px; font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 800; letter-spacing: 0.05em; cursor: pointer; background: linear-gradient(135deg, var(--brand), var(--accent)); color: #fff; transition: opacity 0.2s, box-shadow 0.2s; box-shadow: 0 4px 14px rgba(255,69,0,0.25); }
  .btn:hover { box-shadow: 0 6px 18px rgba(255,69,0,0.32); }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; box-shadow: none; }
  .btn:active { transform: scale(0.98); }
  .result-card { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--brand); border-radius: 12px; padding: 18px; margin-top: 14px; display: none; box-shadow: 0 6px 20px rgba(120,60,20,0.05); }
  .result-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); margin-bottom: 10px; }
  .result-text { font-size: 0.95rem; line-height: 1.7; color: var(--text); white-space: pre-wrap; }

  /* Thread result */
  .thread-container { display: none; margin-top: 14px; }
  .thread-post { background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--brand); border-radius: 12px; padding: 18px; margin-bottom: 10px; box-shadow: 0 6px 20px rgba(120,60,20,0.05); }
  .thread-post-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--accent); margin-bottom: 8px; }
  .thread-post-text { font-size: 0.95rem; line-height: 1.7; color: var(--text); white-space: pre-wrap; margin-bottom: 10px; }
  .thread-connector { text-align: center; color: var(--muted); font-size: 0.8rem; margin: 2px 0 10px; }

  .result-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
  .result-chars { font-size: 0.7rem; color: var(--muted); }
  .copy-btn { padding: 6px 14px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border-strong); background: var(--surface); color: var(--text); transition: all 0.2s; font-family: 'Inter', sans-serif; }
  .copy-btn:hover { border-color: var(--brand); color: var(--accent); }
  .copy-btn.copied { color: var(--green); border-color: var(--green); }
  .error { background: var(--err-bg); border: 1px solid var(--err-border); border-radius: 10px; padding: 11px 14px; font-size: 0.83rem; color: var(--err-text); margin-top: 12px; display: none; }
  .spinner { display:none; text-align:center; padding: 14px 0; color: var(--muted); font-size: 0.83rem; }
  .tip { background: var(--accent-soft); border: 1px solid #F8D8C8; border-radius: 10px; padding: 11px 14px; font-size: 0.8rem; color: #5A4A42; line-height: 1.6; margin-bottom: 18px; }
  .tip strong { color: var(--accent); }
  .tip ul { margin: 6px 0 0 18px; }
  .tip li { margin-bottom: 3px; }

  /* Format picker */
  .fmt-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
  .fmt-btn { padding: 6px 12px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; cursor: pointer; border: 1px solid var(--border-strong); background: var(--surface); color: var(--muted); transition: all 0.2s; font-family: 'Inter', sans-serif; }
  .fmt-btn:hover { border-color: var(--line); color: var(--accent); }
  .fmt-btn.active { border-color: var(--brand); color: #fff; background: var(--brand); }
  .fmt-hint { font-size: 0.72rem; color: var(--muted); margin-top: 7px; line-height: 1.5; }
  .fmt-off { opacity: 0.4; pointer-events: none; }

  /* Warnings from checks.py */
  .warnings { display: none; margin-top: 10px; padding: 10px 12px; border-radius: 10px; background: var(--warn-bg); border: 1px solid var(--warn-border); color: var(--warn-text); font-size: 0.78rem; line-height: 1.55; }
  .warnings ul { margin: 4px 0 0 16px; }
  .note { font-size: 0.75rem; color: var(--muted); margin-top: 8px; }
  .overlap { font-size: 0.74rem; margin-top: 8px; color: var(--green); font-weight: 500; }
  .overlap.high { color: var(--warn-text); }

  /* Result actions */
  .actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
  .posted-btn.posted { color: var(--green); border-color: var(--green); background: #F0FAF3; }

  /* Pacing bar and posting log */
  .pace-bar { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 10px 14px; margin-bottom: 20px; font-size: 0.78rem; color: var(--muted); }
  .pace-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
  .pace b { color: var(--text); }
  .pace.warn, .pace.warn b { color: var(--warn-text); }
  .pace.bad, .pace.bad b { color: var(--err-text); font-weight: 600; }
  .pace-msg { margin-top: 6px; color: var(--warn-text); line-height: 1.5; }
  .sep { color: var(--border-strong); }
  .link-btn { background: none; border: none; color: var(--accent); font: inherit; font-weight: 600; cursor: pointer; padding: 0 2px; }
  .link-btn:hover { text-decoration: underline; }
  .log-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 10px 14px; margin: -12px 0 20px; }
  .log-item { display: flex; gap: 10px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.8rem; }
  .log-time { color: var(--muted); font-variant-numeric: tabular-nums; }
  .log-kind { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent); min-width: 38px; }
  .log-text { flex: 1; color: var(--text); overflow-wrap: anywhere; }
  .log-foot { display: flex; justify-content: space-between; align-items: center; padding-top: 8px; }

  /* Bookmarklets */
  .bm-row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
  .bm { display: inline-block; padding: 7px 14px; border-radius: 999px; background: var(--brand); color: #fff; font-weight: 700; font-size: 0.78rem; text-decoration: none; cursor: grab; }

  /* Image card window */
  body.modal-open { overflow: hidden; }
  .modal { position: fixed; inset: 0; background: rgba(40,20,10,0.45); display: flex; align-items: center; justify-content: center; padding: 16px; z-index: 50; }
  .modal[hidden] { display: none; }
  .modal-box { background: var(--surface); border-radius: 16px; padding: 18px; width: min(720px, 100%); max-height: calc(100vh - 32px); overflow: auto; box-shadow: 0 20px 60px rgba(60,20,0,0.25); }
  .modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
  .icon-btn { background: none; border: 1px solid var(--border); border-radius: 999px; width: 32px; height: 32px; cursor: pointer; color: var(--muted); font-size: 0.9rem; }
  #card-canvas { max-width: 100%; max-height: 58vh; width: auto; height: auto; display: block; margin: 12px auto; border-radius: 10px; border: 1px solid var(--border); }
  .modal-actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .modal-actions .btn { width: auto; flex: 1; margin-top: 0; padding: 10px 14px; font-size: 0.8rem; }
  .btn.secondary { background: var(--surface); color: var(--accent); border: 1px solid var(--brand); box-shadow: none; }

  /* Phones: logo and status on one row, tabs on the next */
  @media (max-width: 600px) {
    header { flex-wrap: wrap; padding: 8px 16px; }
    .logo { height: 48px; }
    nav { order: 3; width: 100%; }
    nav { gap: 4px; }
    .nav-btn { flex: 1; padding: 7px 2px; font-size: 0.74rem; }
    .actions .copy-btn { padding: 6px 10px; }
    main { padding: 24px 16px 40px; }
  }
</style>
</head>
<body>
<header>
  <img class="logo" src="/logo.png" alt="Secret Feeds" width="85" height="60">
  <nav>
    <button class="nav-btn active" id="nav-rewrite" onclick="switchTab('rewrite')">Rewrite</button>
    <button class="nav-btn" id="nav-quote" onclick="switchTab('quote')">Quote</button>
    <button class="nav-btn" id="nav-headline" onclick="switchTab('headline')">Headline</button>
    <button class="nav-btn" id="nav-summarise" onclick="switchTab('summarise')">Summarise</button>
  </nav>
  <span><span class="dot"></span><span class="status">Live</span></span>
</header>

<main>
  <div class="pace-bar" id="pace-bar"></div>
  <div class="log-panel" id="log-panel" hidden><div id="log-list"></div></div>

  <!-- REWRITE TAB -->
  <div class="tab active" id="tab-rewrite">
    <div class="page-title">Rewrite</div>
    <p class="page-sub">Paste any news tweet or quote. Direct quotes are kept exactly — news facts are rewritten in the Secret Feeds voice.</p>
    <div class="tip">
      <strong>Smart detection:</strong> If you paste a direct quote (e.g. <em>Rubio: "Our policy is an eye for an eye"</em>), it's kept word-for-word. News facts are rewritten in a fresh voice. <strong>Auto</strong> rotates between formats so your timeline doesn't repeat the same shape every post.
    </div>
    <div class="card">
      <label>Original Tweet or Quote</label>
      <textarea id="rewrite-input" placeholder='Paste a news tweet or direct quote...' oninput="countChars('rewrite-input','rewrite-count',4000)"></textarea>
      <div class="char-count" id="rewrite-count">0 / 4000</div>

      <div class="fmt-row" id="fmt-row">
        <button class="fmt-btn active" data-format="auto" onclick="pickFormat(this)">Auto (mix it up)</button>
        {% for key, f in formats.items() %}
        <button class="fmt-btn" data-format="{{ key }}" onclick="pickFormat(this)">{{ f.label }}</button>
        {% endfor %}
      </div>
      <div class="fmt-hint" id="fmt-hint">Most posts should be straight news or news + context. Use a question when the story has a real open question.</div>

      <div class="toggle-row">
        <label class="toggle">
          <input type="checkbox" id="thread-toggle" onchange="toggleThread(this)">
          <span class="slider"></span>
        </label>
        <span class="toggle-label">Add a follow-up reply (only your followers see replies; Post 1 must stand alone)</span>
      </div>

      <button class="btn" id="rewrite-btn" onclick="doRewrite()">Rewrite for Secret Feeds</button>
    </div>
    <div class="spinner" id="rewrite-spinner">⏳ Writing...</div>
    <div class="error" id="rewrite-error"></div>

    <!-- Single post result -->
    <div class="result-card" id="rewrite-result">
      <div class="result-label" id="rewrite-label">Rewritten Post</div>
      <div class="result-text" id="rewrite-output"></div>
      <div class="result-meta">
        <span class="result-chars" id="rewrite-chars"></span>
        <div class="actions">
          <button class="copy-btn" onclick="copyText('rewrite-output', this)">Copy</button>
          <button class="copy-btn" onclick="openCard('rewrite-output')">Image</button>
          <button class="copy-btn posted-btn" onclick="markPosted('rewrite-output', 'post', this)">Mark as posted</button>
        </div>
      </div>
      <div class="note" id="rewrite-note" style="display:none"></div>
      <div class="overlap" id="rewrite-overlap"></div>
      <div class="warnings" id="rewrite-warnings"></div>
    </div>

    <!-- Thread result -->
    <div class="thread-container" id="thread-result">
      <div class="thread-post">
        <div class="thread-post-label">Post 1 — What everyone sees</div>
        <div class="thread-post-text" id="thread-post1"></div>
        <div class="result-meta">
          <span class="result-chars" id="thread-chars1"></span>
          <div class="actions">
          <button class="copy-btn" onclick="copyText('thread-post1', this)">Copy</button>
          <button class="copy-btn" onclick="openCard('thread-post1')">Image</button>
          <button class="copy-btn posted-btn" onclick="markPosted('thread-post1', 'post', this)">Mark as posted</button>
        </div>
        </div>
        <div class="overlap" id="thread-overlap"></div>
        <div class="note" id="thread-note" style="display:none"></div>
        <div class="warnings" id="thread-warnings1"></div>
      </div>
      <div class="thread-connector">↓ reply to your own post</div>
      <div class="thread-post">
        <div class="thread-post-label">Post 2 — Reply (followers only)</div>
        <div class="thread-post-text" id="thread-post2"></div>
        <div class="result-meta">
          <span class="result-chars" id="thread-chars2"></span>
          <div class="actions">
          <button class="copy-btn" onclick="copyText('thread-post2', this)">Copy</button>
          <button class="copy-btn posted-btn" onclick="markPosted('thread-post2', 'reply', this)">Mark as posted</button>
        </div>
        </div>
        <div class="warnings" id="thread-warnings2"></div>
      </div>
    </div>

    <div class="tip" style="margin-top:18px">
      <strong>Before you post</strong> (from X's published ranking code)
      <ul>
        <li>Post fast. For You never shows posts older than 48 hours.</li>
        <li>Media flagged as graphic violence is dropped for non-followers. Describe it, or use a non-graphic image.</li>
        <li>Attribute every claim. A predicted report costs a post more than any other action.</li>
        <li>Don't re-upload other accounts' videos or photos. Media removed for copyright (DMCA) takes the post out of For You. Use your own image, or quote-post the original.</li>
        <li>Check names and titles. World leaders update daily from Wikidata; add ministers and anyone else you cover often to <em>current_facts.txt</em>.</li>
      </ul>
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
        <div class="actions">
          <button class="copy-btn" onclick="copyText('summarise-output', this)">Copy</button>
          <button class="copy-btn" onclick="openCard('summarise-output')">Image</button>
          <button class="copy-btn posted-btn" onclick="markPosted('summarise-output', 'post', this)">Mark as posted</button>
        </div>
      </div>
      <div class="overlap" id="summarise-overlap"></div>
      <div class="note" id="summarise-note" style="display:none"></div>
      <div class="warnings" id="summarise-warnings"></div>
    </div>
  </div>

  <!-- QUOTE TAB -->
  <div class="tab" id="tab-quote">
    <div class="page-title">Quote</div>
    <p class="page-sub">Paste a post you want to quote. Get a short take of your own to post on top of it.</p>
    <div class="tip">
      <strong>Why quote:</strong> a quote post counts as your own post, so X can show it to people who don't follow you. Reposts and replies only reach your followers. Your text is new, so there's no duplicate risk, and the original's author gets credit.
    </div>
    <div class="card">
      <label>Post to Quote</label>
      <textarea id="quote-input" placeholder="Paste the post you'll quote..." oninput="countChars('quote-input','quote-count',5000)"></textarea>
      <div class="char-count" id="quote-count">0 / 5000</div>
      <div class="fmt-row" id="angle-row">
        <button class="fmt-btn active" data-angle="auto" onclick="pickAngle(this)">Auto</button>
        <button class="fmt-btn" data-angle="context" onclick="pickAngle(this)">Context</button>
        <button class="fmt-btn" data-angle="question" onclick="pickAngle(this)">Question</button>
      </div>
      <div class="fmt-hint">Context adds one fact the original doesn't say. Question asks something both sides could answer.</div>
      <button class="btn" id="quote-btn" onclick="doQuote()">Write Quote Post</button>
    </div>
    <div class="spinner" id="quote-spinner">⏳ Writing...</div>
    <div class="error" id="quote-error"></div>
    <div class="result-card" id="quote-result">
      <div class="result-label" id="quote-label">Quote Post</div>
      <div class="result-text" id="quote-output"></div>
      <div class="result-meta">
        <span class="result-chars" id="quote-chars"></span>
        <div class="actions">
          <button class="copy-btn" onclick="copyText('quote-output', this)">Copy</button>
          <button class="copy-btn posted-btn" onclick="markPosted('quote-output', 'quote', this)">Mark as posted</button>
        </div>
      </div>
      <div class="note">On X: open the original post, tap Repost, choose Quote, paste this.</div>
      <div class="overlap" id="quote-overlap"></div>
      <div class="note" id="quote-note" style="display:none"></div>
      <div class="warnings" id="quote-warnings"></div>
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
        <div class="actions">
          <button class="copy-btn" onclick="copyText('headline-output', this)">Copy</button>
          <button class="copy-btn" onclick="openCard('headline-output')">Image</button>
          <button class="copy-btn posted-btn" onclick="markPosted('headline-output', 'post', this)">Mark as posted</button>
        </div>
      </div>
      <div class="overlap" id="headline-overlap"></div>
      <div class="note" id="headline-note" style="display:none"></div>
      <div class="warnings" id="headline-warnings"></div>
    </div>
  </div>
  <div class="tip" style="margin-top:28px">
    <strong>One click from X</strong> (on a computer)
    <p style="margin-top:4px">Drag a button to your browser's bookmarks bar. On x.com, select a post's text and click the bookmark: this page opens with the text in and starts writing.</p>
    <div class="bm-row">
      <a class="bm" data-tab="rewrite" href="#">SF Rewrite</a>
      <a class="bm" data-tab="quote" href="#">SF Quote</a>
      <a class="bm" data-tab="headline" href="#">SF Headline</a>
    </div>
  </div>
</main>

<div class="modal" id="card-modal" hidden onclick="if(event.target===this)closeCard()">
  <div class="modal-box" role="dialog" aria-label="Image for your post">
    <div class="modal-head"><strong>Image for your post</strong><button class="icon-btn" onclick="closeCard()" aria-label="Close">✕</button></div>
    <div class="fmt-row" style="margin-top:0">
      <button class="fmt-btn active" data-size="wide" onclick="cardSize(this)">Wide 16:9</button>
      <button class="fmt-btn" data-size="tall" onclick="cardSize(this)">Tall 4:5</button>
    </div>
    <canvas id="card-canvas"></canvas>
    <div class="modal-actions">
      <button class="btn" onclick="cardDownload()">Download</button>
      <button class="btn secondary" onclick="cardCopy(this)">Copy image</button>
      <button class="btn secondary" id="card-share-btn" onclick="cardShare()" hidden>Share to X</button>
    </div>
    <p class="note">Attach it to your post on X. Tall images usually fill more of the screen on phones.</p>
  </div>
</div>

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

let selectedFormat = 'auto';

function pickFormat(btn) {
  btn.parentElement.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedFormat = btn.dataset.format;
}

let selectedAngle = 'auto';

function pickAngle(btn) {
  btn.parentElement.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  selectedAngle = btn.dataset.angle;
}

const FMT_HINT = 'Most posts should be straight news or news + context. Use a question when the story has a real open question.';

function toggleThread(box) {
  document.getElementById('fmt-row').classList.toggle('fmt-off', box.checked);
  document.getElementById('fmt-hint').textContent = box.checked
    ? 'Follow-up mode writes a standalone Post 1 plus a reply, so the format buttons are off.'
    : FMT_HINT;
}

function showOverlap(id, o) {
  const el = document.getElementById(id);
  if (!o) { el.textContent = ''; return; }
  const high = o.percent >= 60 || o.longest_run >= 6;
  const words = o.percent + '% of the words match the tweet you pasted';
  const quotes = (high && o.has_quote) ? ' (the quote has to stay, so add a line of your own)' : '';
  el.className = 'overlap' + (high ? ' high' : '');
  if (high) el.textContent = '⚠ Too similar to the original: ' + words + quotes + '. Change more words or regenerate.';
  else if (o.percent < 40) el.textContent = '✓ Low duplicate risk: only ' + words + quotes + '.';
  else el.textContent = '✓ OK: ' + words + quotes + '. Lower is safer.';
  el.title = 'Duplicate check. X flags posts that use the same words as other posts, in any order. A straight copy scores close to 100%.';
}

function showNote(id, text) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text || '';
  el.style.display = text ? 'block' : 'none';
}

function showWarnings(id, warnings) {
  const el = document.getElementById(id);
  if (!warnings || !warnings.length) { el.style.display = 'none'; el.innerHTML = ''; return; }
  const ul = document.createElement('ul');
  warnings.forEach(w => { const li = document.createElement('li'); li.textContent = w; ul.appendChild(li); });
  el.innerHTML = '<strong>Check before posting:</strong>';
  el.appendChild(ul);
  el.style.display = 'block';
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
      body: JSON.stringify({ tweet, thread: asThread, format: selectedFormat })
    });
    const data = await resp.json();
    if (data.error) throw new Error(data.error);

    if (data.is_thread && data.post1 && data.post2) {
      document.getElementById('thread-post1').textContent = data.post1;
      document.getElementById('thread-post2').textContent = data.post2;
      document.getElementById('thread-chars1').textContent = data.post1.length + ' / 280 chars';
      document.getElementById('thread-chars2').textContent = data.post2.length + ' chars';
      showOverlap('thread-overlap', data.overlap);
      showNote('thread-note', data.note);
      showWarnings('thread-warnings1', data.warnings1);
      showWarnings('thread-warnings2', data.warnings2);
      document.getElementById('thread-post1').dataset.format = 'Post + reply';
      document.getElementById('thread-result').style.display = 'block';
      afterResult('thread-post1', 'thread-warnings1');
      afterResult('thread-post2', 'thread-warnings2');
    } else {
      document.getElementById('rewrite-label').textContent =
        'Rewritten Post' + (data.format_label ? ' · ' + data.format_label : '');
      document.getElementById('rewrite-output').textContent = data.result;
      document.getElementById('rewrite-chars').textContent = data.result.length + ' / 4000 chars';
      const note = document.getElementById('rewrite-note');
      if (data.note) { note.textContent = data.note; note.style.display = 'block'; }
      else { note.style.display = 'none'; }
      showOverlap('rewrite-overlap', data.overlap);
      showWarnings('rewrite-warnings', data.warnings);
      document.getElementById('rewrite-output').dataset.format = data.format_label || '';
      document.getElementById('rewrite-result').style.display = 'block';
      afterResult('rewrite-output', 'rewrite-warnings');
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

async function callEndpoint(endpoint, payload, btnId, spinnerId, errorId, resultId, outputId, charsId, warningsId, limit, formatName) {
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
    document.getElementById(charsId).textContent = data.result.length + ' / ' + limit + ' chars';
    showOverlap(warningsId.replace('-warnings', '-overlap'), data.overlap);
    showNote(warningsId.replace('-warnings', '-note'), data.note);
    showWarnings(warningsId, data.warnings);
    document.getElementById(outputId).dataset.format = data.angle_label ? 'Quote: ' + data.angle_label : (formatName || '');
    if (data.angle_label) document.getElementById('quote-label').textContent = 'Quote Post · ' + data.angle_label;
    document.getElementById(resultId).style.display = 'block';
    afterResult(outputId, warningsId);
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
  callEndpoint('/summarise', { content }, 'summarise-btn', 'summarise-spinner', 'summarise-error', 'summarise-result', 'summarise-output', 'summarise-chars', 'summarise-warnings', 280, 'Summary');
}

function doHeadline() {
  const content = document.getElementById('headline-input').value.trim();
  if (!content) return;
  callEndpoint('/headline', { content }, 'headline-btn', 'headline-spinner', 'headline-error', 'headline-result', 'headline-output', 'headline-chars', 'headline-warnings', 280, 'Headline');
}

function doQuote() {
  const content = document.getElementById('quote-input').value.trim();
  if (!content) return;
  callEndpoint('/quote', { content, angle: selectedAngle }, 'quote-btn', 'quote-spinner', 'quote-error', 'quote-result', 'quote-output', 'quote-chars', 'quote-warnings', 280);
}

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) {
    const active = document.querySelector('.tab.active').id;
    if (active === 'tab-rewrite') doRewrite();
    else if (active === 'tab-summarise') doSummarise();
    else if (active === 'tab-quote') doQuote();
    else doHeadline();
  }
});
</script>
<script src="/static/extras.js"></script>
<script src="/static/cards.js"></script>
</body>
</html>"""


RETRIED_NOTE = "The first draft copied too much of the tweet you pasted, so it was rewritten again."
STILL_CLOSE_NOTE = "Tried twice and it's still close to the tweet you pasted. Edit it by hand or press the button again."


def _tidy(text: str) -> str:
    return unwrap_quotes(clean_text(text))


def _generate(prompt: str, source: str, thread: bool = False) -> tuple[str, str]:
    """Call the AI and tidy the result. If it's too close to the pasted tweet
    (X would see a duplicate), ask once more with the first draft attached."""
    first_post = lambda r: r.split("---THREAD---", 1)[0] if thread else r
    result = _tidy(call_ai(prompt))
    o = word_overlap(source, first_post(result))
    if not too_similar(o):
        return result, ""
    try:
        second = _tidy(call_ai(retry_prompt(prompt, first_post(result), o["percent"])))
    except Exception as e:
        log.warning(f"Retry after a too-similar draft failed: {e}")
        return result, STILL_CLOSE_NOTE
    o2 = word_overlap(source, first_post(second))
    if o2["percent"] < o["percent"]:
        return second, (STILL_CLOSE_NOTE if too_similar(o2) else RETRIED_NOTE)
    return result, STILL_CLOSE_NOTE


def _with_overlap(payload: dict, original: str, text: str, key: str = "warnings") -> dict:
    """Add the duplicate check (words shared with the pasted original) to a response."""
    o = word_overlap(original, text)
    payload["overlap"] = o
    payload[key] = overlap_warnings(o) + payload.get(key, [])
    return payload


@app.route("/")
def index():
    return render_template_string(HTML, formats=FORMATS)


@app.route("/favicon.png")
def favicon():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "favicon.png",
        mimetype="image/png"
    )


@app.route("/logo.png")
def logo():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "logo.png",
        mimetype="image/png"
    )


@app.route("/rewrite", methods=["POST"])
def rewrite_endpoint():
    data = request.get_json()
    tweet = clean_pasted((data or {}).get("tweet", ""))
    as_thread = (data or {}).get("thread", False)
    requested_format = (data or {}).get("format", "auto")
    if not tweet:
        return jsonify({"error": "No tweet provided"}), 400
    if len(tweet) > 5000:
        return jsonify({"error": "Text too long"}), 400
    try:
        if as_thread:
            result, retried = _generate(build_thread_prompt(tweet), tweet, thread=True)
            parts = result.split("---THREAD---", 1)
            post1 = _tidy(parts[0])
            post2 = _tidy(parts[1]) if len(parts) > 1 else ""
            if post2:
                return jsonify(_with_overlap({
                    "result": result,
                    "post1": post1,
                    "post2": post2,
                    "is_thread": True,
                    "note": retried,
                    "warnings1": check_post(post1, limit=280, standalone=True),
                    "warnings2": check_post(post2),
                }, tweet, post1, key="warnings1"))
            # The prompt tells the model to skip Post 2 when the input has nothing
            # more to say. Use Post 1 as a single post instead of spending a second call.
            return jsonify(_with_overlap({
                "result": post1,
                "is_thread": False,
                "note": "No follow-up: the source didn't have enough for a second post, so this is a single post."
                        + (" " + retried if retried else ""),
                "warnings": check_post(post1, limit=280, standalone=True),
            }, tweet, post1))
        fmt = pick_format(requested_format)
        result, retried = _generate(build_rewrite_prompt(tweet, fmt), tweet)
        return jsonify(_with_overlap({
            "result": result,
            "is_thread": False,
            "format": fmt,
            "format_label": FORMATS[fmt]["label"],
            "note": retried,
            "warnings": check_post(result),
        }, tweet, result))
    except Exception as e:
        log.error(f"Rewrite error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/summarise", methods=["POST"])
def summarise_endpoint():
    data = request.get_json()
    content = clean_pasted((data or {}).get("content", ""))
    if not content:
        return jsonify({"error": "No content provided"}), 400
    if len(content) > 15000:
        return jsonify({"error": "Content too long — paste a shorter section"}), 400
    try:
        result, retried = _generate(build_summary_prompt(content), content)
        return jsonify(_with_overlap({"result": result, "note": retried,
                                      "warnings": check_post(result, limit=280)}, content, result))
    except Exception as e:
        log.error(f"Summarise error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/headline", methods=["POST"])
def headline_endpoint():
    data = request.get_json()
    content = clean_pasted((data or {}).get("content", ""))
    if not content:
        return jsonify({"error": "No content provided"}), 400
    if len(content) > 10000:
        return jsonify({"error": "Content too long"}), 400
    try:
        result, retried = _generate(build_headline_prompt(content), content)
        return jsonify(_with_overlap({"result": result, "note": retried,
                                      "warnings": check_post(result, limit=280)}, content, result))
    except Exception as e:
        log.error(f"Headline error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/quote", methods=["POST"])
def quote_endpoint():
    """A short take to post as a quote of the original (X shows the original underneath)."""
    data = request.get_json()
    content = clean_pasted((data or {}).get("content", ""))
    if not content:
        return jsonify({"error": "No post provided"}), 400
    if len(content) > 5000:
        return jsonify({"error": "Text too long"}), 400
    try:
        angle = pick_angle((data or {}).get("angle", "auto"))
        result, retried = _generate(build_quote_prompt(content, angle), content)
        return jsonify(_with_overlap({
            "result": result,
            "angle": angle,
            "angle_label": QUOTE_ANGLES[angle]["label"],
            "note": retried,
            "warnings": check_post(result, limit=280),
        }, content, result))
    except Exception as e:
        log.error(f"Quote error: {e}")
        return jsonify({"error": "AI rate limit reached. Please wait 1-2 minutes and try again."}), 500


@app.route("/facts")
def facts_status():
    """Check the world-leaders data from a browser: /facts?q=Hungarian+PM+resigns"""
    q = request.args.get("q", "")
    return jsonify({
        "world_leaders_updated": world_facts._cache.get("fetched_at"),
        "countries_loaded": len(world_facts._cache.get("countries", [])),
        "matched_for_q": world_facts.facts_for(q) if q else "add ?q=some headline to test matching",
    })


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def start_web():
    world_facts.start_background_refresh()
    port = int(os.getenv("PORT", 5000))
    log.info(f"🌐 Web interface running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_web_in_background():
    thread = threading.Thread(target=start_web, daemon=True)
    thread.start()
