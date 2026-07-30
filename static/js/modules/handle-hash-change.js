/**
 * Hash change handler — the bridge between URL hash and application state.
 *
 * On hashchange (or initial load), parses the hash, writes atoms via
 * bridgeFromHash, synchronises DOM side-effects (dropdown, sidebar active
 * states), and calls filterCards().
 */

import { $activeTag, $activeSearch, $activeCategory, bridgeFromHash } from './state.js';
import { dom } from '../dom.js';
import { filterCards } from './filter-cards.js';

export function handleHashChange() {
  if (!window.location.pathname.includes('browse.html')) return;

  bridgeFromHash(next => {
    $activeTag.set(next.tag);
    $activeSearch.set(next.search);
    $activeCategory.set(next.category);

    // Update dropdown
    if (next.category && dom.categoryFilter) {
      dom.categoryFilter.value = next.category;
    } else if ((next.tag || next.search) && dom.categoryFilter) {
      dom.categoryFilter.value = '';
    }

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

    filterCards();
  });
}

export function installHashChangeListener() {
  window.addEventListener('hashchange', handleHashChange);
}
