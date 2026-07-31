import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

// Wire the real browse-page modules against the fixture (shared registry).
async function setup(url = BROWSE, globals) {
  const state = await loadFresh('static/js/modules/state.js', { url, html: FIX(), globals });
  await loadFresh('static/js/modules/tag-manager.js', { url });
  await loadFresh('static/js/modules/entry-animator.js', { url });
  const sb = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  const fm = await loadFresh('static/js/modules/filter-manager.js', { url });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
  const fc = await loadFresh('static/js/modules/filter-cards.js', { url });
  sb.SidebarManager.init();
  fm.FilterManager.init();
  return { state, handleHashChange: hhc.handleHashChange, filterCards: fc.filterCards };
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

  it('clicking a sidebar subcategory link sets the category and filters', async () => {
    const { state, filterCards } = await setup();
    document.querySelector('.subcategory-link[data-category="backend"]').click();
    // sidebar writes the hash + filterCards; the atom is set via the hashchange
    // path only if handleHashChange is installed; here filterCards ran directly
    expect(document.getElementById('categoryFilter').value).toBe('backend');
    expect(window.location.hash).toBe('#category-backend');
    expect(state.$activeCategory.get()).toBeNull(); // atom set by handleHashChange, not sidebar
    filterCards(); // all visible (no atom filter yet)
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
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