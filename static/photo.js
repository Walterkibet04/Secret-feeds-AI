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
 */
(function () {
  const LONG_EDGE = 2048;
  const MAX_BYTES = 5 * 1024 * 1024;
  const FONT = 'Inter, "Helvetica Neue", Arial, sans-serif';
  const RATIOS = { original: null, wide: 16 / 9, tall: 4 / 5, square: 1 };

  const s = {
    img: null, w: 0, h: 0, name: 'photo',
    source: 'own', credit: 'Photo: Secret Feeds', place: '', date: '', caption: '',
    crop: 'original', fx: 0.5, fy: 0.5,
    corner: 'br', style: 'auto', size: 14, opacity: 90,
    crop_rect: null, out_w: 0, out_h: 0,
  };

  const logo = new Image();
  logo.src = '/logo.png';
  const $ = id => document.getElementById(id);

  // ── rights ────────────────────────────────────────────────────────────────
  const SOURCES = {
    own:      { credit: 'Photo: Secret Feeds', note: '' },
    handout:  { credit: '', note: 'Credit the organisation that released it, e.g. "Photo: Ukrainian Presidential Press Service handout".' },
    licensed: { credit: '', note: 'Keep the credit the licence asks for, e.g. "Photo: Jane Doe / CC BY 4.0".' },
    other:    { credit: '', note: 'Don\'t put your logo on agency photos (Reuters, AP, AFP, Getty) or other accounts\' pictures. ' +
                'X matches reused images, and a copyright complaint takes the post out of For You. Quote-post the original instead.' },
  };

  function exportProblem() {
    if (!s.img) return 'Choose a photo first.';
    if (s.source === 'other') return 'Export is off for photos you don\'t have the rights to.';
    if (!s.credit.trim()) return 'Add a credit. Every news photo carries one.';
    return '';
  }

  function refreshControls() {
    const src = SOURCES[s.source];
    $('photo-source-note').textContent = src.note;
    $('photo-source-note').className = 'note' + (s.source === 'other' ? ' note-bad' : '');
    const problem = exportProblem();
    document.querySelectorAll('.photo-export').forEach(b => { b.disabled = !!problem; });
    $('photo-export-note').textContent = problem;
    $('photo-export-note').style.display = problem ? 'block' : 'none';
  }

  // ── geometry ──────────────────────────────────────────────────────────────
  function cropRect() {
    const r = RATIOS[s.crop];
    if (!r) return { x: 0, y: 0, w: s.w, h: s.h };
    let cw = s.w, ch = s.w / r;
    if (ch > s.h) { ch = s.h; cw = s.h * r; }
    const x = Math.min(Math.max(s.fx * s.w - cw / 2, 0), s.w - cw);
    const y = Math.min(Math.max(s.fy * s.h - ch / 2, 0), s.h - ch);
    return { x, y, w: cw, h: ch };
  }

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

  // ── render ────────────────────────────────────────────────────────────────
  async function render(canvas) {
    if (!s.img) return;
    try { await Promise.all([document.fonts.load(`600 40px Inter`), document.fonts.load(`500 24px Inter`)]); } catch (e) {}
    if (!logo.complete) await new Promise(r => { logo.onload = logo.onerror = r; });

    const c = cropRect();
    const scale = Math.min(1, LONG_EDGE / Math.max(c.w, c.h));
    const W = Math.round(c.w * scale), H = Math.round(c.h * scale);
    canvas.width = W; canvas.height = H;
    s.crop_rect = c; s.out_w = W; s.out_h = H;
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
    return `secret-feeds-photo-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.jpg`;
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
  async function loadFile(file) {
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
    s.img = img; s.w = img.width; s.h = img.height; s.fx = 0.5; s.fy = 0.5;
    $('photo-preview-card').hidden = false;
    $('photo-share-btn').hidden = !(navigator.canShare && navigator.canShare({ files: [new File([''], 'x.jpg', { type: 'image/jpeg' })] }));
    $('photo-drop-label').textContent = file.name + ' · choose another';
    redraw();
  }

  // ── wiring ────────────────────────────────────────────────────────────────
  function bindSeg(rowId, key) {
    const row = $(rowId);
    row.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      row.querySelectorAll('button').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); s[key] = b.dataset.value; redraw();
    }));
  }

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
      const prev = SOURCES[s.source].credit;
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
    bindSeg('photo-corner-row', 'corner');
    bindSeg('photo-style-row', 'style');

    // Tap the preview to move the crop towards that point.
    $('photo-canvas').addEventListener('click', e => {
      if (!s.img || s.crop === 'original') return;
      const r = e.target.getBoundingClientRect();
      const c = s.crop_rect;
      s.fx = (c.x + (e.clientX - r.left) / r.width * c.w) / s.w;
      s.fy = (c.y + (e.clientY - r.top) / r.height * c.h) / s.h;
      redraw();
    });

    $('photo-alt').addEventListener('input', e => { $('photo-alt-count').textContent = e.target.value.length + ' / 1000'; });
    refreshControls();
  });

})();
