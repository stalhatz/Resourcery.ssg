---
size: small
implemented_git_tag: specs/feats/card_entry_animation.md/implemented
---

# Card Entry Animation

## Introduction

Cards on the generated site currently all animate in at once on page load via a blanket `animation: fadeIn ...` rule. This works for the initial render, but creates two issues:

1. **No scroll-triggered animation.** Cards below the fold animate invisibly (they enter already animated) before the user scrolls to them. The initial burst of ~50 simultaneous animations also risks jank on low-end devices.
2. **No re-animation after filtering.** When `filterCards()` hides a card (via `display: none`) and then re-shows it, the CSS animation does **not** re-trigger — the card just pops into view statically.

This spec adds a configurable entry-animation system that animates cards individually as they enter the viewport (IntersectionObserver) and re-triggers the animation whenever a filtered card reappears. The animation style is exposed as a new `entry_animation` enum in the `effects` block of `design.json`, making it configurable by the LLM.

## Current state

- `templates/style.css` lines 1362–1370 defines `@keyframes fadeIn` (opacity 0→1 + translateY(10px→0)) and applies it globally: `.link-card { animation: fadeIn 0.3s var(--motion-easing) forwards; }`. Every card animates identically and simultaneously on page load.
- `static/js/main.js` `filterCards()` (lines 756–812) toggles `card.style.display` between `''` and `'none'`. When a card goes from `display: none` → `display: ''`, the browser does **not** replay CSS animations — the card appears instantly.
- `schemas/design.schema.json` `effects` block (lines 348–370) defines `card_style`, `hover_effect`, and `heading_style` enums. No `entry_animation` property exists.
- `prompts/ingest-design.md` §"Personality Enums (effects)" (lines 144–171) lists the three existing enums. No `entry_animation` is mentioned.
- `prefers-reduced-motion` is already respected via the global reset at lines 160–165 of `style.css` (forces `animation-duration: 0.01ms !important`), but also carries card-specific overrides for hover transforms. The global reset already covers entry animations — no additional CSS is needed for reduced motion.

## Target state

### 1. New `entry_animation` enum in `effects`

The `effects` block of `design.schema.json` gains an optional `entry_animation` property:

| Value | Visual effect | CSS equivalent |
|-------|--------------|----------------|
| `none` | Cards appear immediately, no animation | No animation class added |
| `fade` | Opacity fade only | `opacity: 0 → 1` |
| `slide-up` | Vertical slide only | `translateY(20px → 0)` |
| `fade-slide-up` | Opacity fade + vertical slide | `opacity: 0 → 1` + `translateY(20px → 0)` |

- **Default:** `fade-slide-up` — matches the closest to the current `fadeIn` (which does both opacity and translateY), and is the most popular, unobtrusive choice.
- This is a **non-breaking addition**: existing `design.json` files without `entry_animation` silently get `fade-slide-up`.
- The `validate.py` range/enum checks already cover effects enums; `entry_animation` is added to the enum set. No new validation logic is needed.

### 2. CSS changes (`templates/style.css`)

**Remove** the blanket `.link-card { animation: fadeIn ... }` at line 1370.

**Define** a new set of `@keyframes` and animation classes, keyed by the `entry_animation` value. The build passes the chosen value as a `<body>` data attribute or CSS class (e.g., `data-entry-animation="fade-slide-up"`) so a single set of CSS rules can vary per animation type.

Concrete CSS contract (implementer chooses the exact naming and organisation):

- `@keyframes entry-fade` — `opacity: 0 → 1`
- `@keyframes entry-slide-up` — `transform: translateY(20px) → translateY(0)`
- `@keyframes entry-fade-slide-up` — combined opacity + translateY
- Class `.link-card--enter` (or equivalent) triggers the appropriate animation via:
  ```css
  .link-card--enter { animation: <keyframe-name> var(--motion-duration) var(--motion-easing) forwards; }
  ```
  The `<keyframe-name>` is resolved at build time in the CSS template or via a data-attribute selector.

The existing `@keyframes fadeIn` (lines 1365–1368) may be kept or removed at the implementer's discretion — if kept, it should not be referenced by any rule.

No changes needed to the `prefers-reduced-motion` block (lines 160–184). The global `animation-duration: 0.01ms !important` already suppresses all entry animations for users who prefer reduced motion.

### 3. JS changes (`static/js/main.js`)

**New: `EntryAnimator` module** (or equivalent integration into `CardManager` / standalone function). Responsibilities:

