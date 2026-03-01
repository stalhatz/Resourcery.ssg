/**
 * Main JavaScript for Static Link Aggregation Site
 * Compact Cards + Modal Version
 */

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

const ModalManager = {
    open: function(card) {
        var overlay = document.getElementById('modalOverlay');
        var modal = document.getElementById('modal');
        
        // Populate modal data
        document.getElementById('modalTitle').textContent = card.dataset.title;
        document.getElementById('modalSummary').textContent = card.dataset.summary;
        document.getElementById('modalDescription').textContent = card.dataset.description || card.dataset.summary;
        document.getElementById('modalCategory').textContent = card.dataset.category;
        document.getElementById('modalPricing').textContent = card.dataset.pricing;
        document.getElementById('modalLanguage').textContent = card.dataset.language;
        document.getElementById('modalVisit').href = card.dataset.url;
        
        // Set modal image
        var modalImage = document.getElementById('modalImage');
        if (card.dataset.image) {
            modalImage.style.backgroundImage = 'url(' + card.dataset.image + ')';
        } else {
            modalImage.style.backgroundImage = 'url(/static/images/placeholders/' + card.dataset.category + '.jpg)';
        }
        
        // Populate tags
        var tagsContainer = document.getElementById('modalTags');
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
        
        // Setup share links
        var shareUrl = encodeURIComponent(card.dataset.url);
        var shareTitle = encodeURIComponent(card.dataset.title);
        var twitterLink = document.getElementById('shareTwitter');
        if (twitterLink) {
            twitterLink.href = 'https://twitter.com/intent/tweet?url=' + shareUrl + '&text=' + shareTitle;
        }
        
        // Show modal
        overlay.style.display = 'flex';
        setTimeout(function() {
            overlay.classList.add('active');
        }, 10);
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Focus trap
        modal.focus();
    },
    
    close: function() {
        var overlay = document.getElementById('modalOverlay');
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
        
        // Close on escape
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && overlay.style.display !== 'none') {
                self.close();
            }
        });
        
        // Share button
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

document.addEventListener('DOMContentLoaded', function() {
    if (window.APP_CONFIG) {
        CategoryHierarchy.init(window.APP_CONFIG);
    }
    
    applyThemeColors();
    ThemeManager.init();
    SidebarManager.init();
    FilterManager.init();
    ModalManager.init();
    
    handleHashChange();
    
    window.addEventListener('hashchange', function() {
        handleHashChange();
    });
    
    // Update results count
    updateResultsCount();
});

function applyThemeColors() {
    if (window.APP_CONFIG?.theme?.colors) {
        var root = document.documentElement;
        Object.entries(window.APP_CONFIG.theme.colors).forEach(function(entry) {
            var key = entry[0];
            var value = entry[1];
            root.style.setProperty('--color-' + key, value);
        });
    }
}

var ThemeManager = {
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

var SidebarManager = {
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
    }
};

var FilterManager = {
    init: function() {
        var categoryFilter = document.getElementById('categoryFilter');
        var searchInput = document.getElementById('searchInput');
        var sortFilter = document.getElementById('sortFilter');
        
        if (categoryFilter) {
            categoryFilter.addEventListener('change', function(e) {
                var category = e.target.value;
                if (category) {
                    window.location.hash = 'category-' + category;
                } else {
                    history.pushState('', '', window.location.pathname);
                }
                filterCards();
            });
        }
        
        if (searchInput) {
            searchInput.addEventListener('input', debounce(function() {
                filterCards();
            }, 300));
        }
        
        if (sortFilter) {
            sortFilter.addEventListener('change', function() {
                sortCards();
            });
        }
        
        var sidebarLinks = document.querySelectorAll('.category-link, .subcategory-link');
        
        sidebarLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var category = link.dataset.category;
                
                var dropdown = document.getElementById('categoryFilter');
                if (category && dropdown) {
                    dropdown.value = category;
                    window.location.hash = 'category-' + category;
                    filterCards();
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
    }
};

function filterCards() {
    var searchInput = document.getElementById('searchInput');
    var categoryFilter = document.getElementById('categoryFilter');
    var cards = document.querySelectorAll('.link-card');
    var noResults = document.getElementById('noResults');
    
    var searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    var category = categoryFilter ? categoryFilter.value : '';
    
    var matchingCategories = CategoryHierarchy.getMatchingCategories(category);
    
    var visibleCount = 0;
    
    cards.forEach(function(card) {
        var title = card.dataset.title.toLowerCase();
        var summary = card.dataset.summary.toLowerCase();
        var tags = card.dataset.tags.toLowerCase();
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
    
    updateResultsCount(visibleCount);
}

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

function handleHashChange() {
    var hash = window.location.hash;
    
    if (hash.startsWith('#category-')) {
        var category = hash.replace('#category-', '');
        var dropdown = document.getElementById('categoryFilter');
        
        if (dropdown) {
            dropdown.value = category;
            filterCards();
        }
    }
}

function updateResultsCount(visibleCount) {
    var countEl = document.getElementById('resultsCount');
    if (!countEl) return;
    
    if (visibleCount === undefined) {
        visibleCount = document.querySelectorAll('.link-card[style=""]').length;
    }
    
    countEl.textContent = visibleCount + ' item' + (visibleCount !== 1 ? 's' : '');
}

function debounce(func, wait) {
    var timeout;
    return function() {
        var args = arguments;
        clearTimeout(timeout);
        timeout = setTimeout(function() {
            func.apply(this, args);
        }, wait);
    };
}