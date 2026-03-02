/**
 * Main JavaScript for Static Link Aggregation Site
 * Complete File - Landing Page + Browse Page Support (FIXED v5)
 */

// ==================== PAGE DETECTION ====================
const isLandingPage = !window.location.pathname.includes('browse.html');
const isBrowsePage = window.location.pathname.includes('browse.html');

console.log('📄 Page:', isLandingPage ? 'Landing (index.html)' : 'Browse (browse.html)');

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
    isInitialized: false,
    
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
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Showing';
            filterValue1.style.display = 'inline';
            filterValue1.textContent = '#' + this.activeTag;
            if (filterText2) filterText2.style.display = 'inline';
            
            if (categoryTrigger) {
                categoryTrigger.style.display = 'inline-flex';
                categoryTrigger.style.pointerEvents = 'none';
                categoryTrigger.style.opacity = '1';
            }
            if (filterIcon) filterIcon.style.display = 'none';
            
        } else {
            filterText1.style.display = 'inline';
            filterText1.textContent = 'Showing';
            filterValue1.style.display = 'inline';
            if (filterText2) filterText2.style.display = 'inline';
            
            if (categoryTrigger) {
                categoryTrigger.style.display = 'inline-flex';
                categoryTrigger.style.pointerEvents = 'auto';
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
        
        searchInput.addEventListener('input', this.debounce(function() {
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
                        item.addEventListener('click', function(e) {
                            e.stopPropagation();
                            searchInput.value = '#' + tag;
                            suggestionsBox.classList.remove('active');
                            
                            if (isLandingPage) {
                                window.location.href = 'browse.html#tag-' + TagManager.slugify(tag);
                            } else {
                                TagManager.setActiveTag(tag);
                                filterCards();
                            }
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
        }, 300));
        
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
        
        console.log('📦 Modal opened for:', card.dataset.title);
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

// ==================== SIDEBAR MANAGER (ACCORDION - SINGLE HANDLER) ====================
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
        
        // Category triggers - accordion behavior (browse page only)
        var categoryTriggers = document.querySelectorAll('.category-trigger');
        
        categoryTriggers.forEach(function(trigger) {
            trigger.addEventListener('click', function(e) {
                e.stopPropagation();
                
                // If on landing page, redirect to browse.html
                if (isLandingPage) {
                    var categoryId = trigger.dataset.categoryId;
                    window.location.href = 'browse.html#category-' + categoryId;
                    return;
                }
                
                // Accordion: collapse all, then expand clicked if it wasn't expanded
                var isExpanded = trigger.getAttribute('aria-expanded') === 'true';
                var subcategoryList = document.getElementById(trigger.getAttribute('aria-controls'));
                
                // Collapse ALL categories
                categoryTriggers.forEach(function(t) {
                    t.setAttribute('aria-expanded', 'false');
                    var list = document.getElementById(t.getAttribute('aria-controls'));
                    if (list) {
                        list.classList.remove('expanded');
                    }
                });
                
                // Expand clicked if it wasn't already
                if (!isExpanded && subcategoryList) {
                    trigger.setAttribute('aria-expanded', 'true');
                    subcategoryList.classList.add('expanded');
                }
            });
        });
        
        // Subcategory links
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
                
                // Update filter
                var dropdown = document.getElementById('categoryFilter');
                if (category && dropdown) {
                    dropdown.value = category;
                    
                    var categoryValueEl = document.getElementById('filterValue1');
                    if (categoryValueEl) {
                        var option = Array.from(dropdown.options).find(function(opt) {
                            return opt.value === category;
                        });
                        
                        if (option) {
                            categoryValueEl.textContent = option.textContent;
                            TagManager.setCategoryDisplay(option.textContent);
                        }
                    }
                    
                    window.location.hash = 'category-' + category;
                    filterCards();
                }
                
                // Update sidebar active state
                document.querySelectorAll('.subcategory-link').forEach(function(l) {
                    l.classList.remove('active');
                });
                link.classList.add('active');
                
                document.querySelectorAll('.category-trigger').forEach(function(t) {
                    t.classList.remove('active');
                });
                
                // Close mobile sidebar
                var sidebar = document.getElementById('sidebar');
                var overlay = document.querySelector('.sidebar-overlay');
                if (window.innerWidth <= 1023) {
                    sidebar.classList.remove('active');
                    overlay.classList.remove('active');
                }
            });
        });
    }
};

