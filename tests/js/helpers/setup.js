// tests/js/helpers/setup.js  (registered via test.setupFiles; runs per test file)
import { beforeEach, afterEach } from 'vitest';
import './jsdom-polyfills.js';
import { __resetIOInstances } from './jsdom-polyfills.js';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';

// tests/js/helpers/ -> repo root (import.meta.dirname avoids Vite's
// new URL(..., import.meta.url) -> http://localhost asset transform).
const REPO_ROOT = resolve(import.meta.dirname, '../../..');
const specUrl = (spec) => pathToFileURL(resolve(REPO_ROOT, spec)).href;

beforeEach(() => {
  vi.resetModules(); // (1) clear module registry
  document.documentElement.innerHTML = ''; // (2) reset DOM
  localStorage.clear();
  sessionStorage.clear();
  window.history.pushState({}, '', 'http://localhost/'); // (3) reset URL (pathname+hash)
  delete window.ALL_TAGS; // (4) clear build globals
  delete window.CATEGORY_MAP;
  __resetIOInstances(); // (5) polyfill opt-in reset
});

afterEach(() => {
  vi.restoreAllMocks(); // undo setRect / vi.spyOn
  vi.unstubAllGlobals(); // undo vi.stubGlobal('location', …) used by landing tests
  __resetIOInstances();
});

/**
 * Fresh-import a module under test against a reset jsdom environment.
 * `spec` is repo-root-relative, e.g. 'static/js/modules/state.js'.
 * The url/html/globals are applied BEFORE the dynamic import so that
 * import-time page detection and DOM reads see the seeded state.
 */
/**
 * Stub window.location with a recordable `href` while preserving the real
 * pathname/hash. jsdom doesn't navigate on relative location.href assignment,
 * so landing-branch tests stub location to observe the assigned href. Keeping
 * pathname/hash on the stub means stale hashchange listeners (handleHashChange
 * from earlier tests, which fire asynchronously in jsdom) read a real pathname
 * and early-return instead of crashing on `undefined.includes`.
 */
export function stubLocation() {
  vi.stubGlobal('location', {
    href: '',
    pathname: window.location.pathname,
    hash: '',
  });
}

/**
 * Read a fixture HTML document from tests/js/fixtures/. Returns the file
 * contents as a string (pass it to loadFresh via the `html` option).
 */
export function readFixture(name) {
  return readFileSync(resolve(REPO_ROOT, 'tests/js/fixtures', name), 'utf-8');
}

export async function loadFresh(spec, { url, html, globals } = {}) {
  if (url) window.history.pushState({}, '', url); // set pathname+hash BEFORE import
  if (html) document.documentElement.innerHTML = html;
  if (globals)
    for (const [k, v] of Object.entries(globals)) window[k] = v;
  return import(specUrl(spec)); // fresh eval against reset DOM
}

/**
 * Per-element getBoundingClientRect mock (NOT a global override — jsdom's
 * all-zeros default remains a valid "at origin" case). Drives in-viewport
 * (top < innerHeight && bottom > 0) vs off-viewport branches.
 */
export function setRect(
  el,
  { top = 0, bottom = 0, left = 0, right = 0, width = 100, height = 100 } = {}
) {
  return vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({
    top,
    bottom,
    left,
    right,
    width,
    height,
    x: left,
    y: top,
    toJSON() {},
  });
}