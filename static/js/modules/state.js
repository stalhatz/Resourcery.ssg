/**
 * Central observable state model for Resourcery.ssg.
 *
 * Atoms are Nanostores-based reactive primitives.
 * $visibleCards is a computed derived from the three filter atoms.
 * allCards is built once at module load time from DOM <link-card> elements.
 */

import { atom, computed } from '../vendor/nanostores.js';
import { slugify } from './slugify.js';

// ---------------------------------------------------------------------------
// Batched atom writes — one URL-hash write per logical transition
// ---------------------------------------------------------------------------

/**
 * Nesting depth of active atom-write batches. While > 0, bridgeToHash's
 * hash write is suppressed so multi-atom transitions (e.g. tag -> category)
 * emit a single hashchange instead of one per atom.set().
 */
let batchDepth = 0;

/**
 * Run atom writes as one batch: the URL-hash bridge is suppressed while `fn`
 * runs. Callers that change state must write the URL exactly once themselves
 * (handleHashChange leaves the hash untouched — the parsed state always
 * serialises back to the current hash — while TagManager/FilterManager write
 * the final hash at the end of their own transition).
 *
 * @param {() => void} fn
 */
export function batchAtomWrites(fn) {
  batchDepth += 1;
  try {
    fn();
  } finally {
    batchDepth -= 1;
  }
}

// ---------------------------------------------------------------------------
// Atoms — single source of truth for filter state
// ---------------------------------------------------------------------------

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeTag = atom(null);

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeSearch = atom(null);

/** @type {import('nanostores').WritableAtom<string|null>} */
export const $activeCategory = atom(null);

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
// Computed: visible card ids based on current filter atoms
// ---------------------------------------------------------------------------

/**
 * Returns the list of card ids that match the current filter criteria.
 * Mirrors the logic of today's filterCards().
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
        const lower = search.toLowerCase();
        return title.includes(lower) || summary.includes(lower) || tags.includes(lower);
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
 * Parse a URL hash fragment into filter state.
 *
 * @param {string} hash - window.location.hash (or empty string)
 * @returns {{ tag: string|null, search: string|null, category: string|null }}
 */
function parseHash(hash) {
  const h = hash || '';
  if (h.startsWith('#search-')) return { tag: null, search: decodeURIComponent(h.slice(8)), category: null };
  if (h.startsWith('#tag-')) return { tag: h.slice(5), search: null, category: null };
  if (h.startsWith('#category-')) return { tag: null, search: null, category: h.slice(10) };
  return { tag: null, search: null, category: null };
}

/**
 * Serialise filter atoms into a URL hash string.
 *
 * @param {string|null} tag
 * @param {string|null} search
 * @param {string|null} category
 * @returns {string}
 */
function serialiseHash(tag, search, category) {
  if (tag) return `#tag-${tag}`;
  if (search) return `#search-${encodeURIComponent(search)}`;
  if (category) return `#category-${category}`;
  return '';
}

/**
 * Parse the current URL hash and pass the result to `apply`.
 * Used to initialise atoms from the hash on page load.
 *
 * @param {(next: { tag: string|null, search: string|null, category: string|null }) => void} apply
 */
export function bridgeFromHash(apply) {
  const parsed = parseHash(window.location.hash);
  apply(parsed);
}

/**
 * Subscribe to atom changes and push to URL hash.
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
