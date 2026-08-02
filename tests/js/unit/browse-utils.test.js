import { describe, it, expect } from 'vitest';
import { loadFresh } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';

async function setup(url) {
  // browse-utils imports state.js, which queries .link-card at import —
  // an empty DOM is a valid (zero-card) environment.
  const state = await loadFresh('static/js/modules/state.js', { url, html: '<div></div>' });
  const bu = await loadFresh('static/js/modules/browse-utils.js', { url });
  return { state, isBrowsePage: bu.isBrowsePage, browseUrl: bu.browseUrl };
}

describe('browse-utils.js', () => {
  it('isBrowsePage: true on browse.html with and without a hash', async () => {
    expect((await setup(`${BROWSE}#tag-foo`)).isBrowsePage()).toBe(true);
    expect((await setup(BROWSE)).isBrowsePage()).toBe(true);
  });

  it('isBrowsePage: false on index.html and on the root path', async () => {
    expect((await setup(LANDING)).isBrowsePage()).toBe(false);
    expect((await setup('http://localhost/')).isBrowsePage()).toBe(false);
  });

  it("browseUrl('tag', <slug>): 'c' (the slug of 'c++') -> 'browse.html#tag-c'", async () => {
    const { browseUrl } = await setup(BROWSE);
    // Callers pass the canonical form — tag slugs (TagManager.slugify
    // runs before browseUrl at the tag click sites).
    expect(browseUrl('tag', 'c')).toBe('browse.html#tag-c');
  });

  it("browseUrl('tag', 'δυο') -> 'browse.html#tag-%CE%B4%CF%85%CE%BF' (non-ASCII is percent-encoded)", async () => {
    const { browseUrl } = await setup(BROWSE);
    expect(browseUrl('tag', 'δυο')).toBe('browse.html#tag-%CE%B4%CF%85%CE%BF');
  });

  it("browseUrl('search', 'bar baz') -> 'browse.html#search-bar%20baz'", async () => {
    const { browseUrl } = await setup(BROWSE);
    expect(browseUrl('search', 'bar baz')).toBe('browse.html#search-bar%20baz');
  });

  it("browseUrl('category', 'web') -> 'browse.html#category-web'", async () => {
    const { browseUrl } = await setup(BROWSE);
    expect(browseUrl('category', 'web')).toBe('browse.html#category-web');
  });

  it('browseUrl output is byte-for-byte serialiseHash output prefixed with browse.html (AC 9)', async () => {
    const { state, browseUrl } = await setup(BROWSE);
    expect(browseUrl('tag', 'foo')).toBe('browse.html' + state.serialiseHash('foo', null, null));
    expect(browseUrl('search', 'bar baz')).toBe('browse.html' + state.serialiseHash(null, 'bar baz', null));
    expect(browseUrl('category', 'web')).toBe('browse.html' + state.serialiseHash(null, null, 'web'));
  });

  it('round-trip: loading browseUrl(...) and bridging the hash applies the matching reactive variable', async () => {
    const url = `${BROWSE}#category-web`;
    const { state } = await setup(url);
    let applied = null;
    state.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: null, category: 'web' });
  });
});
