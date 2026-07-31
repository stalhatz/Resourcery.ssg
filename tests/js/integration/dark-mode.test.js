import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');
const TOGGLE = '<button id="themeToggle">Theme</button>';

describe('Dark mode (integration)', () => {
  it('first init sets data-theme from localStorage (default light); toggle flips to dark + persists; re-init reads persisted', async () => {
    const tm1 = await loadFresh('static/js/modules/theme-manager.js', { url: BROWSE, html: TOGGLE });
    tm1.ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    document.getElementById('themeToggle').click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');

    vi.resetModules();
    const tm2 = await loadFresh('static/js/modules/theme-manager.js', { url: BROWSE, html: TOGGLE });
    tm2.ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('main.js bootstrap sets data-theme from localStorage', async () => {
    localStorage.setItem('theme', 'dark');
    await loadFresh('static/js/main.js', { url: BROWSE, html: FIX() });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});