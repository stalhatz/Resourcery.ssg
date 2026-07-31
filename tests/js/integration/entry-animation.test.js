import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, setRect } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE, html = FIX()) {
  const state = await loadFresh('static/js/modules/state.js', { url, html });
  const ea = await loadFresh('static/js/modules/entry-animator.js', { url });
  const fc = await loadFresh('static/js/modules/filter-cards.js', { url });
  return { state, EntryAnimator: ea.EntryAnimator, rearmCards: ea.rearmCards, filterCards: fc.filterCards };
}

describe('Entry animation (integration)', () => {
  it('in-view IO entry adds .link-card--enter + id, unobserves (no re-add on second trigger)', async () => {
    const { state, EntryAnimator } = await setup();
    EntryAnimator.init();
    const card = document.getElementById('card-1');
    window.IntersectionObserver.__trigger([
      { target: card, boundingClientRect: { top: 10, bottom: 50 }, isIntersecting: true },
    ]);
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('card-1')).toBe(true);
    // second trigger does NOT re-add (the card was unobserved)
    const before = state.$animatedIds.get().size;
    window.IntersectionObserver.__trigger([
      { target: card, boundingClientRect: { top: 10, bottom: 50 }, isIntersecting: true },
    ]);
    expect(state.$animatedIds.get().size).toBe(before);
  });

  it('filter change re-animates in-viewport cards via reflow and re-arms off-viewport cards via rearmCards', async () => {
    const { EntryAnimator, filterCards } = await setup();
    EntryAnimator.init();
    const io = window.IntersectionObserver.__instances[0];
    const observeSpy = vi.spyOn(io, 'observe');
    const inView = document.getElementById('card-1');
    const offView = document.getElementById('card-2');
    setRect(inView, { top: 10, bottom: 50 });
    setRect(offView, { top: -9999, bottom: -9900 });
    filterCards(); // no filter -> all visible
    // in-viewport: re-animated (class remove -> re-add)
    expect(inView.classList.contains('link-card--enter')).toBe(true);
    // off-viewport: re-armed via rearmCards -> re-observed
    expect(observeSpy).toHaveBeenCalledWith(offView);
  });

  it('none mode leaves io null and rearmCards is a no-op', async () => {
    const { state, EntryAnimator, rearmCards } = await setup();
    document.body.setAttribute('data-entry-animation', 'none');
    EntryAnimator.init();
    expect(window.IntersectionObserver.__instances.length).toBe(0);
    const card = document.getElementById('card-1');
    card.classList.add('link-card--enter');
    state.$animatedIds.set(new Set(['card-1']));
    rearmCards([card]);
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('card-1')).toBe(true);
  });

  it('main.js bootstrap does not throw on the browse fixture', async () => {
    await expect(loadFresh('static/js/main.js', { url: BROWSE, html: FIX() })).resolves.toBeDefined();
  });
});