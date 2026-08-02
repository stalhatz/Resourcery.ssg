import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

// Mirrors main.js's browse wiring in the shared registry: state first, then
// the managers effects.js depends on, then effects.js itself. Call
// FilterManager.init() + installEffects() in the test (order matters:
// init() builds the dropdowns registry syncSelection needs).
async function setup(url = BROWSE, html = FIX(), globals) {
  const state = await loadFresh('static/js/modules/state.js', { url, html, globals });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  await loadFresh('static/js/modules/entry-animator.js', { url });
  await loadFresh('static/js/modules/filter-cards.js', { url });
  await loadFresh('static/js/modules/sidebar-manager.js', { url });
  const fmMod = await loadFresh('static/js/modules/filter-manager.js', { url });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
  const fx = await loadFresh('static/js/modules/effects.js', { url });
  return {
    state,
    TagManager: tagMod.TagManager,
    FilterManager: fmMod.FilterManager,
    handleHashChange: hhc.handleHashChange,
    installEffects: fx.installEffects,
  };
}

describe('effects.js', () => {
  it('immediate first fire applies a pre-seeded category exactly once at install', async () => {
    const { state, FilterManager, installEffects } = await setup();
    state.$activeCategory.set('frontend'); // pre-seed before install
    FilterManager.init();
    installEffects();
    // select mirror + custom dropdown
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    expect(document.querySelector('#categoryDropdown .filter-dropdown-option[data-value="frontend"]').classList.contains('selected')).toBe(true);
    // header (category label looked up in the mirrored select)
    expect(document.getElementById('filterValue1').textContent).toBe('Frontend');
    // accordion: frontend subcategory active + expanded
    expect(document.querySelector('.subcategory-link[data-category="frontend"]').classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    // cards: frontend matches card-1 + card-4
    expect(document.getElementById('resultsCount').textContent).toBe('2 items');
  });

  it('immediate first fire: no-filter boot shows all cards and the All Categories header', async () => {
    const { FilterManager, installEffects } = await setup();
    FilterManager.init();
    installEffects();
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
    expect(document.getElementById('filterValue1').textContent).toBe('All Categories');
    expect(document.getElementById('categoryFilter').value).toBe('');
  });

  it('AC 6: a batched tri-state transition drains exactly one header/select/card pass with final values', async () => {
    const { state, TagManager, FilterManager, installEffects } = await setup();
    FilterManager.init();
    installEffects();
    const headerSpy = vi.spyOn(TagManager, 'updateFilterHeader');
    const syncSpy = vi.spyOn(FilterManager, 'syncSelection');

    // resultsCount is written once per filterCards pass — count via an
    // instance-level textContent setter that delegates to the prototype
    // (textContent lives on Node.prototype in jsdom).
    const rc = document.getElementById('resultsCount');
    let protoDesc;
    let proto = rc;
    while (proto && !(protoDesc = Object.getOwnPropertyDescriptor(proto, 'textContent'))) {
      proto = Object.getPrototypeOf(proto);
    }
    let cardPasses = 0;
    Object.defineProperty(rc, 'textContent', {
      configurable: true,
      get() { return protoDesc.get.call(this); },
      set(v) { cardPasses++; protoDesc.set.call(this, v); },
    });

    // Intermediate sets are queued, never dispatched: tag -> none -> category.
    // The single drain must read the FINAL value (category web) — an
    // intermediate dispatch would have left the select at '' or 'foo'-state.
    state.batchAtomWrites(() => {
      state.$activeTag.set('foo');
      state.$activeTag.set(null);
      state.$activeCategory.set('web');
    });

    expect(headerSpy).toHaveBeenCalledTimes(1);
    expect(syncSpy).toHaveBeenCalledTimes(1);
    expect(cardPasses).toBe(1);
    // the drain read the FINAL values (category web, not the intermediate tag)
    expect(document.getElementById('categoryFilter').value).toBe('web');
    expect(document.getElementById('filterValue1').textContent).toBe('Web');
  });

  it('registration order is fixed: $activeFilter (header) before $visibleCards (cards)', async () => {
    const { state, TagManager, FilterManager, installEffects } = await setup();
    FilterManager.init();
    installEffects();

    const order = [];
    const origHeader = TagManager.updateFilterHeader;
    TagManager.updateFilterHeader = () => { order.push('header'); origHeader.call(TagManager); };
    const rc = document.getElementById('resultsCount');
    let protoDesc;
    let proto = rc;
    while (proto && !(protoDesc = Object.getOwnPropertyDescriptor(proto, 'textContent'))) {
      proto = Object.getPrototypeOf(proto);
    }
    Object.defineProperty(rc, 'textContent', {
      configurable: true,
      get() { return protoDesc.get.call(this); },
      set(v) { order.push('cards'); protoDesc.set.call(this, v); },
    });

    state.batchAtomWrites(() => {
      state.$activeTag.set('foo');
      state.$activeCategory.set('web');
    });

    expect(order).toEqual(['header', 'cards']);
  });

  it('effects are DOM-only: a transition never writes to reactive state (no feedback loop)', async () => {
    const { state, FilterManager, installEffects } = await setup();
    FilterManager.init();
    installEffects();
    const tagSetSpy = vi.spyOn(state.$activeTag, 'set');
    const searchSetSpy = vi.spyOn(state.$activeSearch, 'set');
    const categorySetSpy = vi.spyOn(state.$activeCategory, 'set');

    state.batchAtomWrites(() => {
      state.$activeTag.set('foo');
      state.$activeCategory.set('web');
    });

    expect(tagSetSpy).toHaveBeenCalledTimes(1);
    expect(categorySetSpy).toHaveBeenCalledTimes(1);
    expect(searchSetSpy).not.toHaveBeenCalled();
  });

  // The DOM side-effect chain of handleHashChange (moved here from
  // handle-hash-change.test.js — the handler itself is now thin).
  describe('handleHashChange -> effects chain', () => {
    async function boot(url) {
      const s = await setup(url);
      s.FilterManager.init();
      s.installEffects();
      return s;
    }

    it("'#category-frontend' -> select/header/accordion/cards all synced", async () => {
      const { state, handleHashChange } = await boot(`${BROWSE}#category-frontend`);
      handleHashChange();
      expect(state.$activeCategory.get()).toBe('frontend');
      expect(document.getElementById('categoryFilter').value).toBe('frontend');
      expect(document.getElementById('filterValue1').textContent).toBe('Frontend');
      expect(document.querySelector('.subcategory-link[data-category="frontend"]').classList.contains('active')).toBe(true);
      expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
      expect(document.getElementById('resultsCount').textContent).toBe('2 items');
    });

    it("'#tag-foo' -> select cleared, header '#foo', cards rendered", async () => {
      const { state, handleHashChange } = await boot(`${BROWSE}#tag-foo`);
      handleHashChange();
      expect(state.$activeTag.get()).toBe('foo');
      expect(document.getElementById('categoryFilter').value).toBe('');
      expect(document.getElementById('filterValue1').textContent).toBe('#foo');
      expect(document.getElementById('resultsCount').textContent).toBe('0 items');
    });

    it("'#search-bar' -> header shows 'Searching \"bar\"'", async () => {
      const { state, handleHashChange } = await boot(`${BROWSE}#search-bar`);
      handleHashChange();
      expect(state.$activeSearch.get()).toBe('bar');
      expect(document.getElementById('filterText1').textContent).toBe('Searching');
      expect(document.getElementById('searchValue').textContent).toBe('"bar"');
      expect(document.getElementById('categoryFilter').value).toBe('');
    });

    it('bare URL after a category -> select cleared, All Categories header, accordion collapsed, all cards', async () => {
      const { state, handleHashChange } = await boot(`${BROWSE}#category-frontend`);
      handleHashChange();
      expect(document.getElementById('filterValue1').textContent).toBe('Frontend');

      window.history.pushState({}, '', BROWSE); // clear hash (no hashchange fired)
      handleHashChange();
      expect(state.$activeCategory.get()).toBeNull();
      expect(document.getElementById('categoryFilter').value).toBe('');
      expect(document.getElementById('filterValue1').textContent).toBe('All Categories');
      document.querySelectorAll('.category-trigger').forEach((t) => {
        expect(t.getAttribute('aria-expanded')).toBe('false');
      });
      document.querySelectorAll('.subcategory-list').forEach((l) => {
        expect(l.classList.contains('expanded')).toBe(false);
      });
      expect(document.getElementById('resultsCount').textContent).toBe('4 items');
    });

    it("malformed '#tag-%' does not throw; reactive variable '%', header '#%', 0 cards", async () => {
      const { state, handleHashChange } = await boot(`${BROWSE}#tag-%`);
      expect(() => handleHashChange()).not.toThrow();
      expect(state.$activeTag.get()).toBe('%');
      expect(document.getElementById('filterValue1').textContent).toBe('#%');
      expect(document.getElementById('resultsCount').textContent).toBe('0 items');
    });
  });
});
