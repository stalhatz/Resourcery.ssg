import { describe, it, expect } from 'vitest';
import { loadFresh } from '../helpers/setup.js';

// Small card set used across the $visibleCards / allCards tests.
const CARDS = `
  <article class="link-card" id="c1" data-title="Alpha" data-summary="Red car" data-tags="JavaScript,React" data-category="frontend"></article>
  <article class="link-card" id="c2" data-title="Beta" data-summary="Blue boat" data-tags="Python,API" data-category="backend"></article>
  <article class="link-card" id="c3" data-title="Gamma" data-summary="Green" data-tags="Vue,JavaScript" data-category="frontend"></article>
`;

const BROWSE = 'http://localhost/browse.html';
const fresh = (opts = {}) =>
  loadFresh('static/js/modules/state.js', { url: BROWSE, html: CARDS, ...opts });

describe('state.js', () => {
  // --- atoms get/set ---
  it('atoms: get/set round-trip for $activeTag/$activeSearch/$activeCategory', async () => {
    const s = await fresh();
    for (const atom of [s.$activeTag, s.$activeSearch, s.$activeCategory]) {
      expect(atom.get()).toBeNull();
      atom.set('foo');
      expect(atom.get()).toBe('foo');
      atom.set(null);
      expect(atom.get()).toBeNull();
    }
  });

  it('atoms: $animatedIds starts empty and accepts a Set', async () => {
    const s = await fresh();
    expect(s.$animatedIds.get()).toBeInstanceOf(Set);
    expect(s.$animatedIds.get().size).toBe(0);
    s.$animatedIds.set(new Set(['a', 'b']));
    expect(s.$animatedIds.get()).toEqual(new Set(['a', 'b']));
  });

  // --- $visibleCards ---
  it('$visibleCards: all-null shows every card', async () => {
    const s = await fresh();
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c2', 'c3']);
  });

  it('$visibleCards: tag filter matches dataset.tags', async () => {
    const s = await fresh();
    s.$activeTag.set('javascript');
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c3']);
    s.$activeTag.set('react');
    expect(s.$visibleCards.get()).toEqual(['c1']);
  });

  it('$visibleCards: search filter matches title/summary/tags substring, case-insensitive', async () => {
    const s = await fresh();
    s.$activeSearch.set('CAR'); // summary "Red car"
    expect(s.$visibleCards.get()).toEqual(['c1']);
    s.$activeSearch.set('BLUE'); // summary "Blue boat"
    expect(s.$visibleCards.get()).toEqual(['c2']);
    s.$activeSearch.set('javascript'); // tags
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c3']);
    s.$activeSearch.set('GAMMA'); // title
    expect(s.$visibleCards.get()).toEqual(['c3']);
  });

  it('$visibleCards: category filter uses window.CATEGORY_MAP[group] then falls back to literal id', async () => {
    const s = await fresh({ globals: { CATEGORY_MAP: { web: ['frontend', 'backend'] } } });
    s.$activeCategory.set('web');
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c2', 'c3']);
    s.$activeCategory.set('frontend');
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c3']);
  });

  it('$visibleCards: without CATEGORY_MAP a literal id matches; an unknown group matches nothing', async () => {
    // beforeEach deleted window.CATEGORY_MAP; fresh() does not re-seed it.
    const s = await fresh();
    s.$activeCategory.set('frontend');
    expect(s.$visibleCards.get().sort()).toEqual(['c1', 'c3']);
    s.$activeCategory.set('web'); // no map → literal ['web'] → no card matches
    expect(s.$visibleCards.get()).toEqual([]);
  });

  it('$visibleCards: at-most-one-of-three is caller discipline', async () => {
    // The invariant is held by callers (TagManager/bridgeFromHash), which set
    // exactly one atom and null the others. bridgeFromHash demonstrates this:
    // a parsed hash populates exactly one of {tag,search,category}.
    const s = await fresh({ url: `${BROWSE}#tag-foo` });
    s.bridgeFromHash((next) => {
      s.$activeTag.set(next.tag);
      s.$activeSearch.set(next.search);
      s.$activeCategory.set(next.category);
    });
    expect(s.$activeTag.get()).toBe('foo');
    expect(s.$activeSearch.get()).toBeNull();
    expect(s.$activeCategory.get()).toBeNull();
  });

  // --- allCards ---
  it('allCards: built once from .link-card at import; id from el.id || dataset.title || generated', async () => {
    const html = `
      <article class="link-card" id="a" data-title="Alpha"></article>
      <article class="link-card" data-title="Beta"></article>
      <article class="link-card"></article>
    `;
    const s = await loadFresh('static/js/modules/state.js', { url: BROWSE, html });
    expect(s.allCards).toHaveLength(3);
    expect(s.allCards[0].id).toBe('a');
    expect(s.allCards[1].id).toBe('Beta');
    expect(s.allCards[2].id).toEqual(expect.any(String));
    expect(s.allCards[2].id.length).toBeGreaterThan(0);
  });

  // --- bridgeFromHash ---
  it("bridgeFromHash: '#tag-foo' -> {tag:'foo', search:null, category:null}", async () => {
    const s = await fresh({ url: `${BROWSE}#tag-foo` });
    let applied = null;
    s.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: 'foo', search: null, category: null });
  });

  it("bridgeFromHash: '#search-bar%20baz' -> {search:'bar baz', …} (decodeURIComponent)", async () => {
    const s = await fresh({ url: `${BROWSE}#search-bar%20baz` });
    let applied = null;
    s.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: 'bar baz', category: null });
  });

  it("bridgeFromHash: '#category-x' -> {category:'x', …}", async () => {
    const s = await fresh({ url: `${BROWSE}#category-x` });
    let applied = null;
    s.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: null, category: 'x' });
  });

  it("bridgeFromHash: bare '' and '#' and unknown '#foo' -> all-null", async () => {
    const sEmpty = await fresh({ url: BROWSE });
    let applied = null;
    sEmpty.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: null, category: null });

    const sHash = await fresh({ url: `${BROWSE}#` });
    applied = null;
    sHash.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: null, category: null });
    // jsdom normalises a bare '#' to ''
    expect(window.location.hash).toBe('');

    const sUnknown = await fresh({ url: `${BROWSE}#foo` });
    applied = null;
    sUnknown.bridgeFromHash((next) => (applied = next));
    expect(applied).toEqual({ tag: null, search: null, category: null });
  });

  it('bridgeFromHash: applies parsed state via the apply callback', async () => {
    const s = await fresh({ url: `${BROWSE}#category-web` });
    let applied = null;
    s.bridgeFromHash((next) => (applied = next));
    expect(applied).not.toBeNull();
    expect(applied.category).toBe('web');
  });

  // --- bridgeToHash ---
  it("bridgeToHash: writes '#tag-<slug>' / '#search-<enc>' / '#category-<id>' for each atom set", async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    s.$activeTag.set('foo');
    expect(window.location.hash).toBe('#tag-foo');
    s.$activeTag.set(null);
    s.$activeSearch.set('bar baz');
    expect(window.location.hash).toBe('#search-bar%20baz');
    s.$activeSearch.set(null);
    s.$activeCategory.set('web');
    expect(window.location.hash).toBe('#category-web');
  });

  it('bridgeToHash: no-op when serialised hash already equals window.location.hash', async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    s.$activeTag.set('foo');
    expect(window.location.hash).toBe('#tag-foo');
    const before = window.location.hash;
    // re-setting the same value: Nanostores === short-circuits, no re-fire
    s.$activeTag.set('foo');
    expect(window.location.hash).toBe(before);
  });

  it("bridgeToHash: all-null serialises to '' (no hash)", async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    s.$activeTag.set('foo');
    expect(window.location.hash).toBe('#tag-foo');
    s.$activeTag.set(null);
    expect(window.location.hash).toBe('');
  });

  // --- no-mock loop-termination (real Nanostores ===) ---
  it('no-mock loop-termination: setting $activeTag to its current value does not re-fire the listener; a different value fires exactly once', async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    let calls = 0;
    s.$activeTag.listen(() => calls++);
    const current = s.$activeTag.get();
    s.$activeTag.set(current); // same
    expect(calls).toBe(0);
    s.$activeTag.set('foo'); // different
    expect(calls).toBe(1);
    s.$activeTag.set('foo'); // same again
    expect(calls).toBe(1);
  });

  it('no-mock loop-termination: $activeSearch same/different', async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    let calls = 0;
    s.$activeSearch.listen(() => calls++);
    s.$activeSearch.set(s.$activeSearch.get()); // same (null)
    expect(calls).toBe(0);
    s.$activeSearch.set('bar');
    expect(calls).toBe(1);
    s.$activeSearch.set('bar');
    expect(calls).toBe(1);
  });

  it('no-mock loop-termination: $activeCategory same/different', async () => {
    const s = await fresh();
    s.bridgeToHash({
      $activeTag: s.$activeTag,
      $activeSearch: s.$activeSearch,
      $activeCategory: s.$activeCategory,
    });
    let calls = 0;
    s.$activeCategory.listen(() => calls++);
    s.$activeCategory.set(s.$activeCategory.get()); // same (null)
    expect(calls).toBe(0);
    s.$activeCategory.set('web');
    expect(calls).toBe(1);
    s.$activeCategory.set('web');
    expect(calls).toBe(1);
  });

  // --- indirect round-trip idempotence ---
  describe('round-trip idempotence (indirect)', () => {
    const cases = [
      { name: '#tag-foo', url: `${BROWSE}#tag-foo` },
      { name: '#search-bar%20baz', url: `${BROWSE}#search-bar%20baz` },
      { name: '#category-x', url: `${BROWSE}#category-x` },
      { name: "bare ''/empty", url: BROWSE },
    ];

    for (const c of cases) {
      it(`load '${c.name}' -> bridgeFromHash -> atoms -> bridgeToHash write -> hash equals load hash`, async () => {
        const s = await fresh({ url: c.url });
        const loadHash = window.location.hash;
        // install the bridge FIRST so atom sets drive writeHash
        s.bridgeToHash({
          $activeTag: s.$activeTag,
          $activeSearch: s.$activeSearch,
          $activeCategory: s.$activeCategory,
        });
        // apply the parsed hash to the atoms (mirrors main.js bootstrap)
        s.bridgeFromHash((next) => {
          s.$activeTag.set(next.tag);
          s.$activeSearch.set(next.search);
          s.$activeCategory.set(next.category);
        });
        // serialise(parse(H)) === H → writeHash is a no-op → hash unchanged
        expect(window.location.hash).toBe(loadHash);
      });
    }
  });
});