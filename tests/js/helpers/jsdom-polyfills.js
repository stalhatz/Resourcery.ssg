// tests/js/helpers/jsdom-polyfills.js  (loaded once by setup.js)
//
// jsdom lacks several APIs the modules under test read. These fakes are
// installed once at setup-file load (before any test runs). The IO instance
// registry is reset per-test via __resetIOInstances() (re-exported by setup.js).

const ioInstances = [];

class FakeIntersectionObserver {
  constructor(cb, opts) {
    this.cb = cb;
    this.opts = opts;
    this._targets = new Set();
    ioInstances.push(this);
  }
  observe(t) {
    this._targets.add(t);
  }
  unobserve(t) {
    this._targets.delete(t);
  }
  disconnect() {
    this._targets.clear();
  }
  takeRecords() {
    return [];
  }
}
FakeIntersectionObserver.__instances = ioInstances;
FakeIntersectionObserver.__trigger = function (entries) {
  for (const inst of [...ioInstances]) inst.cb(entries, inst);
};

window.IntersectionObserver = FakeIntersectionObserver;

// Synchronous rAF so the entry-animator scroll safety-net is deterministic.
window.requestAnimationFrame = (cb) => {
  cb(0);
  return 0;
};
window.cancelAnimationFrame = () => {};

// modal-manager share handler calls navigator.clipboard.writeText(url).then(...)
if (!navigator.clipboard) navigator.clipboard = {};
navigator.clipboard.writeText = () => Promise.resolve();

// tag-manager.highlightSuggestion calls el.scrollIntoView({ block: 'nearest' }).
// jsdom 25 does not ship a scrollIntoView stub; install a no-op so the call is safe.
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

export const __resetIOInstances = () => {
  ioInstances.length = 0;
};