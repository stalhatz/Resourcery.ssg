/**
 * Theme manager — dark/light mode toggle.
 *
 * Persists selection to localStorage. Reads initial theme from localStorage
 * (default: light).
 */

import { dom } from '../dom.js';

export const ThemeManager = {
  init() {
    const toggle = dom.themeToggle;
    if (!toggle) return;

    const saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);

    toggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
    });
  },
};
