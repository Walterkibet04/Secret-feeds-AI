/* Secret Feeds: find a free photo of a speaker on Wikimedia Commons.
 *
 * Runs in your browser, straight to Wikimedia (no server work, nothing to set up).
 * 1. Wikidata finds the person by name and gives their main photo (property P18),
 *    which must be a Wikimedia Commons file, so it always has a free licence, plus their
 *    X account (P2002) for finding their own posts.
 * 2. Commons gives the photo's licence and author, which become the credit on the card.
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
  async function photoInfo(file) {
    const data = await api(COMMONS, {
      action: 'query', prop: 'imageinfo', titles: 'File:' + file, iiprop: 'url|extmetadata|mime|size',
      iiurlwidth: String(WIDTH), iiextmetadatafilter: 'LicenseShortName|Artist|AttributionRequired|NonFree|UsageTerms',
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
      width: ii.thumbwidth || ii.width, height: ii.thumbheight || ii.height,
      licence, author: who, credit: creditLine(who, licence),
      shareAlike: /SA/.test(licence),
    };
  }

  async function download(info) {
    const r = await fetch(info.url);
    if (!r.ok) throw new Error('Photo download failed (' + r.status + ')');
    const blob = await r.blob();
    const ext = (blob.type.split('/')[1] || 'jpg').replace('jpeg', 'jpg');
    return new File([blob], 'wikimedia-' + info.file.replace(/\.[^.]+$/, '').slice(0, 40) + '.' + ext, { type: blob.type || 'image/jpeg' });
  }

  window.SFSpeaker = { people, photoInfo, download, creditLine };
})();
