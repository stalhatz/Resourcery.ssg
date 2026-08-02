/**
 * Hash change handler — the bridge between URL hash and reactive state.
 *
 * On hashchange (or initial load), parses the hash and sets the three
 * filter reactive variables inside one batch. All DOM side-effects (select
 * mirror, custom dropdown, sidebar accordion, filter header, card grid) are
 * owned by the effects layer (effects.js), which the batch drain invokes
 * exactly once per transition.
 */

import { $activeTag, $activeSearch, $activeCategory, bridgeFromHash, batchAtomWrites } from './state.js';
import { isBrowsePage } from './browse-utils.js';

export function handleHashChange() {
  if (!isBrowsePage()) return;

  // Batch the three sets: without batching, each .set() would fire
  // bridgeToHash's writeHash and produce intermediate hashchange/history
  // entries (e.g. '#tag-foo' -> '' -> '#category-web'). The parsed state
  // always serialises back to the current hash, so no hash write is needed.
  batchAtomWrites(() => {
    bridgeFromHash(next => {
      $activeTag.set(next.tag);
      $activeSearch.set(next.search);
      $activeCategory.set(next.category);
    });
  });
}

export function installHashChangeListener() {
  window.addEventListener('hashchange', handleHashChange);
}
