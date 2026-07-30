/**
 * Resourcery.ssg — client-side bootstrap.
 *
 * This is now a slim ES module that imports all managers and wires them
 * together. The URL hash is the single source of truth for cross-module
 * coordination; atom changes are bridged to/from the hash.
 */

import { $activeTag, $activeSearch, $activeCategory, bridgeFromHash, bridgeToHash } from './modules/state.js';
import { ThemeManager } from './modules/theme-manager.js';
import { ModalManager } from './modules/modal-manager.js';
import { TagManager } from './modules/tag-manager.js';
import { SidebarManager } from './modules/sidebar-manager.js';
import { CardManager } from './modules/card-manager.js';
import { EntryAnimator } from './modules/entry-animator.js';
import { FilterManager } from './modules/filter-manager.js';
import { filterCards } from './modules/filter-cards.js';
import { sortCards } from './modules/sort-cards.js';
import { handleHashChange, installHashChangeListener } from './modules/handle-hash-change.js';

const isBrowsePage = window.location.pathname.includes('browse.html');

// Install URL-hash bridge: consume initial hash, then subscribe to atom changes
const filterAtoms = { $activeTag, $activeSearch, $activeCategory };

// Phase 1: Apply initial hash to atoms (no DOM side-effects yet)
bridgeFromHash((next) => {
  if (next.tag) $activeTag.set(next.tag);
  else if (next.search) $activeSearch.set(next.search);
  else if (next.category) $activeCategory.set(next.category);
});

// Phase 2: Subscribe bridge to atom changes (hash writes happen after this)
bridgeToHash(filterAtoms);

// Always-on managers
ThemeManager.init();
SidebarManager.init();
CardManager.init();
EntryAnimator.init();
TagManager.init();
ModalManager.init();

if (isBrowsePage) {
  FilterManager.init();
  handleHashChange();          // Apply initial hash to the DOM (sidebar, dropdown, cards)
  installHashChangeListener(); // Forward subsequent hashchange events
  sortCards();
  filterCards();
}
