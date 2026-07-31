import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, setRect } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

// Import state first (builds allCards + atoms), then entry-animator (so init()
// can create a real io for the rearmCards paths), then filter-cards. All three
// share one module registry, so filter-cards reads the same atoms/allCards.
async function setup({ url = BROWSE, globals } = {}) {
  const state = await loadFresh('static/js/modules/state.js', { url, html: FIX(), globals });
  const ea = await loadFresh('static/js/modules/entry-animator.js', { url });
  const fc = await loadFresh('static/js/modules/filter-cards.js', { url });
  return { state, ea, filterCards: fc.filterCards };
}

describe('filter-cards.js', () => {
  it('filterCards: early-returns on a non-browse page', async () => {
    const { filterCards } = await loadFresh('static/js/modules/filter-cards.js', {
      url: LANDING,
      html: FIX(),
    });
    const rc = document.getElementById('resultsCount');
    rc.textContent = 'untouched';
    filterCards();
    expect(rc.textContent).toBe('untouched');
  });

  it("filterCards: visible cards get display='' and hidden cards get display='none'", async () => {
    const { state, filterCards } = await setup();
    state.$activeTag.set('javascript'); // card-1, card-4
    filterCards();
    expect(document.getElementById('card-1').style.display).toBe('');
    expect(document.getElementById('card-4').style.display).toBe('');
    expect(document.getElementById('card-2').style.display).toBe('none');
    expect(document.getElementById('card-3').style.display).toBe('none');
  });

  it("filterCards: dom.noResults shows iff visibleCount===0; dom.resultsCount pluralises ('N item'/'N items')", async () => {
    const { state, filterCards } = await setup();
    const noResults = document.getElementById('noResults');
    const resultsCount = document.getElementById('resultsCount');

    state.$activeTag.set('zzz'); // 0
    filterCards();
    expect(noResults.style.display).toBe('block');
    expect(resultsCount.textContent).toBe('0 items');

    state.$activeTag.set('react'); // 1 (card-1 only)
    filterCards();
    expect(noResults.style.display).toBe('none');
    expect(resultsCount.textContent).toBe('1 item');

    state.$activeTag.set('javascript'); // 2 (card-1, card-4)
    filterCards();
    expect(noResults.style.display).toBe('none');
    expect(resultsCount.textContent).toBe('2 items');
  });

  it("filterCards: in-viewport visible card is re-animated via reflow-remove→reflow→re-add (.link-card--enter)", async () => {
    const { state, ea, filterCards } = await setup();
    ea.EntryAnimator.init(); // create a real io so rearmCards is the live path
    const io = window.IntersectionObserver.__instances[0];
    const observeSpy = vi.spyOn(io, 'observe');

    const card = document.getElementById('card-1');
    card.classList.add('link-card--enter'); // already animated
    setRect(card, { top: 10, bottom: 50 }); // in viewport
    const removeSpy = vi.spyOn(card.classList, 'remove');
    const addSpy = vi.spyOn(card.classList, 'add');

    state.$activeTag.set(null); // no filter -> all visible
    filterCards();

    // reflow trick: class removed then re-added (replay) for the in-view card
    expect(removeSpy).toHaveBeenCalledWith('link-card--enter');
    expect(addSpy).toHaveBeenCalledWith('link-card--enter');
    expect(card.classList.contains('link-card--enter')).toBe(true);
    // rearmCards NOT called for the in-view card (it would have re-observed)
    expect(observeSpy).not.toHaveBeenCalledWith(card);
  });

  it('filterCards: off-viewport visible card is re-armed via rearmCards', async () => {
    const { state, ea, filterCards } = await setup();
    ea.EntryAnimator.init();
    const io = window.IntersectionObserver.__instances[0];
    const observeSpy = vi.spyOn(io, 'observe');

    const card = document.getElementById('card-1');
    card.classList.add('link-card--enter'); // already animated
    state.$animatedIds.set(new Set(['card-1']));
    setRect(card, { top: -9999, bottom: -9900 }); // off viewport

    state.$activeTag.set(null); // all visible
    filterCards();

    // rearmCards removed the class, dropped the id, and re-observed
    expect(card.classList.contains('link-card--enter')).toBe(false);
    expect(state.$animatedIds.get().has('card-1')).toBe(false);
    expect(observeSpy).toHaveBeenCalledWith(card);
  });

  it("filterCards: data-entry-animation='none' skips re-animate (reanimate=false, no class toggling)", async () => {
    const { state, filterCards } = await setup();
    document.body.setAttribute('data-entry-animation', 'none');

    const card = document.getElementById('card-1');
    card.classList.remove('link-card--enter');
    state.$activeTag.set('javascript'); // card-1 visible
    filterCards();

    // visible card kept display='' with no .link-card--enter toggling
    expect(card.style.display).toBe('');
    expect(card.classList.contains('link-card--enter')).toBe(false);
  });
});