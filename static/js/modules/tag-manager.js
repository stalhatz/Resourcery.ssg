/**
 * Tag manager — search suggestions, active tag/search state, filter header.
 *
 * Uses Nanostores reactive variables ($activeTag, $activeSearch,
 * $activeCategory) instead of plain fields. All URL-hash writing is done
 * here for tag/search; category hash writes happen in filter-manager and
 * sidebar-manager. DOM side-effects (header, dropdowns, accordion, cards)
 * are owned by the effects layer (effects.js).
 */

import { $activeTag, $activeSearch, $activeCategory, $activeFilter, batchAtomWrites } from './state.js';
import { slugify, foldDiacritics } from './slugify.js';
import { dom } from '../dom.js';
import { isBrowsePage, browseUrl } from './browse-utils.js';
import { createLogger } from './logger.js';

export const logger = createLogger(import.meta.url);

const isLandingPage = !isBrowsePage();

export const TagManager = {
  allTags: [],
  isInitialized: false,
  selectedSuggestionIndex: -1,

  init() {
    this.allTags = window.ALL_TAGS || [];
    this.setupSearchSuggestions();
    this.isInitialized = true;
  },

  /**
   * Slugify a tag into its canonical URL/reactive-variable form. Delegates
   * to the shared slugify module — the single source of truth used by
   * state.js matching.
   */
  slugify(text) {
    return slugify(text);
  },

  setActiveTag(tag, updateUrl) {
    const slug = tag ? this.slugify(tag) : null;

    // Invariant: only one reactive variable is active at a time. Batched so
    // the bridge writes the URL once per transition, not once per .set()
    // (which would emit intermediate hashchange/history entries).
    batchAtomWrites(() => {
      $activeSearch.set(null);
      $activeCategory.set(null);
      $activeTag.set(slug);

      if (updateUrl !== false) {
        if (slug) {
          window.location.hash = 'tag-' + slug;
        } else if (window.location.hash) {
          // Only clear the hash when there is one — avoids pushing a
          // spurious history entry when nothing is active.
          history.pushState('', '', window.location.pathname);
        }
      }
    });
  },

  setActiveSearch(searchTerm, updateUrl) {
    const term = searchTerm ? searchTerm.trim() : null;

    // Invariant: only one reactive variable is active at a time. Batched so
    // the bridge writes the URL once per transition, not once per .set().
    batchAtomWrites(() => {
      $activeTag.set(null);
      $activeCategory.set(null);
      $activeSearch.set(term);

      if (updateUrl !== false) {
        if (term) {
          window.location.hash = 'search-' + encodeURIComponent(term);
        } else if (window.location.hash) {
          // Only clear the hash when there is one — avoids pushing a
          // spurious history entry when nothing is active.
          history.pushState('', '', window.location.pathname);
        }
      }
    });
  },

  updateFilterHeader() {
    const filterText1 = dom.filterText1;
    const filterValue1 = dom.filterValue1;
    const filterText2 = dom.filterText2;
    const categoryTrigger = dom.categoryTrigger;
    const searchValue = dom.searchValue;

    if (!filterText1 || !filterValue1) {
      logger.warn('⚠️ Filter header elements not found');
      return;
    }

    const { kind, value } = $activeFilter.get();

    if (kind === 'search') {
      filterText1.style.display = 'inline';
      filterText1.textContent = 'Searching';

      if (categoryTrigger) {
        categoryTrigger.style.display = 'none';
      }

      if (searchValue) {
        searchValue.style.display = 'inline';
        searchValue.textContent = '"' + value + '"';
      }

      if (filterText2) filterText2.style.display = 'none';
    } else if (kind === 'tag') {
      filterText1.style.display = 'inline';
      filterText1.textContent = 'Showing';

      if (categoryTrigger) {
        categoryTrigger.style.display = 'inline-flex';
        categoryTrigger.style.pointerEvents = 'none';
        categoryTrigger.style.opacity = '1';
      }

      filterValue1.style.display = 'inline';
      filterValue1.textContent = '#' + value;

      if (searchValue) {
        searchValue.style.display = 'none';
      }

      if (filterText2) filterText2.style.display = 'inline';
    } else {
      filterText1.style.display = 'inline';
      filterText1.textContent = 'Showing';

      if (categoryTrigger) {
        categoryTrigger.style.display = 'inline-flex';
        categoryTrigger.style.pointerEvents = 'auto';
        categoryTrigger.style.opacity = '1';
      }

      if (searchValue) {
        searchValue.style.display = 'none';
      }

      if (filterText2) filterText2.style.display = 'inline';

      if (dom.categoryFilter) {
        var option = Array.from(dom.categoryFilter.options).find(function (opt) {
          return opt.value === dom.categoryFilter.value;
        });
        filterValue1.textContent = option ? option.textContent : 'All Categories';
      } else {
        filterValue1.textContent = 'All Categories';
      }
    }
  },

  getActiveTag() {
    return $activeTag.get();
  },

  getActiveSearch() {
    return $activeSearch.get();
  },

  /**
   * @param {boolean} [updateUrl] - false when the caller writes the URL itself.
   */
  clearActiveTag(updateUrl = true) {
    this.setActiveTag(null, updateUrl);
  },

  /**
   * @param {boolean} [updateUrl] - false when the caller writes the URL itself.
   */
  clearActiveSearch(updateUrl = true) {
    this.setActiveSearch(null, updateUrl);
  },

  clearSearchInput() {
    if (dom.searchInput) {
      dom.searchInput.value = '';
    }
  },

  setupSearchSuggestions() {
    const searchInput = dom.searchInput;
    if (!searchInput) return;

    const suggestionsBox = document.createElement('div');
    suggestionsBox.className = 'search-suggestions';
    suggestionsBox.id = 'searchSuggestions';
    suggestionsBox.setAttribute('role', 'listbox');
    suggestionsBox.setAttribute('aria-label', 'Search suggestions');
    searchInput.parentNode.style.position = 'relative';
    searchInput.parentNode.appendChild(suggestionsBox);

    // Also update the dom reference for the new element
    dom.searchSuggestions = suggestionsBox;

    searchInput.setAttribute('role', 'combobox');
    searchInput.setAttribute('aria-autocomplete', 'list');
    searchInput.setAttribute('aria-controls', 'searchSuggestions');
    searchInput.setAttribute('aria-expanded', 'false');

    const self = this;

    searchInput.addEventListener(
      'input',
      self.debounce(function () {
        var value = searchInput.value.trim();

        if (value.length >= 1) {
          // B9: fold diacritics on both the query and the tag so 'francais'
          // suggests 'Français' and 'δυο' suggests 'δύο'.
          var query = value.startsWith('#')
            ? foldDiacritics(value.substring(1))
            : foldDiacritics(value);
          var matches = self.allTags
            .filter(function (tag) {
              return foldDiacritics(tag).includes(query);
            })
            .slice(0, 8);

          if (matches.length > 0) {
            self.renderSuggestions(
              matches,
              value.startsWith('#'),
              suggestionsBox,
              searchInput
            );
            searchInput.setAttribute('aria-expanded', 'true');
          } else {
            self.hideSuggestions(suggestionsBox, searchInput);
          }
        } else {
          self.hideSuggestions(suggestionsBox, searchInput);
        }
      }, 200)
    );

    searchInput.addEventListener('keydown', function (e) {
      var suggestions = suggestionsBox.querySelectorAll('.suggestion-item');

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (suggestions.length > 0) {
          self.selectedSuggestionIndex = Math.min(
            self.selectedSuggestionIndex + 1,
            suggestions.length - 1
          );
          self.highlightSuggestion(suggestions, self.selectedSuggestionIndex);
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (suggestions.length > 0) {
          self.selectedSuggestionIndex = Math.max(
            self.selectedSuggestionIndex - 1,
            0
          );
          self.highlightSuggestion(suggestions, self.selectedSuggestionIndex);
        }
      } else if (e.key === 'Enter') {
        e.preventDefault();
        e.stopPropagation();

        if (
          self.selectedSuggestionIndex >= 0 &&
          suggestions[self.selectedSuggestionIndex]
        ) {
          suggestions[self.selectedSuggestionIndex].click();
        } else if (searchInput.value.trim().length > 0) {
          var value = searchInput.value.trim();
          self.hideSuggestions(suggestionsBox, searchInput);
          self.navigateToBrowse(value, searchInput);
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        self.hideSuggestions(suggestionsBox, searchInput);
        searchInput.blur();
      }
    });

    document.addEventListener('click', function (e) {
      if (
        !searchInput.contains(e.target) &&
        !suggestionsBox.contains(e.target)
      ) {
        self.hideSuggestions(suggestionsBox, searchInput);
      }
    });

    searchInput.addEventListener('blur', function () {
      setTimeout(function () {
        self.hideSuggestions(suggestionsBox, searchInput);
      }, 150);
    });
  },

  renderSuggestions(matches, isTagSearch, suggestionsBox, searchInput) {
    this.selectedSuggestionIndex = -1;
    suggestionsBox.innerHTML = '';

    const self = this;

    matches.forEach(function (tag, index) {
      var item = document.createElement('div');
      item.className = 'suggestion-item';
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', 'false');
      item.id = 'suggestion-' + index;
      item.textContent = (isTagSearch ? '#' : '') + tag;
      item.dataset.tag = tag;

      item.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        self.hideSuggestions(suggestionsBox, searchInput);
        self.navigateToBrowse(tag, searchInput);
      });

      item.addEventListener('mouseenter', function () {
        self.selectedSuggestionIndex = index;
        self.highlightSuggestion(
          suggestionsBox.querySelectorAll('.suggestion-item'),
          index
        );
      });

      suggestionsBox.appendChild(item);
    });

    suggestionsBox.classList.add('active');
  },

  highlightSuggestion(suggestions, index) {
    suggestions.forEach(function (s, i) {
      if (i === index) {
        s.classList.add('selected');
        s.setAttribute('aria-selected', 'true');
        s.scrollIntoView({ block: 'nearest' });
      } else {
        s.classList.remove('selected');
        s.setAttribute('aria-selected', 'false');
      }
    });
  },

  hideSuggestions(suggestionsBox, searchInput) {
    suggestionsBox.classList.remove('active');
    searchInput.setAttribute('aria-expanded', 'false');
    this.selectedSuggestionIndex = -1;
  },

  navigateToBrowse(value, searchInput) {
    if (isLandingPage) {
      if (value.startsWith('#')) {
        var tag = value.substring(1).trim();
        window.location.href = browseUrl('tag', this.slugify(tag));
      } else {
        window.location.href = browseUrl('search', value);
      }
    } else {
      if (value.startsWith('#')) {
        var tag = value.substring(1).trim();
        this.setActiveTag(tag, true);
      } else {
        this.setActiveSearch(value, true);
      }

      searchInput.value = '';
    }
  },

  debounce(func, wait) {
    var timeout;
    return function () {
      var args = arguments;
      clearTimeout(timeout);
      timeout = setTimeout(function () {
        func.apply(this, args);
      }, wait);
    };
  },
};