1. **On page load (`DOMContentLoaded`):**
   - Query all `.link-card` elements.
   - Observe them via a single `IntersectionObserver` with a reasonable threshold (e.g., `threshold: 0.05` or `rootMargin: "0px 0px -40px 0px"` for a subtle offset).
   - When a card enters the viewport:
     - Add the animation class (e.g., `.link-card--enter`) to trigger the CSS animation.
     - Unobserve that card (animation runs once per card instance, not on every scroll).
   
2. **Initial-viewport cards:** Cards already intersecting the viewport on first observation should fire immediately (possibly with a staggered delay for visual rhythm, but the spec does not mandate staggering — the implementer may add a small CSS `animation-delay` cascade, e.g., via `nth-child` or a JS-calculated staggered index).

3. **Re-animation after filtering:** In `filterCards()`, when a card transitions from `display: none` to visible:
   - Remove the `.link-card--enter` class if present.
   - Force a reflow (e.g., `void element.offsetWidth` or `requestAnimationFrame`).
   - Re-add `.link-card--enter` to replay the animation.
   
   This replaces the current direct `card.style.display = ''` toggle for matched cards. The implementer may choose to keep a separate CSS class for visibility control or use the existing `display` toggle combined with the reflow trick.

4. **One animation per instance:** The `IntersectionObserver` callback unobserves each card after its first intersection. The animation only replays via the filterCards re-animation path, not on repeated scrolls.

