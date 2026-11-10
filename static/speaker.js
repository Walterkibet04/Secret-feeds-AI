/* Secret Feeds: find a free photo of a speaker on Wikimedia Commons.
 *
 * Runs in your browser, straight to Wikimedia (no server work, nothing to set up).
 * 1. Wikidata finds the person by name and gives their main photo (property P18),
 *    which must be a Wikimedia Commons file, so it always has a free licence, plus their
 *    X account (P2002) for finding their own posts.
 * 2. Commons gives the photo's licence and author, which become the credit on the card.
 * 3. "More photos": Commons photos of that person alone (nobody else tagged in them).
 * Photos with no clear licence are skipped.
 */
(function () {
  const WIKIDATA = 'https://www.wikidata.org/w/api.php';
  const COMMONS = 'https://commons.wikimedia.org/w/api.php';
  const WIDTH = 1280;          // Commons serves standard sizes; 1280 covers a 1080 px card
  const HUMAN = 'Q5';

  async function api(base, params) {
    const q = new URLSearchParams(Object.assign({ format: 'json', origin: '*' }, params));
    const r = await fetch(base + '?' + q);
    if (!r.ok) throw new Error('Wikimedia answered ' + r.status);
    return r.json();
  }

  const value = claim => claim && claim.mainsnak && claim.mainsnak.datavalue && claim.mainsnak.datavalue.value;
  // Best statements first (preferred, then normal); deprecated ones are out of date.
  function ranked(claims) {
    return (claims || []).filter(c => c.rank !== 'deprecated' && value(c))
      .sort((a, b) => (b.rank === 'preferred') - (a.rank === 'preferred')).map(value);
  }
  const text = (obj, langs) => { for (const l of langs) if (obj && obj[l]) return obj[l].value; return ''; };

  // People matching a name, most likely first: [{id, name, description, photos[], x}]
  async function people(name) {
    name = (name || '').trim();
    if (!name) return [];
    const found = await api(WIKIDATA, { action: 'wbsearchentities', type: 'item', language: 'en', uselang: 'en', limit: '8', search: name });
    const ids = (found.search || []).map(x => x.id);
    if (!ids.length) return [];
    const data = await api(WIKIDATA, { action: 'wbgetentities', ids: ids.join('|'), props: 'claims|labels|descriptions|sitelinks',
                                       languages: 'en|mul', sitefilter: 'enwiki' });
    const list = [];
    ids.forEach((id, order) => {
      const e = data.entities && data.entities[id];
      if (!e || !e.claims) return;
      if (!ranked(e.claims.P31).some(v => v.id === HUMAN)) return;     // people only
      list.push({
        id, order,
        name: text(e.labels, ['en', 'mul']),
        description: text(e.descriptions, ['en', 'mul']),
        photos: ranked(e.claims.P18),
        x: ranked(e.claims.P2002)[0] || '',
        famous: !!(e.sitelinks && e.sitelinks.enwiki),
      });
    });
    // Someone with an English Wikipedia article is far more likely to be the one in the news.
    return list.sort((a, b) => (b.famous - a.famous) || (a.order - b.order));
  }

  // Plain text from Commons' HTML fields. DOMParser doesn't run scripts or load images.
  function plain(html) {
    const t = new DOMParser().parseFromString(html || '', 'text/html').body.textContent || '';
    return t.replace(/\s+/g, ' ').trim();
  }
  function author(html) {
    let a = plain(html).replace(/^(©|\(c\)|copyright)\s*/i, '');
    if (/^https?:\/\//i.test(a)) { try { a = new URL(a).hostname.replace(/^www\./, ''); } catch (e) { /* keep */ } }
    if (a.length > 48) a = a.slice(0, 47).replace(/\s+\S*$/, '') + '…';
    return a;
  }
  // Licence names worth printing on the card; "Attribution" and custom names are covered by the author credit.
  const SHOW_LICENCE = /^(CC[ -]|CC0|Public domain|PD|GFDL|OGL)/i;

  function creditLine(who, licence) {
    const lic = SHOW_LICENCE.test(licence) ? licence : '';
    if (who && lic) return `Photo: ${who} / ${lic}`;
    if (who) return `Photo: ${who}`;
    return lic ? `Photo: Wikimedia Commons / ${lic}` : 'Photo: Wikimedia Commons';
  }

  // Licence, author and a card-sized URL for one Commons file. Null if the licence isn't clear.
  async function photoInfo(file, width) {
    const data = await api(COMMONS, {
      action: 'query', prop: 'imageinfo', titles: 'File:' + file, iiprop: 'url|extmetadata|mime|size',
      iiurlwidth: String(width || WIDTH), iiextmetadatafilter: 'LicenseShortName|Artist|AttributionRequired|NonFree|UsageTerms',
    });
    const page = Object.values((data.query && data.query.pages) || {})[0];
    const ii = page && page.imageinfo && page.imageinfo[0];
    if (!ii) return null;
    const m = ii.extmetadata || {};
    const get = k => (m[k] && m[k].value) || '';
    const licence = plain(get('LicenseShortName'));
    if (!licence || /^true$/i.test(get('NonFree'))) return null;
    if (!/^image\/(jpeg|png|webp|gif|tiff)$/.test(ii.mime)) return null;
    const who = author(get('Artist'));
    return {
      file, url: ii.thumburl || ii.url, page: ii.descriptionurl,
      width: ii.thumbwidth || ii.width, height: ii.thumbheight || ii.height, origWidth: ii.width,
      licence, author: who, credit: creditLine(who, licence),
      shareAlike: /SA/.test(licence),
    };
  }

  // ── "More photos": photos of the person alone ────────────────────────────
  // Commons records who is in each photo as "depicts" (P180) statements. A photo counts as
  // "of" the person only if they are tagged and no other person is. Things (a flag, a podium)
  // can be tagged too; Wikidata says which tags are people.
  const SPARQL = 'https://query.wikidata.org/sparql';
  const MIN_WIDTH = 800, WANT = 12, MAX_FETCHES = 3;
  const isHuman = new Map();
  async function markHumans(qids) {
    const need = qids.filter(q => /^Q\d+$/.test(q) && !isHuman.has(q));
    for (let i = 0; i < need.length; i += 80) {
      const chunk = need.slice(i, i + 80);
      const query = `SELECT ?i WHERE { VALUES ?i { ${chunk.map(q => 'wd:' + q).join(' ')} } ?i wdt:P31 wd:Q5 }`;
      const r = await fetch(SPARQL + '?format=json&query=' + encodeURIComponent(query));
      if (!r.ok) throw new Error('Wikidata query failed');
      const people = new Set(((await r.json()).results.bindings || []).map(b => b.i.value.split('/').pop()));
      chunk.forEach(q => isHuman.set(q, people.has(q)));
    }
  }

  // Not everyone in a photo gets tagged, so file names catch the rest: "Blinken meets
  // President Ruto", "Khamenei and Larijani". Others aren't photos of the person at all.
  const OTHERS_IN_TITLE = /\b(meets?|met|meeting|greet(s|ed|ing)?|welcom(es|ed|ing)|receiv(es|ed|ing)|host(s|ed|ing)?|bilateral|summit|delegation|family|wife|husband|and|with|vs|versus)\b|&/i;
  const NOT_A_PHOTO_OF_THEM = /\b(poster|cartoon|caricature|meme|t-?shirt|shirt|logo|signs?|graffiti|mural|banner|protest|display|sticker|mask|statue|wax|doll|stamp|coin|badge|ballot|wanted|drawing|painting|illustration)\b/i;

  const fold = t => t.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  // The file name should name the person ("Ruto", "Zelensky", "Magyar Péter"): photos named
  // after someone else ("Visit of Valdis Dombrovskis to Kenya") are usually of them. Name parts
  // are cut to 5 letters so spellings match (Zelenskyy, Zelensky, Zelenskiy).
  function namesThem(title, name) {
    const parts = fold(name).split(/[\s-]+/).filter(w => w.length >= 3).map(w => w.slice(0, 5));
    return !parts.length || parts.some(w => fold(title).includes(w));
  }
  function looksSolo(title, name) {
    const t = title.replace(/\.[a-z0-9]+$/i, '').replace(/[_.()\d-]/g, ' ');    // digits hide words: "20181130summit11"
    return namesThem(t, name) && !OTHERS_IN_TITLE.test(t) && !NOT_A_PHOTO_OF_THEM.test(t)
      && (t.match(/,/g) || []).length < 2;                                    // "Rachel Ruto, William Ruto, Joe Biden"
  }

  // Keep the pages where the person is the only one tagged. Main-subject tags first.
  async function onlyThem(qid, pages) {
    if (!pages.length) return [];
    const data = await api(COMMONS, { action: 'wbgetentities', ids: pages.map(p => 'M' + p.pageid).join('|'), props: 'claims' });
    const tags = new Map();
    pages.forEach(p => {
      const e = data.entities && data.entities['M' + p.pageid];
      const st = (e && (e.statements || e.claims)) || {};
      tags.set(p.pageid, (st.P180 || []).filter(c => c.rank !== 'deprecated' && value(c) && /^Q\d+$/.test(value(c).id || ''))
        .map(c => ({ id: value(c).id, main: c.rank === 'preferred' })));
    });
    const others = [...new Set([...tags.values()].flat().map(t => t.id).filter(id => id !== qid))];
    let strict = false;
    try { await markHumans(others); } catch (e) { strict = true; }   // can't check: allow nobody else tagged at all
    return pages
      .map(p => ({ p, t: tags.get(p.pageid) }))
      .filter(({ t }) => t.some(x => x.id === qid) && t.every(x => x.id === qid || (!strict && isHuman.get(x.id) === false)))
      .map(({ p, t }) => ({ p, main: t.some(x => x.id === qid && x.main) }))
      .sort((a, b) => b.main - a.main)
      .map(x => x.p);
  }

  // Photos of `person` ({id, name}), best first: a search for their name among photos tagged
  // with them, then all photos tagged with them. Pass `next` back to continue; null = no more.
  // `skip`: files already shown. `onPhotos`: called with each batch as it arrives, so the
  // grid fills while the rest loads.
  async function morePhotos(person, cursor, opts) {
    const { skip = new Set(), onPhotos = null } = opts || {};
    if (!/^Q\d+$/.test(person.id || '')) return { photos: [], next: null };
    const name = (person.name || '').replace(/["\\]/g, '').trim();
    const searches = (name ? [`"${name}" haswbstatement:P180=${person.id}`] : []).concat(`haswbstatement:P180=${person.id}`);
    let { src, offset } = cursor || { src: 0, offset: 0 };
    const photos = [], seen = new Set([...skip].map(f => 'File:' + f));
    for (let fetches = 0; src < searches.length && photos.length < WANT && fetches < MAX_FETCHES; fetches++) {
      const data = await api(COMMONS, {
        action: 'query', generator: 'search', gsrsearch: searches[src], gsrnamespace: '6', gsrlimit: '40',
        gsroffset: String(offset), prop: 'imageinfo', iiprop: 'url|extmetadata|mime|size', iiurlwidth: '320',
        iiextmetadatafilter: 'LicenseShortName|NonFree',
      });
      const pages = Object.values((data.query && data.query.pages) || {}).sort((a, b) => a.index - b.index).filter(p => {
        const ii = p.imageinfo && p.imageinfo[0];
        // Photos only: PNGs on Commons are mostly screenshots and graphics.
        if (!ii || ii.mime !== 'image/jpeg' || ii.width < MIN_WIDTH) return false;
        const m = ii.extmetadata || {};
        if (!plain(m.LicenseShortName && m.LicenseShortName.value) || /^true$/i.test(m.NonFree && m.NonFree.value)) return false;
        return !seen.has(p.title) && looksSolo(p.title.replace(/^File:/, ''), name);
      });
      const batch = (await onlyThem(person.id, pages)).map(p => {
        seen.add(p.title);
        const ii = p.imageinfo[0];
        return { file: p.title.replace(/^File:/, ''), thumb: ii.thumburl || ii.url, width: ii.width, height: ii.height,
                 licence: plain(ii.extmetadata.LicenseShortName.value) };
      });
      photos.push(...batch);
      if (onPhotos && batch.length) onPhotos(batch);
      if (data.continue && data.continue.gsroffset) offset = data.continue.gsroffset;
      else { src++; offset = 0; }
    }
    return { photos, next: src < searches.length ? { src, offset } : null };
  }

  async function download(info) {
    const r = await fetch(info.url);
    if (!r.ok) throw new Error('Photo download failed (' + r.status + ')');
    const blob = await r.blob();
    const ext = (blob.type.split('/')[1] || 'jpg').replace('jpeg', 'jpg');
    return new File([blob], 'wikimedia-' + info.file.replace(/\.[^.]+$/, '').slice(0, 40) + '.' + ext, { type: blob.type || 'image/jpeg' });
  }

  window.SFSpeaker = { people, photoInfo, morePhotos, download, creditLine };
})();
