/**
 * Main JavaScript for Static Link Aggregation Site
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
        
        console.log('📁 [DEBUG] Category hierarchy:', this.map);
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

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 [DEBUG] DOMContentLoaded fired');
    
    if (window.APP_CONFIG) {
        CategoryHierarchy.init(window.APP_CONFIG);
    }
    
    applyThemeColors();
    ThemeManager.init();
    SidebarManager.init();
    FilterManager.init();
    CardManager.init();
    
    console.log('🔍 [DEBUG] Initial hash:', window.location.hash);
    handleHashChange();
    
    window.addEventListener('hashchange', function() {
        console.log('🔔 [DEBUG] Hash change detected:', window.location.hash);
        handleHashChange();
    });
    
    console.log('✅ [DEBUG] Initialization complete');
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
        console.log('🛠️ [DEBUG] FilterManager initializing...');
        
        var categoryFilter = document.getElementById('categoryFilter');
        var searchInput = document.getElementById('searchInput');
        var sortFilter = document.getElementById('sortFilter');
        
        if (categoryFilter) {
            categoryFilter.addEventListener('change', function(e) {
                var category = e.target.value;
                console.log('👇 [DEBUG] Dropdown changed to:', category);
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
                console.log('🔍 [DEBUG] Search input changed');
                filterCards();
            }, 300));
        }
        
        if (sortFilter) {
            sortFilter.addEventListener('change', function() {
                console.log('🔀 [DEBUG] Sort changed');
                sortCards();
            });
        }
        
        var sidebarLinks = document.querySelectorAll('.category-link, .subcategory-link');
        console.log('🔗 [DEBUG] Found ' + sidebarLinks.length + ' sidebar category links');
        
        sidebarLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var category = link.dataset.category;
                console.log('🖱️ [DEBUG] Sidebar link clicked:', category);
                
                var dropdown = document.getElementById('categoryFilter');
                if (category && dropdown) {
                    dropdown.value = category;
                    window.location.hash = 'category-' + category;
                    filterCards();
                }
            });
        });
        
        document.querySelectorAll('.view-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.view-btn').forEach(function(b) {
                    b.classList.remove('active');
                });
                btn.classList.add('active');
                var grid = document.getElementById('linksGrid');
                if (grid) {
                    grid.className = 'links-grid view-' + btn.dataset.view;
                }
                localStorage.setItem('viewMode', btn.dataset.view);
            });
        });
    }
};

var CardManager = {
    init: function() {
        document.querySelectorAll('.copy-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                navigator.clipboard.writeText(btn.dataset.url).then(function() {
                    btn.textContent = '✓';
                    setTimeout(function() {
                        btn.textContent = '📋';
                    }, 2000);
                });
            });
        });
        
        document.querySelectorAll('.tag').forEach(function(tag) {
            tag.addEventListener('click', function() {
                var searchInput = document.getElementById('searchInput');
                if (searchInput) {
                    searchInput.value = tag.dataset.tag;
                    filterCards();
                }
            });
        });
    }
};

function filterCards() {
    console.log('🔄 [DEBUG] filterCards() called');
    
    var searchInput = document.getElementById('searchInput');
    var categoryFilter = document.getElementById('categoryFilter');
    var cards = document.querySelectorAll('.link-card');
    var noResults = document.getElementById('noResults');
    
    console.log('🃏 [DEBUG] Found ' + cards.length + ' cards to filter');
    
    var searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
    var category = categoryFilter ? categoryFilter.value : '';
    
    var matchingCategories = CategoryHierarchy.getMatchingCategories(category);
    console.log('🔑 [DEBUG] Matching categories:', matchingCategories);
    
    var visibleCount = 0;
    
    cards.forEach(function(card) {
        var title = card.querySelector('.card-title');
        var summary = card.querySelector('.card-summary');
        var titleText = title ? title.textContent.toLowerCase() : '';
        var summaryText = summary ? summary.textContent.toLowerCase() : '';
        var tags = card.dataset.tags ? card.dataset.tags.toLowerCase() : '';
        var cardCategory = card.dataset.category || '';
        
        var matchesSearch = !searchTerm || 
                            titleText.includes(searchTerm) || 
                            summaryText.includes(searchTerm) || 
                            tags.includes(searchTerm);
        
        var matchesCategory = !category || matchingCategories.indexOf(cardCategory) !== -1;
        
        if (matchesSearch && matchesCategory) {
            card.style.display = '';
            visibleCount++;
        } else {
            card.style.display = 'none';
        }
    });
    
    console.log('✅ [DEBUG] Filtering complete. Visible: ' + visibleCount + '/' + cards.length);
    
    if (noResults) {
        noResults.style.display = visibleCount === 0 ? 'block' : 'none';
    }
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
            return a.querySelector('.card-title').textContent.localeCompare(
                b.querySelector('.card-title').textContent
            );
        }
        return 0;
    });
    
    cards.forEach(function(card) {
        grid.appendChild(card);
    });
}

function handleHashChange() {
    var hash = window.location.hash;
    console.log('🔗 [DEBUG] handleHashChange:', hash);
    
    if (hash.startsWith('#category-')) {
        var category = hash.replace('#category-', '');
        var dropdown = document.getElementById('categoryFilter');
        
        if (dropdown) {
            console.log('⬇️ [DEBUG] Setting dropdown to:', category);
            dropdown.value = category;
            filterCards();
        }
    }
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