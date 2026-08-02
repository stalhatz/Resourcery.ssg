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
    it(`load '${c.name}' -> bridgeFromHash sets the right reactive variable; handleHashChange updates DOM; filterCards shows matching; round-trip hash equals load`, async () => {
      const state = await loadFresh('static/js/modules/state.js', { url: c.url, html: FIX() });
      await loadFresh('static/js/modules/tag-manager.js', { url: c.url });
      await loadFresh('static/js/modules/entry-animator.js', { url: c.url });
      const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url: c.url });
      await loadFresh('static/js/modules/filter-cards.js', { url: c.url });
      const fx = await loadFresh('static/js/modules/effects.js', { url: c.url });
      const loadHash = window.location.hash;

      // install the bridge FIRST so reactive-variable sets drive writeHash (round-trip);
      // effects before handleHashChange mirrors main.js's boot order
      state.bridgeToHash({
        $activeTag: state.$activeTag,
        $activeSearch: state.$activeSearch,
        $activeCategory: state.$activeCategory,
      });
      fx.installEffects();
      hhc.handleHashChange(); // sets reactive variables + drain-syncs the DOM

      // exactly the right reactive variable set, others null
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

  // B3 regression: a deep link carrying a SLUG ('#tag-rd') must match a card
  // whose raw data-tags hold the un-slugified form ('R&D') end to end:
  // parseHash -> reactive variables -> handleHashChange -> effects -> DOM.
  it("deep link '#tag-rd': handleHashChange sets slug 'rd', filterCards shows the card with raw tag 'R&D'", async () => {
    const html = `
      <span id="filterText1"></span><span id="filterText2"></span><span id="filterValue1"></span>
      <span id="searchValue"></span>
      <span id="resultsCount"></span>
      <article class="link-card" id="rd" data-title="R&D" data-tags="R&D" data-category="backend"></article>
      <article class="link-card" id="js" data-title="JS" data-tags="JavaScript" data-category="frontend"></article>
    `;
    const url = `${BROWSE}#tag-rd`;
    const state = await loadFresh('static/js/modules/state.js', { url, html });
    await loadFresh('static/js/modules/tag-manager.js', { url });
    await loadFresh('static/js/modules/entry-animator.js', { url });
    const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
    await loadFresh('static/js/modules/filter-cards.js', { url });
    const fx = await loadFresh('static/js/modules/effects.js', { url });

    fx.installEffects();
    hhc.handleHashChange();

    expect(state.$activeTag.get()).toBe('rd');
    expect(document.getElementById('rd').style.display).toBe('');
    expect(document.getElementById('js').style.display).toBe('none');
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
  });

  // B8 regression: a deep link carrying the PERCENT-ENCODED Greek tag
  // ('#tag-%CE%B4%CF%85%CE%BF') must decode to the slug 'δυο' and match a card
  // whose raw data-tags hold 'δύο' end to end — and the header must show the
  // DECODED '#δυο', not the raw encoding. (The browser always reports the
  // encoded fragment, so this is the form real deep links and the click-path
  // hashchange round-trip take.)
  it("deep link '#tag-%CE%B4%CF%85%CE%BF': reactive variable 'δυο', card with raw tag 'δύο' visible, header shows '#δυο', hash round-trips unchanged", async () => {
    const html = `
      <span id="filterText1"></span><span id="filterText2"></span><span id="filterValue1"></span>
      <span id="searchValue"></span>
      <span id="resultsCount"></span>
      <article class="link-card" id="gr" data-title="Δύο" data-tags="δύο" data-category="frontend"></article>
      <article class="link-card" id="js" data-title="JS" data-tags="JavaScript" data-category="frontend"></article>
    `;
    const url = `${BROWSE}#tag-%CE%B4%CF%85%CE%BF`;
    const state = await loadFresh('static/js/modules/state.js', { url, html });
    await loadFresh('static/js/modules/tag-manager.js', { url });
    await loadFresh('static/js/modules/entry-animator.js', { url });
    const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
    await loadFresh('static/js/modules/filter-cards.js', { url });
    const fx = await loadFresh('static/js/modules/effects.js', { url });
    const loadHash = window.location.hash;

    state.bridgeToHash({
      $activeTag: state.$activeTag,
      $activeSearch: state.$activeSearch,
      $activeCategory: state.$activeCategory,
    });
    fx.installEffects();
    hhc.handleHashChange();

    // the reactive variable carries the DECODED slug; slug-matching finds the raw 'δύο' card
    expect(state.$activeTag.get()).toBe('δυο');
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
    expect(document.getElementById('gr').style.display).toBe('');
    expect(document.getElementById('js').style.display).toBe('none');
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
    // header shows the decoded slug, not the percent-encoding
    expect(document.getElementById('filterValue1').textContent).toBe('#δυο');
    // round-trip idempotence: serialise(parse(H)) === H -> hash unchanged
    expect(window.location.hash).toBe(loadHash);
  });

  // B9 regression: a deep link with an UNACCENTED search term
  // ('#search-francais') must match a card whose title holds the ACCENTED
  // form ('Français') end to end — parseHash -> reactive variables ->
  // filterCards (diacritic folding in the $visibleCards search branch).
  it("deep link '#search-francais': search reactive variable 'francais' shows the accented 'Français' card, header shows the quoted term", async () => {
    const html = `
      <span id="filterText1"></span><span id="filterText2"></span><span id="filterValue1"></span>
      <span id="searchValue"></span>
      <span id="resultsCount"></span>
      <article class="link-card" id="fr" data-title="Français" data-tags="Français" data-category="frontend"></article>
      <article class="link-card" id="js" data-title="JS" data-tags="JavaScript" data-category="frontend"></article>
    `;
    const url = `${BROWSE}#search-francais`;
    const state = await loadFresh('static/js/modules/state.js', { url, html });
    await loadFresh('static/js/modules/tag-manager.js', { url });
    await loadFresh('static/js/modules/entry-animator.js', { url });
    const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
    await loadFresh('static/js/modules/filter-cards.js', { url });
    const fx = await loadFresh('static/js/modules/effects.js', { url });
    const loadHash = window.location.hash;

    state.bridgeToHash({
      $activeTag: state.$activeTag,
      $activeSearch: state.$activeSearch,
      $activeCategory: state.$activeCategory,
    });
    fx.installEffects();
    hhc.handleHashChange();

    // the search reactive variable carries the raw term; folding happens in $visibleCards
    expect(state.$activeSearch.get()).toBe('francais');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
    expect(document.getElementById('fr').style.display).toBe('');
    expect(document.getElementById('js').style.display).toBe('none');
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
    // header shows the quoted search term ('Searching ... "francais"')
    expect(document.getElementById('filterText1').textContent).toBe('Searching');
    expect(document.getElementById('searchValue').textContent).toBe('"francais"');
    // round-trip idempotence: serialise(parse(H)) === H -> hash unchanged
    expect(window.location.hash).toBe(loadHash);
  });
});
