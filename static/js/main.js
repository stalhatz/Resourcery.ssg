/**
 * Main JavaScript for Static Link Aggregation Site
 * Complete File - Accordion Sidebar (Single Expand)
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
        
        // Accordion behavior: Only one category expanded at a time
        var categoryTriggers = document.querySelectorAll('.category-trigger');
        
        categoryTriggers.forEach(function(trigger) {
            trigger.addEventListener('click', function() {
                var isExpanded = trigger.getAttribute('aria-expanded') === 'true';
                var subcategoryList = document.getElementById(
                    trigger.getAttribute('aria-controls')
                );
                
                // Collapse ALL categories first
                categoryTriggers.forEach(function(t) {
                    t.setAttribute('aria-expanded', 'false');
                    var list = document.getElementById(t.getAttribute('aria-controls'));
                    if (list) {
                        list.classList.remove('expanded');
                    }
                });
                
                // If it wasn't expanded before, expand it now
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
        
        // Category dropdown
        var categoryTrigger = document.getElementById('categoryTrigger');
        var categoryFilter = document.getElementById('categoryFilter');
        var categoryValue = document.getElementById('categoryValue');
        
        // Sort dropdown
        var sortTrigger = document.getElementById('sortTrigger');
        var sortFilter = document.getElementById('sortFilter');
        var sortValue = document.getElementById('sortValue');
        
        // Search input
        var searchInput = document.getElementById('searchInput');
        
        // Initialize dropdowns
        if (categoryTrigger && categoryFilter) {
            this.createDropdown(categoryTrigger, categoryFilter, categoryValue, 'category');
        }
        
        if (sortTrigger && sortFilter) {
            this.createDropdown(sortTrigger, sortFilter, sortValue, 'sort');
        }
        
        // Initialize search
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce(function() {
                filterCards();
            }, 300));
        }
        
        // Sidebar category triggers
        var categoryTriggers = document.querySelectorAll('.category-trigger');
        
        categoryTriggers.forEach(function(trigger) {
            trigger.addEventListener('click', function() {
                var categoryId = trigger.dataset.categoryId;
                
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
                        } else {
                            var nameEl = trigger.querySelector('.category-name');
                            if (nameEl) {
                                categoryValueEl.textContent = nameEl.textContent.trim();
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
                        } else {
                            var nameEl = link.querySelector('.subcategory-name');
                            if (nameEl) {
                                categoryValueEl.textContent = nameEl.textContent.trim();
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
    
    var matchingCategories = CategoryHierarchy.getMatchingCategories(category);
    
    var visibleCount = 0;
    
    cards.forEach(function(card) {
        var title = card.dataset.title ? card.dataset.title.toLowerCase() : '';
        var summary = card.dataset.summary ? card.dataset.summary.toLowerCase() : '';
        var tags = card.dataset.tags ? card.dataset.tags.toLowerCase() : '';
        var cardCategory = card.dataset.category || '';
        
        var matchesSearch = !searchTerm || 
                            title.includes(searchTerm) || 
                            summary.includes(searchTerm) || 
                            tags.includes(searchTerm);
        
        var matchesCategory = !category || matchingCategories.indexOf(cardCategory) !== -1;
        
        if (matchesSearch && matchesCategory) {
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
        var categoryValue = document.getElementById('categoryValue');
        
        if (categoryFilter && categoryValue) {
            categoryFilter.value = category;
            
            var option = Array.from(categoryFilter.options).find(function(opt) {
                return opt.value === category;
            });
            
            if (option) {
                categoryValue.textContent = option.textContent;
            }
            
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
    if (window.APP_CONFIG) {
        CategoryHierarchy.init(window.APP_CONFIG);
    }
    
    ThemeManager.init();
    SidebarManager.init();
    FilterManager.init();
    ModalManager.init();
    
    handleHashChange();
    
    window.addEventListener('hashchange', function() {
        handleHashChange();
    });
    
    updateResultsCount();
});