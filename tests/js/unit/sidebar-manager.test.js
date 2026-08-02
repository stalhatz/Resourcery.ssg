import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE, html = FIX()) {
  const state = await loadFresh('static/js/modules/state.js', { url, html });
  const sbMod = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  return {
    state,
    SidebarManager: sbMod.SidebarManager,
    syncAccordion: sbMod.syncAccordion,
  };
}

describe('sidebar-manager.js', () => {
  it('init: creates a .sidebar-overlay div appended to body; returns early if no #sidebar/#sidebarToggle', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    expect(document.body.querySelector('.sidebar-overlay')).not.toBeNull();

    vi.resetModules();
    const sm2 = await loadFresh('static/js/modules/sidebar-manager.js', {
      url: BROWSE,
      html: '<div></div>',
    });
    expect(() => sm2.SidebarManager.init()).not.toThrow();
    expect(document.body.querySelector('.sidebar-overlay')).toBeNull();
  });

  it('init: toggle click toggles "active" on sidebar + overlay', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    const sidebar = document.getElementById('sidebar');
    const overlay = document.body.querySelector('.sidebar-overlay');
    document.getElementById('sidebarToggle').click();
    expect(sidebar.classList.contains('active')).toBe(true);
    expect(overlay.classList.contains('active')).toBe(true);
    document.getElementById('sidebarToggle').click();
    expect(sidebar.classList.contains('active')).toBe(false);
    expect(overlay.classList.contains('active')).toBe(false);
  });

  it('init: overlay click closes sidebar + overlay', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    const sidebar = document.getElementById('sidebar');
    const overlay = document.body.querySelector('.sidebar-overlay');
    document.getElementById('sidebarToggle').click(); // open
    overlay.click();
    expect(sidebar.classList.contains('active')).toBe(false);
    expect(overlay.classList.contains('active')).toBe(false);
  });

  it('init: category-trigger click on landing sets href browse.html#category-<id>', async () => {
    const { SidebarManager } = await setup(LANDING);
    stubLocation();
    SidebarManager.init();
    document.querySelector('.category-trigger[data-category-id="web"]').click();
    expect(window.location.href).toBe('browse.html#category-web');
  });

  // --- syncAccordion ---
  it('syncAccordion: category kind expands the matching subcategory (subcategory-first) and collapses everything else', async () => {
    const { syncAccordion } = await setup();
    syncAccordion({ kind: 'category', value: 'frontend' });
    const frontendLink = document.querySelector('.subcategory-link[data-category="frontend"]');
    expect(frontendLink.classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    expect(document.querySelector('[aria-controls="subcat-web"]').getAttribute('aria-expanded')).toBe('true');
    // others: no active class, collapsed
    expect(document.querySelector('.subcategory-link[data-category="backend"]').classList.contains('active')).toBe(false);
    expect(document.querySelector('.category-trigger[data-category-id="devops"]').getAttribute('aria-expanded')).toBe('false');
    expect(document.getElementById('subcat-devops').classList.contains('expanded')).toBe(false);
  });

  it('syncAccordion: category kind without a matching subcategory falls back to the trigger', async () => {
    const { syncAccordion } = await setup();
    syncAccordion({ kind: 'category', value: 'web' });
    const trigger = document.querySelector('.category-trigger[data-category-id="web"]');
    expect(trigger.classList.contains('active')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    // no subcategory-link[data-category="web"] -> none of them is active
    document.querySelectorAll('.subcategory-link').forEach((l) => {
      expect(l.classList.contains('active')).toBe(false);
    });
  });

  it('syncAccordion: non-category kinds (tag/search/null) clear every active class and collapse all lists', async () => {
    const { syncAccordion } = await setup();
    syncAccordion({ kind: 'category', value: 'web' }); // expand something first
    syncAccordion({ kind: 'tag', value: 'foo' });
    document.querySelectorAll('.category-trigger').forEach((t) => {
      expect(t.classList.contains('active')).toBe(false);
      expect(t.getAttribute('aria-expanded')).toBe('false');
    });
    document.querySelectorAll('.subcategory-list').forEach((l) => {
      expect(l.classList.contains('expanded')).toBe(false);
    });
    document.querySelectorAll('.subcategory-link').forEach((l) => {
      expect(l.classList.contains('active')).toBe(false);
    });
  });

  // --- click handlers ---
  // AC 3 regression: clicking the already-active category trigger keeps the
  // accordion expanded (a hash write would fire no hashchange and the old
  // collapse-all loop would leave the whole accordion collapsed).
  it('AC 3 regression: same-value category-trigger click keeps the accordion expanded, no hash write', async () => {
    const { state, SidebarManager } = await setup();
    SidebarManager.init();
    state.$activeCategory.set('web');
    const trigger = document.querySelector('.category-trigger[data-category-id="web"]');
    trigger.setAttribute('aria-expanded', 'true');
    document.getElementById('subcat-web').classList.add('expanded');

    trigger.click();

    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(window.location.hash).toBe('');
  });

  it('category-trigger click on a different category writes the hash only (effects do the DOM)', async () => {
    const { state, SidebarManager } = await setup();
    SidebarManager.init();
    state.$activeCategory.set('web');
    const devops = document.querySelector('.category-trigger[data-category-id="devops"]');
    devops.click();
    expect(window.location.hash).toBe('#category-devops');
    // no manual DOM sync in the handler: reactive variables and accordion untouched
    expect(state.$activeCategory.get()).toBe('web');
    expect(devops.getAttribute('aria-expanded')).toBe('false');
  });

  it('subcategory-link click on a different category writes the hash', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    document.querySelector('.subcategory-link[data-category="backend"]').click();
    expect(window.location.hash).toBe('#category-backend');
  });

  it('same-value subcategory-link click syncs the accordion directly, no hash write', async () => {
    const { state, SidebarManager } = await setup();
    SidebarManager.init();
    state.$activeCategory.set('frontend');
    const link = document.querySelector('.subcategory-link[data-category="frontend"]');
    link.click();
    expect(window.location.hash).toBe('');
    expect(link.classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
  });

  it('init: mobile (window.innerWidth<=1023) auto-closes sidebar after a subcategory click', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    const sidebar = document.getElementById('sidebar');
    const overlay = document.body.querySelector('.sidebar-overlay');
    document.getElementById('sidebarToggle').click(); // open
    expect(sidebar.classList.contains('active')).toBe(true);

    vi.spyOn(window, 'innerWidth', 'get').mockReturnValue(800);
    document.querySelector('.subcategory-link[data-category="frontend"]').click();
    expect(sidebar.classList.contains('active')).toBe(false);
    expect(overlay.classList.contains('active')).toBe(false);
  });
});
