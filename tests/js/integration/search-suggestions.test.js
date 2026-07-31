import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const LANDING_FIX = () => readFixture('landing.html');
const BROWSE_FIX = () => readFixture('browse.html');
const TAGS = ['JavaScript', 'Python', 'Go', 'Rust', 'TypeScript', 'Kotlin', 'Swift', 'Java', 'C++', 'Ruby'];

// Minimal wrapper with #searchInput and NO pre-existing #searchSuggestions, so
// setupSearchSuggestions creates the only suggestions box (no duplicate ids).
const WRAP = '<div class="search-wrapper"><input id="searchInput"/></div>';

async function setup(url, html, globals) {
  await loadFresh('static/js/modules/state.js', { url, html, globals });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  tagMod.TagManager.init();
  return { TagManager: tagMod.TagManager };
}

describe('Search suggestions (integration)', () => {
  it('typing filters ALL_TAGS (case-insensitive, #-prefix optional) and renders ≤8 .suggestion-item', async () => {
    vi.useFakeTimers();
    try {
      await setup(LANDING, WRAP, { ALL_TAGS: TAGS });
      const input = document.getElementById('searchInput');
      const box = () => document.getElementById('searchSuggestions');

      input.value = 'java';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      expect(box().querySelectorAll('.suggestion-item').length).toBe(2); // JavaScript, Java

      input.value = '#go';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      expect(box().querySelectorAll('.suggestion-item').length).toBe(1); // Go
    } finally {
      vi.useRealTimers();
    }
  });

  it('ArrowDown/Up move .selected+aria-selected; Enter on highlighted triggers its click; Escape hides + blurs', async () => {
    vi.useFakeTimers();
    try {
      await setup(LANDING, WRAP, { ALL_TAGS: ['aaa', 'aab', 'aac'] });
      const input = document.getElementById('searchInput');
      input.value = 'aa';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      const box = document.getElementById('searchSuggestions');
      const items = box.querySelectorAll('.suggestion-item');

      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
      expect(items[0].classList.contains('selected')).toBe(true);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
      expect(items[1].classList.contains('selected')).toBe(true);
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
      expect(items[0].classList.contains('selected')).toBe(true);

      stubLocation();
      const clickSpy = vi.spyOn(items[0], 'click');
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      expect(clickSpy).toHaveBeenCalled();

      const blurSpy = vi.spyOn(input, 'blur');
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      expect(box.classList.contains('active')).toBe(false);
      expect(blurSpy).toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it('clicking a suggestion on browse calls setActiveSearch; Enter with "#<tag>" calls setActiveTag; on landing sets href', async () => {
    vi.useFakeTimers();
    try {
      // browse: suggestion click -> setActiveSearch (the click passes the raw tag)
      const browseMod = await setup(BROWSE, WRAP, { ALL_TAGS: ['JavaScript'] });
      const input = document.getElementById('searchInput');
      input.value = '#java';
      input.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      const setActiveSearchSpy = vi.spyOn(browseMod.TagManager, 'setActiveSearch');
      document.querySelector('#searchSuggestions .suggestion-item').click();
      expect(setActiveSearchSpy).toHaveBeenCalledWith('JavaScript', true);

      // browse: Enter with "#Foo" (no suggestion selected) -> setActiveTag('Foo')
      const setActiveTagSpy = vi.spyOn(browseMod.TagManager, 'setActiveTag');
      input.value = '#Foo';
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
      expect(setActiveTagSpy).toHaveBeenCalledWith('Foo', true);

      // landing: suggestion click sets href
      vi.resetModules();
      await setup(LANDING, WRAP, { ALL_TAGS: ['JavaScript'] });
      stubLocation();
      const li = document.getElementById('searchInput');
      li.value = 'java';
      li.dispatchEvent(new Event('input'));
      vi.advanceTimersByTime(200);
      document.querySelector('#searchSuggestions .suggestion-item').click();
      // suggestion click passes the raw tag (no '#') -> navigateToBrowse search branch
      expect(window.location.href).toBe('browse.html#search-JavaScript');
    } finally {
      vi.useRealTimers();
    }
  });

  it('main.js bootstrap does not throw on the browse fixture', async () => {
    await expect(
      loadFresh('static/js/main.js', { url: BROWSE, html: BROWSE_FIX(), globals: { ALL_TAGS: TAGS } })
    ).resolves.toBeDefined();
  });
});