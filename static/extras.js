/* Secret Feeds: posting log, pacing guard, extra checks, one-click send from X.
 *
 * The log lives in this browser (localStorage), so each device keeps its own.
 * Numbers come from X's published code (xai-org/x-algorithm):
 *  - each follower's For You only draws on your 50 most recent original posts from the
 *    last 48 hours (thunder/config.rs), so ~25 a day is the useful ceiling;
 *  - the bot detector watches for bursts and machine-regular timing (bdsm/), so gaps vary.
 */
(function () {
  const KEY = 'sf_posting_log_v1';
  const MIN = 60e3, DAY = 24 * 60 * MIN, H48 = 2 * DAY;
  const DAILY_SOFT = 20, DAILY_MAX = 25, WINDOW_48H = 50;
  const MIN_GAP_MIN = 10;
  const SAME_STORY = 0.3;

  // ── storage ──────────────────────────────────────────────────────────────
  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; }
  }
  function save(log) {
    try { localStorage.setItem(KEY, JSON.stringify(log.filter(e => Date.now() - e.t < 14 * DAY).slice(-500))); }
    catch (e) { /* private window or storage blocked: the tool still works, just without a log */ }
  }
  const originals = log => log.filter(e => e.kind !== 'reply');

  // ── text helpers ─────────────────────────────────────────────────────────
  const STOP = new Set(('the a an and or of to in on at for with by from as is are was were be been it its this that ' +
    'these those after before over under into than then says said say will would could has have had not no but if ' +
    'about against between during amid per via new his her their they he she we you our who what when where why how').split(' '));
  function plain(t) { return (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  function keyWords(t) { return (plain(t).match(/[\p{L}\p{N}]+/gu) || []).filter(w => w.length > 2 && !STOP.has(w)); }
  function similarity(a, b) {
    const A = new Set(keyWords(a)), B = new Set(keyWords(b));
    if (!A.size || !B.size) return 0;
    let shared = 0; A.forEach(w => { if (B.has(w)) shared++; });
    return shared / (A.size + B.size - shared);
  }
  function opening(t) {
    const words = plain(t).replace(/[^\p{L}\p{N}\s]/gu, ' ').trim().split(/\s+/);
    return words.slice(0, 2).join(' ');
  }
  function hhmm(ms) { return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  function ago(ms) {
    const m = Math.round((Date.now() - ms) / MIN);
    if (m < 1) return 'just now';
    if (m < 60) return m + ' min ago';
    const h = Math.floor(m / 60);
    return h + ' h ' + (m % 60) + ' min ago';
  }
  function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // ── Posted button ────────────────────────────────────────────────────────
  window.markPosted = function (outputId, kind, btn) {
    const out = document.getElementById(outputId);
    const text = (out && out.textContent || '').trim();
    if (!text) return;
    let log = load();
    if (btn.dataset.entry) {                       // second click = undo
      log = log.filter(e => e.id !== btn.dataset.entry);
      save(log); resetPosted(btn); render(); return;
    }
    const now = Date.now();
    const entry = { id: now.toString(36) + Math.random().toString(36).slice(2, 6), t: now, text, kind,
                    format: out.dataset.format || '' };
    if (kind !== 'reply') {
      // Suggest a varied gap, 25 to 45 minutes, so posting times don't fall into a fixed rhythm.
      entry.next = now + (25 + Math.floor(Math.random() * 21)) * MIN;
    }
    log.push(entry); save(log);
    btn.dataset.entry = entry.id;
    btn.textContent = 'Posted ✓ (undo)';
    btn.classList.add('posted');
    render();
  };
  function resetPosted(btn) {
    delete btn.dataset.entry;
    btn.textContent = 'Mark as posted';
    btn.classList.remove('posted');
  }

  // ── Pacing bar + log list ───────────────────────────────────────────────
  function render() {
    const bar = document.getElementById('pace-bar');
    if (!bar) return;
    const log = load(), now = Date.now();
    const orig = originals(log);
    const n24 = orig.filter(e => now - e.t < DAY).length;
    const n48 = orig.filter(e => now - e.t < H48).length;
    const r24 = log.filter(e => e.kind === 'reply' && now - e.t < DAY).length;
    const last = orig[orig.length - 1];

    const level24 = n24 >= DAILY_MAX ? 'bad' : n24 >= DAILY_SOFT ? 'warn' : 'ok';
    const bits = [
      `<span class="pace ${level24}"><b>${n24}</b> ${n24 === 1 ? 'post' : 'posts'} in 24h</span>`,
      `<span class="pace ${n48 >= WINDOW_48H ? 'bad' : n48 >= 40 ? 'warn' : 'ok'}"><b>${n48}</b>/50 in 48h</span>`,
    ];
    if (r24) bits.push(`<span class="pace ok"><b>${r24}</b> ${r24 === 1 ? 'reply' : 'replies'}</span>`);
    let msg = '';
    if (last) {
      const gapMin = (now - last.t) / MIN;
      bits.push(`<span class="pace ${gapMin < MIN_GAP_MIN ? 'warn' : 'ok'}">last ${ago(last.t)}</span>`);
      if (last.next) {
        bits.push(last.next > now
          ? `<span class="pace warn">next after <b>${hhmm(last.next)}</b></span>`
          : `<span class="pace ok">ready to post</span>`);
      }
      if (gapMin < MIN_GAP_MIN) msg = 'Under 10 minutes since your last post. Fine for breaking news; otherwise wait. Bursts of posts look automated.';
    }
    if (n24 >= DAILY_MAX) msg = `${n24} posts in 24 hours. Followers' For You only uses your 50 newest posts from the last 48 hours, so extra posts push your earlier ones out before they're seen.`;
    else if (n48 >= WINDOW_48H) msg = '50 posts in 48 hours: new posts now push older ones out of followers\' For You.';
    bits.push(`<button class="link-btn" onclick="toggleLog()">Log (${log.filter(e => now - e.t < H48).length})</button>`);
    bar.innerHTML = `<div class="pace-row">${bits.join('<span class="sep">·</span>')}</div>` +
      (msg ? `<div class="pace-msg">${esc(msg)}</div>` : '');
    renderLog(log);
  }

  function renderLog(log) {
    const box = document.getElementById('log-list');
    if (!box) return;
    const now = Date.now();
    const recent = log.filter(e => now - e.t < H48).slice().reverse();
    if (!recent.length) { box.innerHTML = '<p class="note">Nothing logged in the last 48 hours. Press "Mark as posted" after you post on X.</p>'; return; }
    box.innerHTML = recent.map(e => `
      <div class="log-item">
        <span class="log-time">${hhmm(e.t)}</span>
        <span class="log-kind">${e.kind === 'reply' ? 'reply' : e.kind === 'quote' ? 'quote' : 'post'}</span>
        <span class="log-text">${esc(e.text.slice(0, 110))}${e.text.length > 110 ? '…' : ''}</span>
        <button class="link-btn" title="Remove" onclick="removeLogEntry('${e.id}')">✕</button>
      </div>`).join('') +
      '<div class="log-foot"><span class="note">Stored in this browser only.</span><button class="link-btn" onclick="clearLog()">Clear log</button></div>';
  }

  window.toggleLog = function () {
    const panel = document.getElementById('log-panel');
    panel.hidden = !panel.hidden;
    render();
  };
  window.removeLogEntry = function (id) {
    save(load().filter(e => e.id !== id));
    document.querySelectorAll(`.posted-btn[data-entry="${id}"]`).forEach(resetPosted);
    render();
  };
  window.clearLog = function () {
    if (!confirm('Clear your posting log on this device?')) return;
    save([]); document.querySelectorAll('.posted-btn').forEach(resetPosted); render();
  };

  // ── Checks that need your posting history ───────────────────────────────
  // Called after every new result. Adds warnings to the result's warnings box.
  window.afterResult = function (outputId, warningsId) {
    const out = document.getElementById(outputId);
    if (!out) return;
    const card = out.closest('.result-card, .thread-post');
    if (card) card.querySelectorAll('.posted-btn').forEach(resetPosted);

    const text = out.textContent.trim();
    const log = load(), now = Date.now();
    const recent = originals(log).filter(e => now - e.t < DAY);
    const extra = [];

    // Same story already posted today?
    let best = null;
    recent.forEach(e => { const s = similarity(text, e.text); if (s >= SAME_STORY && (!best || s > best.s)) best = { s, e }; });
    if (best) {
      extra.push(`You posted a similar story at ${hhmm(best.e.t)} (${Math.round(best.s * 100)}% of key words match). ` +
        'X spreads similar posts apart, so a second post on the same story mostly competes with your first. Post it only if there is new information.');
    }

    // Repeating patterns across your recent posts (an automated look).
    const last = originals(log).slice(-5);
    if (text.endsWith('?') && last.slice(-4).filter(e => e.text.trim().endsWith('?')).length >= 2) {
      extra.push('Several of your recent posts end with a question. Skip it this time; the same pattern on every post looks automated.');
    }
    const fmt = out.dataset.format;
    if (fmt && last.length >= 3 && last.slice(-3).every(e => e.format === fmt)) {
      extra.push(`Your last 3 posts used the same format ("${fmt}"). Pick a different one for variety.`);
    }
    const open = opening(text);
    const sameOpen = last.slice(-3).find(e => open && opening(e.text) === open);
    if (sameOpen) extra.push(`Starts the same way as your post at ${hhmm(sameOpen.t)} ("${open}"). Change the opening.`);

    if (!extra.length) return;
    const box = document.getElementById(warningsId);
    const existing = box && box.style.display === 'block'
      ? Array.from(box.querySelectorAll('li')).map(li => li.textContent) : [];
    showWarnings(warningsId, existing.concat(extra));
  };

  // ── One-click send from X (bookmarklets) ────────────────────────────────
  function setupBookmarklets() {
    document.querySelectorAll('a.bm').forEach(a => {
      const tab = a.dataset.tab;
      const url = location.origin + '/?tab=' + tab + '&go=1&text=';
      a.href = "javascript:(function(){var t=String(window.getSelection()).trim();" +
        "if(!t){t=prompt('Select the post text first, or paste it here:');}" +
        "if(t){window.open('" + url + "'+encodeURIComponent(t.slice(0,4000)),'secretfeeds');}})();";
      a.addEventListener('click', ev => {
        ev.preventDefault();
        alert('Drag this button to your bookmarks bar. Then on x.com, select a post\'s text and click the bookmark.');
      });
    });
  }

  function prefillFromUrl() {
    const p = new URLSearchParams(location.search);
    const text = p.get('text');
    const tab = p.get('tab') || 'rewrite';
    const targets = {
      rewrite: ['rewrite-input', 'doRewrite', 4000],
      quote: ['quote-input', 'doQuote', 5000],
      headline: ['headline-input', 'doHeadline', 5000],
      summarise: ['summarise-input', 'doSummarise', 10000],
    };
    if (!text || !targets[tab]) return;
    const [inputId, fn, max] = targets[tab];
    switchTab(tab);
    const input = document.getElementById(inputId);
    input.value = text;
    countChars(inputId, inputId.replace('-input', '-count'), max);
    history.replaceState(null, '', location.pathname);   // a reload won't run it again
    if (p.get('go') === '1' && typeof window[fn] === 'function') window[fn]();
  }

  document.addEventListener('DOMContentLoaded', () => {
    render();
    setInterval(render, MIN);
    setupBookmarklets();
    prefillFromUrl();
  });
})();
