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
});