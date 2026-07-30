/**
 * Sort cards — reorder .link-card elements in the grid by date or title.
 */

import { dom } from '../dom.js';

export function sortCards() {
  const sortFilter = dom.sortFilter;
  const grid = dom.linksGrid;
  if (!sortFilter || !grid) return;

  const sortValue = sortFilter.value;
  const cards = Array.from(grid.querySelectorAll('.link-card'));

  cards.sort((a, b) => {
    if (sortValue === 'newest') {
      return new Date(b.dataset.created || 0) - new Date(a.dataset.created || 0);
    }
    if (sortValue === 'oldest') {
      return new Date(a.dataset.created || 0) - new Date(b.dataset.created || 0);
    }
    if (sortValue === 'alphabetical') {
      return a.dataset.title.localeCompare(b.dataset.title);
    }
    return 0;
  });

  cards.forEach(card => grid.appendChild(card));
}
