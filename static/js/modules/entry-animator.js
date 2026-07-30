/**
 * Entry animator — scroll-triggered, filter-replayable entry animation.
 *
 * Uses `$animatedIds` to track which cards have been animated so the
 * IntersectionObserver only fires once per card. The `.link-card--enter`
 * class is toggled; the body `data-entry-animation` attribute selects
 * which keyframe the CSS plays.
 */

import { $animatedIds } from './state.js';
import { dom } from '../dom.js';

// Hoisted so rearmCards() can re-observe cards that filter-cards re-arms.
// Null until EntryAnimator.init() creates it (or stays null in the no-IO / no
// mode fallback, where rearmCards degrades to class/id reset only and relies
// on the scroll safety-net to reveal).
let io = null;

/**
 * Re-arm the entry animation for the given cards so each replays once the
 * next time it scrolls into view. Called by filter-cards for visible cards
 * that sit outside the viewport at filter time.
 *
 * For each card: remove the `.link-card--enter` class (back to the hidden
 * opacity:0 base state), drop its id from `$animatedIds` (so the Intersection
 *  Observer callback and the scroll safety-net stop skipping it), and re-
 * observe it so the observer fires when it next intersects.
 */
export function rearmCards(elements) {
  if (!io) return; // No IntersectionObserver → the init fallback shows every
                   // card immediately and installs no scroll safety-net, so
                   // there is nothing that would re-reveal a hidden card. Keep
                   // such cards visible rather than stranding them at opacity:0.
  const ids = new Set($animatedIds.get());
  let changed = false;
  for (const card of elements) {
    card.classList.remove('link-card--enter');
    const id = card.id || card.dataset.title;
    if (id && ids.has(id)) { ids.delete(id); changed = true; }
    io.observe(card);
  }
  if (changed) $animatedIds.set(ids);
}

export const EntryAnimator = {
  init() {
    const mode = document.body.getAttribute('data-entry-animation') || 'fade-slide-up';
    document.documentElement.classList.add('js');
    if (mode === 'none') return;

    const cards = document.querySelectorAll('.link-card');
    if (!('IntersectionObserver' in window) || !cards.length) {
      cards.forEach(c => c.classList.add('link-card--enter'));
      return;
    }

    const vh = window.innerHeight;
    io = new IntersectionObserver(
      (entries, obs) => {
        const newIds = new Set($animatedIds.get());
        let changed = false;
        entries.forEach(entry => {
          if (entry.boundingClientRect.top < vh) {
            entry.target.classList.add('link-card--enter');
            const id = entry.target.id || entry.target.dataset.title;
            if (id && !newIds.has(id)) {
              newIds.add(id);
              changed = true;
            }
            obs.unobserve(entry.target);
          }
        });
        if (changed) $animatedIds.set(newIds);
      },
      { threshold: 0.05, rootMargin: '0px 0px -40px 0px' }
    );

    cards.forEach(c => io.observe(c));

    // Safety net for fast / coalesced scrolls
    let ticking = false;
    const revealOnScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        const h = window.innerHeight;
        const current = $animatedIds.get();
        const newIds = new Set(current);
        let changed = false;
        for (const c of cards) {
          if (current.has(c.id || c.dataset.title)) continue;
          const r = c.getBoundingClientRect();
          // Only reveal cards that are actually within the viewport (top above
          // the bottom edge AND bottom below the top edge). The bottom>0 guard
          // prevents re-armed cards that sit above the viewport from being
          // re-revealed off-screen on a downward scroll — which would snap them
          // visible with no animation when scrolled back up. With re-arm
          // (filter-cards) above- and below-viewport cards must behave
          // symmetrically, so the safety-net matches the IntersectionObserver's
          // notion of "in view" rather than the looser top<h it used before.
          if (r.top < h && r.bottom > 0) {
            c.classList.add('link-card--enter');
            const id = c.id || c.dataset.title;
            if (id && !newIds.has(id)) {
              newIds.add(id);
              changed = true;
            }
          }
        }
        if (changed) $animatedIds.set(newIds);
      });
    };
    window.addEventListener('scroll', revealOnScroll, { passive: true });
  },
};
