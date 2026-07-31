import { describe, it, expect } from 'vitest';
import { loadFresh, readFixture, stubLocation } from '../helpers/setup.js';

const BROWSE = 'http://localhost/browse.html';
const LANDING = 'http://localhost/index.html';
const FIX = () => readFixture('browse.html');

// card-manager imports modal-manager + tag-manager + filter-cards transitively.
async function setup(url = BROWSE, html = FIX()) {
  await loadFresh('static/js/modules/state.js', { url, html });
  const tagMod = await loadFresh('static/js/modules/tag-manager.js', { url });
  const modalMod = await loadFresh('static/js/modules/modal-manager.js', { url });
  const cardMod = await loadFresh('static/js/modules/card-manager.js', { url });
  cardMod.CardManager.init();
  return { TagManager: tagMod.TagManager, ModalManager: modalMod.ModalManager };
}

describe('card-manager.js', () => {
  it('init: .link-card click -> ModalManager.open(card) + stopPropagation', async () => {
    const { ModalManager } = await setup();
    const openSpy = vi.spyOn(ModalManager, 'open');
    const card = document.getElementById('card-1');
    const e = new MouseEvent('click', { bubbles: true });
    const stopSpy = vi.spyOn(e, 'stopPropagation');
    card.dispatchEvent(e);
    expect(openSpy).toHaveBeenCalledWith(card);
    expect(stopSpy).toHaveBeenCalled();
  });

  it('init: keydown Enter/Space -> open + preventDefault', async () => {
    const { ModalManager } = await setup();
    const openSpy = vi.spyOn(ModalManager, 'open');
    const card = document.getElementById('card-1');

    const eEnter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true });
    const pdEnter = vi.spyOn(eEnter, 'preventDefault');
    card.dispatchEvent(eEnter);
    expect(openSpy).toHaveBeenCalledWith(card);
    expect(pdEnter).toHaveBeenCalled();

    const eSpace = new KeyboardEvent('keydown', { key: ' ', bubbles: true });
    const pdSpace = vi.spyOn(eSpace, 'preventDefault');
    card.dispatchEvent(eSpace);
    expect(openSpy).toHaveBeenCalledTimes(2);
    expect(pdSpace).toHaveBeenCalled();
  });

  it('init: .card-tags .tag click on browse -> setActiveTag + filterCards', async () => {
    const { TagManager, ModalManager } = await setup();
    const setActiveSpy = vi.spyOn(TagManager, 'setActiveTag');
    const openSpy = vi.spyOn(ModalManager, 'open');
    const tag = document.querySelector('#card-1 .card-tags .tag'); // data-tag="JavaScript"
    tag.click();
    expect(setActiveSpy).toHaveBeenCalledWith('JavaScript', true);
    // stopPropagation on the tag click prevents the card (open) handler
    expect(openSpy).not.toHaveBeenCalled();
    // filterCards() ran: card-2 (no JavaScript tag) hidden, card-1 visible
    expect(document.getElementById('card-2').style.display).toBe('none');
    expect(document.getElementById('card-1').style.display).toBe('');
  });

  it('init: .card-tags .tag click on landing -> href browse.html#tag-<slug>', async () => {
    const { TagManager } = await setup(LANDING);
    stubLocation();
    const tag = document.querySelector('#card-1 .card-tags .tag'); // "JavaScript"
    tag.click();
    expect(window.location.href).toBe('browse.html#tag-javascript');
  });

  it("init: queries '.card-tags .tag' (not a class-tagged variant)", async () => {
    const html = `
      <article class="link-card" id="c1" data-title="Alpha" data-tags="JavaScript">
        <div class="card-tags"><span class="tag" data-tag="JavaScript">JavaScript</span></div>
      </article>
      <span class="tag" id="lonely-tag" data-tag="Lonely">Lonely</span>
    `;
    const { TagManager } = await setup(BROWSE, html);
    const setActiveSpy = vi.spyOn(TagManager, 'setActiveTag');
    // the lookalike .tag OUTSIDE .card-tags does NOT get the handler
    document.getElementById('lonely-tag').click();
    expect(setActiveSpy).not.toHaveBeenCalled();
    // the .tag INSIDE .card-tags does
    document.querySelector('#c1 .card-tags .tag').click();
    expect(setActiveSpy).toHaveBeenCalledWith('JavaScript', true);
  });
});