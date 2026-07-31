import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

const CASES = [
  { name: '#tag-foo', url: `${BROWSE}#tag-foo`, atom: '$activeTag', value: 'foo', visible: 0 },
  { name: '#search-bar%20baz', url: `${BROWSE}#search-bar%20baz`, atom: '$activeSearch', value: 'bar baz', visible: 0 },
  { name: '#category-frontend', url: `${BROWSE}#category-frontend`, atom: '$activeCategory', value: 'frontend', visible: 2 },
  { name: "bare ''/empty", url: BROWSE, atom: null, value: null, visible: 4 },
];

describe('URL hash deep-linking (integration)', () => {
  for (const c of CASES) {
    it(`load '${c.name}' -> bridgeFromHash sets the right atom; handleHashChange updates DOM; filterCards shows matching; round-trip hash equals load`, async () => {
      const state = await loadFresh('static/js/modules/state.js', { url: c.url, html: FIX() });
      await loadFresh('static/js/modules/tag-manager.js', { url: c.url });
      await loadFresh('static/js/modules/entry-animator.js', { url: c.url });
      const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url: c.url });
      await loadFresh('static/js/modules/filter-cards.js', { url: c.url });
      const loadHash = window.location.hash;

      // install the bridge FIRST so atom sets drive writeHash (round-trip)
      state.bridgeToHash({
        $activeTag: state.$activeTag,
        $activeSearch: state.$activeSearch,
        $activeCategory: state.$activeCategory,
      });
      hhc.handleHashChange(); // sets atoms + filterCards

      // exactly the right atom set, others null
      if (c.atom) {
        expect(state[c.atom].get()).toBe(c.value);
        for (const key of ['$activeTag', '$activeSearch', '$activeCategory']) {
          if (key !== c.atom) expect(state[key].get()).toBeNull();
        }
      } else {
        expect(state.$activeTag.get()).toBeNull();
        expect(state.$activeSearch.get()).toBeNull();
        expect(state.$activeCategory.get()).toBeNull();
      }

      // filterCards shows the matching cards
      expect(document.getElementById('resultsCount').textContent).toBe(`${c.visible} item${c.visible !== 1 ? 's' : ''}`);

      // round-trip idempotence: serialise(parse(H)) === H -> hash unchanged
      expect(window.location.hash).toBe(loadHash);
    });
  }

  it('main.js bootstrap with each initial hash produces the same DOM state (no throw)', async () => {
    for (const c of CASES) {
      vi.resetModules();
      await loadFresh('static/js/main.js', { url: c.url, html: FIX() });
      expect(document.querySelectorAll('#linksGrid .link-card').length).toBe(4);
    }
  });
});