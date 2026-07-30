/**
 * Card manager — click/keyboard handlers on link cards and tag badges.
 *
 * Card clicks open the modal. Tag badge clicks set the active tag
 * (or navigate to browse.html on the landing page).
 */

import { ModalManager } from './modal-manager.js';
import { TagManager } from './tag-manager.js';
import { filterCards } from './filter-cards.js';

const isLandingPage = !window.location.pathname.includes('browse.html');

export const CardManager = {
  init() {
    document.querySelectorAll('.link-card').forEach(card => {
      card.addEventListener('click', e => {
        e.stopPropagation();
        ModalManager.open(card);
      });

      card.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          ModalManager.open(card);
        }
      });
    });

    document.querySelectorAll('.card-tags .tag').forEach(tag => {
      tag.addEventListener('click', e => {
        e.stopPropagation();
        const tagName = tag.dataset.tag || tag.textContent.trim();

        if (isLandingPage) {
          window.location.href =
            'browse.html#tag-' + TagManager.slugify(tagName);
          return;
        }

        TagManager.setActiveTag(tagName, true);
        filterCards();
      });
    });
  },
};
