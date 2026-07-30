/**
 * DOM manifest for Resourcery.ssg
 *
 * Caches frequently referenced DOM elements by ID at module load time.
 * All keys are camelCase versions of the corresponding HTML id attribute.
 */

function cacheDom() {
  const get = (id) => document.getElementById(id);
  return {
    searchInput: get('searchInput'),
    searchSuggestions: get('searchSuggestions'),
    searchValue: get('searchValue'),
    categoryTrigger: get('categoryTrigger'),
    categoryFilter: get('categoryFilter'),
    categoryDropdown: get('categoryDropdown'),
    sortTrigger: get('sortTrigger'),
    sortFilter: get('sortFilter'),
    sortDropdown: get('sortDropdown'),
    themeToggle: get('themeToggle'),
    sidebarToggle: get('sidebarToggle'),
    sidebar: get('sidebar'),
    linksGrid: get('linksGrid'),
    resultsCount: get('resultsCount'),
    noResults: get('noResults'),
    filterText1: get('filterText1'),
    filterText2: get('filterText2'),
    filterValue1: get('filterValue1'),
    modalOverlay: get('modalOverlay'),
    modal: get('modal'),
    modalClose: get('modalClose'),
    modalShare: get('modalShare'),
    modalVisit: get('modalVisit'),
    modalImage: get('modalImage'),
    modalTags: get('modalTags'),
    modalTitle: get('modalTitle'),
    modalSummary: get('modalSummary'),
    modalDescription: get('modalDescription'),
    modalCategory: get('modalCategory'),
    modalPricing: get('modalPricing'),
    modalLanguage: get('modalLanguage'),
    shareTwitter: get('shareTwitter'),
  };
}

export const dom = cacheDom();
