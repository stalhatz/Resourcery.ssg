import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE, html = FIX()) {
  const state = await loadFresh('static/js/modules/state.js', { url, html });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const fmMod = await loadFresh('static/js/modules/filter-manager.js', { url });
  const fx = await loadFresh('static/js/modules/effects.js', { url });
  return {
    state,
    TagManager: tagMod.TagManager,
    FilterManager: fmMod.FilterManager,
    installEffects: fx.installEffects,
  };
}

const gridOrder = () =>
  Array.from(document.getElementById('linksGrid').querySelectorAll('.link-card')).map((c) => c.id);

describe('filter-manager.js', () => {
  it('init: binds category + sort dropdowns when their triples exist; stores this.dropdowns[type]', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    expect(FilterManager.dropdowns.category).toBeDefined();
    expect(FilterManager.dropdowns.category.trigger).toBe(document.getElementById('categoryTrigger'));
    expect(FilterManager.dropdowns.category.dropdown).toBe(document.getElementById('categoryDropdown'));
    expect(FilterManager.dropdowns.category.native).toBe(document.getElementById('categoryFilter'));
    expect(FilterManager.dropdowns.sort).toBeDefined();
    expect(FilterManager.dropdowns.sort.native).toBe(document.getElementById('sortFilter'));
  });

  it('bindDropdown: category option click -> batched clears + $activeCategory; drain syncs select/header/cards; hash write', async () => {
    const { TagManager, FilterManager, installEffects } = await setup();
    FilterManager.init();
    installEffects();
    const clearSearchSpy = vi.spyOn(TagManager, 'clearActiveSearch');
    const clearTagSpy = vi.spyOn(TagManager, 'clearActiveTag');

    document.querySelector('#categoryDropdown .filter-dropdown-option[data-value="web"]').click();
    expect(clearSearchSpy).toHaveBeenCalled();
    expect(clearTagSpy).toHaveBeenCalled();
    // Silent clears: the dropdown handler owns the URL write, so the clears
    // must not write intermediate hashes (regression: they used to re-write
    // the previous category before the new one was set).
    expect(clearSearchSpy).toHaveBeenCalledWith(false);
    expect(clearTagSpy).toHaveBeenCalledWith(false);
    expect(window.location.hash).toBe('#category-web');
    // the batch drain synced the DOM (no CATEGORY_MAP -> literal 'web' matches 0 cards)
    expect(document.getElementById('categoryFilter').value).toBe('web');
    expect(document.getElementById('filterValue1').textContent).toBe('Web');
    expect(document.getElementById('resultsCount').textContent).toBe('0 items');

    // '' option -> $activeCategory nulled, pushState clears the hash, drain re-renders
    document.querySelector('#categoryDropdown .filter-dropdown-option[data-value=""]').click();
    expect(window.location.hash).toBe('');
    expect(document.getElementById('categoryFilter').value).toBe('');
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });

  it('bindDropdown: sort option click -> sortCards()', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    document.querySelector('#sortDropdown .filter-dropdown-option[data-value="oldest"]').click();
    expect(document.getElementById('sortFilter').value).toBe('oldest');
    // sortCards() reordered the grid oldest -> newest
    expect(gridOrder()).toEqual(['card-4', 'card-1', 'card-3', 'card-2']);
  });

  it('bindDropdown: trigger click toggles the dropdown (.active + aria-expanded)', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    const dropdown = document.getElementById('categoryDropdown');
    const trigger = document.getElementById('categoryTrigger');
    trigger.click();
    expect(dropdown.classList.contains('active')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    trigger.click();
    expect(dropdown.classList.contains('active')).toBe(false);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('bindDropdown: document outside-click closes the dropdown', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    const dropdown = document.getElementById('categoryDropdown');
    document.getElementById('categoryTrigger').click(); // open
    expect(dropdown.classList.contains('active')).toBe(true);
    // click outside the trigger
    document.body.click();
    expect(dropdown.classList.contains('active')).toBe(false);
  });

  it('syncSelection: toggles ".selected" by data-value on the option buttons', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    FilterManager.syncSelection('category', 'web');
    const opts = document.querySelectorAll('#categoryDropdown .filter-dropdown-option');
    opts.forEach((o) => {
      expect(o.classList.contains('selected')).toBe(o.dataset.value === 'web');
    });
  });

  it('toggleDropdown/closeDropdown/closeAllDropdowns flip .active and aria-expanded', async () => {
    const { FilterManager } = await setup();
    FilterManager.init();
    const cat = document.getElementById('categoryDropdown');
    const catT = document.getElementById('categoryTrigger');
    const sort = document.getElementById('sortDropdown');
    const sortT = document.getElementById('sortTrigger');

    FilterManager.toggleDropdown('category');
    expect(cat.classList.contains('active')).toBe(true);
    expect(catT.getAttribute('aria-expanded')).toBe('true');

    FilterManager.toggleDropdown('sort'); // closes category, opens sort
    expect(cat.classList.contains('active')).toBe(false);
    expect(sort.classList.contains('active')).toBe(true);

    FilterManager.closeDropdown('sort');
    expect(sort.classList.contains('active')).toBe(false);
    expect(sortT.getAttribute('aria-expanded')).toBe('false');

    FilterManager.toggleDropdown('category');
    FilterManager.toggleDropdown('sort');
    FilterManager.closeAllDropdowns();
    expect(cat.classList.contains('active')).toBe(false);
    expect(sort.classList.contains('active')).toBe(false);
  });

  it("init: window 'clearFilters' event resets search+tag+category; the batch drain clears the select, syncs, and filters", async () => {
    const s = await loadFresh('static/js/modules/state.js', { url: BROWSE, html: FIX() });
    const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url: BROWSE });
    const fmMod = await loadFresh('static/js/modules/filter-manager.js', { url: BROWSE });
    const fx = await loadFresh('static/js/modules/effects.js', { url: BROWSE });
    const FilterManager = fmMod.FilterManager;
    FilterManager.init();
    fx.installEffects();
    s.$activeSearch.set('foo');
    s.$activeTag.set('bar');
    s.$activeCategory.set('frontend');
    document.getElementById('categoryFilter').value = 'frontend';

    window.dispatchEvent(new Event('clearFilters'));

    expect(s.$activeSearch.get()).toBeNull();
    expect(s.$activeTag.get()).toBeNull();
    expect(s.$activeCategory.get()).toBeNull();
    expect(document.getElementById('categoryFilter').value).toBe('');
    // the drain ran syncSelection('category','') -> only the '' option is .selected
    const selected = document.querySelectorAll('#categoryDropdown .filter-dropdown-option.selected');
    expect(selected.length).toBe(1);
    expect(selected[0].dataset.value).toBe('');
    // the drain rendered with all reactive variables null -> every card visible
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });
});