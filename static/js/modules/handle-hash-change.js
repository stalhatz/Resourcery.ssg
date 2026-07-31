/**
 * Hash change handler — the bridge between URL hash and application state.
 *
 * On hashchange (or initial load), parses the hash, writes atoms via
 * bridgeFromHash, synchronises DOM side-effects (dropdown, sidebar active
 * states, filter header), and calls filterCards().
 */

import { $activeTag, $activeSearch, $activeCategory, bridgeFromHash, batchAtomWrites } from './state.js';
import { dom } from '../dom.js';
import { filterCards } from './filter-cards.js';
import { TagManager } from './tag-manager.js';
import { FilterManager } from './filter-manager.js';

export function handleHashChange() {
  if (!window.location.pathname.includes('browse.html')) return;

  // Batch the three atom sets: without batching, each atom.set() would fire
  // bridgeToHash's writeHash and produce intermediate hashchange/history
  // entries (e.g. '#tag-foo' -> '' -> '#category-web'). The parsed state
  // always serialises back to the current hash, so no hash write is needed.
  batchAtomWrites(() => {
    bridgeFromHash(next => {
      $activeTag.set(next.tag);
      $activeSearch.set(next.search);
      $activeCategory.set(next.category);

      // Update dropdown: the hidden select mirrors the parsed category, and
      // the visible custom dropdown (FilterManager.syncSelection) mirrors the
      // select. Every non-category parsed state (tag, search, or all-null /
      // bare URL back-navigation) clears both — otherwise back to a bare URL
      // leaves a stale category in the select, the visible dropdown and the
      // filter header (B2).
      if (next.category && dom.categoryFilter) {
        dom.categoryFilter.value = next.category;
      } else if (dom.categoryFilter) {
        dom.categoryFilter.value = '';
      }
      FilterManager.syncSelection('category', next.category || '');

      // Update sidebar active states
      document.querySelectorAll('.category-trigger, .subcategory-link').forEach(el => {
        el.classList.remove('active');
      });

      if (next.category) {
        // Try subcategory first, then category trigger
        let found = false;
        document.querySelectorAll('.subcategory-link').forEach(link => {
          link.classList.remove('active');
          if (link.dataset.category === next.category) {
            link.classList.add('active');
            found = true;
            const parentList = link.closest('.subcategory-list');
            if (parentList) {
              parentList.classList.add('expanded');
              const trigger = document.querySelector(
                '[aria-controls="' + parentList.id + '"]'
              );
              if (trigger) {
                trigger.setAttribute('aria-expanded', 'true');
              }
            }
          }
        });

        if (!found) {
          document.querySelectorAll('.category-trigger').forEach(trigger => {
            trigger.classList.remove('active');
            if (trigger.dataset.categoryId === next.category) {
              trigger.classList.add('active');
              trigger.setAttribute('aria-expanded', 'true');
              const list = document.getElementById(
                trigger.getAttribute('aria-controls')
              );
              if (list) list.classList.add('expanded');
            }
          });
        }
      }

      // Refresh the filter header (B1): the header must mirror the parsed
      // hash state, not just the dropdown/sidebar/cards. updateFilterHeader
      // reads the atoms set above plus dom.categoryFilter.value (synced
      // above), so it must run after both.
      TagManager.updateFilterHeader();

      filterCards();
    });
  });
}

export function installHashChangeListener() {
  window.addEventListener('hashchange', handleHashChange);
}
