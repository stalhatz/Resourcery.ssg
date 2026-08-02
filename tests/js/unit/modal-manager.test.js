import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

// modal-manager imports tag-manager + filter-cards + dom + state transitively.
// Import state + tag-manager first so we can spy on the shared TagManager object.
async function setup(url = BROWSE) {
  await loadFresh('static/js/modules/state.js', { url, html: FIX() });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const modalMod = await loadFresh('static/js/modules/modal-manager.js', { url });
  const fx = await loadFresh('static/js/modules/effects.js', { url });
  return {
    TagManager: tagMod.TagManager,
    ModalManager: modalMod.ModalManager,
    installEffects: fx.installEffects,
  };
}

describe('modal-manager.js', () => {
  it('open: populates every modal field from card.dataset (title/summary/description|summary fallback/category/pricing/language/url)', async () => {
    const { ModalManager } = await setup();
    ModalManager.open(document.getElementById('card-1'));
    expect(document.getElementById('modalTitle').textContent).toBe('Alpha Tool');
    expect(document.getElementById('modalSummary').textContent).toBe('Short summary');
    expect(document.getElementById('modalDescription').textContent).toBe('Full alpha description');
    expect(document.getElementById('modalCategory').textContent).toBe('frontend');
    expect(document.getElementById('modalPricing').textContent).toBe('Free');
    expect(document.getElementById('modalLanguage').textContent).toBe('JavaScript');
    expect(document.getElementById('modalVisit').href).toContain('alpha.example.com');

    // card-2 has no description -> modalDescription falls back to summary
    ModalManager.open(document.getElementById('card-2'));
    expect(document.getElementById('modalDescription').textContent).toBe('Beta summary');
  });

  it('open: builds tag spans from dataset.tags with click handlers (browse branch calls setActiveTag + close; the effects drain renders)', async () => {
    const { TagManager, ModalManager, installEffects } = await setup();
    installEffects();
    ModalManager.open(document.getElementById('card-1'));
    const tagSpans = document.getElementById('modalTags').querySelectorAll('.modal-tag');
    expect(tagSpans.length).toBe(3); // JavaScript, React, Frontend

    const setActiveSpy = vi.spyOn(TagManager, 'setActiveTag');
    const closeSpy = vi.spyOn(ModalManager, 'close');
    tagSpans[0].click(); // "JavaScript"

    expect(setActiveSpy).toHaveBeenCalledWith('JavaScript', true);
    expect(closeSpy).toHaveBeenCalled();
    // the effects drain rendered the filtered set: card-2 (no JavaScript tag) hidden
    expect(document.getElementById('card-2').style.display).toBe('none');
    expect(document.getElementById('card-1').style.display).toBe('');
  });

  it('open: tag span click on landing sets href to browse.html#tag-<slug>', async () => {
    const { ModalManager } = await setup(LANDING);
    // jsdom doesn't navigate on location.href assignment; stub a recordable location
    stubLocation();
    ModalManager.open(document.getElementById('card-1'));
    const tagSpans = document.getElementById('modalTags').querySelectorAll('.modal-tag');
    tagSpans[0].click(); // "JavaScript" -> slug "javascript"
    expect(window.location.href).toBe('browse.html#tag-javascript');
  });

  it('open: sets shareTwitter href to the Twitter intent URL (encoded url+title)', async () => {
    const { ModalManager } = await setup();
    ModalManager.open(document.getElementById('card-1'));
    const href = document.getElementById('shareTwitter').href;
    expect(href).toContain('https://twitter.com/intent/tweet?');
    expect(href).toContain('url=' + encodeURIComponent('https://alpha.example.com'));
    expect(href).toContain('text=' + encodeURIComponent('Alpha Tool'));
  });

  it('open: image with dataset.image sets backgroundImage; else placeholder /static/images/placeholders/<category>.jpg', async () => {
    const { ModalManager } = await setup();
    ModalManager.open(document.getElementById('card-1')); // has image img1.jpg
    expect(document.getElementById('modalImage').style.backgroundImage).toContain('img1.jpg');

    ModalManager.open(document.getElementById('card-3')); // no image -> placeholder
    expect(document.getElementById('modalImage').style.backgroundImage).toContain(
      '/static/images/placeholders/devops.jpg'
    );
  });

  it('open: overlay display flex → active after a tick; body overflow hidden; modal.focus()', async () => {
    vi.useFakeTimers();
    try {
      const { ModalManager } = await setup();
      const modal = document.getElementById('modal');
      const focusSpy = vi.spyOn(modal, 'focus');
      ModalManager.open(document.getElementById('card-1'));
      expect(document.getElementById('modalOverlay').style.display).toBe('flex');
      expect(document.body.style.overflow).toBe('hidden');
      expect(focusSpy).toHaveBeenCalled();
      expect(document.getElementById('modalOverlay').classList.contains('active')).toBe(false);
      vi.advanceTimersByTime(10);
      expect(document.getElementById('modalOverlay').classList.contains('active')).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it('close: removes active then hides after a tick and restores overflow', async () => {
    vi.useFakeTimers();
    try {
      const { ModalManager } = await setup();
      ModalManager.open(document.getElementById('card-1'));
      vi.advanceTimersByTime(10); // open's tick -> active added
      const overlay = document.getElementById('modalOverlay');
      expect(overlay.classList.contains('active')).toBe(true);

      ModalManager.close();
      expect(overlay.classList.contains('active')).toBe(false); // removed immediately
      expect(overlay.style.display).toBe('flex'); // still visible until the tick
      expect(document.body.style.overflow).toBe('hidden');

      vi.advanceTimersByTime(300);
      expect(overlay.style.display).toBe('none');
      expect(document.body.style.overflow).toBe('');
    } finally {
      vi.useRealTimers();
    }
  });

  it('init: close-button click -> close()', async () => {
    const { ModalManager } = await setup();
    ModalManager.init();
    const closeSpy = vi.spyOn(ModalManager, 'close');
    document.getElementById('modalClose').click();
    expect(closeSpy).toHaveBeenCalled();
  });

  it('init: overlay click-outside (e.target===overlay) -> close(); child click does not', async () => {
    const { ModalManager } = await setup();
    ModalManager.init();
    const closeSpy = vi.spyOn(ModalManager, 'close');
    const overlay = document.getElementById('modalOverlay');
    overlay.click(); // e.target === overlay
    expect(closeSpy).toHaveBeenCalled();
    closeSpy.mockClear();
    // a click on a child element does NOT close
    document.getElementById('modalTitle').click();
    expect(closeSpy).not.toHaveBeenCalled();
  });

  it('init: Escape keydown (overlay visible) -> close()', async () => {
    const { ModalManager } = await setup();
    ModalManager.init();
    const overlay = document.getElementById('modalOverlay');
    overlay.style.display = 'flex'; // visible
    const closeSpy = vi.spyOn(ModalManager, 'close');
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(closeSpy).toHaveBeenCalled();
  });

  it("init: share button click -> navigator.clipboard.writeText(url).then -> '✓' then revert to '🔗' after 2s", async () => {
    vi.useFakeTimers();
    try {
      const { ModalManager } = await setup();
      ModalManager.init();
      ModalManager.open(document.getElementById('card-1'));
      const shareBtn = document.getElementById('modalShare');
      expect(shareBtn.textContent).toBe('🔗');
      shareBtn.click();
      // clipboard.writeText().then is a microtask; flush it to reach the '✓' state
      await vi.advanceTimersByTimeAsync(0);
      expect(shareBtn.textContent).toBe('✓');
      // after 2s the text reverts to '🔗'
      await vi.advanceTimersByTimeAsync(2000);
      expect(shareBtn.textContent).toBe('🔗');
    } finally {
      vi.useRealTimers();
    }
  });
});