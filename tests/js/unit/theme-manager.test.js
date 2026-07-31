import { describe, it, expect } from 'vitest';
import { loadFresh } from '../helpers/setup.js';

const HTML = '<button id="themeToggle">Theme</button>';
const BROWSE = 'http://localhost/browse.html';
const fresh = (html = HTML) =>
  loadFresh('static/js/modules/theme-manager.js', { url: BROWSE, html });

describe('theme-manager.js', () => {
  it("ThemeManager.init: reads localStorage('theme') default 'light', sets <html data-theme>", async () => {
    const { ThemeManager } = await fresh();
    ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it("ThemeManager.init: persisted 'dark' is honoured on init", async () => {
    localStorage.setItem('theme', 'dark');
    const { ThemeManager } = await fresh();
    ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('ThemeManager.init: toggle click flips dark↔light and persists', async () => {
    const { ThemeManager } = await fresh();
    ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');

    document.getElementById('themeToggle').click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');

    document.getElementById('themeToggle').click();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('theme')).toBe('light');
  });

  it('ThemeManager.init: early-returns when no #themeToggle', async () => {
    document.documentElement.setAttribute('data-theme', 'unchanged');
    const { ThemeManager } = await fresh('<div></div>');
    expect(() => ThemeManager.init()).not.toThrow();
    expect(document.documentElement.getAttribute('data-theme')).toBe('unchanged');
  });

  it('ThemeManager: re-init after resetModules reads the persisted value', async () => {
    const { ThemeManager } = await fresh();
    ThemeManager.init();
    document.getElementById('themeToggle').click(); // -> dark, persisted
    expect(localStorage.getItem('theme')).toBe('dark');

    vi.resetModules();
    const re = await loadFresh('static/js/modules/theme-manager.js', {
      url: BROWSE,
      html: HTML,
    });
    re.ThemeManager.init();
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });
});