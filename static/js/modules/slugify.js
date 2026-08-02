/**
 * Fold diacritics: NFD-normalize, strip combining marks, lowercase.
 * The shared normalization for tag slugs (via slugify) and free-text search
 * matching/suggestions — 'Français' and 'francais' (and 'δύο'/'δυο') fold to
 * the same string, so accented and unaccented forms match each other.
 *
 * @param {*} text
 * @returns {string}
 */
export function foldDiacritics(text) {
  return text
    .toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

/**
 * Slugify a tag name into its canonical URL/reactive-variable form.
 *
 * Single source of truth for tag normalization. The URL hash and the
 * $activeTag reactive variable carry slugs; raw card tags (data-tags) must
 * be slugified with this same function before matching (see state.js
 * $visibleCards).
 *
 * Examples: 'C++' -> 'c', 'C#' -> 'c', 'R&D' -> 'rd',
 *           'Français' -> 'francais', 'machine learning' -> 'machine-learning'
 *
 * @param {*} text
 * @returns {string}
 */
export function slugify(text) {
  return foldDiacritics(text)
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\p{L}\p{N}_\-]+/gu, '')
    .replace(/\-\-+/g, '-');
}
