---
size: medium
modified_date: 2026-07-31
implemented_git_tag: specs/tests/testing-js.md/implemented
---

# Unit and integration testing of the JavaScript frontend

## Introduction

This spec adds the first automated test suite for the project's client-side
JavaScript — the 13 ES modules produced by the implemented
[`specs/refactors/js_state_model.md`](../refactors/js_state_model.md)
refactor. It is the explicitly anticipated follow-up that the parent spec
deferred (its design decision 10, and the "Enables" entry it points at this
spec), and it uses the parent spec's non-regression acceptance criterion 9 —
the manual smoke-test contract for nine feature areas — as its first
integration-test target. The suite is [Vitest](https://vitest.dev/) with a
jsdom environment: unit tests exercise each module's exports in isolation,
and integration tests drive several real modules together against jsdom
fixture documents.

## Current state

No JavaScript tests exist. The frontend was restructured into a modular,
Nanostores-backed state model by the implemented
[`specs/refactors/js_state_model.md`](../refactors/js_state_model.md)
spec, whose design decision 10 deferred exactly this spec: *"A follow-up
spec will add Vitest with a jsdom environment … and test each module in
isolation."* That spec's "Enables" section names this one as the planned
follow-up.

The project's BUILD is intentionally Node-free: `js_vendor.py` (pure Python)
downloads the single vendored JS dependency at build time, and the parent
spec's AC 7 requires no Node toolchain for the build. Adding a Node-based
test runner does not contradict that — the parent spec deliberately carved
out the test toolchain as a separate, later decision, and even set
`package.json`'s `"type": "module"` so that *"any future Node-side tool like
Vitest can read the same intent"* (parent spec, `package.json` field table).
This spec introduces Node **only** as a dev-time test runner; the build
pipeline is unchanged.

The format and conventions of this spec mirror the implemented Python test
spec [`specs/tests/testing.md`](testing.md): Requirements / Constraints /
Acceptance-criteria shape, test infrastructure confined to `tests/`, and no
test-only branches leaking into source code. The Python suite uses pytest
markers (`unit`, `integration`, `network`); the JS suite mirrors the
`unit` / `integration` split (without `network` — nothing in this suite
touches the network).

## Target state

### Requirements

- **Framework:** Vitest (v2 or later) with a jsdom environment and `globals:
  true`. The unit/integration split is expressed by **directory** (`tests/js/unit/`
  vs `tests/js/integration/`) and selected via the `test:unit` /
  `test:integration` path-filter scripts; the `test.projects` config key (a
  Vitest 2.x shape; 1.x used `test.workspace`) is set for structural intent
  but Vitest 2.1.x does not honour it as an inline array, so the path-filter
  scripts — not a `--project` flag — are the operative mechanism. Pin
  `vitest@^2.1.0` or newer. The real Nanostores library is imported in tests —
  it is **not mocked** (see [Loop prevention via real Nanostores](#loop-prevention-via-real-nanostores)).
- **Unit tests:** Every non-trivial export or method across the 13 modules
  under `static/js/` has at least one passing unit test. The per-module
  coverage table below enumerates the testable surface and key assertions.
- **Integration tests:** The nine feature areas of the parent spec's AC 9
  each have at least one jsdom integration test that drives several real
  modules together against a fixture document. The integration coverage
  table below enumerates them.
- **Isolation:** Tests do not pollute one another. Module-load-time side
  effects (DOM reads, `window.location`, `window.ALL_TAGS`, `localStorage`)
  are reset per test via the mandatory isolation pattern documented below.
- **Network isolation:** The suite passes with no network connection after
  `npm install`. No real `hashchange` round-trips to a browser; jsdom
  synthesises the events.
- **No production-code changes:** Tests must not introduce test-only branches,
  exports, or imports in `static/js/`. The single permitted addition is
  test-tooling files and the Vitest alias + `package.json` dev-dependency
  entries described below. (Mirrors the Python spec's "Test infrastructure
  must not leak into source code" constraint.)

### Constraints

- Build stays Node-free. `js_vendor.py` continues to read
  `dependencies.nanostores` and download the vendored file for the build.
  The Node toolchain introduced here is **dev-only**.
- `nanostores` stays in `package.json`'s `dependencies` (the build reads
  it) AND is added to `devDependencies` (tests resolve it from
  `node_modules`). It must live in **both** — see [Handling the
  gitignored vendored nanostores](#handling-the-gitignored-vendored-nanostores).
- No E2E browser tests in this spec (Playwright, real-browser) — explicitly
  deferred to a future spec. Integration here is jsdom-only.
- `parseHash` in `state.js` stays internal; `serialiseHash` is now exported
  (superseded by `specs/refactors/js_reactive_effects.md`, which reuses it in
  `browseUrl`). Both remain tested indirectly through `bridgeFromHash` /
  `bridgeToHash`; `serialiseHash` additionally has direct round-trip unit
  tests.

### Test toolchain & config

**Package manager:** npm (standard, lowest-friction). Commit the lockfile
(`package-lock.json`); do **not** gitignore it. Gitignore `node_modules/`.
(The `static/js/vendor/` directory is already gitignored from the parent
spec.)

**`package.json` additions (committed):**

- `scripts`:
  - `test` → `vitest run` (runs unit + integration projects)
  - `test:watch` → `vitest`
  - `test:unit` → `vitest run --project unit` (see the flag-version note below)
  - `test:integration` → `vitest run --project integration`
- `devDependencies`: `vitest` (v1+), `jsdom`, and `nanostores` (also kept in
  `dependencies` for the build — see the gotcha above).

**`vitest.config.js` at repo root (committed):**

The config sets jsdom globally, enables `globals`, registers the shared
setup file, splits the suite into two named **projects** keyed by directory
(the `unit` / `integration` split, mirroring the Python markers but enforced
by file location rather than test-name strings), and installs the alias
that resolves the gitignored vendored Nanostores import to the real package.
Coverage is out of scope for the first cut (a later spec may add
`@vitest/coverage-v8`).

Sketch (drives the planner — not final syntax):

```js
// vitest.config.js
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/js/helpers/setup.js'],
    projects: [
      { test: { name: 'unit',        include: ['tests/js/unit/**/*.test.js'] } },
      { test: { name: 'integration', include: ['tests/js/integration/**/*.test.js'] } },
    ],
    alias: [
      {
        // state.js imports '../vendor/nanostores.js' (gitignored on a fresh
        // clone). Resolve any such import to the real installed package.
        find: /^.*\/vendor\/nanostores\.js$/,
        replacement: 'nanostores', // bare specifier → node_modules via package exports
      },
    ],
  },
});
```

Why **projects** over test-name tagging: folder-based projects make the
unit/integration boundary structural (matches the Python suite's intent but
enforced by location), let each group carry its own config later (e.g. a
stricter timeout for integration), and require no convention on test-name
strings. The simpler alternative — tagging tests with `describe('unit', …)`
and filtering via `vitest run -t unit` — is acceptable but relies on
naming discipline; this spec recommends projects. `--project` filtering and
the `test.projects` config key require Vitest 2.x (the suite pins
`vitest@^2.1.0`); if a pre-2.0 version is ever pinned, swap `projects:` for
the equivalent `workspace:` form and/or fall back to the path filter
(`vitest run tests/js/unit`), which works regardless.

Tests are NOT marked `network`: nothing in this suite makes network calls
(jsdom synthesises DOM events; Nanostores is resolved locally; no fetches).
This mirrors the Python suite's default-off network stance and goes one
step further by omitting the marker entirely.

### Per-module unit test coverage

| Module | Testable surface | Key assertions |
|--------|------------------|----------------|
| `main.js` | (no exports — bootstrap only) | Covered by integration. Unit scope is limited to asserting nothing; its wiring is verified through the nine integration flows. |
| `dom.js` | `dom` object built at load from 32 `getElementById` lookups | Every key present when all ids exist; a missing id maps to `null` (no throw); a fresh dynamic import after reseeding the DOM re-caches to the new elements (proves cache happens at module load, not once globally). |
| `state.js` | `$activeTag`, `$activeSearch`, `$activeCategory`, `$animatedIds` get/set; `allCards` built at load from `.link-card`; `$visibleCards` computed; `bridgeFromHash(apply)`; `bridgeToHash(atoms)` | At-most-one-of-three is the caller discipline (asserted by setting via `TagManager`/`bridgeFromHash`, not by raw `atom.set`); `$visibleCards` filters by `tag` (matches `dataset.tags`), by `search` (title/summary/tags substring, case-insensitive), by `category` (via `window.CATEGORY_MAP` fallback to literal id), and returns all when none set; `$animatedIds` only grows under `entry-animator` and shrinks only via `rearmCards`; `allCards` is the universe built once from the import-time DOM; `bridgeFromHash` parses all three prefixes (`#tag-`, `#search-`+`decodeURIComponent`, `#category-`) and the bare/`#`/empty case to `{tag,search,category}` all-null; `bridgeToHash` writes the matching hash and **skips** when the serialised hash already equals `window.location.hash`. Round-trip idempotence is asserted **indirectly** (see [Loop prevention via real Nanostores](#loop-prevention-via-real-nanostores)). |
| `tag-manager.js` | `slugify`; `setActiveTag`/`setActiveSearch` (with `updateUrl` true/false); `setCategoryDisplay`; `updateFilterHeader`; getters; `clearActiveTag`/`clearActiveSearch`; `clearSearchInput`; `setupSearchSuggestions` input/keydown wiring; `renderSuggestions`; `highlightSuggestion`; `hideSuggestions`; `navigateToBrowse`; `debounce` | `slugify` strips accents (NFD), spaces→`-`, drops punctuation; `setActiveTag` clears the other two atoms and writes `#tag-<slug>` (or clears hash when `null` and no category); `setActiveSearch` clears the other two and writes `#search-<encoded>`; `updateFilterHeader` has three branches (search / tag / none) controlling `filterText1`/`filterValue1`/`categoryTrigger`/`searchValue`/`filterText2` visibility; `navigateToBrowse` branches on `isLandingPage` (href) vs browse (`setActiveTag`/`setActiveSearch` + `filterCards`) and on `value.startsWith('#')` (tag vs search); `debounce` coalesces rapid calls into one trailing call. Requires `window.ALL_TAGS` + the `isLandingPage` page state set before import. |
| `modal-manager.js` | `open(card)`; `close()`; `init()` | `open` populates every modal field from the card's `dataset` (title, summary, description-with-summary-fallback, category, pricing, language, url, image-with-placeholder-fallback, tags→span elements), builds tag click handlers with the `isLandingPage` branch, sets the Twitter share href, shows overlay (display:flex → `active` after a tick), sets `body.overflow=hidden`, focuses modal; `close` removes `active` then hides after a tick and restores overflow; `init` wires close-button, overlay click-outside, Escape, and share button (`navigator.clipboard.writeText` → `✓` then revert). |
| `theme-manager.js` | `ThemeManager.init()` | Reads `localStorage('theme')` (default `'light'`), sets `<html data-theme>`, and the toggle click flips dark↔light, persists to `localStorage`; re-init reads the persisted value. |
| `sidebar-manager.js` | `SidebarManager.init()` | Creates an overlay `div` and appends to body; toggle adds/removes `active` on sidebar+overlay; overlay click closes; category-trigger click on **landing** sets `window.location.href` to `browse.html#category-<id>`, on **browse** collapses sibling triggers (`aria-expanded=false`, expanded list off) then writes `#category-<id>`; subcategory-link click sets `dom.categoryFilter.value`, calls `setCategoryDisplay` when an option exists, writes the hash, calls `filterCards`, updates `.active` classes; mobile (`window.innerWidth<=1023`) auto-closes. |
| `card-manager.js` | `CardManager.init()` | `.link-card` click → `ModalManager.open(card)` and `stopPropagation`; keydown `Enter`/`Space` → `open` with `preventDefault`; `.card-tags .tag` click → on **browse** `setActiveTag` + `filterCards`, on **landing** navigate to `browse.html#tag-<slug>`. Confirms it queries `.card-tags .tag` (not a class-tagged variant). |
| `filter-manager.js` | `init`; `bindDropdown`; `syncSelection`; `toggleDropdown`; `closeDropdown`; `closeAllDropdowns`; `clearFilters` listener | `init` binds category + sort dropdowns and the `clearFilters` window event; `bindDropdown` wires `.filter-dropdown-option` clicks (category → clear search+tag, `setCategoryDisplay`, write `#category-<v>` or `pushState` to clear, then `filterCards`; sort → `sortCards`), trigger toggle, and document outside-click to close; `syncSelection` toggles `.selected` by `data-value`; `toggle/close/closeAll` flip `.active` and `aria-expanded`; the `clearFilters` event resets search/tag, clears the select, syncs, and filters. |
| `entry-animator.js` | `EntryAnimator.init()`; `rearmCards(elements)` | `init` reads `data-entry-animation` (default `fade-slide-up`); `none` mode early-returns after adding the `js` class so `io` stays **null**; the no-`IntersectionObserver`/no-cards fallback adds `.link-card--enter` to all; the IO callback adds `.link-card--enter`, pushes the id into `$animatedIds`, and `unobserve`s (only fires once per card); the scroll safety-net (rAF) reveals cards where `rect.top < innerHeight && rect.bottom > 0` and skips ids already in `$animatedIds`; `rearmCards` **early-returns when `io` is null** (call it the "no-IO degrade" contract) and otherwise removes the class, deletes the id from `$animatedIds`, and re-observes. |
| `filter-cards.js` | `filterCards()` | Early-returns on a non-browse page; reads `$visibleCards`; visible cards get `display:''` and either an in-viewport reflow re-animation (remove class → forced `body.offsetWidth` → re-add) or `rearmCards` for off-viewport visible cards; hidden cards get `display:none`; `dom.noResults` shows iff `visibleCount===0`; `dom.resultsCount` reads `"N item"` vs `"N items"` (pluralisation `visibleCount !== 1 ? 's' : ''`). |
| `sort-cards.js` | `sortCards()` | Early-returns when `sortFilter`/`linksGrid` absent; `newest` sorts by `new Date(dataset.created)` descending; `oldest` ascending; `alphabetical` by `dataset.title.localeCompare`; unknown value → stable (returns 0, keeps order); final order is applied via `grid.appendChild` on the sorted array. |
| `handle-hash-change.js` | `handleHashChange()`; `installHashChangeListener()` | `handleHashChange` early-returns on non-browse, calls `bridgeFromHash`, sets all three atoms (preserving the at-most-one invariant for the parsed case), syncs `dom.categoryFilter.value` (set for category, cleared for tag/search), strips `.active` from `.category-trigger`/`.subcategory-link`, then for a category resolves **subcategory-first** (match `dataset.category` → `.active`, expand the closest `.subcategory-list`, set `aria-expanded=true` on the trigger found via `[aria-controls="<list.id>"]`) and **falls back** to the category trigger (match `dataset.categoryId` → `.active`, `aria-expanded=true`, expand its `aria-controls` list); calls `filterCards`. `installHashChangeListener` attaches `handleHashChange` to `window.hashchange`. |

### Integration test coverage (parent spec AC 9 feature areas)

Each row is a jsdom-only integration test: a fixture HTML document under
`tests/js/fixtures/` is loaded into jsdom, the real modules are fresh-imported
against it through the isolation helper, and several modules are driven end
to end. No real browser is involved.

| Feature area (parent AC 9) | jsdom flow | Key assertions |
|----------------------------|------------|-----------------|
| **Filter** | Browse fixture with cards across categories + the category dropdown/sidebar wired (via `FilterManager.init`/`SidebarManager.init`); set `#category-<id>` and call `handleHashChange` + `filterCards`; also click a sidebar subcategory link. | `$visibleCards` matches the category; only matching cards have `display!==none`; `dom.resultsCount`/`dom.noResults` reflect the count; the dropdown `<select>` and sidebar `.active`/`aria-expanded`/expanded list all reflect the chosen category. |
| **Sort** | Browse fixture with cards carrying varied `dataset.created` and `dataset.title`; set `dom.sortFilter.value` and call `sortCards`. | DOM order in `linksGrid` matches newest / oldest / alphabetical for each value; unknown sort value leaves order unchanged; `appendChild` reorder is stable. |
| **Modal** | Fixture with a `.link-card` (full `dataset`) + the modal shell; dispatch a click on the card; dispatch Escape. | `ModalManager.open` populates every modal field from the card's `dataset`; overlay becomes `active`; tag spans render with click handlers (browse branch calls `setActiveTag`); Escape triggers `close()`. |
| **Dark mode** | Fixture with `themeToggle` and `localStorage`; toggle click; re-init. | First init sets `data-theme` from `localStorage` (default `light`); toggle flips to `dark` and persists; after `vi.resetModules()` + re-init, `data-theme` reads the persisted value. |
| **Sidebar** | Fixture with sidebar, toggle, overlay, `.category-trigger`s (with `data-category-id` + `aria-controls`), `.subcategory-link`s; toggle, trigger click (browse + landing branches), subcategory click, and `innerWidth<=1023` mobile case. | Toggle opens/closes sidebar and overlay; overlay click closes; browse trigger click writes the hash and collapses siblings; browse subcategory click writes `dom.categoryFilter.value`, calls `setCategoryDisplay`, writes hash, filters, toggles active classes; mobile closes sidebar. Landing branches assert the `href` assignment. |
| **Search suggestions** | Fixture with `#searchInput` and `window.ALL_TAGS`; `TagManager.init`; fire `input` events and keydown `ArrowDown`/`ArrowUp`/`Enter`/`Escape`; click a suggestion. | Typing filters `ALL_TAGS` (case-insensitive, `#`-prefix optional) and renders ≤8 `.suggestion-item`s; arrow keys move `.selected`+`aria-selected`; Enter on a highlighted suggestion invites its click handler; clicking a suggestion on **browse** calls `setActiveTag`/`setActiveSearch` + `filterCards` (depending on `#` prefix), on **landing** sets `href`; Escape hides suggestions and blurs. |
| **Entry animation** | Fixture with cards + `body[data-entry-animation="fade-slide-up"]` and a driveable `IntersectionObserver` polyfill; drive the IO in-view, then a filter change that swaps in an in-viewport and an off-viewport card. Also run the `data-entry-animation="none"` fixture. | In-view IO entry adds `.link-card--enter`, adds the id to `$animatedIds`, and `unobserve`s (a second IO trigger does **not** re-add); filter change re-animates in-viewport cards via the reflow trick and re-arms off-viewport cards via `rearmCards`; `none` mode leaves `io` null and `rearmCards` is a no-op. |
| **URL hash deep-linking** | Browse fixture; load with `#tag-foo`, `#search-bar%20baz`, `#category-x`, and bare `#`/empty in turn (fresh import each). | For each, `bridgeFromHash` sets exactly the right atom (and nulls the others), `handleHashChange` updates the dropdown/sidebar/filter header, and `filterCards` shows the matching cards. Round-trip assertion: `bridgeToHash` writes a hash equal to the load hash for all four cases (see [Loop prevention via real Nanostores](#loop-prevention-via-real-nanostores)). |
| **Browser back/forward** | Browse fixture; push filter states via the hash, then `history.back()`/`forward()`; assert `hashchange` re-applies state without looping. | Each `history` step fires `hashchange` → `handleHashChange` re-applies the matching filter to the DOM; listener-call counts prove the cycle terminates after one round-trip (no infinite re-fire) thanks to Nanostores' `===` equality and the round-trip-idempotent bridge. |

### Loop prevention via real Nanostores

The parent spec's loop-prevention design **depends** on Nanostores' built-in
`===` equality to terminate the atom→hash→atom cycle, and on
`serialise(parse(hash))===hash` / `parse(serialise(atoms))===atoms`. Therefore the test
suite MUST use the real Nanostores library (no mock). Concretely:

- **No-mock assertion.** A test subscribes a listener to `$activeTag` (via
  `bridgeToHash` once installed), sets the atom to its **current** value, and
  asserts the listener does **not** re-fire (Nanostores short-circuits on
  `===`). Then it sets a genuinely different value and asserts the listener
  fires exactly once. Repeat for `$activeSearch` and `$activeCategory`.
- **Round-trip idempotence (indirect).** Because `parseHash`/`serialiseHash`
  are not exported and this spec does not refactor `state.js`, round-trip is
  asserted through the bridge: load hash `H` → `bridgeFromHash` → read the
  three atoms → trigger `bridgeToHash`'s write path → assert
  `window.location.hash === H`. This is run for all four cases (`#tag-…`,
  `#search-…`, `#category-…`, bare `#`/empty). The combination of "same-value
  set does not re-fire" + "bridge reproduces the load hash" is the indirect
  proof that `parse(serialise(atoms))===atoms` and that the cycle terminates.

### Isolation strategy for module-load side effects

`dom.js` (cache), `state.js` (`allCards` from `querySelectorAll`, atoms),
`tag-manager`/`modal-manager`/`sidebar-manager`/`card-manager` (the
`isLandingPage` page detection), `theme-manager` (`localStorage`), and
`entry-animator`/`filter-cards` (`document.body`/`data-entry-animation`) all
read external state **at import time**. ES modules are singletons in the
module registry: sourcing a module twice in one test run returns the same
cached instance with stale load-time state. Therefore every test that needs
a clean module must (a) clear the module registry and (b) re-seed the
jsdom globals **before** the import, then dynamically import.

The suite's **single mandatory pattern** is a shared setup file registered
via `test.setupFiles` and a small `loadFresh()` helper that every test uses
instead of top-level static imports:

```js
// tests/js/helpers/setup.js  (registered via test.setupFiles; runs per test file)
import { beforeEach } from 'vitest';

beforeEach(() => {
  vi.resetModules();                                   // (1) clear module registry
  document.documentElement.innerHTML = '';             // (2) reset DOM
  localStorage.clear();
  sessionStorage.clear();
  window.history.pushState({}, '', 'http://localhost/'); // (3) reset URL
  delete window.ALL_TAGS;                             // (4) clear build globals
  delete window.CATEGORY_MAP;
  // (5) jsdom polyfills installed once at setup; per-test reset is opt-in
});

export async function loadFresh(spec, { url, html, globals } = {}) {
  if (url)    window.history.pushState({}, '', url);   // set pathname + hash BEFORE import
  if (html)   document.documentElement.innerHTML = html;
  if (globals) for (const [k, v] of Object.entries(globals)) window[k] = v;
  return import(spec);                                 // fresh eval against reset DOM
}
```

Rules this pattern enforces:

1. **No top-level static imports of the modules under test** in test files.
   A static import evaluates once at file load against the first jsdom DOM
   and is then stale. Tests instead do
   `const { ModalManager } = await loadFresh('.../modal-manager.js', { url, html, globals })`
   inside each test. Because `vi.resetModules()` clears the registry, the
   module (and its whole transitive import graph — `dom.js`, `state.js`,
   the vendored Nanostores) re-evaluates against the freshly seeded DOM.
2. **The URL is the single knob for page detection.** `isLandingPage` /
   `isBrowsePage` are computed at import, so the `url` passed to `loadFresh`
   decides browse (`…/browse.html`) vs landing. Never mutate `window.location`
   after import — always pass it to `loadFresh`. (`window.history.pushState`
   is supported by jsdom and changes pathname+hash synchronously; this is
   the recommended consistent mechanism. An alternative is the
   `@vitest-environment jsdom` docblock pragma for a file-wide default URL,
   but per-test `loadFresh({ url })` is preferred for tests that switch
   pages.)
3. **Build globals** (`window.ALL_TAGS`, `window.CATEGORY_MAP`) are seeded
   via the `globals` argument, mirroring how `build.py` inlines them into
   `base.html`.

### Handling the gitignored vendored nanostores

`static/js/state.js` imports `'../vendor/nanostores.js'`, which is
gitignored — on a fresh clone the file does not exist. The tests must not
depend on running `poetry run acquire-js` first. The Vitest alias
(see [Test toolchain & config](#test-toolchain--config)) maps any
`…/vendor/nanostores.js` import to the real `nanostores` package installed
by `npm install` into `node_modules`.

Gotcha — **keep `nanostores` in BOTH `dependencies` and `devDependencies`:**

- `js_vendor.py` reads `dependencies.nanostores` to download the vendored
  file for the **build** (acquire-js still hits the network for the real
  file). Removing it from `dependencies` would break the build.
- Tests resolve the same library from `node_modules` via the alias, so it
  must also be a `devDependency` for `npm install` to place it there.

The alias `replacement` is the bare specifier `'nanostores'`, resolved by
Vite through the package's `exports`. The planner must verify the installed
`nanostores@<version>` entry actually exports `atom` and `computed` (it does
for the pinned 0.11.x). If bare-specifier resolution misbehaves, the fallback
is an explicit file path:

```js
replacement: fileURLToPath(new URL('./node_modules/nanostores/index.js', import.meta.url))
```

(adjust to the package's real `exports`/`module` entry). A pre-test
`npm install` is therefore required; this is the accepted, well-scoped
Node-dev-tooling trade-off called out in the parent spec.

### jsdom polyfills

jsdom lacks several APIs the code reads and the tests rely on. A single
`tests/js/helpers/jsdom-polyfills.js` is imported by `setup.js` and
installs the following before any test runs:

| API | Used by | jsdom behaviour | Required test shim |
|-----|---------|-----------------|--------------------|
| `IntersectionObserver` | `entry-animator` | **not provided** | A fake class with `observe`/`unobserve`/`disconnect` and a driveable registry (a module-level array of instances) so tests can invoke the callback with fabricated `entries` (each carrying `target`, `boundingClientRect`, `isIntersecting`). Tests call `__trigger(entries)` to drive in/out of view. |
| `requestAnimationFrame` | `entry-animator` (scroll safety-net) | jsdom may stub/omit | Stub to run the callback **synchronously** (`(cb) => { cb(0); return 0; }`) so the scroll safety-net's reveal logic is deterministic (or use `vi.useFakeTimers` + a rAF shim — synchronous is simpler). |
| `getBoundingClientRect` | `entry-animator`, `filter-cards` | jsdom returns all-zeros | Do NOT override globally (zeros is a valid "at origin" case). Override **per element** in the tests via `vi.spyOn(el, 'getBoundingClientRect').mockReturnValue({ top, bottom, left, right, width, height })` (a `setRect(card, {top, bottom})` helper) to drive in-viewport (`top < innerHeight && bottom > 0`) vs off-viewport branches. |
| `navigator.clipboard.writeText` | `modal-manager` (share) | **not provided** | Stub `navigator.clipboard.writeText` to return `Promise.resolve()` so the share-button handler's `.then` runs. |
| `scrollIntoView` | `tag-manager.highlightSuggestion` | jsdom stub is a no-op | No extra shim needed; assert it is called (or simply not assert) — the no-op is fine. |
| `Element.prototype.closest` | `handle-hash-change`, `entry-animator`, `sidebar-manager` | jsdom supports | None. |
| `history.pushState` / `hashchange` | many modules | jsdom supports | None — jsdom fires `hashchange` on `location.hash` assignment. |
| `matchMedia` | — | (not used by any module) | **No polyfill needed.** Confirmed: no module references `matchMedia`. |

## Acceptance criteria

1. `npm install && npm test` (and equivalently `npm run test:unit && npm
   run test:integration`) exits 0 with no `node_modules`/network needed
   beyond the initial install. The suite is fully offline once installed.
2. Every non-trivial export or method across the 13 modules has at least one
   passing unit test, enumerated in the [per-module coverage
   table](#per-module-unit-test-coverage). `state.js` in particular has unit
   tests for: atom get/set; `$visibleCards` filtering by tag, search, and
   category (and the all-null "show all" case); `$animatedIds` only-grows;
   `allCards` universe; `bridgeFromHash` parsing for all three prefixes plus
   the bare/`#`/empty case; `bridgeToHash` writing the matching hash and
   skipping a no-op write.
3. The nine parent-spec feature areas (filter, sort, modal, dark mode,
   sidebar, search suggestions, entry animation, URL hash deep-linking,
   browser back/forward) each have at least one passing jsdom integration
   test, enumerated in the [integration coverage
   table](#integration-test-coverage-parent-spec-ac-9-feature-areas).
4. Real Nanostores is used (no mock). A test asserts that setting an atom to
   its current value does **not** re-fire listeners (the loop-termination
   property), for `$activeTag`, `$activeSearch`, and `$activeCategory`. The
   indirect round-trip idempotence test passes for all four hash cases
   (`#tag-…`, `#search-…`, `#category-…`, bare `#`/empty).
5. No production-code changes are required to make tests pass: no test-only
   exports, imports, or branches are added to `static/js/`. (The only
   committed additions are `vitest.config.js`, `tests/js/**`, `package.json`
   entries, `.gitignore`'s `node_modules/` line, and the lockfile.)
6. The isolation pattern is actually used: tests import modules only via
   `loadFresh()` after `vi.resetModules()` + DOM/URL/global reset; running
   the whole suite is order-independent (no test pollutes another's module
   registry or jsdom DOM).

## Related specs

### Depends upon

- [`specs/refactors/js_state_model.md`](../refactors/js_state_model.md) —
  produced the modular `static/js/` layout under test. Its design decision 10
  and "Enables" section defer this spec; its non-regression AC 9 (nine
  feature areas) seeds this spec's integration tests; and its `package.json`
  `"type": "module"` justification authorises the dev Node toolchain.

### See also

- [`specs/tests/testing.md`](testing.md) — the implemented Python testing
  spec. Format/convention template (Requirements / Constraints / Acceptance
  criteria shape, test infra confined to `tests/`, no source-code leak) and
  the `unit`/`integration` marker philosophy mirrored here as Vitest
  projects.
- [`specs/refactors/src_layout_package.md`](../refactors/src_layout_package.md) —
  the one-concern-per-module precedent whose layout the JS modules mirror;
  shared structural conventions.

### Enables (future, out of scope here)

- A browser E2E spec (Playwright or equivalent) testing the built site in a
  real browser — explicitly out of scope for this spec; integration here is
  jsdom-only.
- A JSDoc / `@ts-check` spec adding type annotations and
  `tsc --noEmit --allowJs --checkJs` — the other follow-up named in
  `js_state_model.md`'s "Enables" section; benefits from the settled module
  layout this suite locks in.

## Open questions / risks

- **Lockfile / package manager.** Recommended: npm with a committed
  `package-lock.json`. Alternatives (pnpm + `pnpm-lock.yaml`) are viable but
  add a non-standard step; npm keeps the toolchain standard. *Flagged for
  user confirmation of the package manager choice.*
- **jsdom vs happy-dom.** Decided: **jsdom**. Required because the suite
  needs `getBoundingClientRect`/`IntersectionObserver` polyfilling and
  jsdom's `document`/`history` fidelity; happy-dom lacks several of these
  and would shift more of the surface onto shims. jsdom is also the
  environment the parent spec named in its deferral.
- **`getBoundingClientRect` stub strategy.** Decided: per-element
  `vi.spyOn` mocks via a `setRect(card, {top, bottom})` helper (NOT a global
  override), so the all-zeros default remains a valid in-test case and
  in-viewport vs off-viewport branches are driven explicitly.
- **Nanostores alias resolution.** The bare-specifier `'nanostores'`
  replacement is expected to resolve under Vite for the pinned 0.11.x; the
  planner must verify the package `exports` actually exposes `atom` and
  `computed` and fall back to the explicit `node_modules` entry path if not.
- **Vitest `--project` flag / `test.projects` key.** Both require Vitest 2.x
  (1.x used `test.workspace` and an earlier `--project`); the suite pins
  `vitest@^2.1.0`. Verify the installed version supports `test.projects`; if
  a pre-2.0 version is pinned, switch the config key to `workspace:` and/or
  fall back to the path-filter form (`vitest run tests/js/unit`).
- **Coverage.** Out of scope for the first cut; a later spec may add
  `@vitest/coverage-v8` and a `test:coverage` script.
- **`requestAnimationFrame` determinism.** A synchronous rAF stub is
  recommended for the entry-animator safety-net; if timing-sensitive
  behaviour needs asserting, `vi.useFakeTimers()` is the alternative. Not
  expected to block.

## Note on file paths

The `js_state_model.md` spec said the Vitest follow-up should "reuse the
existing `tests/fixtures/` directory." As implemented, the Python suite does
not use `tests/fixtures/` for that purpose: it reads from
`data/testdata/` (via `tests/conftest.py`), and `tests/fixtures/` currently
holds unrelated Python-test fixtures (`design/`, `markdown/`,
`e2e-config.yaml`).

This spec therefore places JS fixture documents at `tests/js/fixtures/`
rather than `tests/fixtures/`, to avoid colliding with the existing Python
fixtures and to keep the JS suite self-contained under `tests/js/`
(`unit/`, `integration/`, `fixtures/`, `helpers/`). This is a deliberate
reconciliation with the parent spec's wording, not a contradiction of its
behavioural intent.