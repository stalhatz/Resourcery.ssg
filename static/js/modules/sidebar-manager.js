/**
 * Sidebar manager — collapsible category accordion, mobile overlay.
 *
 * Category trigger clicks and subcategory link clicks update the URL hash
 * and trigger filtering. On the landing page, clicks navigate to browse.html.
 */

import { dom } from '../dom.js';
import { TagManager } from './tag-manager.js';
import { filterCards } from './filter-cards.js';

const isLandingPage = !window.location.pathname.includes('browse.html');

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

        if (isLandingPage) {
          const categoryId = trigger.dataset.categoryId;
          window.location.href = 'browse.html#category-' + categoryId;
          return;
        }

        const categoryId = trigger.dataset.categoryId;
        if (!categoryId) return;

        // Collapse all other category triggers before setting hash
        categoryTriggers.forEach(t => {
          t.setAttribute('aria-expanded', 'false');
          const list = document.getElementById(t.getAttribute('aria-controls'));
          if (list) {
            list.classList.remove('expanded');
          }
        });

        // Set the hash — handleHashChange (triggered via hashchange event)
        // handles: expanding matching trigger, filtering cards,
        // updating filter header, syncing dropdown selection
        window.location.hash = 'category-' + categoryId;
      });
    });

    const subcategoryLinks = document.querySelectorAll('.subcategory-link');

    subcategoryLinks.forEach(link => {
      link.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();

        const category = link.dataset.category;

        if (isLandingPage) {
          window.location.href = 'browse.html#category-' + category;
          return;
        }

        if (category && dom.categoryFilter) {
          dom.categoryFilter.value = category;

          var categoryValueEl = dom.filterValue1;
          if (categoryValueEl) {
            var option = Array.from(dom.categoryFilter.options).find(function (
              opt
            ) {
              return opt.value === category;
            });

            if (option) {
              TagManager.setCategoryDisplay(category);
            }
          }

          window.location.hash = 'category-' + category;
          filterCards();
        }

        document.querySelectorAll('.subcategory-link').forEach(function (l) {
          l.classList.remove('active');
        });
        link.classList.add('active');

        document.querySelectorAll('.category-trigger').forEach(function (t) {
          t.classList.remove('active');
        });

        if (window.innerWidth <= 1023) {
          sidebar.classList.remove('active');
          overlay.classList.remove('active');
        }
      });
    });
  },
};
