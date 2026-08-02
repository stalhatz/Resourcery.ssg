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

describe('handle-hash-change.js (thin handler)', () => {
  it('handleHashChange: early-returns on a non-browse page', async () => {
    const { handleHashChange } = await setup(LANDING);
    const rc = document.getElementById('resultsCount');
    rc.textContent = 'untouched';
    handleHashChange();
    expect(rc.textContent).toBe('untouched');
  });

  it("handleHashChange: '#category-<c>' sets $activeCategory, others null", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#category-frontend`);
    handleHashChange();
    expect(state.$activeCategory.get()).toBe('frontend');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeSearch.get()).toBeNull();
  });

  it("handleHashChange: '#tag-<t>' sets $activeTag, others null", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#tag-foo`);
    handleHashChange();
    expect(state.$activeTag.get()).toBe('foo');
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
  });

  it("handleHashChange: '#search-<s>' sets $activeSearch, others null", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#search-bar`);
    handleHashChange();
    expect(state.$activeSearch.get()).toBe('bar');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
  });

  it('handleHashChange: bare URL sets all three reactive variables to null', async () => {
    const { state, handleHashChange } = await setup(BROWSE);
    handleHashChange();
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
  });

  // B8 / E4 regression: a hand-typed malformed percent-sequence ('#tag-%' or
  // '#search-%') must NOT crash the hashchange handler with URIError. The
  // reactive variables end up holding the raw segment (non-matching — the
  // filter simply shows 0 items via the effects layer).
  it("handleHashChange: malformed '#tag-%' does not throw; reactive variable='%'", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#tag-%`);
    expect(() => handleHashChange()).not.toThrow();
    expect(state.$activeTag.get()).toBe('%');
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
  });

  it("handleHashChange: malformed '#search-%' does not throw; reactive variable='%'", async () => {
    const { state, handleHashChange } = await setup(`${BROWSE}#search-%`);
    expect(() => handleHashChange()).not.toThrow();
    expect(state.$activeSearch.get()).toBe('%');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
  });

  it('thin: sets reactive variables only — no direct DOM writes (select, header, cards untouched)', async () => {
    const { handleHashChange } = await setup(`${BROWSE}#category-frontend`);
    const select = document.getElementById('categoryFilter');
    const rc = document.getElementById('resultsCount');
    select.value = 'web'; // a valid option value (invalid values clamp to '')
    rc.textContent = 'stale';
    handleHashChange();
    expect(select.value).toBe('web');
    expect(rc.textContent).toBe('stale');
    expect(document.getElementById('filterValue1').textContent).toBe('');
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