5. **Respect `prefers-reduced-motion`:** No JS change required — the CSS already suppresses animations. The `IntersectionObserver` should still add the class (it's harmless when animation is suppressed), or the JS may skip entirely if `window.matchMedia('(prefers-reduced-motion: reduce)').matches`. The implementer chooses the simpler approach (the CSS-only approach of adding the class regardless is fine).

**Changes to `filterCards()` (line 756):**
- On the matched-card branch (`card.style.display = ''`), introduce the re-animation logic described above. The `display: none` branch is unchanged.
- `filterCards()` is called from many places (search, tag, category, dropdowns, hash changes). All paths benefit automatically.

### 4. Schema changes (`schemas/design.schema.json`)

Inside `properties.theme.properties.effects.properties`, add:

```json
"entry_animation": {
  "type": "string",
  "enum": ["none", "fade", "slide-up", "fade-slide-up"],
  "default": "fade-slide-up",
  "description": "Entry animation for link cards when they first appear (scroll into viewport or reappear after filtering). 'none' disables entry animation entirely."
}
```

No changes to the `required` arrays — `entry_animation` is optional with a default.

### 5. Prompt changes (`prompts/ingest-design.md`)

In §"🎭 Personality Enums (effects)", add a row to the enum table and a brief guide entry:

| Field | Valid Values | Default | Use For |
|-------|-------------|---------|---------|
| `entry_animation` | `none`, `fade`, `slide-up`, `fade-slide-up` | `fade-slide-up` | Card entry motion when scrolling or after filtering |

Guide text:
> - `none`: Cards appear instantly. Clean and minimal.
> - `fade`: Gentle opacity fade. Subtle and lightweight.
> - `slide-up`: Cards rise from below. Playful and dynamic.
> - `fade-slide-up`: Combined fade + slide (default). The most common and versatile choice.

Update the pre-submission checklist to include `entry_animation` in the list of valid enum values.

### 6. No changes required to other files

- `build.py` / `token_gen.py`: No changes needed. The `entry_animation` value is consumed at runtime by JS/CSS, not at build time.
- The build already passes the full `theme` object into the template context. The CSS template renders the animation keyframe selector based on the value, or the JS reads it from a data attribute.

## Design decisions

1. **CSS-driven animation, JS-driven trigger.** The animation itself (`@keyframes`, duration, easing) lives in CSS, consuming the existing `--motion-duration` and `--motion-easing` tokens. JS only adds/removes the trigger class. This keeps animation timing in the design system where it belongs.

2. **Non-breaking addition.** Adding `entry_animation` to the `effects` enum with a default of `fade-slide-up` means existing sites upgrade seamlessly — the old behaviour (fade + slide) is preserved by default. No migration needed.

3. **Once-per-card via IntersectionObserver + unobservation.** Using unobserve after first intersection avoids wasted CPU on repeated intersection checks. The re-animation after filtering is the only path that re-triggers, and it's intentional user-driven action.

4. **Single animation class instead of per-value classes.** The CSS contract uses a single `.link-card--enter` class; the actual `@keyframes` name is resolved at build time (via a data attribute or template variable). This keeps the JS simple — it always adds/removes the same class.

5. **Reflow-forcing for filterCards re-animation.** CSS animations do not replay when an element transitions from `display: none` to visible. The standard fix (remove class → reflow → add class) is well-documented and reliable. The spec does not micro-manage the exact reflow mechanism but constrains it to work.

## Acceptance criteria

1. **Default behaviour preserved.** With no `entry_animation` in `design.json`, cards animate with fade + slide-up on page load (same visual as current `fadeIn`), timed by `--motion-duration` and `--motion-easing`.

2. **Scroll-triggered animation.** Cards below the initial viewport do not animate until the user scrolls them into view. Once animated, they do not re-animate on subsequent scroll passes.

3. **Re-animation on filter.** After a filtering action (category change, tag click, search) that hides and then re-shows a card, the card animates in again.

4. **All four enum values work.** Setting `entry_animation` to `none`, `fade`, `slide-up`, or `fade-slide-up` produces the correct visual effect. `none` suppresses all entry animation (cards appear instantly).

5. **prefers-reduced-motion respected.** Users with `prefers-reduced-motion: reduce` see no entry animations (the existing global CSS override handles this; verify no regression).

6. **No regression on existing interactions.** Card click-to-open modal, hover effects, sort, category dropdowns, tag search, hash-based deep linking — all continue to work with entry animations integrated.

7. **No new build-time dependencies.** The feature is entirely CSS + JS, consuming existing design tokens. No Python changes are needed.

8. **Schema validation passes.** A `design.json` with `entry_animation: "slide-up"` validates; one with `entry_animation: "zoom"` (invalid value) fails schema validation.

## Open questions / risks

1. **Staggered delay.** Should cards in the initial viewport have a staggered `animation-delay` (e.g., 30–50ms apart) for a polished cascade effect, or should they all start simultaneously? The current behaviour is simultaneous (all cards get the same `animation` rule). A staggered delay would be more polished but adds complexity. **Decision: left to the implementer.** If implemented, staggering must use CSS `animation-delay` only (no JS timers), derived from the card's index in the DOM. The `prefers-reduced-motion` override already strips `animation-delay` via the duration override.

2. **Interaction with `sortCards()`.** When the user changes the sort order, `sortCards()` reorders DOM nodes (lines 814–837). Moving a previously-animated card in the DOM does not inherently re-trigger its animation. This is acceptable behaviour — the card keeps its current visual state (no re-animation on sort). If the user wants re-animation on sort, it would require a separate feature.

3. **filterCards re-animation performance.** Forcing a reflow on each matched card during `filterCards()` could be expensive with many cards (e.g., 50+). Mitigation: the reflow is needed only for matched (visible) cards, and `filterCards()` already iterates over all cards. The implementer should batch or use `requestAnimationFrame` to avoid layout thrashing. This is a performance constraint, not a correctness one.

4. **Animations and card `display` state.** The current `filterCards()` uses `display: ''` / `display: 'none'`. The implementer may choose to use a CSS class for visibility instead (e.g., `.link-card--hidden { display: none; }`) to make the re-animation logic cleaner. Either approach is acceptable as long as the acceptance criteria are met.

## Related specs

### Extends
- [specs/refactors/design_token_system.md](../refactors/design_token_system.md) — this spec adds `entry_animation` to the `effects` block established by the design token system, and consumes its existing `motion` tokens (`--motion-duration`, `--motion-easing`) for animation timing.

### Depends upon
- (none — the design token system is already implemented, and the CSS/JS patterns this feature builds on exist in the current codebase.)

### See also
- [specs/feats/build_attribution.md](build_attribution.md) — reference for spec structure and level of detail.

## Technical details

- The `entry_animation` value must be accessible from both CSS (at template render time) and JS (at runtime). The simplest approach is to render it as a `<body>` data attribute in `base.html`: `<body data-entry-animation="{{ theme.effects.entry_animation | default('fade-slide-up') }}">`. The JS reads it once, and the CSS uses attribute selectors (e.g., `[data-entry-animation="fade-slide-up"] .link-card--enter { animation: entry-fade-slide-up ... }`).
- The existing `@keyframes fadeIn` at line 1365 uses `translateY(10px)`. The new keyframes use `translateY(20px)` as specified in the enum table. If the implementer prefers keeping 10px for visual continuity with the existing site, they may adjust — the spec only constrains that `slide-up` and `fade-slide-up` use translateY, not the exact pixel value.
- The implementer should verify that the IntersectionObserver polyfill is not needed (browsers supported by this project — modern Chromium, Firefox, Safari — all support IO natively). No polyfill is required.
- The `prefers-reduced-motion` block at lines 160–165 already overrides `animation-duration: 0.01ms !important`. This will effectively suppress entry animations. The block also has card-specific transform overrides (lines 167–170) that remain unchanged.
