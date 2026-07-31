import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

// jsdom fires hashchange asynchronously, so wait for the atom side-effect
// (handleHashChange ran) to settle before counting events.
const waitFor = (fn) => vi.waitFor(fn, { timeout: 500, interval: 10 });
const settle = () => new Promise((r) => setTimeout(r, 50));

// Full browse wiring: dropdown (FilterManager), sidebar, hashchange listener
// and the atom->hash bridge — mirrors main.js on the browse page.
async function setup() {
  const state = await loadFresh('static/js/modules/state.js', { url: BROWSE, html: FIX() });
  await loadFresh('static/js/modules/tag-manager.js', { url: BROWSE });
  await loadFresh('static/js/modules/entry-animator.js', { url: BROWSE });
  await loadFresh('static/js/modules/filter-cards.js', { url: BROWSE });
  const sb = await loadFresh('static/js/modules/sidebar-manager.js', { url: BROWSE });
  const fm = await loadFresh('static/js/modules/filter-manager.js', { url: BROWSE });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url: BROWSE });
  sb.SidebarManager.init();
  fm.FilterManager.init();
  hhc.installHashChangeListener();
  state.bridgeToHash({
    $activeTag: state.$activeTag,
    $activeSearch: state.$activeSearch,
    $activeCategory: state.$activeCategory,
  });
  return { state };
}

function attachCounter() {
  let count = 0;
  const fn = () => count++;
  window.addEventListener('hashchange', fn);
  return {
    count: () => count,
    detach: () => window.removeEventListener('hashchange', fn),
  };
}

const option = (value) =>
  document.querySelector(`#categoryDropdown .filter-dropdown-option[data-value="${value}"]`);

describe('Hash transitions (integration): one hashchange per user action', () => {
  it('dropdown category click from a tag state: single hashchange, atoms converge, cards filtered', async () => {
    const { state } = await setup();
    window.location.hash = 'tag-foo';
    await waitFor(() => expect(state.$activeTag.get()).toBe('foo'));

    const c = attachCounter();
    option('frontend').click();

    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    await settle();
    c.detach();
    expect(c.count()).toBe(1); // regression: was 2 (tag cleared + category set)
    expect(window.location.hash).toBe('#category-frontend');
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    expect(document.getElementById('resultsCount').textContent).toBe('2 items');
  });

  it('dropdown category->category switch: single hashchange, no intermediate old-category state', async () => {
    const { state } = await setup();
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));

    const c = attachCounter();
    option('backend').click();

    await waitFor(() => expect(state.$activeCategory.get()).toBe('backend'));
    await settle();
    c.detach();
    expect(c.count()).toBe(1); // regression: was multiple (old-category re-writes)
    expect(window.location.hash).toBe('#category-backend');
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
  });

  it("dropdown 'All Categories' from a category: pushState clears the hash, zero hashchange, everything visible", async () => {
    const { state } = await setup();
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));

    const c = attachCounter();
    option('').click();

    await settle();
    c.detach();
    expect(c.count()).toBe(0); // pushState fires no hashchange; no other writes
    expect(window.location.hash).toBe('');
    expect(state.$activeCategory.get()).toBeNull();
    expect(state.$activeTag.get()).toBeNull();
    expect(document.getElementById('categoryFilter').value).toBe('');
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });

  it('clearFilters with a category active: fully clears (atoms, hash, select, grid) with zero hashchange', async () => {
    const { state } = await setup();
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    expect(document.getElementById('resultsCount').textContent).toBe('2 items');

    const c = attachCounter();
    window.dispatchEvent(new Event('clearFilters'));

    await settle();
    c.detach();
    expect(c.count()).toBe(0);
    expect(state.$activeCategory.get()).toBeNull();
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeTag.get()).toBeNull();
    expect(window.location.hash).toBe('');
    expect(document.getElementById('categoryFilter').value).toBe('');
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });

  it('sidebar subcategory click from a tag state: single hashchange', async () => {
    const { state } = await setup();
    window.location.hash = 'tag-foo';
    await waitFor(() => expect(state.$activeTag.get()).toBe('foo'));

    const c = attachCounter();
    document.querySelector('.subcategory-link[data-category="backend"]').click();

    await waitFor(() => expect(state.$activeCategory.get()).toBe('backend'));
    await settle();
    c.detach();
    expect(c.count()).toBe(1);
    expect(window.location.hash).toBe('#category-backend');
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
  });
});
