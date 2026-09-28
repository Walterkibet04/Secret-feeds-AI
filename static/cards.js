/* Secret Feeds: branded image cards for posts.
 *
 * Draws the post's headline on a card with your logo, in the browser (no server work).
 * Why: a photo people tap and a post they stop to read both count in X's ranking
 * (photo_expand and dwell time in home-mixer/params/param.rs), and using your own image
 * avoids re-uploading other accounts' media, which can be removed for copyright.
 */
(function () {
  const SIZES = { wide: [1200, 675], tall: [1080, 1350] };
  const BRAND = { orange: '#FF4500', orangeText: '#D93A00', ink: '#1A1A1A', body: '#4F423B',
                  muted: '#75655D', line: '#FF9A73', bgIn: '#FFF9F5', bgOut: '#FFE7D6' };
  const FONT = 'Inter, "Helvetica Neue", Arial, sans-serif';
  // Emojis (flags included) don't draw reliably on every computer, so they're left off the card.
  const EMOJI = /[\p{Extended_Pictographic}\u{1F1E6}-\u{1F1FF}\u{FE0F}\u{200D}\u{20E3}]/gu;

  const state = { text: '', size: 'wide', blob: null };
  const logo = new Image();
  logo.src = '/logo.png';

  function countries(text) {
    const ri = Array.from(text).map(c => c.codePointAt(0)).filter(c => c >= 0x1F1E6 && c <= 0x1F1FF);
    const codes = [];
    for (let i = 0; i + 1 < ri.length; i += 2) {
      codes.push(String.fromCharCode(65 + ri[i] - 0x1F1E6, 65 + ri[i + 1] - 0x1F1E6));
    }
    let names = null;
    try { names = new Intl.DisplayNames(['en'], { type: 'region' }); } catch (e) { /* old browser */ }
    return Array.from(new Set(codes)).map(c => { try { return names ? names.of(c) : c; } catch (e) { return c; } });
  }

  function split(text) {
    const paras = text.split(/\n\s*\n/)
      .map(p => p.replace(EMOJI, '').replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    return { head: paras[0] || '', body: paras.slice(1).join(' ') };
  }

  function wrap(ctx, text, maxW) {
    const words = text.split(' ');
    const lines = [];
    let line = '';
    for (const w of words) {
      const test = line ? line + ' ' + w : w;
      if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; }
      else line = test;
    }
    if (line) lines.push(line);
    return lines;
  }

  // Largest font size (between max and min) at which the text fits the box.
  function fit(ctx, text, weight, maxW, maxH, maxSize, minSize, lh) {
    for (let size = maxSize; size >= minSize; size -= 2) {
      ctx.font = `${weight} ${size}px ${FONT}`;
      const lines = wrap(ctx, text, maxW);
      if (lines.length * size * lh <= maxH) return { size, lines };
    }
    ctx.font = `${weight} ${minSize}px ${FONT}`;
    let lines = wrap(ctx, text, maxW);
    const maxLines = Math.max(1, Math.floor(maxH / (minSize * lh)));
    if (lines.length > maxLines) {
      lines = lines.slice(0, maxLines);
      lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, '') + '…';
    }
    return { size: minSize, lines };
  }

  async function draw() {
    const canvas = document.getElementById('card-canvas');
    const [W, H] = SIZES[state.size];
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');
    try {
      await Promise.all([document.fonts.load(`800 60px Inter`), document.fonts.load(`500 30px Inter`),
                         document.fonts.load(`700 24px Inter`)]);
    } catch (e) { /* falls back to Arial */ }
    if (!logo.complete) await new Promise(r => { logo.onload = logo.onerror = r; });

    const pad = Math.round(Math.min(W, H) * 0.1);
    const { head, body } = split(state.text);
    const places = countries(state.text);

    // Background: the logo's cream, a little lighter in the middle.
    const g = ctx.createRadialGradient(W * 0.45, H * 0.35, 0, W * 0.45, H * 0.35, Math.max(W, H) * 0.85);
    g.addColorStop(0, BRAND.bgIn); g.addColorStop(1, BRAND.bgOut);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = BRAND.orange; ctx.fillRect(0, 0, W, Math.round(H * 0.012) + 4);

    // Top row: countries (from the post's flags) and today's date.
    const small = Math.round(Math.min(W, H) * 0.036);
    let y = pad;
    ctx.textBaseline = 'top';
    ctx.font = `700 ${small}px ${FONT}`;
    if ('letterSpacing' in ctx) ctx.letterSpacing = '2px';
    ctx.fillStyle = BRAND.orangeText; ctx.textAlign = 'left';
    ctx.fillText((places.length ? places.slice(0, 3).join('  ·  ') : 'World news').toUpperCase(), pad, y);
    ctx.fillStyle = BRAND.muted; ctx.textAlign = 'right';
    ctx.fillText(new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }).toUpperCase(), W - pad, y);
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    ctx.textAlign = 'left';

    // Bottom: divider and logo.
    const logoH = Math.round(Math.min(W, H) * 0.13);
    const logoW = logo.naturalWidth ? Math.round(logoH * logo.naturalWidth / logo.naturalHeight) : 0;
    const footTop = H - pad - logoH;
    ctx.strokeStyle = BRAND.line; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(pad, footTop - 28); ctx.lineTo(W - pad, footTop - 28); ctx.stroke();
    if (logoW) ctx.drawImage(logo, pad, footTop, logoW, logoH);

    // Middle: headline, then the rest of the post if it fits.
    const top = y + small + Math.round(H * 0.06);
    const bottom = footTop - 28 - Math.round(H * 0.05);
    const maxW = W - pad * 2;
    const room = bottom - top;
    const headRoom = body ? room * 0.66 : room;
    const big = state.size === 'tall' ? 92 : 74;
    const h = fit(ctx, head, 800, maxW, headRoom, big, 34, 1.16);
    ctx.fillStyle = BRAND.ink; ctx.font = `800 ${h.size}px ${FONT}`;
    let ty = top;
    h.lines.forEach(line => { ctx.fillText(line, pad, ty); ty += h.size * 1.16; });

    const left = bottom - ty - Math.round(H * 0.03);
    if (body && left > 60) {
      ty += Math.round(H * 0.03);
      const b = fit(ctx, body, 500, maxW, left, state.size === 'tall' ? 40 : 32, 24, 1.4);
      ctx.fillStyle = BRAND.body; ctx.font = `500 ${b.size}px ${FONT}`;
      b.lines.forEach(line => { ctx.fillText(line, pad, ty); ty += b.size * 1.4; });
    }

    state.blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
  }

  function fileName() {
    const slug = split(state.text).head.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      .replace(/[^a-z0-9]+/g, '-').slice(0, 40).replace(/^-+|-+$/g, '');
    return `secret-feeds-${slug || 'post'}.png`;
  }

  window.openCard = function (outputId) {
    const el = document.getElementById(outputId);
    state.text = (el && el.textContent || '').trim();
    if (!state.text) return;
    document.getElementById('card-modal').hidden = false;
    document.body.classList.add('modal-open');
    const share = document.getElementById('card-share-btn');
    share.hidden = !(navigator.canShare && navigator.canShare({ files: [new File([''], 'x.png', { type: 'image/png' })] }));
    draw();
  };
  window.closeCard = function () {
    document.getElementById('card-modal').hidden = true;
    document.body.classList.remove('modal-open');
  };
  window.cardSize = function (btn) {
    btn.parentElement.querySelectorAll('.fmt-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.size = btn.dataset.size;
    draw();
  };
  window.cardDownload = function () {
    if (!state.blob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(state.blob);
    a.download = fileName();
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  window.cardCopy = async function (btn) {
    try {
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': state.blob })]);
      flash(btn, 'Copy image');
    } catch (e) {
      btn.textContent = 'Copy not supported here, use Download';
    }
  };
  window.cardShare = async function () {
    try {
      await navigator.share({ files: [new File([state.blob], fileName(), { type: 'image/png' })], text: state.text });
    } catch (e) { /* cancelled */ }
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCard(); });
})();
