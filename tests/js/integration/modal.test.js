import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const FIX = () => readFixture('browse.html');

async function setup(url = BROWSE) {
  await loadFresh('static/js/modules/state.js', { url, html: FIX() });
  await loadFresh('static/js/modules/entry-animator.js', { url });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const cardMod = await loadFresh('static/js/modules/card-manager.js', { url });
  const modalMod = await loadFresh('static/js/modules/modal-manager.js', { url });
  cardMod.CardManager.init();
  modalMod.ModalManager.init();
  return { TagManager: tagMod.TagManager, ModalManager: modalMod.ModalManager };
}

describe('Modal (integration)', () => {
  it('card click opens modal, populates every field; overlay active; Escape closes; share ✓→🔗', async () => {
    vi.useFakeTimers();
    try {
      const { ModalManager } = await setup();
      document.getElementById('card-1').click();
      expect(document.getElementById('modalTitle').textContent).toBe('Alpha Tool');
      expect(document.getElementById('modalCategory').textContent).toBe('frontend');
      expect(document.getElementById('modalVisit').href).toContain('alpha.example.com');
      expect(document.getElementById('modalOverlay').style.display).toBe('flex');
      vi.advanceTimersByTime(10);
      expect(document.getElementById('modalOverlay').classList.contains('active')).toBe(true);

      // Escape closes
      document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      expect(document.getElementById('modalOverlay').classList.contains('active')).toBe(false);
      vi.advanceTimersByTime(300);
      expect(document.getElementById('modalOverlay').style.display).toBe('none');

      // share button ✓ -> 🔗
      ModalManager.open(document.getElementById('card-1'));
      vi.advanceTimersByTime(10);
      const shareBtn = document.getElementById('modalShare');
      shareBtn.click();
      await vi.advanceTimersByTimeAsync(0);
      expect(shareBtn.textContent).toBe('✓');
      await vi.advanceTimersByTimeAsync(2000);
      expect(shareBtn.textContent).toBe('🔗');
    } finally {
      vi.useRealTimers();
    }
  });

  it('tag span click (browse) calls setActiveTag', async () => {
    const { TagManager, ModalManager } = await setup();
    ModalManager.open(document.getElementById('card-1'));
    const spy = vi.spyOn(TagManager, 'setActiveTag');
    document.querySelector('#modalTags .modal-tag').click();
    expect(spy).toHaveBeenCalledWith('JavaScript', true);
  });

  it('main.js bootstrap does not throw on the browse fixture', async () => {
    await expect(loadFresh('static/js/main.js', { url: BROWSE, html: FIX() })).resolves.toBeDefined();
  });
});