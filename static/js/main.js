/**
 * Main JavaScript for Static Link Aggregation Site
 * Complete File - Landing Page + Browse Page Support (FIXED v7)
 */

// ==================== PAGE DETECTION ====================
const isLandingPage = !window.location.pathname.includes('browse.html');
const isBrowsePage = window.location.pathname.includes('browse.html');

// ==================== TAG MANAGER ====================
const TagManager = {
    activeTag: null,
    activeSearch: null,
    allTags: [],
    isInitialized: false,
    selectedSuggestionIndex: -1,
    
    // No longer needs linksData — tags pre-computed by build.py
    init: function() {
        this.allTags = window.ALL_TAGS || [];
        this.setupSearchSuggestions();
        this.isInitialized = true;
    },

    slugify: function(text) {
        return text
            .toString()
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim()
            .replace(/\s+/g, '-')
            .replace(/[^\w\-]+/g, '')
            .replace(/\-\-+/g, '-');
    },

    setActiveTag: function(tag, updateUrl) {
        this.activeTag = tag ? this.slugify(tag) : null;
        this.activeSearch = null;
        
        if (updateUrl !== false) {
            if (this.activeTag) {
                window.location.hash = 'tag-' + this.activeTag;
            } else {
                var categoryFilter = document.getElementById('categoryFilter');
                if (categoryFilter && categoryFilter.value) {
                    window.location.hash = 'category-' + categoryFilter.value;
                } else {
                    history.pushState('', '', window.location.pathname);
                }
            }
        }
        
        this.updateFilterHeader();
    },

    setActiveSearch: function(searchTerm, updateUrl) {
        this.activeSearch = searchTerm ? searchTerm.trim() : null;
        this.activeTag = null;
        
        if (updateUrl !== false) {
            if (this.activeSearch) {
                window.location.hash = 'search-' + encodeURIComponent(this.activeSearch);
            } else {
                var categoryFilter = document.getElementById('categoryFilter');
                if (categoryFilter && categoryFilter.value) {
                    window.location.hash = 'category-' + categoryFilter.value;
                } else {
                    history.pushState('', '', window.location.pathname);
                }
            }
        }
        
        this.updateFilterHeader();
    },

    setCategoryDisplay: function(categoryId) {
        var categoryFilter = document.getElementById('categoryFilter');
        if (categoryFilter) {
            categoryFilter.value = categoryId || ''; // ✅ ID matches option.value
        }
        this.updateFilterHeader();
    },

    updateFilterHeader: function() {
        var filterText1 = document.getElementById('filterText1');
        var filterValue1 = document.getElementById('filterValue1');
        var filterText2 = document.getElementById('filterText2');
        var categoryTrigger = document.getElementById('categoryTrigger');
        var searchValue = document.getElementById('searchValue');
        var filterIcon = categoryTrigger ? categoryTrigger.querySelector('.filter-icon') : null;
        
        if (!filterText1 || !filterValue1) {
            console.warn('⚠️ Filter header elements not found');
            return;
        }
        
        if (this.activeSearch) {
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Searching';
            
            if (categoryTrigger) {
                categoryTrigger.style.display = 'none';
            }
            
            if (searchValue) {
                searchValue.style.display = 'inline';
                searchValue.textContent = '"' + this.activeSearch + '"';
            }
            
            if (filterText2) filterText2.style.display = 'none';
            
        } else if (this.activeTag) {
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Showing';
            
            if (categoryTrigger) {
                categoryTrigger.style.display = 'inline-flex';
                categoryTrigger.style.pointerEvents = 'none';
                categoryTrigger.style.opacity = '1';
            }
            
            filterValue1.style.display = 'inline';
            filterValue1.textContent = '#' + this.activeTag;
            
            if (searchValue) {
                searchValue.style.display = 'none';
            }
            
            if (filterText2) filterText2.style.display = 'inline';
            if (filterIcon) filterIcon.style.display = 'none';
            
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
            if (filterIcon) filterIcon.style.display = 'inline';
            
            var categoryFilter = document.getElementById('categoryFilter');
            if (categoryFilter) {
                var option = Array.from(categoryFilter.options).find(function(opt) {
                    return opt.value === categoryFilter.value;
                });
                filterValue1.textContent = option ? option.textContent : 'All Categories';
            } else {
                filterValue1.textContent = 'All Categories';
            }
        }       
    },

    getActiveTag: function() {
        return this.activeTag;
    },

    getActiveSearch: function() {
        return this.activeSearch;
    },

    clearActiveTag: function() {
        this.setActiveTag(null, true);
    },

    clearActiveSearch: function() {
        this.setActiveSearch(null, true);
    },

    clearSearchInput: function() {
        var searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = '';
        }
    },

    setupSearchSuggestions: function() {
        var self = this;
        var searchInput = document.getElementById('searchInput');
        if (!searchInput) return;
        
        var suggestionsBox = document.createElement('div');
        suggestionsBox.className = 'search-suggestions';
        suggestionsBox.id = 'searchSuggestions';
        suggestionsBox.setAttribute('role', 'listbox');
        suggestionsBox.setAttribute('aria-label', 'Search suggestions');
        searchInput.parentNode.style.position = 'relative';
        searchInput.parentNode.appendChild(suggestionsBox);
        
        searchInput.setAttribute('role', 'combobox');
        searchInput.setAttribute('aria-autocomplete', 'list');
        searchInput.setAttribute('aria-controls', 'searchSuggestions');
        searchInput.setAttribute('aria-expanded', 'false');

        searchInput.addEventListener('input', self.debounce(function() {
            var value = searchInput.value.trim();
            
            if (value.length >= 1) {
                var query = value.startsWith('#') ? value.substring(1).toLowerCase() : value.toLowerCase();
                var matches = self.allTags.filter(function(tag) {
                    return tag.toLowerCase().includes(query);
                }).slice(0, 8);
                
                if (matches.length > 0) {
                    self.renderSuggestions(matches, value.startsWith('#'), suggestionsBox, searchInput);
                    searchInput.setAttribute('aria-expanded', 'true');
                } else {
                    self.hideSuggestions(suggestionsBox, searchInput);
                }
            } else {
                self.hideSuggestions(suggestionsBox, searchInput);
            }
        }, 200));

        searchInput.addEventListener('keydown', function(e) {
            var suggestions = suggestionsBox.querySelectorAll('.suggestion-item');
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (suggestions.length > 0) {
                    self.selectedSuggestionIndex = Math.min(self.selectedSuggestionIndex + 1, suggestions.length - 1);
                    self.highlightSuggestion(suggestions, self.selectedSuggestionIndex);
                }
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (suggestions.length > 0) {
                    self.selectedSuggestionIndex = Math.max(self.selectedSuggestionIndex - 1, 0);
                    self.highlightSuggestion(suggestions, self.selectedSuggestionIndex);
                }
            } else if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                
                if (self.selectedSuggestionIndex >= 0 && suggestions[self.selectedSuggestionIndex]) {
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

        document.addEventListener('click', function(e) {
            if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
                self.hideSuggestions(suggestionsBox, searchInput);
            }
        });

        searchInput.addEventListener('blur', function() {
            setTimeout(function() {
                self.hideSuggestions(suggestionsBox, searchInput);
            }, 150);
        });
    },

    renderSuggestions: function(matches, isTagSearch, suggestionsBox, searchInput) {
        var self = this;
        self.selectedSuggestionIndex = -1;
        suggestionsBox.innerHTML = '';
        
        matches.forEach(function(tag, index) {
            var item = document.createElement('div');
            item.className = 'suggestion-item';
            item.setAttribute('role', 'option');
            item.setAttribute('aria-selected', 'false');
            item.id = 'suggestion-' + index;
            item.textContent = (isTagSearch ? '#' : '') + tag;
            item.dataset.tag = tag;
            
            item.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                self.hideSuggestions(suggestionsBox, searchInput);
                self.navigateToBrowse(tag, searchInput);
            });
            
            item.addEventListener('mouseenter', function() {
                self.selectedSuggestionIndex = index;
                self.highlightSuggestion(suggestionsBox.querySelectorAll('.suggestion-item'), index);
            });
            
            suggestionsBox.appendChild(item);
        });
        
        suggestionsBox.classList.add('active');
    },

    highlightSuggestion: function(suggestions, index) {
        suggestions.forEach(function(s, i) {
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

    hideSuggestions: function(suggestionsBox, searchInput) {
        suggestionsBox.classList.remove('active');
        searchInput.setAttribute('aria-expanded', 'false');
        this.selectedSuggestionIndex = -1;
    },

    navigateToBrowse: function(value, searchInput) {
        var self = this;
        
        if (isLandingPage) {
            if (value.startsWith('#')) {
                var tag = value.substring(1).trim();
                window.location.href = 'browse.html#tag-' + self.slugify(tag);
            } else {
                window.location.href = 'browse.html#search-' + encodeURIComponent(value);
            }
        } else {
            if (value.startsWith('#')) {
                var tag = value.substring(1).trim();
                self.setActiveTag(tag, true);
            } else {
                self.setActiveSearch(value, true);
            }
            
            searchInput.value = '';
            
            if (typeof filterCards === 'function') {
                filterCards();
            }
        }
    },

    debounce: function(func, wait) {
        var timeout;
        return function() {
            var args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(function() {
                func.apply(this, args);
            }, wait);
        };
    }
};

// ==================== MODAL MANAGER ====================
const ModalManager = {
    open: function(card) {
        var overlay = document.getElementById('modalOverlay');
        var modal = document.getElementById('modal');
        if (!overlay || !modal) {
            console.warn('⚠️ Modal elements not found');
            return;
        }
        
        document.getElementById('modalTitle').textContent = card.dataset.title;
        document.getElementById('modalSummary').textContent = card.dataset.summary;
        document.getElementById('modalDescription').textContent = card.dataset.description || card.dataset.summary;
        document.getElementById('modalCategory').textContent = card.dataset.category;
        document.getElementById('modalPricing').textContent = card.dataset.pricing;
        document.getElementById('modalLanguage').textContent = card.dataset.language;
        document.getElementById('modalVisit').href = card.dataset.url;
        
        var modalImage = document.getElementById('modalImage');
        if (modalImage) {
            if (card.dataset.image) {
                modalImage.style.backgroundImage = 'url(' + card.dataset.image + ')';
            } else {
                modalImage.style.backgroundImage = 'url(/static/images/placeholders/' + card.dataset.category + '.jpg)';
            }
        }
        
        var tagsContainer = document.getElementById('modalTags');
        if (tagsContainer) {
            tagsContainer.innerHTML = '';
            var tags = card.dataset.tags.split(',');
            tags.forEach(function(tag) {
                if (tag.trim()) {
                    var tagEl = document.createElement('span');
                    tagEl.className = 'modal-tag';
                    tagEl.textContent = tag.trim();
                    tagEl.style.cursor = 'pointer';
                    tagEl.addEventListener('click', function(e) {
                        e.stopPropagation();
                        var tagName = tag.trim();
                        
                        if (isLandingPage) {
                            window.location.href = 'browse.html#tag-' + TagManager.slugify(tagName);
                        } else {
                            TagManager.setActiveTag(tagName);
                            ModalManager.close();
                            filterCards();
                        }
                    });
                    tagsContainer.appendChild(tagEl);
                }
            });
        }
        
        var shareUrl = encodeURIComponent(card.dataset.url);
        var shareTitle = encodeURIComponent(card.dataset.title);
        var twitterLink = document.getElementById('shareTwitter');
        if (twitterLink) {
            twitterLink.href = 'https://twitter.com/intent/tweet?url=' + shareUrl + '&text=' + shareTitle;
        }
        
        overlay.style.display = 'flex';
        setTimeout(function() {
            overlay.classList.add('active');
        }, 10);
        
        document.body.style.overflow = 'hidden';
        modal.focus();       
    },

    close: function() {
        var overlay = document.getElementById('modalOverlay');
        if (!overlay) return;
        
        overlay.classList.remove('active');
        
        setTimeout(function() {
            overlay.style.display = 'none';
            document.body.style.overflow = '';
        }, 300);
    },

    init: function() {
        var self = this;
        var overlay = document.getElementById('modalOverlay');
        var closeBtn = document.getElementById('modalClose');
        
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                self.close();
            });
        }
        
        if (overlay) {
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) {
                    self.close();
                }
            });
        }
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && overlay && overlay.style.display !== 'none') {
                self.close();
            }
        });
        
        var shareBtn = document.getElementById('modalShare');
        if (shareBtn) {
            shareBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                var url = document.getElementById('modalVisit').href;
                navigator.clipboard.writeText(url).then(function() {
                    shareBtn.textContent = '✓';
                    setTimeout(function() {
                        shareBtn.textContent = '🔗';
                    }, 2000);
                });
            });
        }
    }
};

