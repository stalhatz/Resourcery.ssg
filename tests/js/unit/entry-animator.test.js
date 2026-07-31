import { describe, it, expect } from 'vitest';
import { loadFresh, setRect } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';

async function setup(html, { url = BROWSE } = {}) {
  const state = await loadFresh('static/js/modules/state.js', { url, html });
  const ea = await loadFresh('static/js/modules/entry-animator.js', { url });
  return { state, EntryAnimator: ea.EntryAnimator, rearmCards: ea.rearmCards };
}

const ONE_CARD = '<article class="link-card" id="c1" data-title="Alpha"></article>';

describe('entry-animator.js', () => {
  it("init: reads data-entry-animation (default 'fade-slide-up'); adds 'js' class to <html>", async () => {
    const { EntryAnimator } = await setup(ONE_CARD);
    EntryAnimator.init();
    expect(document.documentElement.classList.contains('js')).toBe(true);
    // default mode (not 'none') -> io created
    expect(window.IntersectionObserver.__instances.length).toBe(1);
  });

  it("init: mode='none' early-returns after adding 'js' (io stays null)", async () => {
    const { EntryAnimator, rearmCards, state } = await setup(ONE_CARD);
    document.body.setAttribute('data-entry-animation', 'none');
    EntryAnimator.init();
    expect(document.documentElement.classList.contains('js')).toBe(true);
    expect(window.IntersectionObserver.__instances.length).toBe(0); // io never created
    // io null -> rearmCards is a no-op
    const card = document.getElementById('c1');
    card.classList.add('link-card--enter');
    state.$animatedIds.set(new Set(['c1']));
    rearmCards([card]);
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('c1')).toBe(true);
  });

  it('init: no IntersectionObserver fallback adds .link-card--enter to all cards (io stays null)', async () => {
    const html = '<article class="link-card" id="c1"></article><article class="link-card" id="c2"></article>';
    const { EntryAnimator, rearmCards } = await setup(html);
    const savedIO = window.IntersectionObserver;
    delete window.IntersectionObserver;
    try {
      EntryAnimator.init();
      expect(document.getElementById('c1').classList.contains('link-card--enter')).toBe(true);
      expect(document.getElementById('c2').classList.contains('link-card--enter')).toBe(true);
      // io stays null -> rearmCards is a no-op
      const card = document.getElementById('c1');
      expect(() => rearmCards([card])).not.toThrow();
      expect(card.classList.contains('link-card--enter')).toBe(true);
    } finally {
      window.IntersectionObserver = savedIO;
    }
  });

  it('init: no cards fallback adds .link-card--enter to all (zero cards → none) and io stays null', async () => {
    const { EntryAnimator, rearmCards } = await setup('<div></div>');
    EntryAnimator.init();
    expect(document.querySelectorAll('.link-card--enter').length).toBe(0);
    expect(window.IntersectionObserver.__instances.length).toBe(0);
    expect(() => rearmCards([])).not.toThrow();
  });

  it('IO callback: in-view entry adds .link-card--enter, pushes id into $animatedIds, unobserves (only fires once per card)', async () => {
    const { state, EntryAnimator } = await setup(ONE_CARD);
    EntryAnimator.init();
    const card = document.getElementById('c1');
    const io = window.IntersectionObserver.__instances[0];
    const unobserveSpy = vi.spyOn(io, 'unobserve');
    window.IntersectionObserver.__trigger([
      { target: card, boundingClientRect: { top: 10, bottom: 50 }, isIntersecting: true },
    ]);
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('c1')).toBe(true);
    expect(unobserveSpy).toHaveBeenCalledWith(card); // unobserved -> won't fire again
  });

  it('IO callback: out-of-view entry (top >= vh) does NOT add the class', async () => {
    const { state, EntryAnimator } = await setup(ONE_CARD);
    EntryAnimator.init();
    const card = document.getElementById('c1');
    window.IntersectionObserver.__trigger([
      { target: card, boundingClientRect: { top: 9999, bottom: 10000 }, isIntersecting: true },
    ]);
    expect(card.classList.contains('link-card--enter')).toBe(false);
    expect(state.$animatedIds.get().has('c1')).toBe(false);
  });

  it('scroll safety-net (rAF): reveals cards where rect.top<innerHeight && rect.bottom>0; skips ids already in $animatedIds', async () => {
    const { state, EntryAnimator } = await setup(ONE_CARD);
    EntryAnimator.init();
    const card = document.getElementById('c1');
    setRect(card, { top: 10, bottom: 50 }); // in viewport
    window.dispatchEvent(new Event('scroll'));
    // rAF is synchronous -> card revealed
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('c1')).toBe(true);
    // second scroll with same id skipped
    const addSpy = vi.spyOn(card.classList, 'add');
    window.dispatchEvent(new Event('scroll'));
    expect(addSpy).not.toHaveBeenCalledWith('link-card--enter');
  });

  it('scroll safety-net: card above viewport (bottom<=0) is NOT re-revealed', async () => {
    const { state, EntryAnimator } = await setup(ONE_CARD);
    EntryAnimator.init();
    const card = document.getElementById('c1');
    setRect(card, { top: -9999, bottom: -9900 }); // above viewport
    window.dispatchEvent(new Event('scroll'));
    expect(card.classList.contains('link-card--enter')).toBe(false);
    expect(state.$animatedIds.get().has('c1')).toBe(false);
  });

  it('rearmCards(elements): early-returns when io is null (no-IO degrade)', async () => {
    const { EntryAnimator, rearmCards, state } = await setup(ONE_CARD);
    document.body.setAttribute('data-entry-animation', 'none');
    EntryAnimator.init(); // io null
    const card = document.getElementById('c1');
    card.classList.add('link-card--enter');
    state.$animatedIds.set(new Set(['c1']));
    rearmCards([card]);
    expect(card.classList.contains('link-card--enter')).toBe(true);
    expect(state.$animatedIds.get().has('c1')).toBe(true);
  });

  it('rearmCards(elements): otherwise removes .link-card--enter, deletes id from $animatedIds, and re-observes', async () => {
    const { state, EntryAnimator, rearmCards } = await setup(ONE_CARD);
    EntryAnimator.init();
    const io = window.IntersectionObserver.__instances[0];
    const observeSpy = vi.spyOn(io, 'observe');
    const card = document.getElementById('c1');
    card.classList.add('link-card--enter');
    state.$animatedIds.set(new Set(['c1']));
    rearmCards([card]);
    expect(card.classList.contains('link-card--enter')).toBe(false);
    expect(state.$animatedIds.get().has('c1')).toBe(false);
    expect(observeSpy).toHaveBeenCalledWith(card);
  });
});