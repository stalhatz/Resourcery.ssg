/**
 * Browse-page utilities — page detection and canonical browse.html URLs.
 *
 * The single home for "are we on the browse page" and for building
 * browse.html#... links. browseUrl reuses state.js's serialiseHash so the
 * hrefs and the URL-hash bridge can never drift apart (the value is placed
 * in the position of its kind; callers pass the canonical form — tag slugs,
 * raw search terms, category ids).
 */

import { serialiseHash } from './state.js';

export const isBrowsePage = () => window.location.pathname.includes('browse.html');

export function browseUrl(kind, value) {
  const tag = kind === 'tag' ? value : null;
  const search = kind === 'search' ? value : null;
  const category = kind === 'category' ? value : null;
  return 'browse.html' + serialiseHash(tag, search, category);
}