// ==================== CARD MANAGER (Works on BOTH pages) ====================
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

// ==================== FILTER MANAGER (Browse page only) ====================
const FilterManager = {
    dropdowns: {},
    
    init: function() {
        var self = this;
        
        var categoryTrigger = document.getElementById('categoryTrigger');
        var categoryFilter = document.getElementById('categoryFilter');
        var categoryValue = document.getElementById('filterValue1');
        
        var sortTrigger = document.getElementById('sortTrigger');
        var sortFilter = document.getElementById('sortFilter');
        var sortValue = document.getElementById('sortValue');
        
        var searchInput = document.getElementById('searchInput');
        
        console.log('🔧 FilterManager elements:', {
            categoryTrigger: !!categoryTrigger,
            categoryFilter: !!categoryFilter,
            categoryValue: !!categoryValue,
            sortTrigger: !!sortTrigger,
            sortFilter: !!sortFilter,
            sortValue: !!sortValue,
            searchInput: !!searchInput
        });
        
        if (categoryTrigger && categoryFilter && categoryValue) {
            this.createDropdown(categoryTrigger, categoryFilter, categoryValue, 'category');
        }
        
        if (sortTrigger && sortFilter && sortValue) {
            this.createDropdown(sortTrigger, sortFilter, sortValue, 'sort');
        }
        
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(function() {
                var value = searchInput.value.trim();
                
                if (isLandingPage && value.length > 0) {
                    if (value.startsWith('#')) {
                        var tag = value.substring(1).trim();
                        window.location.href = 'browse.html#tag-' + TagManager.slugify(tag);
                    } else {
                        window.location.href = 'browse.html#search-' + encodeURIComponent(value);
                    }
                    return;
                }
                
                if (value.startsWith('#')) {
                    var tag = value.substring(1).trim();
                    TagManager.setActiveTag(tag, false);
                } else {
                    TagManager.clearActiveTag();
                }
                
                filterCards();
            }, 300));
            
            searchInput.addEventListener('keydown', function(e) {
                var value = searchInput.value.trim();
                if (e.key === 'Enter') {
                    if (isLandingPage && value.length > 0) {
                        if (value.startsWith('#')) {
                            var tag = value.substring(1).trim();
                            window.location.href = 'browse.html#tag-' + TagManager.slugify(tag);
                        } else {
                            window.location.href = 'browse.html#search-' + encodeURIComponent(value);
                        }
                        return;
                    }
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
        
        // NOTE: Category triggers are handled by SidebarManager (no duplicate handlers)
        // NOTE: Subcategory links are handled by SidebarManager (no duplicate handlers)
    },
    
    createDropdown: function(trigger, nativeSelect, valueDisplay, type) {
        var self = this;
        var dropdown = document.createElement('div');
        dropdown.className = 'filter-dropdown';
        dropdown.id = type + 'Dropdown';
        
        Array.from(nativeSelect.options).forEach(function(option) {
            var btn = document.createElement('button');
            btn.className = 'filter-dropdown-option';
            btn.type = 'button';
            btn.textContent = option.textContent;
            btn.dataset.value = option.value;
            
            if (option.value === nativeSelect.value) {
                btn.classList.add('selected');
            }
            
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('🖱️ Dropdown option clicked:', option.textContent);
                
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
            e.preventDefault();
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
    if (isLandingPage) {
        return;
    }
    
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
    if (isLandingPage) {
        return;
    }
    
    var hash = window.location.hash;
    
    if (hash.startsWith('#category-')) {
        var category = hash.replace('#category-', '');
        var categoryFilter = document.getElementById('categoryFilter');
        
        if (categoryFilter) {
            categoryFilter.value = category;
            
            TagManager.clearActiveTag();
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
    SidebarManager.init();  // Handles sidebar accordion (single handler)
    
    CardManager.init();
    
    if (isBrowsePage) {
        FilterManager.init();  // Handles filter dropdowns only (no sidebar handlers)
    }
    
    ModalManager.init();
    
    if (isBrowsePage) {
        handleHashChange();
        
        window.addEventListener('hashchange', function() {
            handleHashChange();
        });
        
        updateResultsCount();
    }
    
    console.log('✅ Initialization complete');
    console.log('📄 Page type:', isLandingPage ? 'Landing' : 'Browse');
});