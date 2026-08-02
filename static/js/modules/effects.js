/**
 * Effects layer — DOM subscriptions over the reactive state.
 *
 * Registers the two DOM effects once at boot (main.js browse branch; tests
 * call installEffects() directly on the same seam): the $activeFilter
 * effect syncs the native select + custom dropdown, the filter header and
 * the sidebar accordion; the $visibleCards effect runs the filterCards
 * body. Registration order is fixed ($activeFilter first) to preserve the
 * header-before-cards sequence. Subscribers are DOM-only: they read final
 * values and never write to reactive state (no feedback loops).
 */

import { effect, $activeFilter, $visibleCards } from './state.js';
import { dom } from '../dom.js';
import { filterCards } from './filter-cards.js';
import { TagManager } from './tag-manager.js';
import { FilterManager } from './filter-manager.js';
import { syncAccordion } from './sidebar-manager.js';

export function installEffects() {
  effect($activeFilter, descriptor => {
    // 1. Native select mirror + custom dropdown sync (category kind only);
    //    every other kind clears both — a bare-URL back-navigation must not
    //    leave a stale category in the select, the visible dropdown or the
    //    filter header.
    if (dom.categoryFilter) {
      dom.categoryFilter.value = descriptor.kind === 'category' ? descriptor.value : '';
    }
    FilterManager.syncSelection('category', descriptor.kind === 'category' ? descriptor.value : '');

    // 2. Filter header — runs after the select mirror (category label
    //    lookup in updateFilterHeader reads the mirrored select).
    TagManager.updateFilterHeader();

    // 3. Sidebar accordion.
    syncAccordion(descriptor);
  });

  effect($visibleCards, () => {
    filterCards();
  });
}
