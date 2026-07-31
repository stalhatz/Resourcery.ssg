import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');
const LANDING_FIX = () => readFixture('landing.html');

async function setup(url = BROWSE, html = FIX(), globals) {
  const state = await loadFresh('static/js/modules/state.js', { url, html, globals });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  return { state, TagManager: tagMod.TagManager };
}

describe('tag-manager.js', () => {
  it('slugify: strips accents (NFD), spaces->"-", drops punctuation, collapses "--"', async () => {
    const { TagManager } = await setup();
    expect(TagManager.slugify('Café au Lait!')).toBe('cafe-au-lait');
    expect(TagManager.slugify('Web  Dev!!')).toBe('web-dev');
    expect(TagManager.slugify('a--b')).toBe('a-b');
  });

  it('setActiveTag(tag,true): clears other two atoms, sets $activeTag=slug, writes "#tag-<slug>"', async () => {
    const { state, TagManager } = await setup();
    TagManager.setActiveTag('foo', true);
    expect(state.$activeTag.get()).toBe('foo');
    expect(state.$activeSearch.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
    expect(window.location.hash).toBe('#tag-foo');
  });

  // B3 regression: setActiveTag slugifies ('C++' -> 'c', 'machine learning'
  // -> 'machine-learning'); $visibleCards must match cards whose raw
  // data-tags hold the un-slugified form.
  it("setActiveTag('C++', true): slug atom 'c' + hash '#tag-c' match a card with raw data-tags 'C++'", async () => {
    const html = `
      <article class="link-card" id="cpp" data-title="C++" data-tags="C++" data-category="frontend"></article>
      <article class="link-card" id="js" data-title="JS" data-tags="JavaScript" data-category="frontend"></article>
    `;
    const { state, TagManager } = await setup(BROWSE, html);
    TagManager.setActiveTag('C++', true);
    expect(state.$activeTag.get()).toBe('c');
    expect(window.location.hash).toBe('#tag-c');
    expect(state.$visibleCards.get()).toEqual(['cpp']);
  });

  it("setActiveTag('machine learning', true): slug atom 'machine-learning' matches raw data-tags 'machine learning'", async () => {
    const html = `
      <article class="link-card" id="ml" data-title="ML" data-tags="machine learning" data-category="ai"></article>
      <article class="link-card" id="js" data-title="JS" data-tags="JavaScript" data-category="frontend"></article>
    `;
    const { state, TagManager } = await setup(BROWSE, html);
    TagManager.setActiveTag('machine learning', true);
    expect(state.$activeTag.get()).toBe('machine-learning');
    expect(state.$visibleCards.get()).toEqual(['ml']);
  });

  it("setActiveTag('R&D', true): slug atom 'rd' matches raw data-tags 'R&D'", async () => {
    const html = `
      <article class="link-card" id="rd" data-title="R&D" data-tags="R&D" data-category="backend"></article>
    `;
    const { state, TagManager } = await setup(BROWSE, html);
    TagManager.setActiveTag('R&D', true);
    expect(state.$activeTag.get()).toBe('rd');
    expect(state.$visibleCards.get()).toEqual(['rd']);
  });

  it('setActiveTag(null,true) with no category: history.pushState clears the hash', async () => {
    const { TagManager } = await setup();
    window.location.hash = '#tag-foo';
    TagManager.setActiveTag(null, true);
    expect(window.location.hash).toBe('');
  });

  it('setActiveTag(null,true) with an active category: switches to category (sets $activeCategory, writes "#category-<v>")', async () => {
    const { state, TagManager } = await setup();
    document.getElementById('categoryFilter').value = 'web';
    TagManager.setActiveTag(null, true);
    expect(state.$activeCategory.get()).toBe('web');
    expect(window.location.hash).toBe('#category-web');
  });

  it('setActiveSearch(term,true): clears tag+category, writes "#search-<encoded>"', async () => {
    const { state, TagManager } = await setup();
    TagManager.setActiveSearch('bar baz', true);
    expect(state.$activeSearch.get()).toBe('bar baz');
    expect(state.$activeTag.get()).toBeNull();
    expect(state.$activeCategory.get()).toBeNull();
    expect(window.location.hash).toBe('#search-bar%20baz');
  });

  it('setActiveSearch(null,true): same null branches as setActiveTag(null)', async () => {
    const { TagManager } = await setup();
    window.location.hash = '#search-foo';
    TagManager.setActiveSearch(null, true);
    expect(window.location.hash).toBe('');

    vi.resetModules();
    const s2 = await setup();
    document.getElementById('categoryFilter').value = 'web';
    s2.TagManager.setActiveSearch(null, true);
    expect(s2.state.$activeCategory.get()).toBe('web');
    expect(window.location.hash).toBe('#category-web');
  });

  it("updateFilterHeader: 'search' branch (filterText1='Searching', hide categoryTrigger, searchValue shows quoted term, filterText2 hidden)", async () => {
    const { TagManager } = await setup();
    TagManager.setActiveSearch('bar', true);
    expect(document.getElementById('filterText1').style.display).toBe('inline');
    expect(document.getElementById('filterText1').textContent).toBe('Searching');
    expect(document.getElementById('categoryTrigger').style.display).toBe('none');
    expect(document.getElementById('searchValue').style.display).toBe('inline');
    expect(document.getElementById('searchValue').textContent).toBe('"bar"');
    expect(document.getElementById('filterText2').style.display).toBe('none');
  });

  it("updateFilterHeader: 'tag' branch (filterText1='Showing', categoryTrigger inline-flex+pe none+opacity1, filterValue1='#<tag>', searchValue hidden, filterText2 inline)", async () => {
    const { TagManager } = await setup();
    TagManager.setActiveTag('foo', true);
    const ct = document.getElementById('categoryTrigger');
    expect(document.getElementById('filterText1').textContent).toBe('Showing');
    expect(ct.style.display).toBe('inline-flex');
    expect(ct.style.pointerEvents).toBe('none');
    expect(ct.style.opacity).toBe('1');
    expect(document.getElementById('filterValue1').style.display).toBe('inline');
    expect(document.getElementById('filterValue1').textContent).toBe('#foo');
    expect(document.getElementById('searchValue').style.display).toBe('none');
    expect(document.getElementById('filterText2').style.display).toBe('inline');
  });

  it("updateFilterHeader: 'none' branch (filterText1='Showing', categoryTrigger inline-flex+pe auto+opacity1, searchValue hidden, filterText2 inline, filterValue1=option.textContent|'All Categories')", async () => {
    const { TagManager } = await setup();
    TagManager.setActiveTag(null, true); // all null
    const ct = document.getElementById('categoryTrigger');
    expect(document.getElementById('filterText1').textContent).toBe('Showing');
    expect(ct.style.display).toBe('inline-flex');
    expect(ct.style.pointerEvents).toBe('auto');
    expect(ct.style.opacity).toBe('1');
    expect(document.getElementById('searchValue').style.display).toBe('none');
    expect(document.getElementById('filterText2').style.display).toBe('inline');
    expect(document.getElementById('filterValue1').textContent).toBe('All Categories');
  });

  it('updateFilterHeader: early-returns (console.warn) when filterText1 or filterValue1 absent', async () => {
    const { TagManager } = await setup(BROWSE, '<div></div>');
    const warnSpy = vi.spyOn(console, 'warn');
    expect(() => TagManager.updateFilterHeader()).not.toThrow();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('getActiveTag/getActiveSearch getters return atom values', async () => {
    const { state, TagManager } = await setup();
    state.$activeTag.set('foo');
    expect(TagManager.getActiveTag()).toBe('foo');
    state.$activeSearch.set('bar');
    expect(TagManager.getActiveSearch()).toBe('bar');
  });

  it('clearActiveTag/clearActiveSearch call setActive*(null,true)', async () => {
    const { TagManager } = await setup();
    const tagSpy = vi.spyOn(TagManager, 'setActiveTag');
    const searchSpy = vi.spyOn(TagManager, 'setActiveSearch');
    TagManager.clearActiveTag();
    expect(tagSpy).toHaveBeenCalledWith(null, true);
    TagManager.clearActiveSearch();
    expect(searchSpy).toHaveBeenCalledWith(null, true);
  });

  it('clearActiveTag(false)/clearActiveSearch(false) pass updateUrl=false (caller owns the URL write)', async () => {
    const { TagManager } = await setup();
    const tagSpy = vi.spyOn(TagManager, 'setActiveTag');
    const searchSpy = vi.spyOn(TagManager, 'setActiveSearch');
    TagManager.clearActiveTag(false);
    TagManager.clearActiveSearch(false);
    expect(tagSpy).toHaveBeenCalledWith(null, false);
    expect(searchSpy).toHaveBeenCalledWith(null, false);
  });

  // Regression: a tag<->category transition must emit exactly ONE hashchange.
  // Without batching, the sequential atom sets fire bridgeToHash's writeHash
  // per atom (e.g. '#category-frontend' -> '' -> '#tag-foo'), polluting the
  // browser back-stack with intermediate entries.
  describe('one hashchange per transition (with the atom->hash bridge installed)', () => {
    const installBridge = (state) =>
      state.bridgeToHash({
        $activeTag: state.$activeTag,
        $activeSearch: state.$activeSearch,
        $activeCategory: state.$activeCategory,
      });
    const settle = () => new Promise((r) => setTimeout(r, 50));
    const countHashchanges = async () => {
      let count = 0;
      const fn = () => count++;
      window.addEventListener('hashchange', fn);
      await settle(); // let any intermediate writeHash events fire
      window.removeEventListener('hashchange', fn);
      return count;
    };

    it('setActiveTag(tag,true) from an active category: exactly one hashchange, no intermediate empty entry', async () => {
      const { state, TagManager } = await setup();
      installBridge(state);
      state.$activeCategory.set('frontend'); // bridge writes '#category-frontend'
      await settle();

      TagManager.setActiveTag('foo', true);
      const count = await countHashchanges();

      expect(window.location.hash).toBe('#tag-foo');
      expect(state.$activeCategory.get()).toBeNull();
      expect(count).toBe(1);
    });

    it('setActiveSearch(term,true) from an active tag: exactly one hashchange', async () => {
      const { state, TagManager } = await setup();
      installBridge(state);
      state.$activeTag.set('foo'); // bridge writes '#tag-foo'
      await settle();

      TagManager.setActiveSearch('bar baz', true);
      const count = await countHashchanges();

      expect(window.location.hash).toBe('#search-bar%20baz');
      expect(state.$activeTag.get()).toBeNull();
      expect(count).toBe(1);
    });

    it('clearActiveTag with a category in the select: falls back to the category with exactly one hashchange', async () => {
      const { state, TagManager } = await setup();
      installBridge(state);
      state.$activeTag.set('foo'); // bridge writes '#tag-foo'
      document.getElementById('categoryFilter').value = 'web';
      await settle();

      TagManager.clearActiveTag();
      const count = await countHashchanges();

      expect(state.$activeCategory.get()).toBe('web');
      expect(window.location.hash).toBe('#category-web');
      expect(count).toBe(1);
    });
  });

  it('clearSearchInput: sets dom.searchInput.value=""', async () => {
    const { TagManager } = await setup();
    document.getElementById('searchInput').value = 'hello';
    TagManager.clearSearchInput();
    expect(document.getElementById('searchInput').value).toBe('');
  });

  it('setupSearchSuggestions: builds suggestions box (#searchSuggestions, role listbox), sets searchInput ARIA, dom.searchSuggestions updated', async () => {
    const { TagManager } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: ['JavaScript'] });
    TagManager.init();
    const box = document.getElementById('searchSuggestions');
    expect(box).not.toBeNull();
    expect(box.getAttribute('role')).toBe('listbox');
    expect(box.className).toContain('search-suggestions');
    const input = document.getElementById('searchInput');
    expect(input.getAttribute('role')).toBe('combobox');
    expect(input.getAttribute('aria-autocomplete')).toBe('list');
    expect(input.getAttribute('aria-controls')).toBe('searchSuggestions');
    expect(input.getAttribute('aria-expanded')).toBe('false');
  });

  it('setupSearchSuggestions: input filters ALL_TAGS case-insensitively, "#"-prefix optional, renders <=8 .suggestion-item', async () => {
    vi.useFakeTimers();
    try {
      const { TagManager } = await setup(LANDING, LANDING_FIX(), {
        ALL_TAGS: ['JavaScript', 'aaa', 'bbbAAAbb'],
      });
      TagManager.init();
      const input = document.getElementById('searchInput');
      const box = () => document.getElementById('searchSuggestions');

      input.value = 'java';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      expect(box().querySelectorAll('.suggestion-item').length).toBe(1);

      input.value = '#a';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      // '#'-prefix stripped -> query 'a' matches all three (JavaScript, aaa, bbbAAAbb)
      expect(box().querySelectorAll('.suggestion-item').length).toBe(3);

      // 20 tags matching 'a' -> capped at 8
      vi.resetModules();
      const many = Array.from({ length: 20 }, (_, i) => 'a' + i);
      const { TagManager: TM2 } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: many });
      TM2.init();
      const input2 = document.getElementById('searchInput');
      input2.value = 'a';
      input2.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      expect(document.getElementById('searchSuggestions').querySelectorAll('.suggestion-item').length).toBe(8);
    } finally {
      vi.useRealTimers();
    }
  });

  it('setupSearchSuggestions: ArrowDown/Up move .selected + aria-selected; Enter on highlighted suggestion triggers its click; Escape hides + blurs', async () => {
    vi.useFakeTimers();
    try {
      const { TagManager } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: ['aaa', 'aab', 'aac'] });
      TagManager.init();
      const input = document.getElementById('searchInput');
      input.value = 'aa';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      const box = document.getElementById('searchSuggestions');
      const items = box.querySelectorAll('.suggestion-item');
      expect(items.length).toBe(3);

      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
      expect(items[0].classList.contains('selected')).toBe(true);
      expect(items[0].getAttribute('aria-selected')).toBe('true');
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
      expect(items[1].classList.contains('selected')).toBe(true);
      expect(items[0].classList.contains('selected')).toBe(false);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
      expect(items[0].classList.contains('selected')).toBe(true);

      // Enter on highlighted (index 0) triggers its click handler
      stubLocation();
      const clickSpy = vi.spyOn(items[0], 'click');
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      expect(clickSpy).toHaveBeenCalled();

      // Escape hides suggestions + blurs
      const blurSpy = vi.spyOn(input, 'blur');
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      expect(box.classList.contains('active')).toBe(false);
      expect(input.getAttribute('aria-expanded')).toBe('false');
      expect(blurSpy).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('renderSuggestions: builds .suggestion-item with role option, aria-selected false, id "suggestion-<i>", text (#-prefixed if isTagSearch), dataset.tag; adds "active" to box', async () => {
    const { TagManager } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: ['JavaScript'] });
    TagManager.init();
    const input = document.getElementById('searchInput');
    const box = document.getElementById('searchSuggestions');
    TagManager.renderSuggestions(['JavaScript'], false, box, input);
    const item = box.querySelector('.suggestion-item');
    expect(item.getAttribute('role')).toBe('option');
    expect(item.getAttribute('aria-selected')).toBe('false');
    expect(item.id).toBe('suggestion-0');
    expect(item.textContent).toBe('JavaScript');
    expect(item.dataset.tag).toBe('JavaScript');
    expect(box.classList.contains('active')).toBe(true);

    TagManager.renderSuggestions(['JavaScript'], true, box, input);
    expect(box.querySelector('.suggestion-item').textContent).toBe('#JavaScript');
  });

  it('highlightSuggestion: adds "selected"+aria-selected true on index; removes from others', async () => {
    const { TagManager } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: ['aaa', 'aab'] });
    TagManager.init();
    const input = document.getElementById('searchInput');
    const box = document.getElementById('searchSuggestions');
    TagManager.renderSuggestions(['aaa', 'aab'], false, box, input);
    const items = box.querySelectorAll('.suggestion-item');
    TagManager.highlightSuggestion(items, 1);
    expect(items[1].classList.contains('selected')).toBe(true);
    expect(items[1].getAttribute('aria-selected')).toBe('true');
    expect(items[0].classList.contains('selected')).toBe(false);
    expect(items[0].getAttribute('aria-selected')).toBe('false');
  });

  it('hideSuggestions: removes "active" on box, aria-expanded false, resets index', async () => {
    const { TagManager } = await setup(LANDING, LANDING_FIX(), { ALL_TAGS: ['aaa'] });
    TagManager.init();
    const input = document.getElementById('searchInput');
    const box = document.getElementById('searchSuggestions');
    TagManager.renderSuggestions(['aaa'], false, box, input);
    TagManager.selectedSuggestionIndex = 2;
    TagManager.hideSuggestions(box, input);
    expect(box.classList.contains('active')).toBe(false);
    expect(input.getAttribute('aria-expanded')).toBe('false');
    expect(TagManager.selectedSuggestionIndex).toBe(-1);
  });

  it('navigateToBrowse (landing): "#<tag>" -> href "browse.html#tag-<slug>"; else -> href "browse.html#search-<enc>"', async () => {
    const { TagManager } = await setup(LANDING, LANDING_FIX());
    stubLocation();
    const input = document.getElementById('searchInput');
    TagManager.navigateToBrowse('#Foo Bar', input);
    expect(window.location.href).toBe('browse.html#tag-foo-bar');
    TagManager.navigateToBrowse('bar baz', input);
    expect(window.location.href).toBe('browse.html#search-bar%20baz');
  });

  it('navigateToBrowse (browse): "#<tag>" -> setActiveTag; else -> setActiveSearch; then searchInput.value="" + filterCards()', async () => {
    const { TagManager } = await setup();
    const setActiveTagSpy = vi.spyOn(TagManager, 'setActiveTag');
    const setActiveSearchSpy = vi.spyOn(TagManager, 'setActiveSearch');
    const input = document.getElementById('searchInput');
    input.value = 'keepme';
    TagManager.navigateToBrowse('#Foo', input);
    expect(setActiveTagSpy).toHaveBeenCalledWith('Foo', true);
    expect(input.value).toBe('');

    input.value = 'keepme';
    TagManager.navigateToBrowse('bar baz', input);
    expect(setActiveSearchSpy).toHaveBeenCalledWith('bar baz', true);
    expect(input.value).toBe('');
    // filterCards() ran as a side-effect
    expect(document.getElementById('resultsCount').textContent).not.toBe('');
  });

  it('debounce: coalesces rapid calls into one trailing call', async () => {
    vi.useFakeTimers();
    try {
      const { TagManager } = await setup();
      const fn = vi.fn();
      const debounced = TagManager.debounce(fn, 100);
      debounced();
      debounced();
      debounced();
      expect(fn).not.toHaveBeenCalled();
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});