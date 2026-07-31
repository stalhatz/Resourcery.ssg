import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');
const order = () =>
  Array.from(document.getElementById('linksGrid').querySelectorAll('.link-card')).map((c) => c.id);

describe('Sort (integration)', () => {
  it('newest/oldest/alphabetical reorder the grid; unknown is stable; appendChild reorder', async () => {
    const sc = await loadFresh('static/js/modules/sort-cards.js', { url: BROWSE, html: FIX() });

    document.getElementById('sortFilter').value = 'newest';
    sc.sortCards();
    expect(order()).toEqual(['card-2', 'card-3', 'card-1', 'card-4']);

    document.getElementById('sortFilter').value = 'oldest';
    sc.sortCards();
    expect(order()).toEqual(['card-4', 'card-1', 'card-3', 'card-2']);

    document.getElementById('sortFilter').value = 'alphabetical';
    sc.sortCards();
    expect(order()).toEqual(['card-1', 'card-2', 'card-4', 'card-3']);

    const before = order();
    document.getElementById('sortFilter').value = 'weird';
    sc.sortCards();
    expect(order()).toEqual(before);
  });

  it('main.js bootstrap does not throw and sorts on the browse fixture', async () => {
    await expect(loadFresh('static/js/main.js', { url: BROWSE, html: FIX() })).resolves.toBeDefined();
    expect(document.querySelectorAll('#linksGrid .link-card').length).toBe(4);
  });
});