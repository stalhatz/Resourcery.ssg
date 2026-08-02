/**
 * Filter cards — show/hide cards based on the current $visibleCards set.
 *
 * Reads the computed $visibleCards reactive variable and applies visibility
 * to the DOM. Re-animates in-viewport cards on filter changes; re-arms
 * out-of-viewport visible cards so they replay their entry animation when
 * scrolled to. Its body is also the $visibleCards effect callback
 * (effects.js), so it runs once per batched state transition.
 */

import { $visibleCards, allCards } from './state.js';
import { rearmCards } from './entry-animator.js';
import { dom } from '../dom.js';
import { isBrowsePage } from './browse-utils.js';

export function filterCards() {
  if (!isBrowsePage()) return;

  const visible = new Set($visibleCards.get());
  const mode = document.body.getAttribute('data-entry-animation') || 'fade-slide-up';
  const reanimate = mode !== 'none';
  const reshownCards = [];
  let visibleCount = 0;

  allCards.forEach(({ id, el: card }) => {
    if (visible.has(id)) {
      card.style.display = '';
      if (reanimate) {
        const rect = card.getBoundingClientRect();
        const inView = rect.top < window.innerHeight && rect.bottom > 0;
        if (inView) {
          // Visible to the user right now: replay the animation immediately
          // (remove the class, force a reflow below, re-add it).
          card.classList.remove('link-card--enter');
          reshownCards.push(card);
        } else {
          // Off-screen but part of the new filtered set: re-arm so it
          // plays its entry animation the next time it scrolls into view.
          // Hiding it here is correct — the user can't see it yet — and
          // re-arm (class off, id dropped from $animatedIds, re-observed)
          // guarantees a real absent→present transition on scroll, which is
          // exactly what makes the CSS keyframe fire. Without this, a
          // previously-animated card would keep a stale .link-card--enter
          // and snap visible with no animation (the observer already
          // unobserved it and the scroll safety-net skips known ids).
          rearmCards([card]);
        }
      }
      visibleCount++;
    } else {
      card.style.display = 'none';
    }
  });

  // Force one reflow, then re-add .link-card--enter to the in-viewport
  // re-shown cards so the entry animation replays once for the visible set.
  if (reshownCards.length) {
    void document.body.offsetWidth; // force reflow so animation can replay
    reshownCards.forEach(card => card.classList.add('link-card--enter'));
  }

  if (dom.noResults) {
    dom.noResults.style.display = visibleCount === 0 ? 'block' : 'none';
  }

  if (dom.resultsCount) {
    dom.resultsCount.textContent =
      visibleCount + ' item' + (visibleCount !== 1 ? 's' : '');
  }
}
