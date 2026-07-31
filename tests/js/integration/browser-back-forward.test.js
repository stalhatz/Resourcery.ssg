import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

// jsdom fires hashchange for location.hash assignment and history.back()/forward()
// asynchronously, so wait for the atom side-effect (handleHashChange ran) to settle.
const waitFor = (fn) => vi.waitFor(fn, { timeout: 500, interval: 10 });
const settle = () => new Promise((r) => setTimeout(r, 50));

describe('Browser back/forward (integration)', () => {
  it('history back/forward re-applies filter via hashchange; cycle terminates after one round-trip (no loop)', async () => {
    const state = await loadFresh('static/js/modules/state.js', { url: BROWSE, html: FIX() });
    await loadFresh('static/js/modules/tag-manager.js', { url: BROWSE });
    await loadFresh('static/js/modules/entry-animator.js', { url: BROWSE });
    await loadFresh('static/js/modules/filter-cards.js', { url: BROWSE });
    const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url: BROWSE });
    hhc.installHashChangeListener();
    // install the bridge so atom sets drive writeHash — the loop-termination path.
    // Category→category transitions keep all atoms non-null-or-null consistently,
    // so writeHash is a no-op (serialise(hash)===hash) and no extra hashchange fires.
    state.bridgeToHash({
      $activeTag: state.$activeTag,
      $activeSearch: state.$activeSearch,
      $activeCategory: state.$activeCategory,
    });

    // push two category filter states
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    window.location.hash = 'category-backend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('backend'));

    // Count hashchange events during back. The freshly-installed handler is the
    // only hashchange listener in this fresh setup, so events === handler fires.
    // If writeHash re-wrote the hash (a non-idempotent round-trip), an extra
    // hashchange would fire and count would be > 1.
    let count = 0;
    const counter = () => count++;
    window.addEventListener('hashchange', counter);
    history.back();
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    await settle(); // allow any writeHash-induced hashchange to fire
    expect(count).toBe(1); // exactly one hashchange -> no loop
    expect(document.getElementById('categoryFilter').value).toBe('frontend');

    count = 0;
    history.forward();
    await waitFor(() => expect(state.$activeCategory.get()).toBe('backend'));
    await settle();
    expect(count).toBe(1); // exactly one -> no loop
    expect(document.getElementById('categoryFilter').value).toBe('backend');

    window.removeEventListener('hashchange', counter);
  });

  it('tag<->category<->search transitions fire exactly ONE hashchange per user action (no intermediate history entries)', async () => {
    const state = await loadFresh('static/js/modules/state.js', { url: BROWSE, html: FIX() });
    await loadFresh('static/js/modules/tag-manager.js', { url: BROWSE });
    await loadFresh('static/js/modules/entry-animator.js', { url: BROWSE });
    await loadFresh('static/js/modules/filter-cards.js', { url: BROWSE });
    const hhc = await loadFresh('static/js/modules/handle-hash-change.js', { url: BROWSE });
    hhc.installHashChangeListener();
    state.bridgeToHash({
      $activeTag: state.$activeTag,
      $activeSearch: state.$activeSearch,
      $activeCategory: state.$activeCategory,
    });

    window.location.hash = 'tag-foo';
    await waitFor(() => expect(state.$activeTag.get()).toBe('foo'));

    // Regression: a tag->category switch used to fire two extra hashchanges
    // (the intermediate '' from $activeTag.set(null), then the re-set hash),
    // adding spurious back-stack entries. Each user action must fire exactly
    // one event.
    let count = 0;
    const counter = () => count++;
    window.addEventListener('hashchange', counter);

    // tag -> category
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    await settle();
    expect(count).toBe(1);
    expect(window.location.hash).toBe('#category-frontend');
    expect(document.getElementById('categoryFilter').value).toBe('frontend');

    // category -> tag
    count = 0;
    window.location.hash = 'tag-foo';
    await waitFor(() => expect(state.$activeTag.get()).toBe('foo'));
    await settle();
    expect(count).toBe(1);
    expect(window.location.hash).toBe('#tag-foo');

    // tag -> search
    count = 0;
    window.location.hash = 'search-bar%20baz';
    await waitFor(() => expect(state.$activeSearch.get()).toBe('bar baz'));
    await settle();
    expect(count).toBe(1);
    expect(window.location.hash).toBe('#search-bar%20baz');

    // search -> category (the remaining cross-type pair)
    count = 0;
    window.location.hash = 'category-frontend';
    await waitFor(() => expect(state.$activeCategory.get()).toBe('frontend'));
    await settle();
    expect(count).toBe(1);

    window.removeEventListener('hashchange', counter);
  });

  it('main.js bootstrap does not throw on the browse fixture', async () => {
    await expect(loadFresh('static/js/main.js', { url: BROWSE, html: FIX() })).resolves.toBeDefined();
  });
});