// ==================== THEME MANAGER ====================
const ThemeManager = {
    init: function() {
        var toggle = document.getElementById('themeToggle');
        if (!toggle) return;
        
        var savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        toggle.addEventListener('click', function() {
            var current = document.documentElement.getAttribute('data-theme');
            var next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
        });
    }
};

// ==================== SIDEBAR MANAGER ====================
const SidebarManager = {
    init: function() {
        var toggle = document.getElementById('sidebarToggle');
        var sidebar = document.getElementById('sidebar');
        if (!toggle || !sidebar) return;
        
        var overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        document.body.appendChild(overlay);
        
        toggle.addEventListener('click', function() {
            sidebar.classList.toggle('active');
            overlay.classList.toggle('active');
        });
        
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('active');
            overlay.classList.remove('active');
        });
        
        var categoryTriggers = document.querySelectorAll('.category-trigger');
        
        categoryTriggers.forEach(function(trigger) {
            trigger.addEventListener('click', function(e) {
                e.stopPropagation();
                
                if (isLandingPage) {
                    var categoryId = trigger.dataset.categoryId;
                    window.location.href = 'browse.html#category-' + categoryId;
                    return;
                }
                
                var categoryId = trigger.dataset.categoryId;
                if (!categoryId) return;
                
                // Collapse all other category triggers before setting hash
                // (handleHashChange will re-expand the correct one)
                categoryTriggers.forEach(function(t) {
                    t.setAttribute('aria-expanded', 'false');
                    var list = document.getElementById(t.getAttribute('aria-controls'));
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
        
        var subcategoryLinks = document.querySelectorAll('.subcategory-link');
        
        subcategoryLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                var category = link.dataset.category;
                
                if (isLandingPage) {
                    window.location.href = 'browse.html#category-' + category;
                    return;
                }
                
                var dropdown = document.getElementById('categoryFilter');
                if (category && dropdown) {
                    dropdown.value = category;
                    
                    var categoryValueEl = document.getElementById('filterValue1');
                    if (categoryValueEl) {
                        var option = Array.from(dropdown.options).find(function(opt) {
                            return opt.value === category;
                        });
                        
                        if (option) {
                            TagManager.setCategoryDisplay(category); // ✅ passes the ID already in scope
                        }
                    }
                    
                    window.location.hash = 'category-' + category;
                    filterCards();
                }
                
                document.querySelectorAll('.subcategory-link').forEach(function(l) {
                    l.classList.remove('active');
                });
                link.classList.add('active');
                
                document.querySelectorAll('.category-trigger').forEach(function(t) {
                    t.classList.remove('active');
                });
                
                if (window.innerWidth <= 1023) {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                }
            });
        });
    }
};

