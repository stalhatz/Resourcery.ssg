import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const KEYS = [
  'searchInput', 'searchSuggestions', 'searchValue', 'categoryTrigger',
  'categoryFilter', 'categoryDropdown', 'sortTrigger', 'sortFilter',
  'sortDropdown', 'themeToggle', 'sidebarToggle', 'sidebar', 'linksGrid',
  'resultsCount', 'noResults', 'filterText1', 'filterText2', 'filterValue1',
  'modalOverlay', 'modal', 'modalClose', 'modalShare', 'modalVisit',
  'modalImage', 'modalTags', 'modalTitle', 'modalSummary', 'modalDescription',
  'modalCategory', 'modalPricing', 'modalLanguage', 'shareTwitter',
];

describe('dom.js', () => {
  it('dom: every key present when all 32 ids exist', async () => {
    const { dom } = await loadFresh('static/js/dom.js', {
      url: BROWSE,
      html: readFixture('browse.html'),
    });
    expect(KEYS).toHaveLength(32);
    for (const k of KEYS) {
      expect(dom[k], `dom.${k}`).not.toBeNull();
      expect(dom[k]).toBeInstanceOf(Element);
    }
  });

  it('dom: a missing id maps to null (no throw)', async () => {
    const html = readFixture('browse.html').replace('id="modalImage"', 'id="modalImage-missing"');
    const { dom } = await loadFresh('static/js/dom.js', { url: BROWSE, html });
    expect(dom.modalImage).toBeNull();
    // other keys still present
    expect(dom.modalTitle).not.toBeNull();
    expect(dom.linksGrid).not.toBeNull();
  });

  it('dom: fresh dynamic import re-caches to new elements (cache happens at module load)', async () => {
    const a = await loadFresh('static/js/dom.js', {
      url: BROWSE,
      html: '<div id="linksGrid"></div>',
    });
    const gridA = a.dom.linksGrid;
    expect(gridA).not.toBeNull();
    // reset the module registry so the next import re-evaluates dom.js against
    // the new DOM (proves per-import caching, not a once-globally-frozen cache)
    vi.resetModules();
    const b = await loadFresh('static/js/dom.js', {
      url: BROWSE,
      html: '<div id="linksGrid"><article class="link-card"></article></div>',
    });
    const gridB = b.dom.linksGrid;
    expect(gridB).not.toBe(gridA);
    expect(gridB.children.length).toBe(1);
  });
});