/**
 * Modal manager — open/close link detail modals.
 *
 * All DOM access is through the `dom` manifest. Preserves timing,
 * clipboard behaviour, and tag-click navigation from the original.
 */

import { dom } from '../dom.js';
import { TagManager } from './tag-manager.js';
import { filterCards } from './filter-cards.js';
import { createLogger } from './logger.js';

export const logger = createLogger(import.meta.url);

const isLandingPage = !window.location.pathname.includes('browse.html');

export const ModalManager = {
  open(card) {
    const overlay = dom.modalOverlay;
    const modal = dom.modal;
    if (!overlay || !modal) {
      logger.warn('⚠️ Modal elements not found');
      return;
    }

    dom.modalTitle.textContent = card.dataset.title;
    dom.modalSummary.textContent = card.dataset.summary;
    dom.modalDescription.textContent = card.dataset.description || card.dataset.summary;
    dom.modalCategory.textContent = card.dataset.category;
    dom.modalPricing.textContent = card.dataset.pricing;
    dom.modalLanguage.textContent = card.dataset.language;
    dom.modalVisit.href = card.dataset.url;

    if (dom.modalImage) {
      if (card.dataset.image) {
        dom.modalImage.style.backgroundImage = 'url(' + card.dataset.image + ')';
      } else {
        dom.modalImage.style.backgroundImage =
          'url(/static/images/placeholders/' + card.dataset.category + '.jpg)';
      }
    }

    if (dom.modalTags) {
      dom.modalTags.innerHTML = '';
      const tags = card.dataset.tags.split(',');
      tags.forEach(tag => {
        if (tag.trim()) {
          const tagEl = document.createElement('span');
          tagEl.className = 'modal-tag';
          tagEl.textContent = tag.trim();
          tagEl.style.cursor = 'pointer';
          tagEl.addEventListener('click', e => {
            e.stopPropagation();
            const tagName = tag.trim();

            if (isLandingPage) {
              window.location.href =
                'browse.html#tag-' + TagManager.slugify(tagName);
            } else {
              TagManager.setActiveTag(tagName, true);
              ModalManager.close();
              filterCards();
            }
          });
          dom.modalTags.appendChild(tagEl);
        }
      });
    }

    const shareUrl = encodeURIComponent(card.dataset.url);
    const shareTitle = encodeURIComponent(card.dataset.title);
    if (dom.shareTwitter) {
      dom.shareTwitter.href =
        'https://twitter.com/intent/tweet?url=' + shareUrl + '&text=' + shareTitle;
    }

    overlay.style.display = 'flex';
    setTimeout(() => {
      overlay.classList.add('active');
    }, 10);

    document.body.style.overflow = 'hidden';
    modal.focus();
  },

  close() {
    const overlay = dom.modalOverlay;
    if (!overlay) return;

    overlay.classList.remove('active');

    setTimeout(() => {
      overlay.style.display = 'none';
      document.body.style.overflow = '';
    }, 300);
  },

  init() {
    const overlay = dom.modalOverlay;
    const closeBtn = dom.modalClose;

    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        this.close();
      });
    }

    if (overlay) {
      overlay.addEventListener('click', e => {
        if (e.target === overlay) {
          this.close();
        }
      });
    }

    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && overlay && overlay.style.display !== 'none') {
        this.close();
      }
    });

    const shareBtn = dom.modalShare;
    if (shareBtn) {
      shareBtn.addEventListener('click', e => {
        e.stopPropagation();
        const url = dom.modalVisit.href;
        navigator.clipboard.writeText(url).then(() => {
          shareBtn.textContent = '✓';
          setTimeout(() => {
            shareBtn.textContent = '🔗';
          }, 2000);
        });
      });
    }
  },
};