// ==================== CARD MANAGER ====================
const CardManager = {
    init: function() {
        document.querySelectorAll('.link-card').forEach(function(card) {
            card.addEventListener('click', function(e) {
                e.stopPropagation();
                ModalManager.open(card);
            });
            
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    ModalManager.open(card);
                }
            });
        });
        
        document.querySelectorAll('.card-tags .tag').forEach(function(tag) {
            tag.addEventListener('click', function(e) {
                e.stopPropagation();
                var tagName = tag.dataset.tag || tag.textContent.trim();
                
                if (isLandingPage) {
                    window.location.href = 'browse.html#tag-' + TagManager.slugify(tagName);
                    return;
                }
                
                TagManager.setActiveTag(tagName, true);
                filterCards();
            });
        });
    }
};

// ==================== ENTRY ANIMATOR ====================
// Scroll-triggered, filter-replayable entry animation for .link-card elements.
// JS only adds/removes the `.link-card--enter` class; the body
// data-entry-animation attribute selects which keyframe the CSS plays.
var EntryAnimator = {
  init: function() {
    var mode = (document.body.getAttribute('data-entry-animation') || 'fade-slide-up');
    // Ensure the `.js` class is present even if the inline <head> script was
    // blocked (e.g. by a CSP). main.js is an external script and runs reliably.
    document.documentElement.classList.add('js');

    if (mode === 'none') return;

    var cards = document.querySelectorAll('.link-card');
    if (!('IntersectionObserver' in window) || !cards.length) {
      // Fallback: animate all immediately so nothing stays hidden.
      cards.forEach(function(c){ c.classList.add('link-card--enter'); });
      return;
    }

    var vh = window.innerHeight;
    var io = new IntersectionObserver(function(entries, obs) {
      entries.forEach(function(entry) {
        // Reveal if the card is in or above the viewport. Using the rect
        // (not just `isIntersecting`) catches cards scrolled past very fast:
        // the browser may coalesce the IO callback to the final "not
        // intersecting" state after the card has already gone past the
        // threshold, which would otherwise leave it stuck invisible.
        if (entry.boundingClientRect.top < vh) {
          entry.target.classList.add('link-card--enter');
          obs.unobserve(entry.target); // animate once per card instance
        }
      });
    }, { threshold: 0.05, rootMargin: "0px 0px -40px 0px" });

    cards.forEach(function(c){ io.observe(c); });

    // Safety net for fast / coalesced scrolls: a throttled scroll listener
    // reveals any card whose top has entered (or passed) the viewport but
    // which the IO may have missed. Guarantees no card stays hidden.
    var scrollTicking = false;
    function revealOnScroll() {
      if (scrollTicking) return;
      scrollTicking = true;
      requestAnimationFrame(function() {
        scrollTicking = false;
        var h = window.innerHeight;
        for (var i = 0; i < cards.length; i++) {
          var c = cards[i];
          if (c.classList.contains('link-card--enter')) continue;
          if (c.getBoundingClientRect().top < h) {
            c.classList.add('link-card--enter');
          }
        }
      });
    }
    window.addEventListener('scroll', revealOnScroll, { passive: true });
  }
};

