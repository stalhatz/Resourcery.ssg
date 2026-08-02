/**
 * Sidebar manager — collapsible category accordion, mobile overlay.
 *
 * Category trigger clicks and subcategory link clicks write the URL hash;
 * the reactive effects layer (effects.js) then syncs the accordion, the
 * dropdowns, the filter header and the card grid. Same-value clicks (the
 * clicked category is already active) sync the accordion directly — that is
 * the bug fix: without it, the collapse-all + hash write (which fires no
 * hashchange for an unchanged hash) would collapse the whole accordion. On
 * the landing page, clicks navigate to browse.html via browseUrl.
 */

import { dom } from '../dom.js';
import { $activeFilter } from './state.js';
import { isBrowsePage, browseUrl } from './browse-utils.js';

const isLandingPage = !isBrowsePage();

/**
 * The single accordion state machine: expand the matching subcategory link
 * (or fall back to the matching category trigger) and collapse everything
 * else; for every non-category descriptor (tag, search, none) clear all
 * active classes and collapse every list.
 *
 * @param {{ kind: 'tag'|'search'|'category'|null, value: string|null }} descriptor
 */
export function syncAccordion(descriptor) {
  const categoryTriggers = document.querySelectorAll('.category-trigger');

  // Reset everything: no active classes, all lists collapsed.
  categoryTriggers.forEach(t => {
    t.classList.remove('active');
    t.setAttribute('aria-expanded', 'false');
    const list = document.getElementById(t.getAttribute('aria-controls'));
    if (list) list.classList.remove('expanded');
  });
  document.querySelectorAll('.subcategory-link').forEach(link => {
    link.classList.remove('active');
  });

  if (descriptor.kind !== 'category' || !descriptor.value) return;

  // Subcategory first: expand the matching link's parent list + its trigger.
  let found = false;
  document.querySelectorAll('.subcategory-link').forEach(link => {
    if (link.dataset.category === descriptor.value) {
      link.classList.add('active');
      found = true;
      const parentList = link.closest('.subcategory-list');
      if (parentList) {
        parentList.classList.add('expanded');
        const trigger = document.querySelector(
          '[aria-controls="' + parentList.id + '"]'
        );
        if (trigger) trigger.setAttribute('aria-expanded', 'true');
      }
    }
  });

  // Fallback: the category trigger itself.
  if (!found) {
    categoryTriggers.forEach(trigger => {
      if (trigger.dataset.categoryId === descriptor.value) {
        trigger.classList.add('active');
        trigger.setAttribute('aria-expanded', 'true');
        const list = document.getElementById(trigger.getAttribute('aria-controls'));
        if (list) list.classList.add('expanded');
      }
    });
  }
}

export const SidebarManager = {
  init() {
    const toggle = dom.sidebarToggle;
    const sidebar = dom.sidebar;
    if (!toggle || !sidebar) return;

    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    toggle.addEventListener('click', () => {
      sidebar.classList.toggle('active');
      overlay.classList.toggle('active');
    });

    overlay.addEventListener('click', () => {
      sidebar.classList.remove('active');
      overlay.classList.remove('active');
    });

    const categoryTriggers = document.querySelectorAll('.category-trigger');

    categoryTriggers.forEach(trigger => {
      trigger.addEventListener('click', e => {
        e.stopPropagation();

        const categoryId = trigger.dataset.categoryId;
        if (!categoryId) return;

        if (isLandingPage) {
          window.location.href = browseUrl('category', categoryId);
          return;
        }

        const { kind, value } = $activeFilter.get();
        if (kind === 'category' && value === categoryId) {
          // Bug fix: same-value click keeps the accordion expanded (a hash
          // write would fire no hashchange and leave everything collapsed).
          syncAccordion({ kind: 'category', value: categoryId });
        } else {
          // Different category — the effects layer does the rest.
          window.location.hash = 'category-' + categoryId;
        }
      });
    });

    const subcategoryLinks = document.querySelectorAll('.subcategory-link');

    subcategoryLinks.forEach(link => {
      link.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();

        const category = link.dataset.category;

        if (isLandingPage) {
          window.location.href = browseUrl('category', category);
          return;
        }

        const { kind, value } = $activeFilter.get();
        if (kind === 'category' && value === category) {
          syncAccordion({ kind: 'category', value: category });
        } else {
          window.location.hash = 'category-' + category;
        }

        if (window.innerWidth <= 1023) {
          sidebar.classList.remove('active');
          overlay.classList.remove('active');
        }
      });
    });
  },
};
