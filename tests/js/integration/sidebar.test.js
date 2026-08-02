import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

// jsdom fires hashchange asynchronously, so wait for the reactive-state
// side-effect (handleHashChange ran) to settle before asserting the
// drain-synced DOM.
const waitFor = (fn) => vi.waitFor(fn, { timeout: 500, interval: 10 });

// Browse setups wire the full main.js chain: sidebar + hashchange listener +
// effects (FilterManager.init is not needed — syncSelection no-ops without
// dropdowns, and the effect's select mirror + accordion + header still run).
// Landing setups import the same modules but install nothing (main.js only
// installs effects on the browse page).
async function setup(url = BROWSE) {
  await loadFresh('static/js/modules/state.js', { url, html: FIX() });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  await loadFresh('static/js/modules/entry-animator.js', { url });
  await loadFresh('static/js/modules/filter-cards.js', { url });
  const sb = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
  const fx = await loadFresh('static/js/modules/effects.js', { url });
  sb.SidebarManager.init();
  if (url === BROWSE) {
    hhc.installHashChangeListener();
    fx.installEffects();
  }
  return { TagManager: tagMod.TagManager };
}

describe('Sidebar (integration)', () => {
  it('toggle opens/closes sidebar + overlay; overlay click closes', async () => {
    await setup();
    const sidebar = document.getElementById('sidebar');
    const overlay = document.body.querySelector('.sidebar-overlay');
    document.getElementById('sidebarToggle').click();
    expect(sidebar.classList.contains('active')).toBe(true);
    expect(overlay.classList.contains('active')).toBe(true);
    overlay.click();
    expect(sidebar.classList.contains('active')).toBe(false);
    expect(overlay.classList.contains('active')).toBe(false);
  });

  it('browse trigger click writes the hash; the hash -> reactive state -> effects chain expands the matching trigger and collapses the others', async () => {
    await setup();
    document.querySelector('.category-trigger[data-category-id="web"]').click();
    expect(window.location.hash).toBe('#category-web');
    await waitFor(() =>
      expect(document.querySelector('.category-trigger[data-category-id="web"]').getAttribute('aria-expanded')).toBe('true')
    );
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    expect(document.querySelector('.category-trigger[data-category-id="devops"]').getAttribute('aria-expanded')).toBe('false');
  });

  it('browse subcategory click: hash -> reactive state -> effects sync select, header and active classes', async () => {
    await setup();
    document.querySelector('.subcategory-link[data-category="frontend"]').click();
    await waitFor(() => expect(document.getElementById('categoryFilter').value).toBe('frontend'));
    expect(window.location.hash).toBe('#category-frontend');
    expect(document.getElementById('filterValue1').textContent).toBe('Frontend');
    expect(document.querySelector('.subcategory-link[data-category="frontend"]').classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
  });

  it('mobile (innerWidth<=1023) closes sidebar after a subcategory click', async () => {
    await setup();
    const sidebar = document.getElementById('sidebar');
    document.getElementById('sidebarToggle').click();
    expect(sidebar.classList.contains('active')).toBe(true);
    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(800);
    document.querySelector('.subcategory-link[data-category="frontend"]').click();
    expect(sidebar.classList.contains('active')).toBe(false);
  });

  it('landing category-trigger click sets href browse.html#category-<id>', async () => {
    await setup(LANDING);
    stubLocation();
    document.querySelector('.category-trigger[data-category-id="web"]').click();
    expect(window.location.href).toBe('browse.html#category-web');
  });

  it('main.js bootstrap does not throw on the browse fixture', async () => {
    await expect(loadFresh('static/js/main.js', { url: BROWSE, html: FIX() })).resolves.toBeDefined();
  });
});
