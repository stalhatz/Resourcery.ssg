/**
 * Resourcery.ssg — client-side bootstrap.
 *
 * This is now a slim ES module that imports all managers and wires them
 * together. The reactive variables are the single source of truth for
 * cross-module coordination; the URL hash is one input/output among several
 * (bridged to/from the reactive state). DOM side-effects are handled by the
 * effects layer, installed in the browse-page branch.
 */

import { $activeTag, $activeSearch, $activeCategory, bridgeFromHash, bridgeToHash } from './modules/state.js';
import { ThemeManager } from './modules/theme-manager.js';
import { ModalManager } from './modules/modal-manager.js';
import { TagManager } from './modules/tag-manager.js';
import { SidebarManager } from './modules/sidebar-manager.js';
import { CardManager } from './modules/card-manager.js';
import { EntryAnimator } from './modules/entry-animator.js';
import { FilterManager } from './modules/filter-manager.js';
import { sortCards } from './modules/sort-cards.js';
import { installHashChangeListener } from './modules/handle-hash-change.js';
import { installEffects } from './modules/effects.js';
import { isBrowsePage } from './modules/browse-utils.js';

// Install URL-hash bridge: consume initial hash, then subscribe to reactive-variable changes
const filterAtoms = { $activeTag, $activeSearch, $activeCategory };

// Phase 1: Apply initial hash to reactive variables (no DOM side-effects yet)
bridgeFromHash((next) => {
  if (next.tag) $activeTag.set(next.tag);
  else if (next.search) $activeSearch.set(next.search);
  else if (next.category) $activeCategory.set(next.category);
});

// Phase 2: Subscribe bridge to reactive-variable changes (hash writes happen after this)
bridgeToHash(filterAtoms);

// Always-on managers
ThemeManager.init();
SidebarManager.init();
CardManager.init();
EntryAnimator.init();
TagManager.init();
ModalManager.init();

if (isBrowsePage()) {
  FilterManager.init();
  installHashChangeListener();
  installEffects();     // immediate fires replace the boot hash/DOM sync calls
  sortCards();
}