// ==================== FILTER MANAGER ====================
const FilterManager = {
  dropdowns: {},

  init: function() {

    var self = this;

    var categoryTrigger  = document.getElementById('categoryTrigger');
    var categoryFilter   = document.getElementById('categoryFilter');
    var categoryDropdown = document.getElementById('categoryDropdown');

    var sortTrigger  = document.getElementById('sortTrigger');
    var sortFilter   = document.getElementById('sortFilter');
    var sortDropdown = document.getElementById('sortDropdown');

    if (categoryTrigger && categoryFilter && categoryDropdown) {
      this.bindDropdown(categoryTrigger, categoryFilter, categoryDropdown, 'category');
    }
    if (sortTrigger && sortFilter && sortDropdown) {
      this.bindDropdown(sortTrigger, sortFilter, sortDropdown, 'sort');
    }

    window.addEventListener('clearFilters', function() {
      TagManager.clearActiveSearch();
      TagManager.clearActiveTag();
      if (categoryFilter) categoryFilter.value = '';
      self.syncSelection('category', '');
      filterCards();
    });
  },

  bindDropdown: function(trigger, nativeSelect, dropdown, type) {
    var self = this;

    // Attach click handlers to pre-rendered option buttons
    dropdown.querySelectorAll('.filter-dropdown-option').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
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
    trigger.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      self.toggleDropdown(type);
    });

    document.addEventListener('click', function(e) {
      if (!trigger.contains(e.target)) {
        self.closeDropdown(type);
      }
    });

    this.dropdowns[type] = {
      trigger:  trigger,
      dropdown: dropdown,
      native:   nativeSelect,
    };
  },

  // Mark the button matching `value` as selected, clear others
  syncSelection: function(type, value) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    entry.dropdown.querySelectorAll('.filter-dropdown-option').forEach(function(btn) {
      btn.classList.toggle('selected', btn.dataset.value === value);
    });
  },

  toggleDropdown: function(type) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    var isActive = entry.dropdown.classList.contains('active');
    this.closeAllDropdowns();
    if (!isActive) {
      entry.dropdown.classList.add('active');
      entry.trigger.setAttribute('aria-expanded', 'true');
    }
  },

  closeDropdown: function(type) {
    var entry = this.dropdowns[type];
    if (!entry) return;
    entry.dropdown.classList.remove('active');
    entry.trigger.setAttribute('aria-expanded', 'false');
  },

  closeAllDropdowns: function() {
    var self = this;
    Object.keys(this.dropdowns).forEach(function(type) {
      self.closeDropdown(type);
    });
  },
};


