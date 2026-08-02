/**
 * Central observable state model for Resourcery.ssg.
 *
 * Reactive variables are Nanostores-based reactive primitives.
 * $activeFilter / $visibleCards are computeds derived from the three filter
 * reactive variables. allCards is built once at module load time from DOM
 * <link-card> elements.
 */

import { atom, computed } from '../vendor/nanostores.js';
import { slugify, foldDiacritics } from './slugify.js';

// ---------------------------------------------------------------------------
// Batched reactive-variable writes — one URL-hash write per logical transition
// ---------------------------------------------------------------------------

/**
 * Nesting depth of active reactive-variable write batches. While > 0,
 * bridgeToHash's hash write is suppressed so multi-variable transitions
 * (e.g. tag -> category) emit a single hashchange instead of one per .set().
 */
let batchDepth = 0;

/** Map of store -> callback, queued while a batch is active (deduped per store). */
const effectQueue = new Map();
let draining = false;

/**
 * Route an effect dispatch: immediately outside a batch, queued (once per
 * store) while a batch is active or while the drain is running, so a
 * re-entrant effect write cannot recurse.
 */
function dispatch(store, cb) {
  if (batchDepth > 0 || draining) {
    effectQueue.set(store, cb);
    return;
  }
  cb(store.get());
}

/**
 * Nanostores-subscribe-like registration that honours batching: fires
 * immediately with the current value, then on every change; while a batch
 * is active the change is queued (once per store) and drained at the
 * outermost batch exit with the final value.
 *
 * @param {import('nanostores').Store} store
 * @param {(value: any) => void} cb
 */
export function effect(store, cb) {
  dispatch(store, cb);
  return store.listen(() => dispatch(store, cb));
}

/**
 * Run reactive-variable writes as one batch: the URL-hash bridge is
 * suppressed and effect dispatches are queued while `fn` runs, then drained
 * exactly once, synchronously, at the outermost batch exit — each effect
 * reading the *final* value of its store. Callers that change state must
 * write the URL exactly once themselves (handleHashChange leaves the hash
 * untouched — the parsed state always serialises back to the current hash —
 * while TagManager/FilterManager write the final hash at the end of their
 * own transition).
 *
 * @param {() => void} fn
 */
