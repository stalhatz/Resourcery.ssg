/**
 * Filter manager — custom dropdown for category/sort with full ARIA.
 *
 * Manages the category and sort dropdowns. Category selection writes to
 * the URL hash (which triggers handleHashChange → filterCards). Sort
 * selection calls sortCards() directly.
 */

import { dom } from '../dom.js';
import { TagManager } from './tag-manager.js';
import { filterCards } from './filter-cards.js';
import { sortCards } from './sort-cards.js';

export const FilterManager = {
  dropdowns: {},

  init() {
    const categoryTrigger = dom.categoryTrigger;
    const categoryFilter = dom.categoryFilter;
    const categoryDropdown = dom.categoryDropdown;

    const sortTrigger = dom.sortTrigger;
    const sortFilter = dom.sortFilter;
    const sortDropdown = dom.sortDropdown;

    if (categoryTrigger && categoryFilter && categoryDropdown) {
      this.bindDropdown(categoryTrigger, categoryFilter, categoryDropdown, 'category');
    }
    if (sortTrigger && sortFilter && sortDropdown) {
      this.bindDropdown(sortTrigger, sortFilter, sortDropdown, 'sort');
    }

    window.addEventListener('clearFilters', () => {
      TagManager.clearActiveSearch();
      TagManager.clearActiveTag();
      if (dom.categoryFilter) dom.categoryFilter.value = '';
      this.syncSelection('category', '');
      filterCards();
    });
  },

  bindDropdown(trigger, nativeSelect, dropdown, type) {
    const self = this;

    // Attach click handlers to pre-rendered option buttons
    dropdown.querySelectorAll('.filter-dropdown-option').forEach(btn => {
      btn.addEventListener('click', e => {
        e.preventDefault();
        e.stopPropagation();

        var value = btn.dataset.value;
        nativeSelect.value = value;
        self.syncSelection(type, value);
        self.closeAllDropdowns();

        if (type === 'category') {
          TagManager.clearActiveSearch();
          TagManager.clearActiveTag();
          TagManager.setCategoryDisplay(value);
          if (value) {
            window.location.hash = 'category-' + value;
          } else {
            history.pushState('', '', window.location.pathname);
          }
          filterCards();
        } else if (type === 'sort') {
          sortCards();
        }
      });
    });

    // Toggle open/close
    trigger.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      self.toggleDropdown(type);
    });

    document.addEventListener('click', e => {
      if (!trigger.contains(e.target)) {
        self.closeDropdown(type);
      }
    });

    this.dropdowns[type] = {
      trigger: trigger,
      dropdown: dropdown,
      native: nativeSelect,
    };
  },

  syncSelection(type, value) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    entry.dropdown.querySelectorAll('.filter-dropdown-option').forEach(btn => {
      btn.classList.toggle('selected', btn.dataset.value === value);
    });
  },

  toggleDropdown(type) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    var isActive = entry.dropdown.classList.contains('active');
    this.closeAllDropdowns();
    if (!isActive) {
      entry.dropdown.classList.add('active');
      entry.trigger.setAttribute('aria-expanded', 'true');
    }
  },

  closeDropdown(type) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    entry.dropdown.classList.remove('active');
    entry.trigger.setAttribute('aria-expanded', 'false');
  },

  closeAllDropdowns() {
    Object.keys(this.dropdowns).forEach(type => {
      this.closeDropdown(type);
    });
  },
};
