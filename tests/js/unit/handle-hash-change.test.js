import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE, html = FIX()) {
  const state = await loadFresh('static/js/modules/state.js', { url, html });
  const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url });
  return {
    state,
    handleHashChange: hhc.handleHashChange,
    installHashChangeListener: hhc.installHashChangeListener,
  };
}

describe('handle-hash-change.js', () => {
  it('handleHashChange: early-returns on a non-browse page', async () => {
    const { handleHashChange } = await setup(LANDING);
    const rc = document.getElementById('resultsCount');
    rc.textContent = 'untouched';
    handleHashChange();
    expect(rc.textContent).toBe('untouched');
  });

  it("handleHashChange: '#category-<c>' sets $activeCategory (others null), sets categoryFilter.value, strips .active, then resolves subcategory-first", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#category-frontend`);
    handleHashChange();
    expect(state.$activeCategory.get()).toBe('frontend');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeSearch.get()).toBeNull();
    expect(document.getElementById('categoryFilter').value).toBe('frontend');
    // subcategory-first: frontend link active, subcat-web expanded, trigger aria-expanded=true
    const frontendLink = document.querySelector('.subcategory-link[data-category="frontend"]');
    expect(frontendLink.classList.contains('active')).toBe(true);
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
    expect(document.querySelector('[aria-controls="subcat-web"]').getAttribute('aria-expanded')).toBe('true');
    // other subcategory links not active
    expect(document.querySelector('.subcategory-link[data-category="backend"]').classList.contains('active')).toBe(false);
  });

  it('handleHashChange: category fallback to trigger when no subcategory matches', async () => {
    const { handleHashChange } = await setup(`${BROWSE}#category-web`);
    handleHashChange();
    // no subcategory-link[data-category="web"] -> fallback to trigger[data-category-id="web"]
    const trigger = document.querySelector('.category-trigger[data-category-id="web"]');
    expect(trigger.classList.contains('active')).toBe(true);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(document.getElementById('subcat-web').classList.contains('expanded')).toBe(true);
  });

  it("handleHashChange: '#tag-<t>' sets $activeTag, clears categoryFilter.value, strips .active, calls filterCards", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#tag-foo`);
    handleHashChange();
    expect(state.$activeTag.get()).toBe('foo');
    expect(document.getElementById('categoryFilter').value).toBe('');
    // filterCards ran (no 'foo' tag -> 0 cards)
    expect(document.getElementById('resultsCount').textContent).toBe('0 items');
  });

  it("handleHashChange: '#search-<s>' sets $activeSearch, clears categoryFilter.value, calls filterCards", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#search-bar`);
    handleHashChange();
    expect(state.$activeSearch.get()).toBe('bar');
    expect(document.getElementById('categoryFilter').value).toBe('');
    expect(document.getElementById('resultsCount').textContent).toBe('0 items');
  });

  it('handleHashChange: calls filterCards() (browse page)', async () => {
    const { handleHashChange } = await setup(BROWSE); // no hash -> all visible
    handleHashChange();
    expect(document.getElementById('resultsCount').textContent).toBe('4 items');
  });

  it('installHashChangeListener: attaches handleHashChange to window "hashchange"', async () => {
    const { state, installHashChangeListener } = await setup(BROWSE);
    installHashChangeListener();
    window.location.hash = 'tag-foo';
    // jsdom fires hashchange asynchronously
    await new Promise((r) => setTimeout(r, 0));
    expect(state.$activeTag.get()).toBe('foo');
  });

  // B1 regression: the hash-change path must refresh the filter header, not
  // just the atoms/dropdown/sidebar/cards. (tag-manager.js updateFilterHeader
  // — which owns the header — is only invoked on direct user interactions.)
  describe('handleHashChange refreshes the filter header from the parsed hash (B1)', () => {
    const header = () => ({
      filterText1: document.getElementById('filterText1'),
      filterValue1: document.getElementById('filterValue1'),
      filterText2: document.getElementById('filterText2'),
      categoryTrigger: document.getElementById('categoryTrigger'),
      searchValue: document.getElementById('searchValue'),
    });

    it("'#tag-foo' -> filterText1='Showing', filterValue1='#foo' (inline), categoryTrigger inline-flex+pe:none+opacity 1, searchValue hidden, filterText2 inline", async () => {
      const { handleHashChange } = await setup(`${BROWSE}#tag-foo`);
      handleHashChange();
      const h = header();
      expect(h.filterText1.style.display).toBe('inline');
      expect(h.filterText1.textContent).toBe('Showing');
      expect(h.filterValue1.style.display).toBe('inline');
      expect(h.filterValue1.textContent).toBe('#foo');
      expect(h.categoryTrigger.style.display).toBe('inline-flex');
      expect(h.categoryTrigger.style.pointerEvents).toBe('none');
      expect(h.categoryTrigger.style.opacity).toBe('1');
      expect(h.searchValue.style.display).toBe('none');
      expect(h.filterText2.style.display).toBe('inline');
    });

    it("'#search-bar' -> filterText1='Searching', categoryTrigger hidden, searchValue='\"bar\"' (inline), filterText2 hidden", async () => {
      const { handleHashChange } = await setup(`${BROWSE}#search-bar`);
      handleHashChange();
      const h = header();
      expect(h.filterText1.style.display).toBe('inline');
      expect(h.filterText1.textContent).toBe('Searching');
      expect(h.categoryTrigger.style.display).toBe('none');
      expect(h.searchValue.style.display).toBe('inline');
      expect(h.searchValue.textContent).toBe('"bar"');
      expect(h.filterText2.style.display).toBe('none');
    });

    it("'#category-frontend' -> filterText1='Showing', filterValue1='Frontend' (option label), categoryTrigger inline-flex+pe:auto, searchValue hidden, filterText2 inline", async () => {
      const { handleHashChange } = await setup(`${BROWSE}#category-frontend`);
      handleHashChange();
      const h = header();
      expect(h.filterText1.style.display).toBe('inline');
      expect(h.filterText1.textContent).toBe('Showing');
      expect(h.filterValue1.textContent).toBe('Frontend');
      expect(h.categoryTrigger.style.display).toBe('inline-flex');
      expect(h.categoryTrigger.style.pointerEvents).toBe('auto');
      expect(h.searchValue.style.display).toBe('none');
      expect(h.filterText2.style.display).toBe('inline');
    });

    it("bare URL after '#tag-foo' (back/forward) -> header resets: filterValue1='All Categories', categoryTrigger pe:auto, searchValue hidden, filterText2 inline", async () => {
      const { handleHashChange } = await setup(`${BROWSE}#tag-foo`);
      handleHashChange();
      // sanity: the tag state was applied first
      expect(document.getElementById('filterValue1').textContent).toBe('#foo');

      window.history.pushState({}, '', BROWSE); // clear hash (no hashchange fired)
      handleHashChange();
      const h = header();
      expect(h.filterText1.style.display).toBe('inline');
      expect(h.filterText1.textContent).toBe('Showing');
      expect(h.filterValue1.textContent).toBe('All Categories');
      expect(h.categoryTrigger.style.display).toBe('inline-flex');
      expect(h.categoryTrigger.style.pointerEvents).toBe('auto');
      expect(h.categoryTrigger.style.opacity).toBe('1');
      expect(h.searchValue.style.display).toBe('none');
      expect(h.filterText2.style.display).toBe('inline');
    });
  });

  // B2 regression: an all-null hash (bare URL after back/forward) must clear
  // the category dropdown, not leave the previous category in the hidden
  // select — updateFilterHeader's else-branch resolves the header label from
  // categoryFilter.value, so a stale select also stales the header.
  describe('handleHashChange clears the category dropdown on an all-null hash (B2)', () => {
    it("bare URL after '#category-frontend' (back/forward): categoryFilter.value reset to '' and header shows 'All Categories'", async () => {
      const { handleHashChange } = await setup(`${BROWSE}#category-frontend`);
      handleHashChange();
      // sanity: the category state was applied first
      expect(document.getElementById('categoryFilter').value).toBe('frontend');
      expect(document.getElementById('filterValue1').textContent).toBe('Frontend');

      window.history.pushState({}, '', BROWSE); // clear hash (no hashchange fired)
      handleHashChange();
      expect(document.getElementById('categoryFilter').value).toBe('');
      expect(document.getElementById('filterValue1').textContent).toBe('All Categories');
    });
  });
});