export function batchAtomWrites(fn) {
  batchDepth += 1;
  try {
    fn();
  } finally {
    batchDepth -= 1;
    if (batchDepth === 0) {
      draining = true;
      try {
        while (effectQueue.size > 0) {
          const entries = Array.from(effectQueue.entries());
          effectQueue.clear();
          for (const [store, cb] of entries) cb(store.get());
        }
      } finally {
        draining = false;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Reactive variables — single source of truth for filter state
// ---------------------------------------------------------------------------

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeTag = atom(null);

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeSearch = atom(null);

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeCategory = atom(null);

/**
 * Computed descriptor of which filter is active (at most one of the three
 * filter reactive variables is non-null — invariant held by all writers).
 * @type {import('nanostores').Computed<{ kind: 'tag'|'search'|'category'|null, value: string|null }>}
 */
export const $activeFilter = computed(
  [$activeTag, $activeSearch, $activeCategory],
  (tag, search, category) => {
    if (tag) return { kind: 'tag', value: tag };
    if (search) return { kind: 'search', value: search };
    if (category) return { kind: 'category', value: category };
    return { kind: null, value: null };
  }
);

/** @type {import('nanostores').WritableAtom<Set<string>>} */
export const $animatedIds = atom(new Set());

// ---------------------------------------------------------------------------
// Card index — built once from the rendered DOM
// ---------------------------------------------------------------------------

/**
 * Array of all link cards with their DOM element and stable id.
 * Built at module load time (module scripts are deferred, so DOM is ready).
 */
export const allCards = Array.from(document.querySelectorAll('.link-card')).map(el => ({
  id: el.id || el.dataset.title || Math.random().toString(36).slice(2),
  el,
}));

// ---------------------------------------------------------------------------
// Computed: visible card ids based on the current filter reactive variables
// ---------------------------------------------------------------------------

/**
 * Returns the list of card ids that match the current filter criteria.
 * Mirrors the logic of today's card filtering.
 */
export const $visibleCards = computed(
  [$activeTag, $activeSearch, $activeCategory],
  (tag, search, category) => {
    return allCards.filter(({ el }) => {
      const cardCategory = el.dataset.category || '';
      const tags = (el.dataset.tags || '').toLowerCase();
      const cardTagsArray = tags ? tags.split(',').map(t => t.trim()) : [];
      const title = (el.dataset.title || '').toLowerCase();
      const summary = (el.dataset.summary || '').toLowerCase();

      if (search) {
        // B9: fold diacritics so 'francais' matches 'Français' and 'δυο'
        // matches 'δύο' (and vice versa). The same normalization slugify
        // applies to tags. Folding happens only inside this branch — the
        // tag branch below keeps the raw/lowercase tags for slugify().
        const folded = foldDiacritics(search);
        return (
          foldDiacritics(title).includes(folded) ||
          foldDiacritics(summary).includes(folded) ||
          foldDiacritics(tags).includes(folded)
        );
      }
      if (tag) {
        // $activeTag carries the SLUGGED tag (see TagManager.setActiveTag /
        // parseHash: 'C++' -> 'c', 'R&D' -> 'rd', 'Français' -> 'francais',
        // 'machine learning' -> 'machine-learning'). Slugify each raw card
        // tag with the same normalization so both sides compare slug-to-slug.
        return cardTagsArray.some(t => slugify(t) === tag);
      }
      if (category) {
        const matching = window.CATEGORY_MAP?.[category] || [category];
        return matching.includes(cardCategory);
      }
      return true; // no filter → show all
    }).map(({ id }) => id);
  }
);

// ---------------------------------------------------------------------------
// URL-hash bridge
// ---------------------------------------------------------------------------

/**
 * Decode a percent-encoded URL-hash segment. Browsers percent-encode
 * non-ASCII characters in the fragment (writing 'tag-δυο' makes
 * location.hash read '#tag-%CE%B4%CF%85%CE%BF'), so tag and search segments
 * must both be decoded on the way in.
 *
 * A malformed sequence (e.g. a hand-typed '#tag-%' or '#search-%') would
 * throw URIError; fall back to the raw segment so the hashchange handler
 * never crashes — the filter simply won't match garbage.
 *
 * @param {string} segment
 * @returns {string}
 */
function decodeHashSegment(segment) {
  try {
    return decodeURIComponent(segment);
  } catch (e) {
    if (e instanceof URIError) return segment;
    throw e;
  }
}

/**
 * Parse a URL hash fragment into filter state.
 *
 * @param {string} hash - window.location.hash (or empty string)
 * @returns {{ tag: string|null, search: string|null, category: string|null }}
 */
function parseHash(hash) {
  const h = hash || '';
  if (h.startsWith('#search-')) return { tag: null, search: decodeHashSegment(h.slice(8)), category: null };
  if (h.startsWith('#tag-')) return { tag: decodeHashSegment(h.slice(5)), search: null, category: null };
  if (h.startsWith('#category-')) return { tag: null, search: null, category: h.slice(10) };
  return { tag: null, search: null, category: null };
}

/**
 * Serialise filter reactive variables into a URL hash string.
 *
 * Exported for `browseUrl`; keep in sync with `parseHash`'s inverse
 * contract. Tag and search segments are percent-encoded so the written URL
 * is always the normalized form — matching what the browser reports in
 * window.location.hash, which keeps writeHash's comparison stable (both
 * sides encoded) and the hash round-trip idempotent. ASCII values are
 * unaffected (encodeURIComponent('foo') === 'foo').
 *
 * @param {string|null} tag
 * @param {string|null} search
 * @param {string|null} category
 * @returns {string}
 */
export function serialiseHash(tag, search, category) {
  if (tag) return `#tag-${encodeURIComponent(tag)}`;
  if (search) return `#search-${encodeURIComponent(search)}`;
  if (category) return `#category-${category}`;
  return '';
}

/**
 * Parse the current URL hash and pass the result to `apply`.
 * Used to initialise reactive variables from the hash on page load.
 *
 * @param {(next: { tag: string|null, search: string|null, category: string|null }) => void} apply
 */
export function bridgeFromHash(apply) {
  const parsed = parseHash(window.location.hash);
  apply(parsed);
}

/**
 * Subscribe to reactive-variable changes and push to URL hash.
 * Nanostores' built-in === equality check prevents write loops when
 * handleHashChange re-applies the same values.
 *
 * @param {{ $activeTag, $activeSearch, $activeCategory }} atoms
 */
export function bridgeToHash(atoms) {
  const writeHash = () => {
    if (batchDepth > 0) return; // batched transition — caller writes the final hash
    const tag = atoms.$activeTag.get();
    const search = atoms.$activeSearch.get();
    const category = atoms.$activeCategory.get();
    const hash = serialiseHash(tag, search, category);
    if (hash !== window.location.hash) {
      window.location.hash = hash;
    }
  };
  atoms.$activeTag.listen(writeHash);
  atoms.$activeSearch.listen(writeHash);
  atoms.$activeCategory.listen(writeHash);
}
