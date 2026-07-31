import { describe, it, expect } from 'vitest';
import { loadFresh } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';

// Three cards with distinct created dates + titles.
const CARDS = `
  <select id="sortFilter">
    <option value="newest">Newest</option>
    <option value="oldest">Oldest</option>
    <option value="alphabetical">Alphabetical</option>
  </select>
  <div id="linksGrid">
    <article class="link-card" data-title="Charlie" data-created="2024-02-10"></article>
    <article class="link-card" data-title="Alpha" data-created="2024-03-20"></article>
    <article class="link-card" data-title="Bravo" data-created="2024-01-15"></article>
  </div>
`;
const fresh = (html = CARDS) =>
  loadFresh('static/js/modules/sort-cards.js', { url: BROWSE, html });
const order = (grid) => Array.from(grid.querySelectorAll('.link-card')).map((c) => c.dataset.title);

describe('sort-cards.js', () => {
  it("sortCards: early-returns when sortFilter or linksGrid absent", async () => {
    const { sortCards } = await loadFresh('static/js/modules/sort-cards.js', {
      url: BROWSE,
      html: '<div id="linksGrid"><article class="link-card" data-title="X"></article></div>',
    });
    expect(() => sortCards()).not.toThrow();
  });

  it("sortCards: 'newest' sorts by new Date(dataset.created) descending", async () => {
    const { sortCards } = await fresh();
    document.getElementById('sortFilter').value = 'newest';
    sortCards();
    expect(order(document.getElementById('linksGrid'))).toEqual(['Alpha', 'Charlie', 'Bravo']);
  });

  it("sortCards: 'oldest' sorts ascending", async () => {
    const { sortCards } = await fresh();
    document.getElementById('sortFilter').value = 'oldest';
    sortCards();
    expect(order(document.getElementById('linksGrid'))).toEqual(['Bravo', 'Charlie', 'Alpha']);
  });

  it("sortCards: 'alphabetical' sorts by dataset.title.localeCompare", async () => {
    const { sortCards } = await fresh();
    document.getElementById('sortFilter').value = 'alphabetical';
    sortCards();
    expect(order(document.getElementById('linksGrid'))).toEqual(['Alpha', 'Bravo', 'Charlie']);
  });

  it('sortCards: unknown value is stable (returns 0, keeps order)', async () => {
    const { sortCards } = await fresh();
    document.getElementById('sortFilter').value = 'weird';
    const before = order(document.getElementById('linksGrid'));
    sortCards();
    expect(order(document.getElementById('linksGrid'))).toEqual(before);
  });

  it('sortCards: final order applied via grid.appendChild on the sorted array', async () => {
    const { sortCards } = await fresh();
    document.getElementById('sortFilter').value = 'newest';
    sortCards();
    const grid = document.getElementById('linksGrid');
    // appendChild moves (not clones): children order matches the sorted array
    expect(Array.from(grid.children)).toEqual(
      Array.from(grid.querySelectorAll('.link-card'))
    );
    expect(order(grid)).toEqual(['Alpha', 'Charlie', 'Bravo']);
  });
});