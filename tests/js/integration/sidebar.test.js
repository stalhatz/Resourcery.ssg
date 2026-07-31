import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE) {
  await loadFresh('static/js/modules/state.js', { url, html: FIX() });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const sb = await loadFresh('static/js/modules/sidebar-manager.js', { url });
  sb.SidebarManager.init();
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

  it('browse trigger click writes hash + collapses siblings', async () => {
    await setup();
    document.querySelector('.category-trigger[data-category-id="web"]').click();
    document.querySelectorAll('.category-trigger').forEach((t) => {
      expect(t.getAttribute('aria-expanded')).toBe('false');
    });
    expect(window.location.hash).toBe('#category-web');
  });

  it('browse subcategory click sets categoryFilter.value, writes hash, filters, toggles .active', async () => {
    const { TagManager } = await setup();
    const spy = vi.spyOn(TagManager, 'setCategoryDisplay');
    document.querySelector('.subcategory-link[data-category="frontend"]').click();
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    expect(spy).toHaveBeenCalledWith('frontend');
    expect(window.location.hash).toBe('#category-frontend');
    expect(document.querySelector('.subcategory-link[data-category="frontend"]').classList.contains('active')).toBe(true);
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