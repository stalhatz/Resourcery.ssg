/**
 * Main JavaScript for Static Link Aggregation Site
 * Complete File - Simplified Filter Header (Tag OR Category, not both)
 */

// ==================== CATEGORY HIERARCHY ====================
const CategoryHierarchy = {
    map: {},
    
    init: function(config) {
        var categories = config.navigation?.categories || [];
        var self = this;
        
        categories.forEach(function(cat) {
            self.map[cat.id] = cat.children ? cat.children.map(function(c) { return c.id; }) : [];
            
            if (cat.children) {
                cat.children.forEach(function(child) {
                    self.map[child.id] = [child.id];
                    self.map[child.id + '_parent'] = cat.id;
                });
            }
        });
    },
    
    getMatchingCategories: function(categoryId) {
        var children = this.map[categoryId] || [];
        if (children.length > 0) {
            return children.concat([categoryId]);
        } else {
            return [categoryId];
        }
    }
};

// ==================== TAG MANAGER ====================
const TagManager = {
    activeTag: null,
    allTags: [],
    
    init: function(linksData) {
        var tagSet = {};
        if (linksData && linksData.links) {
            linksData.links.forEach(function(link) {
                if (link.tags && Array.isArray(link.tags)) {
                    link.tags.forEach(function(tag) {
                        if (tag && tag.trim()) {
                            tagSet[tag.trim().toLowerCase()] = tag.trim();
                        }
                    });
                }
            });
        }
        
        this.allTags = Object.values(tagSet).sort();
        console.log('🏷️ TagManager initialized with', this.allTags.length, 'tags');
        
        this.setupSearchSuggestions();
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
        
        console.log('🏷️ Active tag:', this.activeTag);
    },
    
    setCategoryDisplay: function(categoryName) {
        if (this.isUpdating) return;
        
        var categoryFilter = document.getElementById('categoryFilter');
        if (categoryFilter) {
            categoryFilter.value = categoryName || '';
        }
        this.updateFilterHeader();
    },
    
    updateFilterHeader: function() {
        var filterText1 = document.getElementById('filterText1');
        var filterValue1 = document.getElementById('filterValue1');
        var filterText2 = document.getElementById('filterText2');
        var categoryTrigger = document.getElementById('categoryTrigger');
        var filterIcon = categoryTrigger ? categoryTrigger.querySelector('.filter-icon') : null;
        
        if (!filterText1 || !filterValue1) {
            console.warn('⚠️ Filter header elements not found');
            return;
        }
        
        if (this.activeTag) {
            // TAG MODE: "Showing #tagname by..."
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Showing';
            filterValue1.style.display = 'inline';
            filterValue1.textContent = '#' + this.activeTag;
            if (filterText2) filterText2.style.display = 'inline';
            
            // Keep button visible but hide dropdown arrow (not clickable for tags)
            if (categoryTrigger) {
                categoryTrigger.style.display = 'inline-flex';
                categoryTrigger.style.pointerEvents = 'none';  // Disable clicks
                categoryTrigger.style.opacity = '1';
            }
            if (filterIcon) filterIcon.style.display = 'none';
            
        } else {
            // CATEGORY MODE: "Showing CategoryName by..."
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Showing';
            filterValue1.style.display = 'inline';
            if (filterText2) filterText2.style.display = 'inline';
            
            // Show button with dropdown arrow (clickable for categories)
            if (categoryTrigger) {
                categoryTrigger.style.display = 'inline-flex';
                categoryTrigger.style.pointerEvents = 'auto';  // Enable clicks
                categoryTrigger.style.opacity = '1';
            }
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
        
        console.log('📝 Filter header:', this.activeTag ? '#' + this.activeTag : filterValue1.textContent);
    },
    
    getActiveTag: function() {
        return this.activeTag;
    },
    
    clearActiveTag: function() {
        this.setActiveTag(null, true);
    },
    
    clearSearchInput: function() {
        var searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = '';
        }
    },
    
    setupSearchSuggestions: function() {
        var searchInput = document.getElementById('searchInput');
        if (!searchInput) return;
        
        var suggestionsBox = document.createElement('div');
        suggestionsBox.className = 'search-suggestions';
        suggestionsBox.id = 'searchSuggestions';
        searchInput.parentNode.style.position = 'relative';
        searchInput.parentNode.appendChild(suggestionsBox);
        
        searchInput.addEventListener('input', function() {
            var value = searchInput.value.trim();
            
            if (value.startsWith('#')) {
                var query = value.substring(1).toLowerCase();
                var matches = TagManager.allTags.filter(function(tag) {
                    return tag.toLowerCase().includes(query);
                }).slice(0, 5);
                
                if (matches.length > 0) {
                    suggestionsBox.innerHTML = '';
                    matches.forEach(function(tag) {
                        var item = document.createElement('div');
                        item.className = 'suggestion-item';
                        item.textContent = '#' + tag;
                        item.addEventListener('click', function() {
                            searchInput.value = '#' + tag;
                            suggestionsBox.classList.remove('active');
                            TagManager.setActiveTag(tag);
                            filterCards();
                        });
                        suggestionsBox.appendChild(item);
                    });
                    suggestionsBox.classList.add('active');
                } else {
                    suggestionsBox.classList.remove('active');
                }
            } else {
                suggestionsBox.classList.remove('active');
            }
        });
        
        document.addEventListener('click', function(e) {
            if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
                suggestionsBox.classList.remove('active');
            }
        });
        
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                suggestionsBox.classList.remove('active');
            }
        });
    }
};

