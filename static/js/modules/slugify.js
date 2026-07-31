/**
 * Slugify a tag name into its canonical URL/atom form.
 *
 * Single source of truth for tag normalization. The URL hash and the
 * $activeTag atom carry slugs; raw card tags (data-tags) must be slugified
 * with this same function before matching (see state.js $visibleCards).
 *
 * Examples: 'C++' -> 'c', 'C#' -> 'c', 'R&D' -> 'rd',
 *           'Français' -> 'francais', 'machine learning' -> 'machine-learning'
 *
 * @param {*} text
 * @returns {string}
 */
export function slugify(text) {
  return text
    .toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\-]+/g, '')
    .replace(/\-\-+/g, '-');
}
