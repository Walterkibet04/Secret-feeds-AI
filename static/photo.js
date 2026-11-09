/* Secret Feeds: watermark and caption a photo.
 *
 * Everything runs in the browser; the photo is never sent to the server.
 * Follows common newsroom practice:
 *  - a credit line on every photo ("Photo: name / organisation"), dateline (place · date),
 *    optional one-line caption on a dark gradient ("scrim") so it reads on any photo;
 *  - logo in a corner, inside a 4% safe margin, sized as a share of the width, with a
 *    white version on dark areas so it's always visible;
 *  - export as JPEG, long side at most 2048 px and under X's 5 MB photo limit;
 *    re-encoding drops EXIF metadata, including GPS location;
 *  - no logo on photos you don't have the rights to (agency or other accounts' photos).
 *
 * Quote card mode: the person's photo, their exact words on a panel, name, title, date and
 * where they said it, your logo and the photo credit. 1080 px wide (square or 4:5), the
 * usual size for quote graphics on X.
 *
 * "Find their words and photo": the server (/speaker, quotes.py) names the speaker and
 * returns their words only if they are in the pasted text word for word; speaker.js then
 * fetches a free photo and its credit from Wikimedia Commons.
 */
(function () {
  const LONG_EDGE = 2048;
  const MAX_BYTES = 5 * 1024 * 1024;
  const FONT = 'Inter, "Helvetica Neue", Arial, sans-serif';
  const RATIOS = { original: null, wide: 16 / 9, tall: 4 / 5, square: 1 };

  const s = {
    img: null, w: 0, h: 0, name: 'photo',
    source: 'own', credit: 'Photo: Secret Feeds', place: '', date: '', caption: '',
    crop: 'original', fx: 0.5, fy: 0.5, zoom: 1,
    crop_box: null,    // where on the canvas the photo is drawn (side-by-side cards use the left part)
    corner: 'br', style: 'auto', size: 14, opacity: 90,
    crop_rect: null, out_w: 0, out_h: 0,
    mode: 'photo', quote: '', speaker: '', title: '', where: '', cardSize: 'square', panel: 'light', warn: '',
    verified: '',      // the words "Find" took from the pasted text, to flag later edits
    headline: '',      // reported card: the news in our words
  };
  // Quote cards and reported cards share the speaker, photo and layout controls.
  const cardMode = () => s.mode === 'quote' || s.mode === 'reported';
  // Speaker finder: people matching the name on Wikidata, and which person/photo is shown.
  const finder = { people: [], pi: 0, ph: 0, info: null, pending: null, last: null };

  const logo = new Image();
  logo.src = '/logo.png';
  const $ = id => document.getElementById(id);

  // ── rights ────────────────────────────────────────────────────────────────
  const SOURCES = {
    own:      { credit: 'Photo: Secret Feeds', note: '' },
    handout:  { credit: '', note: 'Credit the organisation that released it, e.g. "Photo: Ukrainian Presidential Press Service handout".' },
    licensed: { credit: '', note: 'Keep the credit the licence asks for, e.g. "Photo: Jane Doe / CC BY 4.0".' },
    commons:  { credit: '', note: 'Free licence from Wikimedia Commons. The credit comes from the photo\'s licence page, so keep it as it is.' },
    other:    { credit: '', note: 'Don\'t put your logo on agency photos (Reuters, AP, AFP, Getty) or other accounts\' pictures. ' +
                'X matches reused images, and a copyright complaint takes the post out of For You. Quote-post the original instead.' },
  };

  function exportProblem() {
    if (!s.img) return 'Choose a photo first.';
    if (s.source === 'other') return 'Export is off for photos you don\'t have the rights to.';
    if (!s.credit.trim()) return 'Add a credit. Every news photo carries one.';
    if (s.mode === 'reported' && !cleanHeadline(s.headline)) return 'Add the headline: what they said, in your words.';
    if (cardMode()) {
      if (s.mode === 'quote' && !cleanQuote(s.quote)) return 'Add the quote: their exact words.';
      if (!s.speaker.trim()) return 'Add who said it.';
      if (!s.date) return 'Add the date it was said.';
    }
    return '';
  }

  function cleanHeadline(h) { return (h || '').replace(/\s+/g, ' ').trim(); }
  // Quote marks in a headline claim exact words. Apostrophes (Iran's) are fine.
  function hasQuoteMarks(h) { return /["“”«»„]/.test(h) || /(^|[\s(])['‘][^'’]+['’](?=[\s.,;:!?)]|$)/.test(h); }

  // Strip quotation marks people paste around the words; the card adds its own.
  function cleanQuote(q) {
    return (q || '').trim().replace(/^["“”'‘’«»]+|["“”'‘’«»]+$/g, '').replace(/\s+/g, ' ').trim();
  }

  function refreshControls() {
    const src = SOURCES[s.source];
    $('photo-source-note').textContent = src.note;
    $('photo-source-note').className = 'note' + (s.source === 'other' ? ' note-bad' : '');
    const problem = exportProblem();
    document.querySelectorAll('.photo-export').forEach(b => { b.disabled = !!problem; });
    $('photo-export-note').textContent = problem;
    $('photo-export-note').style.display = problem ? 'block' : 'none';
    const quoteMode = cardMode();
    document.querySelectorAll('.photo-only').forEach(el => { el.hidden = quoteMode; });
    document.querySelectorAll('.quote-only').forEach(el => { el.hidden = !quoteMode; });
    document.querySelectorAll('.exact-only').forEach(el => { el.hidden = s.mode !== 'quote'; });
    document.querySelectorAll('.reported-only').forEach(el => { el.hidden = s.mode !== 'reported'; });
    $('photo-date-label').textContent = quoteMode ? 'Date said' : 'Date taken';
    $('photo-zoom-row').hidden = !framed();
    $('photo-canvas').classList.toggle('movable', framed());
    $('photo-frame-hint').textContent = !framed() ? 'Pick a crop to zoom or move the photo'
      : quoteMode ? 'Drag the photo to move it' : 'Drag the photo or tap a point to move the crop';
    // Quote cards keep the logo in a top corner: show the matching top button as selected.
    const shown = quoteMode ? 't' + s.corner.slice(1) : s.corner;
    document.querySelectorAll('#photo-corner-row button').forEach(btn => btn.classList.toggle('active', btn.dataset.value === shown));
  }

  // ── geometry ──────────────────────────────────────────────────────────────
  function cropRect(ratio) {
    const r = ratio !== undefined ? ratio : RATIOS[s.crop];
    if (!r) return { x: 0, y: 0, w: s.w, h: s.h };
    let cw = s.w, ch = s.w / r;
    if (ch > s.h) { ch = s.h; cw = s.h * r; }
    cw /= s.zoom; ch /= s.zoom;
    const x = Math.min(Math.max(s.fx * s.w - cw / 2, 0), s.w - cw);
    const y = Math.min(Math.max(s.fy * s.h - ch / 2, 0), s.h - ch);
    // Keep the focus point where the crop really is, so dragging never hits a dead zone.
    s.fx = (x + cw / 2) / s.w; s.fy = (y + ch / 2) / s.h;
    return { x, y, w: cw, h: ch };
  }
  const framed = () => cardMode() || s.crop !== 'original';

  function wrap(ctx, text, maxW, maxLines) {
    const words = text.split(/\s+/).filter(Boolean);
    const lines = []; let line = '';
    for (const w of words) {
      const t = line ? line + ' ' + w : w;
      if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t;
    }
    if (line) lines.push(line);
    if (lines.length > maxLines) {
      const kept = lines.slice(0, maxLines);
      let last = kept[maxLines - 1] + '…';
      while (ctx.measureText(last).width > maxW && last.length > 2) last = last.slice(0, -2) + '…';
      kept[maxLines - 1] = last;
      return kept;
    }
    return lines;
  }

  function luminance(ctx, x, y, w, h) {
    x = Math.max(0, Math.floor(x)); y = Math.max(0, Math.floor(y));
    w = Math.max(1, Math.floor(w)); h = Math.max(1, Math.floor(h));
    const d = ctx.getImageData(x, y, w, h).data;
    let sum = 0, n = 0;
    for (let i = 0; i < d.length; i += 16) {       // every 4th pixel is plenty
      const lin = [d[i], d[i + 1], d[i + 2]].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
      sum += 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]; n++;
    }
    return n ? sum / n : 1;
  }

  function whiteLogo(w, h) {
    const c = document.createElement('canvas');
    c.width = Math.ceil(w); c.height = Math.ceil(h);
    const x = c.getContext('2d');
    x.drawImage(logo, 0, 0, c.width, c.height);
    x.globalCompositeOperation = 'source-in';
    x.fillStyle = '#FFFFFF'; x.fillRect(0, 0, c.width, c.height);
    return c;
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  function dateline() {
    let d = '';
    if (s.date) {
      const [y, m, day] = s.date.split('-').map(Number);
      d = new Date(y, m - 1, day).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    }
    return [s.place.trim(), d, s.credit.trim()].filter(Boolean).join('  ·  ');
  }

  function prettyDate() {
    if (!s.date) return '';
    const [y, m, day] = s.date.split('-').map(Number);
    return new Date(y, m - 1, day).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  function drawLogo(ctx, W, x, y, lw, lh) {
    let variant = s.style;
    if (variant === 'auto' || variant === 'plate') {
      variant = s.style === 'plate' ? 'plate' : (luminance(ctx, x, y, lw, lh) < 0.35 ? 'white' : 'colour');
    }
    ctx.save();
    ctx.globalAlpha = s.opacity / 100;
    if (variant === 'plate') {
      const pad = Math.round(lh * 0.22);
      ctx.fillStyle = 'rgba(255,246,240,0.94)';
      roundRect(ctx, x - pad, y - pad, lw + pad * 2, lh + pad * 2, Math.round((lh + pad * 2) * 0.14)); ctx.fill();
      ctx.drawImage(logo, x, y, lw, lh);
    } else if (variant === 'white') {
      ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = Math.round(lh * 0.08);
      ctx.drawImage(whiteLogo(lw, lh), x, y, lw, lh);
    } else {
      ctx.shadowColor = 'rgba(255,255,255,0.55)'; ctx.shadowBlur = Math.round(lh * 0.08);
      ctx.drawImage(logo, x, y, lw, lh);
    }
    ctx.restore();
  }

  // Largest size between max and min at which the quote fits; centred or left lines.
  function fitQuote(ctx, text, maxW, maxH, maxSize, minSize, lh) {
    for (let size = maxSize; size >= minSize; size -= 2) {
      ctx.font = `700 ${size}px ${FONT}`;
      const lines = wrap(ctx, text, maxW, 99);
      if (lines.length * size * lh <= maxH) return { size, lines, cut: false };
    }
    ctx.font = `700 ${minSize}px ${FONT}`;
    const maxLines = Math.max(1, Math.floor(maxH / (minSize * lh)));
    return { size: minSize, lines: wrap(ctx, text, maxW, maxLines), cut: true };
  }

  // Warn when zoom stretches the photo past its own pixels: it starts to look soft.
  function softWarning(c, boxW) {
    return c.w < boxW * 0.75 ? 'The photo is enlarged a lot at this zoom and may look soft. Zoom out a little or pick a sharper photo.' : '';
  }
  function showWarn(W, H, ...msgs) {
    s.warn = msgs.filter(Boolean).join(' ');
    $('photo-info').textContent = `${W} × ${H} px`;
    $('photo-warn').textContent = s.warn;
    $('photo-warn').style.display = s.warn ? 'block' : 'none';
  }
  const CUT_WARNING = 'The quote is too long to fit, so the end is cut off. Use the key sentence; if you shorten it, cut at a sentence break and mark the cut with … Never change their words.';

  const cutWarning = () => s.mode === 'reported'
    ? 'The headline is too long to fit, so the end is cut off. Shorten it.' : CUT_WARNING;

  // Reported cards: "MARCO RUBIO · US SECRETARY OF STATE" above the headline, in small capitals.
  function setSpacing(ctx, px) { if ('letterSpacing' in ctx) ctx.letterSpacing = px + 'px'; }
  function whoLabel(ctx, name, size, maxW) {
    ctx.font = `700 ${size}px ${FONT}`; setSpacing(ctx, 2);
    const lines = joinLines(ctx, [name, s.title.trim()].filter(Boolean).map(t => t.toUpperCase()), '  ·  ', maxW, 2);
    setSpacing(ctx, 0);
    return lines;
  }
  function drawLabel(ctx, lines, size, colour, x, y) {
    ctx.fillStyle = colour; ctx.font = `700 ${size}px ${FONT}`; ctx.textAlign = 'left'; setSpacing(ctx, 2);
    lines.forEach((line, i) => ctx.fillText(line, x, y + i * size * 1.5));
    setSpacing(ctx, 0);
  }

  // Lay out items ("President of Ukraine", "9 November 2026", ...) on up to maxLines lines,
  // breaking between items rather than inside them, so no line starts with a separator.
  function joinLines(ctx, parts, sep, maxW, maxLines) {
    const lines = [];
    let line = '';
    for (const part of parts) {
      const t = line ? line + sep + part : part;
      if (ctx.measureText(t).width <= maxW) { line = t; continue; }
      if (line) lines.push(line);
      line = ctx.measureText(part).width <= maxW ? part : wrap(ctx, part, maxW, 1)[0];
    }
    if (line) lines.push(line);
    return lines.slice(0, maxLines);
  }

  // Side by side: photo on the left, quote on the right. Suits head-and-shoulders portraits,
  // which lose the face behind a panel on the other layouts.
  function renderSideCard(canvas, W, H) {
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingQuality = 'high';
    const photoW = Math.round(W * 0.44), bar = 8;
    const c = cropRect(photoW / H);
    s.crop_rect = c; s.crop_box = { x: 0, y: 0, w: photoW, h: H }; s.out_w = W; s.out_h = H;

    ctx.fillStyle = '#FFF8F3'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, photoW, H);
    ctx.drawImage(s.img, c.x, c.y, c.w, c.h, 0, 0, photoW, H);
    ctx.fillStyle = '#FF4500'; ctx.fillRect(photoW, 0, bar, H * 0.62);
    ctx.fillStyle = '#FF9A73'; ctx.fillRect(photoW, H * 0.62, bar, H * 0.38);

    const margin = Math.round(W * 0.055), pad = Math.round(W * 0.045);
    const x0 = photoW + bar + pad, textW = W - x0 - margin;
    const reported = s.mode === 'reported';
    const text = reported ? cleanHeadline(s.headline) : cleanQuote(s.quote), name = s.speaker.trim();
    const nameSize = Math.round(W * 0.034), metaSize = Math.round(W * 0.023), markSize = Math.round(W * 0.1);
    const labelSize = Math.round(W * 0.024);

    // Logo: top right of the text side, or top left over the photo.
    const right = s.corner.endsWith('r');
    const lw = Math.round(W * s.size / 100);
    const lh = logo.naturalWidth ? Math.round(lw * logo.naturalHeight / logo.naturalWidth) : 0;
    if (lh) drawLogo(ctx, W, right ? W - margin - lw : margin, margin, lw, lh);

    ctx.textBaseline = 'top'; ctx.textAlign = 'left';
    // Above the words: the quote mark, or for a reported card a label saying who.
    const labelLines = reported ? whoLabel(ctx, name, labelSize, textW) : [];
    const headH = reported ? labelLines.length * labelSize * 1.5 + pad * 0.3 : markSize * 0.6;
    // Below: name, title, date and place for a quote; date and place for a reported card (the label has the rest).
    ctx.font = `500 ${metaSize}px ${FONT}`;
    const metaParts = reported ? [prettyDate(), s.where.trim()] : [s.title.trim(), prettyDate(), s.where.trim()];
    const metaLines = joinLines(ctx, metaParts.filter(Boolean), '  ·  ', textW, 2);
    const attrH = (reported ? 0 : nameSize * 1.3) + metaLines.length * metaSize * 1.45;
    const top = margin + (right && lh ? lh + margin * 0.6 : 0);
    const bottom = H - margin;
    const textMaxH = bottom - top - headH - pad * 0.7 - attrH;
    const fit = fitQuote(ctx, text, textW, textMaxH, Math.round(W * 0.05), Math.round(W * 0.034), 1.28);
    const blockH = headH + fit.lines.length * fit.size * 1.28 + pad * 0.7 + attrH;
    let y = top + Math.max(0, (bottom - top - blockH) / 2);      // centre the block vertically

    if (reported) {
      drawLabel(ctx, labelLines, labelSize, '#D93A00', x0, y);
    } else {
      ctx.fillStyle = '#FF4500';
      ctx.font = `700 ${markSize * 1.6}px Georgia, "Times New Roman", serif`;
      ctx.fillText('“', x0 - markSize * 0.06, y - markSize * 0.35);
    }
    y += headH;
    ctx.fillStyle = '#1A1A1A'; ctx.font = `700 ${fit.size}px ${FONT}`;
    fit.lines.forEach(line => { ctx.fillText(line, x0, y); y += fit.size * 1.28; });
    y += pad * 0.7;
    if (!reported) {
      ctx.font = `700 ${nameSize}px ${FONT}`; ctx.fillText(name, x0, y);
      y += nameSize * 1.3;
    }
    ctx.fillStyle = '#6A5A52'; ctx.font = `500 ${metaSize}px ${FONT}`;
    metaLines.forEach(line => { ctx.fillText(line, x0, y); y += metaSize * 1.45; });

    // Credit along the bottom of the photo, up to two lines.
    const credit = s.credit.trim();
    if (credit) {
      const cs = Math.round(W * 0.019);
      ctx.font = `500 ${cs}px ${FONT}`;
      const maxW = photoW - margin * 1.5;
      // Too long for one line: break at the "/" so the licence ("CC BY 4.0") stays in one piece.
      const lines = ctx.measureText(credit).width > maxW && credit.includes(' / ')
        ? credit.split(' / ').slice(0, 2).map(part => wrap(ctx, part, maxW, 1)[0])
        : wrap(ctx, credit, maxW, 2);
      ctx.fillStyle = 'rgba(255,255,255,0.94)';
      ctx.shadowColor = 'rgba(0,0,0,0.7)'; ctx.shadowBlur = 6;
      lines.forEach((line, i) => ctx.fillText(line, margin * 0.75, H - margin * 0.75 - (lines.length - i) * cs * 1.35));
      ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
    }
    showWarn(W, H, fit.cut ? cutWarning() : '', softWarning(c, photoW));
  }

  async function renderQuoteCard(canvas) {
    const W = 1080, H = s.cardSize === 'tall' ? 1350 : 1080;
    canvas.width = W; canvas.height = H;
    if (s.panel === 'side') return renderSideCard(canvas, W, H);
    const c = cropRect(W / H);
    s.crop_rect = c; s.crop_box = { x: 0, y: 0, w: W, h: H }; s.out_w = W; s.out_h = H;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingQuality = 'high';
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, W, H);      // under PNGs with transparent parts
    ctx.drawImage(s.img, c.x, c.y, c.w, c.h, 0, 0, W, H);

    const margin = Math.round(W * 0.055);
    const reported = s.mode === 'reported';
    const text = reported ? cleanHeadline(s.headline) : cleanQuote(s.quote);
    const name = s.speaker.trim();
    const light = s.panel === 'light';
    const ink = light ? '#1A1A1A' : '#FFFFFF';
    const sub = light ? '#6A5A52' : 'rgba(255,255,255,0.82)';

    // Panel area: the lower part of the card.
    const panelX = light ? margin : 0;
    const panelW = light ? W - margin * 2 : W;
    const pad = Math.round(W * 0.05);
    const markSize = Math.round(W * 0.11);
    const nameSize = Math.round(W * 0.034), metaSize = Math.round(W * 0.023), labelSize = Math.round(W * 0.024);
    const textW = panelW - pad * 2;
    ctx.textBaseline = 'top';
    // Top of the panel: the quote mark, or for a reported card a label saying who.
    const labelLines = reported ? whoLabel(ctx, name, labelSize, textW) : [];
    const headH = reported ? labelLines.length * labelSize * 1.5 + pad * 0.3 : markSize * 0.55;
    // Bottom: name and details for a quote; date and place for a reported card.
    const meta = (reported ? [prettyDate(), s.where.trim()] : [s.title.trim(), prettyDate(), s.where.trim()]).filter(Boolean).join('  ·  ');
    const attrH = (reported ? 0 : nameSize * 1.3) + (meta ? metaSize * 1.5 : 0);
    const maxPanelH = Math.round(H * (s.cardSize === 'tall' ? 0.58 : 0.62));
    const textMaxH = maxPanelH - pad * 2 - headH - attrH - pad * 0.5;
    // Never smaller than ~37 px on a 1080 card, or it's unreadable on a phone; longer text gets cut instead.
    const fit = fitQuote(ctx, text, textW, textMaxH, Math.round(W * 0.052), Math.round(W * 0.034), 1.28);
    const textH = fit.lines.length * fit.size * 1.28;
    const panelH = Math.round(pad * 2 + headH + textH + pad * 0.5 + attrH);
    const panelY = light ? H - margin - panelH : H - panelH;

    if (light) {
      ctx.save();
      ctx.shadowColor = 'rgba(0,0,0,0.25)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 6;
      ctx.fillStyle = 'rgba(255,248,243,0.97)';
      roundRect(ctx, panelX, panelY, panelW, panelH, 22); ctx.fill();
      ctx.restore();
      // brand bar along the bottom edge of the panel
      ctx.save();
      roundRect(ctx, panelX, panelY, panelW, panelH, 22); ctx.clip();
      ctx.fillStyle = '#FF4500'; ctx.fillRect(panelX, panelY + panelH - 10, panelW * 0.62, 10);
      ctx.fillStyle = '#FF9A73'; ctx.fillRect(panelX + panelW * 0.62, panelY + panelH - 10, panelW * 0.38, 10);
      ctx.restore();
    } else {
      const top = panelY - H * 0.18;
      const g = ctx.createLinearGradient(0, top, 0, H);
      g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(0.35, 'rgba(0,0,0,0.62)'); g.addColorStop(1, 'rgba(0,0,0,0.9)');
      ctx.fillStyle = g; ctx.fillRect(0, top, W, H - top);
    }

    ctx.textAlign = 'left';
    if (!light) { ctx.shadowColor = 'rgba(0,0,0,0.4)'; ctx.shadowBlur = 6; }
    if (reported) {
      drawLabel(ctx, labelLines, labelSize, light ? '#D93A00' : '#FF9A73', panelX + pad, panelY + pad);
    } else {
      // Big opening quote mark.
      ctx.fillStyle = '#FF4500';
      ctx.font = `700 ${markSize * 1.6}px Georgia, "Times New Roman", serif`;
      ctx.fillText('“', panelX + pad - markSize * 0.06, panelY + pad * 0.55 - markSize * 0.35);
    }

    // The words: a quote is centred on the light panel; a headline always reads from the left.
    let y = panelY + pad + headH;
    ctx.fillStyle = ink;
    ctx.font = `700 ${fit.size}px ${FONT}`;
    const centred = light && !reported;
    ctx.textAlign = centred ? 'center' : 'left';
    const tx = centred ? panelX + panelW / 2 : panelX + pad;
    fit.lines.forEach(line => { ctx.fillText(line, tx, y); y += fit.size * 1.28; });

    // Attribution.
    y += pad * 0.5;
    if (reported) {
      if (meta) {
        ctx.textAlign = 'left'; ctx.fillStyle = sub; ctx.font = `500 ${metaSize}px ${FONT}`;
        ctx.fillText(wrap(ctx, meta, textW, 1)[0], panelX + pad, y);
      }
    } else {
      ctx.textAlign = light ? 'right' : 'left';
      const ax = light ? panelX + panelW - pad : panelX + pad;
      ctx.fillStyle = light ? ink : '#FFFFFF';
      ctx.font = `700 ${nameSize}px ${FONT}`;
      ctx.fillText(name, ax, y);
      if (meta) {
        ctx.fillStyle = sub; ctx.font = `500 ${metaSize}px ${FONT}`;
        ctx.fillText(wrap(ctx, meta, panelW - pad * 2, 1)[0], ax, y + nameSize * 1.3);
      }
    }
    ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;

    // Logo in a top corner; photo credit small in the other top corner.
    if (logo.naturalWidth) {
      const lw = Math.round(W * s.size / 100);
      const lh = Math.round(lw * logo.naturalHeight / logo.naturalWidth);
      const right = s.corner.endsWith('r');
      drawLogo(ctx, W, right ? W - margin - lw : margin, margin, lw, lh);
      const credit = s.credit.trim();
      if (credit) {
        ctx.font = `500 ${Math.round(W * 0.019)}px ${FONT}`;
        ctx.textAlign = right ? 'left' : 'right';
        ctx.fillStyle = 'rgba(255,255,255,0.92)';
        ctx.shadowColor = 'rgba(0,0,0,0.6)'; ctx.shadowBlur = 6;
        ctx.fillText(credit, right ? margin : W - margin, margin);
        ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
      }
    }
    showWarn(W, H, fit.cut ? cutWarning() : '', softWarning(c, W));
  }

  // ── render ────────────────────────────────────────────────────────────────
  async function render(canvas) {
    if (!s.img) return;
    if (cardMode()) {
      try { await Promise.all([document.fonts.load(`700 40px Inter`), document.fonts.load(`500 24px Inter`)]); } catch (e) {}
      if (!logo.complete) await new Promise(r => { logo.onload = logo.onerror = r; });
      return renderQuoteCard(canvas);
    }
    $('photo-warn').style.display = 'none';
    try { await Promise.all([document.fonts.load(`600 40px Inter`), document.fonts.load(`500 24px Inter`)]); } catch (e) {}
    if (!logo.complete) await new Promise(r => { logo.onload = logo.onerror = r; });

    const c = cropRect();
    const scale = Math.min(1, LONG_EDGE / Math.max(c.w, c.h));
    const W = Math.round(c.w * scale), H = Math.round(c.h * scale);
    canvas.width = W; canvas.height = H;
    s.crop_rect = c; s.crop_box = { x: 0, y: 0, w: W, h: H }; s.out_w = W; s.out_h = H;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(s.img, c.x, c.y, c.w, c.h, 0, 0, W, H);

    const unit = Math.min(W, H);
    const margin = Math.round(unit * 0.04);                 // 4% safe area
    const capSize = Math.round(Math.max(18, Math.min(60, W * 0.03)));
    const meta = dateline();
    const caption = s.caption.trim();
    // Credit/dateline: smaller under a caption, a bit larger on its own so it reads on a phone.
    const metaSize = Math.round(Math.max(14, capSize * (caption ? 0.7 : 0.8)));

    // Caption strip on a dark gradient scrim.
    let stripTop = H;
    if (caption || meta) {
      ctx.font = `600 ${capSize}px ${FONT}`;
      const maxTextW = W - margin * 2;
      const capLines = caption ? wrap(ctx, caption, maxTextW, 2) : [];
      const textH = capLines.length * capSize * 1.25 + (meta ? metaSize * 1.5 : 0);
      const stripH = textH + margin * 1.4;
      stripTop = H - stripH;
      const g = ctx.createLinearGradient(0, stripTop - stripH * 0.9, 0, H);
      g.addColorStop(0, 'rgba(0,0,0,0)');
      g.addColorStop(0.45, caption ? 'rgba(0,0,0,0.45)' : 'rgba(0,0,0,0.25)');
      g.addColorStop(1, caption ? 'rgba(0,0,0,0.78)' : 'rgba(0,0,0,0.62)');
      ctx.fillStyle = g;
      ctx.fillRect(0, stripTop - stripH * 0.9, W, H - (stripTop - stripH * 0.9));

      ctx.textBaseline = 'top'; ctx.textAlign = 'left';
      ctx.shadowColor = 'rgba(0,0,0,0.35)'; ctx.shadowBlur = Math.round(capSize * 0.15);
      let y = stripTop + margin * 0.7;
      ctx.fillStyle = '#FFFFFF';
      ctx.font = `600 ${capSize}px ${FONT}`;
      capLines.forEach(l => { ctx.fillText(l, margin, y); y += capSize * 1.25; });
      if (meta) {
        ctx.font = `500 ${metaSize}px ${FONT}`;
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        const metaLine = wrap(ctx, meta, maxTextW, 1)[0];
        ctx.fillText(metaLine, margin, y + (capLines.length ? metaSize * 0.35 : 0));
      }
      ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
    }

    // Logo watermark in the chosen corner, above the caption strip if it's at the bottom.
    if (logo.naturalWidth) {
      const lw = Math.round(W * s.size / 100);
      const lh = Math.round(lw * logo.naturalHeight / logo.naturalWidth);
      const plate = s.style === 'plate';
      const padX = plate ? Math.round(lh * 0.22) : 0;
      const boxW = lw + padX * 2, boxH = lh + padX * 2;
      const right = s.corner.endsWith('r'), bottom = s.corner.startsWith('b');
      const x = right ? W - margin - boxW : margin;
      let y = bottom ? Math.min(H - margin - boxH, stripTop - Math.round(margin * 0.6) - boxH) : margin;
      if (y < margin) y = margin;

      let variant = s.style;
      if (variant === 'auto') variant = luminance(ctx, x, y, boxW, boxH) < 0.35 ? 'white' : 'colour';

      ctx.save();
      ctx.globalAlpha = s.opacity / 100;
      if (plate) {
        ctx.fillStyle = 'rgba(255,246,240,0.94)';
        ctx.shadowColor = 'rgba(0,0,0,0.18)'; ctx.shadowBlur = Math.round(lh * 0.12);
        roundRect(ctx, x, y, boxW, boxH, Math.round(boxH * 0.14)); ctx.fill();
        ctx.shadowColor = 'transparent'; ctx.shadowBlur = 0;
        ctx.drawImage(logo, x + padX, y + padX, lw, lh);
      } else if (variant === 'white') {
        ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = Math.round(lh * 0.08);
        ctx.drawImage(whiteLogo(lw, lh), x, y, lw, lh);
      } else {
        ctx.shadowColor = 'rgba(255,255,255,0.55)'; ctx.shadowBlur = Math.round(lh * 0.08);
        ctx.drawImage(logo, x, y, lw, lh);
      }
      ctx.restore();
    }

    $('photo-info').textContent = `${W} × ${H} px` + (Math.max(s.w, s.h) < 1000 ? ' · low resolution, X will show it small' : '');
  }

  // Sliders fire many events; draw at most once per frame.
  let queued = false;
  function redraw() {
    refreshControls();
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; render($('photo-canvas')); });
  }

  // ── export ────────────────────────────────────────────────────────────────
  async function jpegBlob() {
    const canvas = $('photo-canvas');
    for (let q = 0.92; q >= 0.6; q -= 0.08) {
      const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', q));
      if (blob && blob.size <= MAX_BYTES) return blob;
    }
    return new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.6));
  }
  function fileName() {
    const d = new Date(); const p = n => String(n).padStart(2, '0');
    return `secret-feeds-${s.mode}-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.jpg`;
  }

  window.photoDownload = async function () {
    if (exportProblem()) return;
    const blob = await jpegBlob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = fileName();
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  };
  window.photoCopy = async function (btn) {
    if (exportProblem()) return;
    try {
      const png = await new Promise(r => $('photo-canvas').toBlob(r, 'image/png'));
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]);
      flash(btn, 'Copy image');
    } catch (e) { btn.textContent = 'Copy not supported here, use Download'; }
  };
  window.photoShare = async function () {
    if (exportProblem()) return;
    try {
      const blob = await jpegBlob();
      await navigator.share({ files: [new File([blob], fileName(), { type: 'image/jpeg' })] });
    } catch (e) { /* cancelled */ }
  };

  // ── loading ───────────────────────────────────────────────────────────────
  // Back to the whole photo, centred.
  function resetFrame(draw) {
    s.fx = 0.5; s.fy = 0.5; s.zoom = 1;
    $('photo-zoom').value = 100; $('photo-zoom-val').textContent = '100%';
    if (draw !== false) redraw();
  }
  window.resetFrame = resetFrame;

  function setSource(value, credit) {
    s.source = value; $('photo-source').value = value;
    s.credit = credit; $('photo-credit').value = credit;
  }

  // `commons` is set when the photo came from Wikimedia Commons: {credit, label}.
  async function loadFile(file, commons) {
    if (!file || !file.type.startsWith('image/')) { alert('That file isn\'t an image.'); return; }
    let img;
    try {
      img = await createImageBitmap(file, { imageOrientation: 'from-image' });   // respects phone rotation
    } catch (e) {
      img = await new Promise((res, rej) => {
        const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = URL.createObjectURL(file);
      }).catch(() => null);
    }
    if (!img) { alert('This browser can\'t open that photo format. Try a JPEG or PNG (iPhone: Settings → Camera → Formats → Most Compatible).'); return; }
    s.img = img; s.w = img.width; s.h = img.height;
    resetFrame(false);
    if (commons) {
      setSource('commons', commons.credit);
    } else if (s.source === 'commons') {
      // Your own file replaces a Commons photo: its credit no longer applies.
      setSource('own', SOURCES.own.credit);
      $('qc-photo-status').hidden = true;
    }
    $('photo-preview-card').hidden = false;
    $('photo-share-btn').hidden = !(navigator.canShare && navigator.canShare({ files: [new File([''], 'x.jpg', { type: 'image/jpeg' })] }));
    $('photo-drop-label').textContent = (commons ? commons.label : file.name) + ' · choose another';
    redraw();
  }

  // ── quote card: find the speaker, their exact words and a free photo ─────
  function setMode(mode) {
    s.mode = mode;
    $('photo-mode-row').querySelectorAll('button').forEach(b => b.classList.toggle('active', b.dataset.value === mode));
    redraw();
  }
  function setField(id, value) {
    const el = $(id);
    el.value = value;
    el.dispatchEvent(new Event('input'));      // updates the card and the counters
  }
  function el(tag, attrs, text) {
    const e = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k, v]) => { if (k === 'onclick') e.onclick = v; else e.setAttribute(k, v); });
    if (text) e.textContent = text;
    return e;
  }
  function useQuote(words) {
    s.verified = words;
    setField('qc-quote', words);
  }

  // Switch between quote card and reported card from the finder's buttons.
  function switchCard(mode) {
    setMode(mode);
    if (finder.last) showFinder(finder.last);
  }

  function showFinder(data) {
    finder.last = data;
    $('qc-find-out').hidden = false;
    const status = $('qc-find-status');
    const opts = $('qc-find-options');
    const rep = $('qc-find-reported');
    opts.textContent = '';

    if (s.mode === 'reported') {
      // A reported card needs no exact words: the headline is in your words.
      status.className = 'finder-status ' + (data.headline ? 'ok' : 'warn');
      status.textContent = data.headline
        ? '✓ Headline written from the post, in your words. Check it says what they said and no more.'
        : 'Couldn\'t write a headline from this post. Type one in the Headline box.';
      if (data.status === 'exact') {
        opts.appendChild(el('div', { class: 'note' }, 'This post has their exact words too.'));
        opts.appendChild(el('button', { class: 'option-btn', type: 'button', onclick: () => switchCard('quote') }, 'Make a quote card with their words instead'));
      }
      rep.style.display = 'none';
      finder.terms = '';
      renderLinks('');
      return;
    }

    status.className = 'finder-status ' + (data.status === 'exact' ? 'ok' : 'warn');
    status.textContent = (data.status === 'exact' ? '✓ ' : '') + data.note;
    if (data.status !== 'exact' && data.headline) {
      opts.appendChild(el('button', { class: 'option-btn switch-btn', type: 'button', onclick: () => switchCard('reported') },
        'No exact words? Make a reported card instead: "' + data.headline + '"'));
    }
    if ((data.options || []).length && data.status === 'exact') {
      opts.appendChild(el('div', { class: 'note' }, 'Other quoted words in your text. Tap one only if the speaker said it:'));
    }
    (data.options || []).forEach(o => opts.appendChild(el('button', { class: 'option-btn', type: 'button', onclick: () => {
      useQuote(o);
      status.className = 'finder-status ok';
      status.textContent = '✓ Using the quote you picked. Check it is the speaker\'s words, not someone else\'s quoted in the same post.';
    } }, '“' + o + '”')));

    rep.textContent = data.status !== 'exact' && data.reported ? 'What the post says they said: ' + data.reported : '';
    rep.style.display = rep.textContent ? 'block' : 'none';

    // Links to find their own words, only when the text didn't have them.
    finder.terms = data.status === 'exact' ? '' : [data.speaker].concat(data.terms || []).filter(Boolean).join(' ');
    renderLinks('');
  }

  // Where to find their own words: their X account (from Wikidata) and a news search.
  function renderLinks(handle) {
    const box = $('qc-find-links');
    box.textContent = '';
    if (!finder.terms) { box.style.display = 'none'; return; }
    box.appendChild(document.createTextNode('Find their own words: '));
    if (handle) {
      box.appendChild(el('a', { href: 'https://x.com/' + encodeURIComponent(handle), target: '_blank', rel: 'noopener' }, '@' + handle + ' on X'));
      box.appendChild(document.createTextNode(' · '));
    }
    box.appendChild(el('a', { href: 'https://news.google.com/search?q=' + encodeURIComponent(finder.terms), target: '_blank', rel: 'noopener' }, 'search the news'));
    box.appendChild(document.createTextNode('. Copy their post or statement, paste it above, tick "own post" and press Find again.'));
    box.style.display = 'block';
  }

  function photoStatus(parts) {
    const box = $('qc-photo-status');
    box.textContent = '';
    parts.forEach(p => box.appendChild(typeof p === 'string' ? document.createTextNode(p) : p));
    box.hidden = false;
  }

  async function findPhoto(name) {
    finder.people = []; finder.info = null; finder.pending = null;
    closeGallery();
    if (!name) { $('qc-photo-status').hidden = true; return; }
    photoStatus([`Looking for a free photo of ${name}…`]);
    try {
      finder.people = await SFSpeaker.people(name);
    } catch (e) {
      photoStatus(['Couldn\'t reach Wikimedia Commons right now. Choose a photo yourself: an official handout or a Creative Commons photo.']);
      return;
    }
    const top = finder.people[0];
    renderLinks(top ? top.x : '');
    if (!top) {
      photoStatus([`No match on Wikimedia for "${name}". Choose a photo yourself: an official handout or a Creative Commons photo.`]);
      return;
    }
    // The best match stays first even without a main photo (Commons may still have photos of
    // them); other matches only count if they have one.
    finder.people = finder.people.filter((p, i) => i === 0 || p.photos.length);
    return showPhoto(0, 0);
  }

  // Show person pi's main photo number ph. Skips photos whose licence isn't clear.
  async function showPhoto(pi, ph) {
    const p = finder.people[pi];
    finder.pi = pi;
    for (; ph < p.photos.length; ph++) {
      let info = null;
      try { info = await SFSpeaker.photoInfo(p.photos[ph]); } catch (e) { info = null; }
      if (!info) continue;
      finder.ph = ph; finder.info = info;
      // Don't swap out a photo you chose yourself; offer this one instead.
      if (s.img && s.source !== 'commons') { finder.pending = info; renderPhotoStatus(p, info, true); return; }
      return applyPhoto(p, info);
    }
    const body = el('div', {}, `No main photo of ${p.name}${p.description ? ' (' + p.description + ')' : ''} on Wikidata. Pick one of the photos tagged with them, or choose your own.`);
    body.appendChild(actions(pi, false));
    photoStatus([body]);
    return openGallery(pi);
  }

  async function applyPhoto(p, info) {
    photoStatus([`Loading the photo of ${p.name}…`]);
    try {
      const file = await SFSpeaker.download(info);
      await loadFile(file, { credit: info.credit, label: 'Wikimedia Commons: ' + p.name });
      finder.pending = null; finder.info = info;
      renderPhotoStatus(p, info, false);
      markThumb(info.file);
    } catch (e) {
      photoStatus(['Couldn\'t load the photo from Wikimedia Commons. Choose a photo yourself.']);
    }
  }

  function actions(pi, offerInfo) {
    const acts = el('div', { class: 'finder-acts' });
    const p = finder.people[pi];
    if (offerInfo) acts.appendChild(el('button', { class: 'link-btn', type: 'button', onclick: () => applyPhoto(p, offerInfo) }, 'Use this photo'));
    acts.appendChild(el('button', { class: 'link-btn', type: 'button', onclick: () => toggleGallery(pi) }, 'More photos'));
    if (pi + 1 < finder.people.length) acts.appendChild(el('button', { class: 'link-btn', type: 'button', onclick: () => { closeGallery(); showPhoto(pi + 1, 0); } }, 'Wrong person?'));
    return acts;
  }

  function renderPhotoStatus(p, info, offer) {
    const thumb = el('img', { src: info.url, alt: p.name, crossorigin: 'anonymous' });
    const body = el('div');
    const who = el('div', { class: 'finder-who' }, p.name + (p.description ? ' · ' + p.description : ''));
    body.appendChild(who);
    body.appendChild(el('div', {}, `${info.licence}${info.author ? ' · ' + info.author : ''} · `));
    body.lastChild.appendChild(el('a', { href: info.page, target: '_blank', rel: 'noopener' }, 'licence page'));
    if (info.width < 900) body.appendChild(el('div', { class: 'note-warn' }, `Small photo (${info.width} px wide): it may look soft on the card.`));
    body.appendChild(actions(finder.pi, offer ? info : null));
    photoStatus([thumb, body]);
  }

  // ── "More photos": a grid of free photos of the person, tap one to use it ──
  const gallery = { pi: -1, next: null, seen: null, busy: false, grid: null, more: null, msg: null };

  function closeGallery() {
    const box = $('qc-gallery');
    box.hidden = true; box.textContent = '';
    gallery.pi = -1;
  }
  function toggleGallery(pi) {
    const box = $('qc-gallery');
    if (gallery.pi === pi) { box.hidden = !box.hidden; return; }
    openGallery(pi);
  }
  function markThumb(file) {
    if (!gallery.grid) return;
    gallery.grid.querySelectorAll('.thumb').forEach(t => t.classList.toggle('on', t.dataset.file === file));
  }

  async function openGallery(pi) {
    const p = finder.people[pi];
    const box = $('qc-gallery');
    gallery.pi = pi; gallery.next = 0; gallery.seen = new Set(); gallery.busy = false;
    box.textContent = ''; box.hidden = false;
    box.appendChild(el('div', { class: 'gallery-head' }, `Free photos of ${p.name} on Wikimedia Commons, newest first. Tap one to use it. Group shots work too: zoom in on them under the preview.`));
    gallery.grid = el('div', { class: 'gallery-grid' }); box.appendChild(gallery.grid);
    gallery.msg = el('div', { class: 'note' }); box.appendChild(gallery.msg);
    gallery.more = el('button', { class: 'btn secondary gallery-more', type: 'button', onclick: () => loadGallery(p) }, 'Load more photos');
    gallery.more.hidden = true; box.appendChild(gallery.more);
    // Main portraits first: they're the ones picked as the person's picture on Wikidata.
    const portraits = await Promise.all(p.photos.slice(0, 3).map(f => SFSpeaker.photoInfo(f, 320).catch(() => null)));
    if (gallery.pi !== pi) return;
    portraits.filter(Boolean).forEach(i => addThumb(p, { file: i.file, thumb: i.url, licence: i.licence }));
    return loadGallery(p);
  }

  async function loadGallery(p) {
    if (gallery.busy || gallery.next === null) return;
    const pi = gallery.pi;
    gallery.busy = true; gallery.more.hidden = true;
    gallery.msg.textContent = 'Loading photos…';
    try {
      const page = await SFSpeaker.morePhotos(p.id, gallery.next);
      if (gallery.pi !== pi) return;
      page.photos.forEach(ph => addThumb(p, ph));
      gallery.next = page.next;
      gallery.msg.textContent = gallery.grid.childNodes.length ? ''
        : `Wikimedia Commons has no other free photos of ${p.name}. Choose your own photo below.`;
    } catch (e) {
      if (gallery.pi === pi) gallery.msg.textContent = 'Couldn\'t load photos from Wikimedia Commons right now.';
    } finally {
      if (gallery.pi === pi) { gallery.busy = false; gallery.more.hidden = gallery.next === null; }
    }
  }

  function addThumb(p, ph) {
    if (gallery.seen.has(ph.file)) return;
    gallery.seen.add(ph.file);
    const b = el('button', { class: 'thumb', type: 'button', title: ph.file + ' · ' + ph.licence });
    b.dataset.file = ph.file;
    b.appendChild(el('img', { src: ph.thumb, alt: '', loading: 'lazy' }));
    if (finder.info && finder.info.file === ph.file) b.classList.add('on');
    b.onclick = async () => {
      markThumb(ph.file);
      const info = await SFSpeaker.photoInfo(ph.file).catch(() => null);
      if (!info) { gallery.msg.textContent = 'That photo\'s licence isn\'t clear. Pick another.'; b.classList.remove('on'); return; }
      await applyPhoto(p, info);
    };
    gallery.grid.appendChild(b);
  }

  window.findSpeaker = async function () {
    const text = $('qc-paste-input').value.trim();
    if (!text) { $('qc-paste-input').focus(); return; }
    if (!cardMode()) setMode('quote');
    const btn = $('qc-find-btn');
    btn.disabled = true; btn.textContent = 'Finding…';
    $('qc-find-error').style.display = 'none';
    try {
      const resp = await fetch('/speaker', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, own_words: $('qc-own').checked }) });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      if (data.speaker) setField('qc-speaker', data.speaker);
      setField('qc-title', data.role || '');
      setField('qc-where', data.where || '');
      setField('qc-headline', data.headline || '');
      // Only words found in your text go in the quote box. No match means an empty box, not a guess.
      if (data.status === 'exact') useQuote(data.quote); else { s.verified = ''; setField('qc-quote', ''); }
      showFinder(data);
      await findPhoto(data.speaker);
    } catch (e) {
      $('qc-find-error').textContent = 'Error: ' + e.message;
      $('qc-find-error').style.display = 'block';
    } finally {
      btn.disabled = false; btn.textContent = 'Find their words and photo';
    }
  };
  window.findSpeakerPhoto = () => findPhoto(s.speaker.trim());

  // ── wiring ────────────────────────────────────────────────────────────────
  function bindSeg(rowId, key) {
    const row = $(rowId);
    row.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      row.querySelectorAll('button').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); s[key] = b.dataset.value; redraw();
    }));
  }

  window.writeCardCaption = async function () {
    const reported = s.mode === 'reported';
    const quote = reported ? cleanHeadline(s.headline) : cleanQuote(s.quote), speaker = s.speaker.trim();
    if (!quote || !speaker) { alert(reported ? 'Add the headline and who said it first.' : 'Add the quote and who said it first.'); return; }
    const btn = $('qc-caption-btn');
    btn.disabled = true; btn.textContent = 'Writing…';
    $('qc-caption-error').style.display = 'none';
    try {
      const resp = await fetch('/caption', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quote, speaker, title: s.title.trim(), where: s.where.trim(), date: prettyDate(), kind: s.mode }) });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      $('qc-caption-output').textContent = data.result;
      $('qc-caption-output').dataset.format = reported ? 'Reported card' : 'Quote card';
      $('qc-caption-chars').textContent = data.result.length + ' / 280 chars';
      showNote('qc-caption-note', data.note);
      showWarnings('qc-caption-warnings', data.warnings);
      $('qc-caption-result').style.display = 'block';
      afterResult('qc-caption-output', 'qc-caption-warnings');
    } catch (e) {
      $('qc-caption-error').textContent = 'Error: ' + e.message;
      $('qc-caption-error').style.display = 'block';
    } finally {
      btn.disabled = false; btn.textContent = 'Write caption for X';
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    if (!$('tab-photo')) return;
    const today = new Date(); const p = n => String(n).padStart(2, '0');
    s.date = `${today.getFullYear()}-${p(today.getMonth() + 1)}-${p(today.getDate())}`;
    $('photo-date').value = s.date;
    $('photo-credit').value = s.credit;

    $('photo-file').addEventListener('change', e => loadFile(e.target.files[0]));
    const drop = $('photo-drop');
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
    drop.addEventListener('drop', e => loadFile(e.dataTransfer.files[0]));

    $('photo-source').addEventListener('change', e => {
      const prev = s.source === 'commons' && finder.info ? finder.info.credit : SOURCES[s.source].credit;
      s.source = e.target.value;
      if (!s.credit || s.credit === prev) { s.credit = SOURCES[s.source].credit; $('photo-credit').value = s.credit; }
      redraw();
    });
    [['photo-credit', 'credit'], ['photo-place', 'place'], ['photo-date', 'date'], ['photo-caption', 'caption']].forEach(([id, key]) => {
      $(id).addEventListener('input', e => { s[key] = e.target.value; redraw(); });
    });
    $('photo-caption').addEventListener('input', e => { $('photo-caption-count').textContent = e.target.value.length + ' / 90'; });
    $('photo-size').addEventListener('input', e => { s.size = +e.target.value; $('photo-size-val').textContent = s.size + '%'; redraw(); });
    $('photo-opacity').addEventListener('input', e => { s.opacity = +e.target.value; $('photo-opacity-val').textContent = s.opacity + '%'; redraw(); });
    bindSeg('photo-crop-row', 'crop');
    bindSeg('photo-mode-row', 'mode');
    bindSeg('qc-size-row', 'cardSize');
    bindSeg('qc-panel-row', 'panel');
    [['qc-quote', 'quote'], ['qc-speaker', 'speaker'], ['qc-title', 'title'], ['qc-where', 'where'], ['qc-headline', 'headline']].forEach(([id, key]) => {
      $(id).addEventListener('input', e => { s[key] = e.target.value; redraw(); });
    });
    $('qc-headline').addEventListener('input', e => {
      $('qc-headline-count').textContent = e.target.value.length + ' / 160';
      const marks = hasQuoteMarks(e.target.value);
      $('qc-headline-check').textContent = marks
        ? 'Quote marks tell readers these are their exact words. Take them out, or check the words against the source and make a Quote card.' : '';
      $('qc-headline-check').style.display = marks ? 'block' : 'none';
    });
    // Switching card type by hand: refresh the finder's advice for the new type.
    $('photo-mode-row').addEventListener('click', () => { if (finder.last && cardMode()) showFinder(finder.last); });
    $('qc-quote').addEventListener('input', e => {
      const n = cleanQuote(e.target.value).length;
      $('qc-quote-count').textContent = n + ' characters' + (n > 220 ? ' · long for a card, aim for under 220' : '');
      $('qc-quote-count').className = 'char-count' + (n > 220 ? ' over' : '');
      // Words found by "Find" were checked against the post. Say so if they've been changed since.
      const changed = s.verified && cleanQuote(e.target.value) !== cleanQuote(s.verified);
      $('qc-quote-check').textContent = changed
        ? 'You\'ve changed the words found in the post. The card must show exactly what they said: only cut at a sentence break and mark the cut with …'
        : '';
      $('qc-quote-check').style.display = changed ? 'block' : 'none';
    });
    bindSeg('photo-corner-row', 'corner');
    bindSeg('photo-style-row', 'style');

    // Move the photo inside its frame: drag it (mouse or finger), or in photo mode tap a point
    // to centre on it. Zoom with the slider.
    const canvas = $('photo-canvas');
    let drag = null, dragged = false;
    const toCanvas = (e, r) => [(e.clientX - r.left) * canvas.width / r.width, (e.clientY - r.top) * canvas.height / r.height];
    canvas.addEventListener('pointerdown', e => {
      if (!s.img || !framed() || !s.crop_rect) return;
      const r = canvas.getBoundingClientRect();
      const [px, py] = toCanvas(e, r), b = s.crop_box;
      if (px < b.x || px > b.x + b.w || py < b.y || py > b.y + b.h) return;   // not on the photo
      drag = { x: px, y: py, fx: s.fx, fy: s.fy, c: s.crop_rect, b, moved: false };
      canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', e => {
      if (!drag) return;
      const [px, py] = toCanvas(e, canvas.getBoundingClientRect());
      const dx = px - drag.x, dy = py - drag.y;
      if (!drag.moved && Math.hypot(dx, dy) < 6) return;
      drag.moved = true;
      // Dragging right shows more of the left side: the crop moves the other way.
      s.fx = drag.fx - dx * drag.c.w / drag.b.w / s.w;
      s.fy = drag.fy - dy * drag.c.h / drag.b.h / s.h;
      redraw();
    });
    const endDrag = () => { if (drag) dragged = drag.moved; drag = null; };
    canvas.addEventListener('pointerup', endDrag);
    canvas.addEventListener('pointercancel', endDrag);
    canvas.addEventListener('click', e => {
      if (dragged) { dragged = false; return; }
      // Tap to centre: photo mode only. On a quote card the centre sits behind the text, so drag there.
      if (!s.img || cardMode() || s.crop === 'original') return;
      const [px, py] = toCanvas(e, canvas.getBoundingClientRect());
      const c = s.crop_rect, b = s.crop_box;
      s.fx = (c.x + (px - b.x) / b.w * c.w) / s.w;
      s.fy = (c.y + (py - b.y) / b.h * c.h) / s.h;
      redraw();
    });
    $('photo-zoom').addEventListener('input', e => {
      s.zoom = Number(e.target.value) / 100;
      $('photo-zoom-val').textContent = e.target.value + '%';
      redraw();
    });

    $('photo-alt').addEventListener('input', e => { $('photo-alt-count').textContent = e.target.value.length + ' / 1000'; });
    refreshControls();
  });

})();