// ==================== FILTER CARDS FUNCTION ====================
function filterCards() {

    if (isLandingPage) {
        return;
    }

    var categoryFilter = document.getElementById('categoryFilter');
    var cards = document.querySelectorAll('.link-card');
    var noResults = document.getElementById('noResults');
    var resultsCount = document.getElementById('resultsCount');

    var activeTag = TagManager.getActiveTag();
    var activeSearch = TagManager.getActiveSearch();
    var category = categoryFilter ? categoryFilter.value : '';

    var matchingCategories = category ? (window.CATEGORY_MAP[category] || [category]) : [];

    var visibleCount = 0;
    // On a filter change, only re-animate cards that are currently within the
    // viewport. Cards below the fold must be left WITHOUT `.link-card--enter`
    // (hidden) so the IntersectionObserver reveals them when the user scrolls
    // to them. Re-adding the class to below-fold cards would make them animate
    // on filter instead of on scroll (and they'd already have the class, so
    // scrolling would do nothing).
    var mode = document.body.getAttribute('data-entry-animation') || 'fade-slide-up';
    var reanimate = mode !== 'none';
    var reshownCards = [];

    cards.forEach(function(card) { 
        var title = card.dataset.title ? card.dataset.title.toLowerCase() : '';
        var summary = card.dataset.summary ? card.dataset.summary.toLowerCase() : '';
        var tags = card.dataset.tags ? card.dataset.tags.toLowerCase() : '';
        var cardCategory = card.dataset.category || '';
        var cardTagsArray = card.dataset.tags ? card.dataset.tags.split(',').map(function(t) { return t.trim().toLowerCase(); }) : [];
        
        var matchesFilter = true;
        
        if (activeSearch) {
            var searchLower = activeSearch.toLowerCase();
            matchesFilter = title.includes(searchLower) || 
                           summary.includes(searchLower) || 
                           tags.includes(searchLower);
        
        } else if (activeTag) {
            matchesFilter = cardTagsArray.indexOf(activeTag) !== -1;
        
        } else if (category) {
            matchesFilter = matchingCategories.indexOf(cardCategory) !== -1;
        }
        
        if (matchesFilter) {
            card.style.display = '';
            if (reanimate) {
                var rect = card.getBoundingClientRect();
                var inView = rect.top < window.innerHeight && rect.bottom > 0;
                // Always drop the class so the reveal can replay...
                card.classList.remove('link-card--enter');
                if (inView) {
                    // ...but only re-add it now for cards the user can see.
                    reshownCards.push(card);
                }
                // Below-fold cards stay without the class (hidden) and are
                // revealed by the IntersectionObserver as they scroll into view.
            }
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });

    // Force ONE reflow, then re-add .link-card--enter to the in-viewport
    // re-shown cards so the entry animation replays once for the visible set.
    if (reshownCards.length) {
        void document.body.offsetWidth; // force reflow so the animation can replay
        reshownCards.forEach(function(card) {
            card.classList.add('link-card--enter');
        });
    }

    if (noResults) {
        noResults.style.display = visibleCount === 0 ? 'block' : 'none';
    }

    if (resultsCount) {
        resultsCount.textContent = visibleCount + ' item' + (visibleCount !== 1 ? 's' : '');
    }
}

// ==================== SORT CARDS FUNCTION ====================
function sortCards() {
    var sortFilter = document.getElementById('sortFilter');
    var grid = document.getElementById('linksGrid');
    if (!sortFilter || !grid) return;
    
    var sortValue = sortFilter.value;
    var cards = Array.from(grid.querySelectorAll('.link-card'));

    cards.sort(function(a, b) {
        if (sortValue === 'newest') {
            return new Date(b.dataset.created || 0) - new Date(a.dataset.created || 0);
        } else if (sortValue === 'oldest') {
            return new Date(a.dataset.created || 0) - new Date(b.dataset.created || 0);
        } else if (sortValue === 'alphabetical') {
            return a.dataset.title.localeCompare(b.dataset.title);
        }
        return 0;
    });

    cards.forEach(function(card) {
        grid.appendChild(card);
    });
}

// ==================== HANDLE HASH CHANGE ====================
function handleHashChange() {
    if (isLandingPage) {
        return;
    }
    
    var hash = window.location.hash;

    if (hash.startsWith('#search-')) {
        var searchTerm = decodeURIComponent(hash.replace('#search-', ''));
        
        TagManager.setActiveSearch(searchTerm, false);
        // REMOVED: TagManager.clearActiveTag(); - setActiveSearch already clears activeTag
        
        var categoryFilter = document.getElementById('categoryFilter');
        if (categoryFilter) {
            categoryFilter.value = '';
        }
        
        document.querySelectorAll('.category-trigger, .subcategory-link').forEach(function(el) {
            el.classList.remove('active');
        });
        
        filterCards();
        return;
    }

    if (hash.startsWith('#category-')) {
        var category = hash.replace('#category-', '');
        var categoryFilter = document.getElementById('categoryFilter');
        
        if (categoryFilter) {
            categoryFilter.value = category;
            
            TagManager.clearActiveTag();
            TagManager.clearActiveSearch();
            TagManager.updateFilterHeader();
            FilterManager.syncSelection('category', category);

            var foundSubcategory = false;
            document.querySelectorAll('.subcategory-link').forEach(function(link) {
                link.classList.remove('active');
                if (link.dataset.category === category) {
                    link.classList.add('active');
                    foundSubcategory = true;
                    
                    var parentList = link.closest('.subcategory-list');
                    if (parentList) {
                        parentList.classList.add('expanded');
                        var trigger = document.querySelector(
                            '[aria-controls="' + parentList.id + '"]'
                        );
                        if (trigger) {
                            trigger.setAttribute('aria-expanded', 'true');
                        }
                    }
                }
            });
            
            if (!foundSubcategory) {
                document.querySelectorAll('.category-trigger').forEach(function(trigger) {
                    trigger.classList.remove('active');
                    if (trigger.dataset.categoryId === category) {
                        trigger.classList.add('active');
                        trigger.setAttribute('aria-expanded', 'true');
                        var subcategoryList = document.getElementById(
                            trigger.getAttribute('aria-controls')
                        );
                        if (subcategoryList) {
                            subcategoryList.classList.add('expanded');
                        }
                    }
                });
            }
            
            filterCards();
            return;
        }
    }

    if (hash.startsWith('#tag-')) {
        var tag = hash.replace('#tag-', '');
        
        TagManager.setActiveTag(tag, false);
        // REMOVED: TagManager.clearActiveSearch(); - setActiveTag already clears activeSearch
        
        var categoryFilter = document.getElementById('categoryFilter');
        if (categoryFilter) {
            categoryFilter.value = '';
        }
        
        document.querySelectorAll('.category-trigger, .subcategory-link').forEach(function(el) {
            el.classList.remove('active');
        });
        
        filterCards();
        return;
    }

    if (!hash || hash === '') {
        TagManager.activeTag = null;
        TagManager.activeSearch = null;
        TagManager.updateFilterHeader();
    }
}

// ==================== UPDATE RESULTS COUNT ====================
function updateResultsCount() {
    var countEl = document.getElementById('resultsCount');
    if (!countEl) return;
    
    var visibleCount = document.querySelectorAll('.link-card[style=""]').length;
    countEl.textContent = visibleCount + ' item' + (visibleCount !== 1 ? 's' : '');
}

// ==================== DOM CONTENT LOADED ====================
document.addEventListener('DOMContentLoaded', function() {
   
    TagManager.init();

    ThemeManager.init();
    SidebarManager.init();
    CardManager.init();
    EntryAnimator.init();

    if (isBrowsePage) {
        FilterManager.init();
        handleHashChange();
        
        window.addEventListener('hashchange', function() {
            handleHashChange();
        });
        
        // updateResultsCount();
    }

    ModalManager.init();
});