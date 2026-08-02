import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

// jsdom fires hashchange asynchronously, so wait for the reactive-state side-effect
// (handleHashChange ran) to settle before asserting the drain-synced DOM.
const waitFor = (fn) => vi.waitFor(fn, { timeout: 500, interval: 10 });

// Wire the real browse-page modules against the fixture (shared registry),
// mirroring main.js: FilterManager.init() then installEffects().
async function setup(url = BROWSE, globals) {
  const state = await loadFresh('static/js/modules/state.js', { url, html: FIX(), globals });
  await loadFresh('static/js/modules/tag-manager.js', { url });
  await loadFresh('static/js/modules/entry-animator.js', { url });
  const sb = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  const fm = await loadFresh('static/js/modules/filter-manager.js', { url });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
  const fx = await loadFresh('static/js/modules/effects.js', { url });
  sb.SidebarManager.init();
  fm.FilterManager.init();
  hhc.installHashChangeListener(); // sidebar/filter clicks traverse the async hashchange
  fx.installEffects();
  return { state, handleHashChange: hhc.handleHashChange };
}

describe('Filter (integration)', () => {
  it('set #category-<id> + handleHashChange filters cards, syncs the dropdown + sidebar', async () => {
    const { state, handleHashChange } = await setup(BROWSE, {
      CATEGORY_MAP: { web: ['frontend', 'backend'] },
    });
    window.location.hash = 'category-frontend';
    handleHashChange();

    expect(state.$activeCategory.get()).toBe('frontend');
    expect(document.getElementById('card-1').style.display).toBe(''); // frontend
    expect(document.getElementById('card-4').style.display).toBe(''); // frontend
    expect(document.getElementById('card-2').style.display).toBe('none'); // backend
    expect(document.getElementById('card-3').style.display).toBe('none'); // devops
    expect(document.getElementById('resultsCount').textContent).toBe('2 items');
    expect(document.getElementById('noResults').style.display).toBe('none');
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    expect(document.querySelector('.subcategory-link[data-category="frontend"]').classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
  });

  it('clicking a sidebar subcategory link sets the category and filters via the hash -> reactive state -> effects chain', async () => {
    const { state } = await setup();
    document.querySelector('.subcategory-link[data-category="backend"]').click();
    await waitFor(() => expect(state.$activeCategory.get()).toBe('backend'));
    expect(window.location.hash).toBe('#category-backend');
    // the drain synced the DOM: select, header, active classes
    expect(document.getElementById('categoryFilter').value).toBe('backend');
    expect(document.getElementById('filterValue1').textContent).toBe('Backend');
    expect(document.querySelector('.subcategory-link[data-category="backend"]').classList.contains('active')).toBe(true);
    // cards: backend matches card-2 only
    expect(document.getElementById('resultsCount').textContent).toBe('1 item');
  });

  it('main.js bootstrap against the browse fixture with an initial #category- hash does not throw', async () => {
    await expect(
      loadFresh('static/js/main.js', { url: `${BROWSE}#category-frontend`, html: FIX() })
    ).resolves.toBeDefined();
    // bootstrap applied the hash: frontend cards visible, others hidden
    expect(document.getElementById('card-1').style.display).toBe('');
    expect(document.getElementById('card-4').style.display).toBe('');
    expect(document.getElementById('card-2').style.display).toBe('none');
  });
});
