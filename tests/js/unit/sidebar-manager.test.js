import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE, html = FIX()) {
  await loadFresh('static/js/modules/state.js', { url, html });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const sbMod = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  return { TagManager: tagMod.TagManager, SidebarManager: sbMod.SidebarManager };
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

  it('init: category-trigger click on browse collapses sibling triggers (aria-expanded=false, lists off) then writes "#category-<id>"', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    document.querySelector('.category-trigger[data-category-id="web"]').click();
    // all triggers collapsed
    document.querySelectorAll('.category-trigger').forEach((t) => {
      expect(t.getAttribute('aria-expanded')).toBe('false');
    });
    // all subcategory lists lost expanded
    document.querySelectorAll('.subcategory-list').forEach((l) => {
      expect(l.classList.contains('expanded')).toBe(false);
    });
    expect(window.location.hash).toBe('#category-web');
  });

  it('init: subcategory-link click on browse sets categoryFilter.value, calls setCategoryDisplay when an option exists, writes "#category-<cat>", calls filterCards, toggles .active', async () => {
    const { TagManager, SidebarManager } = await setup();
    SidebarManager.init();
    const setCatSpy = vi.spyOn(TagManager, 'setCategoryDisplay');
    document.querySelector('.subcategory-link[data-category="frontend"]').click();
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    expect(setCatSpy).toHaveBeenCalledWith('frontend');
    expect(window.location.hash).toBe('#category-frontend');
    // filterCards() ran (no atom filter set — setCategoryDisplay only updates the
    // select, the hash drives the atom via handleHashChange — so all 4 visible):
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });

  it('init: subcategory-link click toggles .active classes on subcategory-links + category-triggers', async () => {
    const { SidebarManager } = await setup();
    SidebarManager.init();
    const frontendLink = document.querySelector('.subcategory-link[data-category="frontend"]');
    frontendLink.click();
    expect(frontendLink.classList.contains('active')).toBe(true);
    // other subcategory links lost active
    document.querySelectorAll('.subcategory-link').forEach((l) => {
      if (l !== frontendLink) expect(l.classList.contains('active')).toBe(false);
    });
    // all category triggers lost active
    document.querySelectorAll('.category-trigger').forEach((t) => {
      expect(t.classList.contains('active')).toBe(false);
    });
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