// ==================== MODAL MANAGER ====================
const ModalManager = {
    open: function(card) {
        var overlay = document.getElementById('modalOverlay');
        var modal = document.getElementById('modal');
        
        if (!overlay || !modal) return;
        
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
                        TagManager.setActiveTag(tag.trim());
                        ModalManager.close();
                        filterCards();
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
            shareBtn.addEventListener('click', function() {
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

// ==================== SIDEBAR MANAGER (ACCORDION) ====================
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
            trigger.addEventListener('click', function() {
                var isExpanded = trigger.getAttribute('aria-expanded') === 'true';
                var subcategoryList = document.getElementById(
                    trigger.getAttribute('aria-controls')
                );
                
                categoryTriggers.forEach(function(t) {
                    t.setAttribute('aria-expanded', 'false');
                    var list = document.getElementById(t.getAttribute('aria-controls'));
                    if (list) {
                        list.classList.remove('expanded');
                    }
                });
                
                if (!isExpanded) {
                    trigger.setAttribute('aria-expanded', 'true');
                    if (subcategoryList) {
                        subcategoryList.classList.add('expanded');
                    }
                }
            });
        });
    }
};

// ==================== FILTER MANAGER ====================
const FilterManager = {
    dropdowns: {},
    
    init: function() {
        var self = this;
        
        var categoryTrigger = document.getElementById('categoryTrigger');
        var categoryFilter = document.getElementById('categoryFilter');
        var categoryValue = document.getElementById('categoryValue');
        
        var sortTrigger = document.getElementById('sortTrigger');
        var sortFilter = document.getElementById('sortFilter');
        var sortValue = document.getElementById('sortValue');
        
        var searchInput = document.getElementById('searchInput');
        
        if (categoryTrigger && categoryFilter) {
            this.createDropdown(categoryTrigger, categoryFilter, categoryValue, 'category');
        }
        
        if (sortTrigger && sortFilter) {
            this.createDropdown(sortTrigger, sortFilter, sortValue, 'sort');
        }
        
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(function() {
                var value = searchInput.value.trim();
                
                if (value.startsWith('#')) {
                    var tag = value.substring(1).trim();
                    TagManager.setActiveTag(tag, false);
                } else {
                    TagManager.clearActiveTag();
                }
                
                filterCards();
            }, 300));
            
            searchInput.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    var value = searchInput.value.trim();
                    if (value.startsWith('#')) {
                        TagManager.setActiveTag(value.substring(1).trim(), true);
                    }
                    searchInput.blur();
                }
                if (e.key === 'Escape' && searchInput.value === '') {
                    TagManager.clearActiveTag();
                    filterCards();
                }
            });
        }
        
        // Sidebar category triggers
        var categoryTriggers = document.querySelectorAll('.category-trigger');
        
        categoryTriggers.forEach(function(trigger) {
            trigger.addEventListener('click', function() {
                var categoryId = trigger.dataset.categoryId;
                
                TagManager.clearActiveTag();
                TagManager.clearSearchInput();
                
                var dropdown = document.getElementById('categoryFilter');
                var categoryValueEl = document.getElementById('categoryValue');
                
                if (categoryId && dropdown) {
                    dropdown.value = categoryId;
                    
                    if (categoryValueEl) {
                        var option = Array.from(dropdown.options).find(function(opt) {
                            return opt.value === categoryId;
                        });
                        
                        if (option) {
                            categoryValueEl.textContent = option.textContent;
                            TagManager.setCategoryDisplay(option.textContent);
                        } else {
                            var nameEl = trigger.querySelector('.category-name');
                            if (nameEl) {
                                categoryValueEl.textContent = nameEl.textContent.trim();
                                TagManager.setCategoryDisplay(nameEl.textContent.trim());
                            }
                        }
                    }
                    
                    window.location.hash = 'category-' + categoryId;
                    filterCards();
                }
                
                document.querySelectorAll('.category-trigger').forEach(function(t) {
                    t.classList.remove('active');
                });
                trigger.classList.add('active');
                
                document.querySelectorAll('.subcategory-link').forEach(function(l) {
                    l.classList.remove('active');
                });
            });
        });
        
        // Sidebar subcategory links
        var subcategoryLinks = document.querySelectorAll('.subcategory-link');
        
        subcategoryLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var category = link.dataset.category;
                
                TagManager.clearActiveTag();
                TagManager.clearSearchInput();
                
                var dropdown = document.getElementById('categoryFilter');
                if (category && dropdown) {
                    dropdown.value = category;
                    
                    var categoryValueEl = document.getElementById('categoryValue');
                    if (categoryValueEl) {
                        var option = Array.from(dropdown.options).find(function(opt) {
                            return opt.value === category;
                        });
                        
                        if (option) {
                            categoryValueEl.textContent = option.textContent;
                            TagManager.setCategoryDisplay(option.textContent);
                        } else {
                            var nameEl = link.querySelector('.subcategory-name');
                            if (nameEl) {
                                categoryValueEl.textContent = nameEl.textContent.trim();
                                TagManager.setCategoryDisplay(nameEl.textContent.trim());
                            }
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
                
                var sidebar = document.getElementById('sidebar');
                var overlay = document.querySelector('.sidebar-overlay');
                if (window.innerWidth <= 1023) {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                }
            });
        });
        
        // Card tag clicks
        document.querySelectorAll('.card-tags .tag, .modal-tag').forEach(function(tag) {
            tag.addEventListener('click', function(e) {
                e.stopPropagation();
                var tagName = tag.dataset.tag || tag.textContent.trim();
                TagManager.setActiveTag(tagName, true);
                filterCards();
            });
        });
        
        // Card click handlers
        document.querySelectorAll('.link-card').forEach(function(card) {
            card.addEventListener('click', function() {
                ModalManager.open(card);
            });
            
            card.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    ModalManager.open(card);
                }
            });
        });
    },
    
    createDropdown: function(trigger, nativeSelect, valueDisplay, type) {
        var self = this;
        var dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        dropdown.id = type + 'Dropdown';
        
        Array.from(nativeSelect.options).forEach(function(option) {
            var btn = document.createElement('button');
            btn.className = 'filter-dropdown-option';
            btn.textContent = option.textContent;
            btn.dataset.value = option.value;
            
            if (option.value === nativeSelect.value) {
                btn.classList.add('selected');
            }
            
            btn.addEventListener('click', function() {
                nativeSelect.value = option.value;
                valueDisplay.textContent = option.textContent;
                
                dropdown.querySelectorAll('.filter-dropdown-option').forEach(function(opt) {
                    opt.classList.remove('selected');
                });
                btn.classList.add('selected');
                
                self.closeAllDropdowns();
                
                if (type === 'category') {
                    TagManager.clearActiveTag();
                    TagManager.clearSearchInput();
                    TagManager.setCategoryDisplay(option.textContent);
                    
                    if (option.value) {
                        window.location.hash = 'category-' + option.value;
                    } else {
                        history.pushState('', '', window.location.pathname);
                    }
                }
                
                filterCards();
            });
            
            dropdown.appendChild(btn);
        });
        
        trigger.style.position = 'relative';
        trigger.appendChild(dropdown);
        
        trigger.addEventListener('click', function(e) {
            e.stopPropagation();
            self.toggleDropdown(type);
        });
        
        this.dropdowns[type] = {
            trigger: trigger,
            dropdown: dropdown,
            native: nativeSelect,
            display: valueDisplay
        };
        
        document.addEventListener('click', function(e) {
            if (!trigger.contains(e.target)) {
                self.closeDropdown(type);
            }
        });
    },
    
    toggleDropdown: function(type) {
        var dropdown = this.dropdowns[type];
        if (!dropdown) return;
        
        var isActive = dropdown.dropdown.classList.contains('active');
        this.closeAllDropdowns();
        
        if (!isActive) {
            dropdown.dropdown.classList.add('active');
            dropdown.trigger.classList.add('active');
        }
    },
    
    closeDropdown: function(type) {
        var dropdown = this.dropdowns[type];
        if (!dropdown) return;
        
        dropdown.dropdown.classList.remove('active');
        dropdown.trigger.classList.remove('active');
    },
    
    closeAllDropdowns: function() {
        var self = this;
        Object.keys(this.dropdowns).forEach(function(type) {
            self.closeDropdown(type);
        });
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

// ==================== FILTER CARDS FUNCTION ====================
function filterCards() {
    var searchInput = document.getElementById('searchInput');
    var categoryFilter = document.getElementById('categoryFilter');
    var cards = document.querySelectorAll('.link-card');
    var noResults = document.getElementById('noResults');
    var resultsCount = document.getElementById('resultsCount');
    
    var searchTerm = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var category = categoryFilter ? categoryFilter.value : '';
    var activeTag = TagManager.getActiveTag();
    
    var tagOnlySearch = searchTerm.startsWith('#');
    if (tagOnlySearch) {
        searchTerm = searchTerm.substring(1).trim();
    }
    
    var matchingCategories = CategoryHierarchy.getMatchingCategories(category);
    
    var visibleCount = 0;
    
    cards.forEach(function(card) {
        var title = card.dataset.title ? card.dataset.title.toLowerCase() : '';
        var summary = card.dataset.summary ? card.dataset.summary.toLowerCase() : '';
        var tags = card.dataset.tags ? card.dataset.tags.toLowerCase() : '';
        var cardCategory = card.dataset.category || '';
        var cardTagsArray = card.dataset.tags ? card.dataset.tags.split(',').map(function(t) { return t.trim().toLowerCase(); }) : [];
        
        var matchesTag = !activeTag || cardTagsArray.indexOf(activeTag) !== -1;
        
        var matchesSearch = true;
        if (searchTerm) {
            if (tagOnlySearch) {
                matchesSearch = tags.includes(searchTerm);
            } else {
                matchesSearch = title.includes(searchTerm) || 
                                summary.includes(searchTerm) || 
                                tags.includes(searchTerm);
            }
        }
        
        var matchesCategory = !category || matchingCategories.indexOf(cardCategory) !== -1;
        
        var matchesFilter = matchesSearch && matchesTag && (activeTag ? true : matchesCategory);
        
        if (matchesFilter) {
            card.style.display = '';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
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
    var hash = window.location.hash;
    
    if (hash.startsWith('#category-')) {
        var category = hash.replace('#category-', '');
        var categoryFilter = document.getElementById('categoryFilter');
        
        if (categoryFilter) {
            categoryFilter.value = category;
            
            // Clear tag state directly (NO hash write)
            TagManager.activeTag = null;
            TagManager.clearSearchInput();
            TagManager.updateFilterHeader();
            
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
        }
    }
    
    if (hash.startsWith('#tag-')) {
        var tag = hash.replace('#tag-', '');
        
        // Set state directly (NO hash write - don't call setActiveTag!)
        TagManager.activeTag = TagManager.slugify(tag);
        TagManager.clearSearchInput();
        TagManager.updateFilterHeader();
        
        var categoryFilter = document.getElementById('categoryFilter');
        if (categoryFilter) {
            categoryFilter.value = '';
        }
        
        document.querySelectorAll('.category-trigger, .subcategory-link').forEach(function(el) {
            el.classList.remove('active');
        });
        
        filterCards();
    }
    
    if (!hash || hash === '') {
        TagManager.activeTag = null;
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

// ==================== HANDLE HASH CHANGE EVENT ====================
function onHashChange() {
    console.log('🔔 hashchange event fired');
    handleHashChange();
}

// ==================== DOM CONTENT LOADED ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOMContentLoaded fired');
    
    if (window.APP_CONFIG) {
        CategoryHierarchy.init(window.APP_CONFIG);
    }
    
    if (window.LINKS_DATA) {
        TagManager.init(window.LINKS_DATA);
    }
    
    ThemeManager.init();
    SidebarManager.init();
    FilterManager.init();
    ModalManager.init();
    
    // REMOVED: TagManager.updateFilterHeader(); ← This was the problem

    handleHashChange();  // ← This calls updateFilterHeader() after reading hash
    
    

    window.addEventListener('hashchange', onHashChange);
    
    updateResultsCount();
    
    console.log('✅ Initialization complete');
});
