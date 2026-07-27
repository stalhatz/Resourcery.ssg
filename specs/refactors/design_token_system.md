---
size: big
modified_date: 2026-07-27
implemented_git_tag: specs/refactors/design_token_system/implemented
---

# Modern Design Token System (redesign of `design.json` vocabulary)

## Introduction

`data_design_split.md` split design out of `site.config.json` into `design.json`,
validated by `schemas/design.schema.json` and emitted by the LLM via
`prompts/ingest-design.md`. That split was about *file structure*, not the
*token vocabulary*. This spec redesigns that vocabulary so the generated theme
gives the LLM **more leeway WITH guidance**, produces a coherent design system
(palettes, ramps, spacing, motion) instead of a flat colour list, fixes known
CSS defects, and enforces accessibility. It is **complementary** to
`data_design_split.md` (we do not re-split files; we improve the content of the
already-split `design.json`).

## Current state

Concrete critique of today's design surface:

- **Flat palette, no ramps.** `design.schema.json` exposes 9 anchor hex colours
  plus an optional `dark` block. `style.css` maps them 1:1 to CSS vars
  (`--color-primary`, …). There is no tonal ramp, so cards/modals can't express
  hover/focus/subtle states derived from the brand.
- **Hardcoded overlays blind to brand.** Overlays, scrims, focus rings, and
  borders use literal `rgba(0,0,0,x)` / `rgba(255,255,255,x)`
  (e.g. lines 101, 107, 242, 295, 346, 446, 471, 591, 729–734, 832, 935, 964,
  1048, 1239, 1338). These ignore `--color-primary`/`--color-accent`, so a
  strongly-branded site still renders neutral-black scrims.
- **Undefined variable bug.** `style.css` lines 540–541 reference
  `rgba(var(--color-accent-rgb), …)`, but `--color-accent-rgb` is **never
  defined** anywhere — the filter-trigger hover/focus styles silently fail.
- **No spacing scale.** All spacing is hardcoded `rem`/`px` (e.g. `1.25rem`,
  `0.6rem`, `1.5rem`). Refactoring density means editing dozens of literals.
- **Heading sizing is a single multiplier.** `heading_size_scale` (0.8–1.5)
  only multiplies a few `calc(...)` sizes. No modular type scale; body/spacing
  rhythm is disconnected.
- **Enum-locked global radius/shadow/border.** `border_radius`,
  `shadow_intensity`, `border_treatment` are enums applied globally. You cannot
  give cards a different radius from buttons, nor cards a different elevation
  from modals/dropdowns.
- **`transition: all` anti-pattern.** `--transition: all 0.3s ease` (line 67)
  plus `transition: var(--transition)` on body, sidebar, main-content, links,
  etc. Animates *every* property, causing jank and ignoring reduced-motion.
- **WCAG unenforced.** `validate.py` only checks hex *format* and a few effect
  *warnings*. It never verifies text/background contrast, so an invalid palette
  passes validation and ships inaccessible.

## Target state

A LLM-authored `design.json` that:

1. Declares **anchor colours + range levers**; build time generates full colour
   ramps and brand/neutral-aware semantic tokens (overlays, borders, subtle
   bg, on-color text, `--color-accent-rgb`).
2. Declares **typographic scales** (`type_scale_ratio`, line-heights, measure)
   that generate `--font-size--1..6`; keeps `heading_style` enum but adds
   explicit `heading_weight` / `heading_letter_spacing` overrides.
3. Introduces **spacing**, **radius**, **elevation**, **border**, and
   **motion** as ranges/scales with sensible defaults, replacing hardcoded
   literals and global enums.
4. Keeps high-level "personality" enums (`heading_style`, `card_style`,
   `hover_effect`) for LLM convenience, but they now *consume derived tokens* so
   they are palette-aware and functional.
5. Rewrites `style.css` into a token-consuming design system: every visual
   decision reads a CSS variable; transitions are scoped to specific
   properties; per-element radius/shadow are distinct.
6. `validate.py` rejects palettes failing WCAG contrast and any range value
   outside its bounds, before build.

The net effect: more expressive themes with bounded, well-guided freedom, and
a maintainable, accessible stylesheet.

## Design decisions

1. **Scope bundle (locked).** This spec covers, together:
   (a) redesign of `design.schema.json` token vocabulary,
   (b) rewrite of `prompts/ingest-design.md` to guide the LLM with ranges +
   constraints + examples,
   (c) rewrite of `templates/style.css` into a token-consuming design system,
   (d) additions to `src/resourcery_ssg/validate.py` for accessibility/contrast
   and range validation.
2. **Hybrid leeway model (locked).** Keep a few high-level personality enums the
   LLM is good at (`heading_style`, `card_style`, `hover_effect`) for
   convenience, but add continuous **ranges / scales** for fine-grained tokens.
   Goal = "more leeway WITH guidance," not unbounded freedom.
3. **Breaking change (locked).** This is a **BREAKING** change to
   `design.schema.json`. No backward compatibility. Existing `design.json`
   files may fail validation; migration = regenerate via the pipeline.
   Explicitly stated in schema `description` and prompt.
4. **Contrast + range enforcement (locked).** `validate.py` MUST enforce:
   - `text` on `background` ≥ 4.5:1
   - `text_muted` on `background` ≥ 3:1
   - `primary` used as text or on `background` meets the appropriate ratio
     (4.5:1 as text, 3:1 as a large UI component / focus indicator)
   - `accent` where used as text meets 3:1 (large) or 4.5:1 (normal)
   - all range values fall within their declared bounds
   - reject failing palettes with a clear, actionable message
5. **Generated-at-build ramps (locked).** Colour ramps
   (`--color-primary-50..900`, `--color-neutral-0..1000`) and the derived
   semantic tokens are **generated at build time** (via `color-mix()` in CSS or
   a small helper in `build.py`), not authored by the LLM. The LLM supplies
   anchors + the three levers; the build derives the rest. This keeps the LLM
   prompt small and the output deterministic.
6. **Complementary, not overlapping.** This spec modifies the *content* of the
   `design.json` file introduced by `data_design_split.md`; it does not revisit
   the file split. Cross-link the two specs.

## Proposed new `design.schema.json` token shape (concrete)

Intended property set (illustrative; exact JSON is the builder's job, but the
contract is fixed here):

```jsonc
{
  "theme": {
    "colors": {
      "primary":   "#hex", "accent": "#hex", "background": "#hex",
      "surface":   "#hex", "text": "#hex", "text_muted": "#hex",
      "secondary": "#hex", "error": "#hex", "success": "#hex",
      "dark": { "primary"?, "accent"?, "background"?, "surface"?,
                "text"?, "text_muted"?, "secondary"?, "error"?, "success"?,
                "auto"?: true },   // auto: derive dark ramp from levers
      "levers": {
        "brand_saturation":  { "type": "number", "minimum": 0, "maximum": 1, "default": 0.8,
          "description": "0 = fully desaturated/neutral brand, 1 = maximally saturated primary/accent." },
        "neutral_temperature": { "type": "number", "minimum": -1, "maximum": 1, "default": 0,
          "description": "-1 = cool grays (blue-tinted), 0 = true neutral, +1 = warm grays (beige-tinted)." },
        "shade_spread": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.6,
          "description": "0 = narrow ramp (low contrast between 50 and 900), 1 = wide spread (high depth)." },
      "overlay_strength": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.7,
        "description": "Strength/opacity of derived image-overlay scrims (0 = no scrim, 1 = maximum). Drives the alpha of --color-overlay so the cinematic card treatment is tunable per theme." }
    },
    "typography": {
      "font_family":   "stack", "heading_font": "stack",
      "font_size_base": { "type": "number", "minimum": 14, "maximum": 20, "default": 16,
        "description": "Body base font size in px (e.g. 16). Hard-bounded 14–20 so small models cannot emit extreme sizes; the build emits it as '<n>px'." },
      "type_scale_ratio": { "type": "number", "minimum": 1.125, "maximum": 1.5, "default": 1.25,
        "description": "Modular scale ratio. Build generates --font-size--1..6 = base * ratio^n." },
      "body_line_height":   { "type": "number", "minimum": 1.4, "maximum": 1.8, "default": 1.6 },
      "heading_line_height":{ "type": "number", "minimum": 1.0, "maximum": 1.3, "default": 1.15 },
      "measure": { "type": "number", "minimum": 60, "maximum": 75, "default": 68,
        "description": "Optimal line length in ch for body copy." },
      "heading_weight": { "type": "integer", "minimum": 300, "maximum": 900, "default": 700,
        "description": "Overrides the heading_style enum weight when set." },
      "heading_letter_spacing": { "type": "string", "pattern": "^[-+]?[0-9.]+em$",
        "default": "0",
        "description": "Overrides the heading_style enum letter-spacing. Valid range -0.04em..0.12em; bounds are enforced by the custom em-parser in validate_design_tokens() (JSON-Schema min/max do NOT apply to string types), not by schema min/max." }
      // NOTE: heading_size_scale is REMOVED in favour of type_scale_ratio.
    },
    "spacing": {
      "space_base": { "type": "integer", "enum": [4, 8], "default": 8,
        "description": "Base spacing unit in px. Build emits --space-1..8 = base * n." },
      "space_ratio": { "type": "number", "minimum": 1.5, "maximum": 2, "default": 1.5,
        "description": "Geometric spacing ratio; alternative to fixed space_base." }
    },
    "radius": {
      "radius_base": { "type": "number", "minimum": 0, "maximum": 16, "default": 8,
        "description": "Base corner radius in px. Build emits --radius-sm/md/lg/xl." },
      "radius_card":    "px?", "radius_button": "px?", "radius_pill": "px?",
      "description": "Optional per-element overrides; default to radius_base-derived steps."
    },
    "elevation": {
      "shadow_strength": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.35,
        "description": "0 = flat, 1 = maximum depth. Drives --shadow-1..4 alpha." },
      "shadow_softness": { "type": "number", "minimum": 0, "maximum": 1, "default": 0.5,
        "description": "0 = tight/hard shadow, 1 = large/soft blur." }
      // NOTE: shadow_intensity enum is REMOVED.
    },
    "border": {
      "border_width": { "type": "number", "minimum": 0, "maximum": 2, "default": 1,
        "description": "Structural border width in px." },
      "border_style": { "type": "string", "enum": ["solid", "none"], "default": "solid" },
      "border_color": { "type": "string", "description":
        "Optional explicit border color; default derived from neutral ramp (--color-border*)." }
      // NOTE: border_treatment enum is REMOVED; border_color defaults to neutral ramp.
    },
    "motion": {
      "transition_duration": { "type": "number", "minimum": 120, "maximum": 360, "default": 200,
        "description": "Base transition duration in ms." },
      "transition_easing": { "type": "string",
        "enum": ["ease", "ease-in-out", "ease-out", "linear", "material-standard", "snappy"],
        "default": "ease-out",
        "description": "Curated easing curves only — no raw cubic-bezier from the LLM." }
    },
    "effects": {   // personality enums RETAINED (hybrid model)
      "heading_style": { "enum": ["natural","editorial","elegant","uppercase"], "default": "natural" },
      "card_style":    { "enum": ["image-overlay","flat","outlined","elevated"], "default": "image-overlay" },
      "hover_effect":  { "enum": ["none","lift","glow","outline"], "default": "lift" }
      // card_style/hover_effect CSS now consume derived tokens (see style.css section).
    }
  }
}
```

`theme_constants.py` must be extended: when `heading_weight` /
`heading_letter_spacing` are present they override the enum-derived values from
`HEADING_STYLE_CONFIG`; the Google-fonts weight list is taken from the effective
weight (max of enum default and override).

## Prompt (`ingest-design.md`) changes

Rewrite the prompt from an enum-checklist into a **guided token authoring**
prompt:

- Keep the "strictly adhere to schema / don't invent fields" rule.
- Replace the colour prose with **ranges + constraints + examples**: for each
  lever (`brand_saturation`, `neutral_temperature`, `shade_spread`,
  `overlay_strength`) give the valid range, the default, and 2–3 example values
  with the resulting mood
  ("brand_saturation 0.3 → restrained, corporate; 1.0 → vivid, creative").
- Provide **recommended value bands** for every numeric token (matching schema
  bounds) so small models pick valid defaults without search.
- Add an explicit **accessibility instruction**: "Choose `text`, `text_muted`,
  `primary`, `accent` such that they meet the stated WCAG ratios against
  `background`; `validate.py` will reject failing palettes." Include the exact
  ratio table.
- Keep the pre-submission checklist but extend it: every range value within
  bounds, contrast ratios satisfied, no references to removed fields
  (`heading_size_scale`, `shadow_intensity`, `border_radius`, `border_treatment`).
- Note the **breaking change**: existing `design.json` must be regenerated.

Per CONTRIBUTING.md #8, every `description` in the schema is itself prompt
guidance — so the schema rewrite and the prompt rewrite are two views of the
same guidance and must stay in sync.

## `style.css` rewrite principles

1. **Token consumption only.** No hardcoded hex/rgba in component rules. Every
   colour reads a var: anchors, ramps, or semantic tokens.
2. **Derived semantic tokens** (generated at build): `--color-border`,
   `--color-border-strong`, `--color-overlay` (brand/neutral-aware, replacing
   all `rgba(0,0,0,x)`/`rgba(255,255,255,x)` scrims), `--color-primary-subtle`
   (hover/focus bg), `--color-on-primary`, and **`--color-accent-rgb`** (fixes
    the undefined-variable bug at lines 540–541). Filter-trigger hover/focus use
    these. The alpha of `--color-overlay` is driven by the `overlay_strength`
    lever so the scrim depth is tunable per theme.
3. **Scoped transitions.** Remove `--transition: all`. Replace with
   `--transition-fast`/`--transition-base` scoped to specific properties
   (`transition: background-color var(--transition-base), transform
   var(--transition-base)`). Honour `prefers-reduced-motion`.
4. **Per-element radius/shadow.** Cards use `--radius-md`/`-lg` and
   `--shadow-2`; modals `--shadow-4`; dropdowns `--shadow-3`; buttons
   `--radius-button`. Distinct, not one global enum.
5. **Spacing scale.** Replace rem literals with `--space-1..8`.
6. **Personality enums consume tokens.** `card_style` / `hover_effect` blocks
   reference derived tokens so they remain palette-aware (e.g. `glow` uses
   `--color-primary`, `outline` uses `--color-border-strong`).
7. **Type scale.** Headings use `--font-size--N` from `type_scale_ratio`; body
   uses `--font-size-base` and `--measure`.

## `validate.py` contrast/range additions

Add a `validate_design_tokens()` step (runs only after schema validation
passes):

- **Range check:** for every numeric token under `colors` (the `levers` block and
  `overlay_strength`; anchors excluded), `typography.*`, `spacing.*`, `radius.*`,
  `elevation.*`, `border.*`, `motion.*`, assert `minimum ≤ value ≤ maximum` (or
  enum membership). `font_size_base` (14–20) and `heading_letter_spacing`
  (-0.04em..0.12em) are covered — the latter via a custom em-parser since it is a
  string type. Emit errors, not warnings.
- **Contrast check:** compute relative luminance for `text`, `text_muted`,
  `primary`, `accent`, `background` (and the `dark` block when present), and
  assert:
  - `text`/`background` ≥ 4.5:1
  - `text_muted`/`background` ≥ 3:1
  - `primary` as text on `background` ≥ 4.5:1; as large UI/focus ≥ 3:1
  - `accent` as text ≥ 4.5:1 (normal) / 3:1 (large)
  - Fail the build with the offending pair + measured ratio.
- Reuse existing `_is_valid_hex_color` for anchors.
- Remove the old `validate_effects` enum-pair warnings that referenced removed
  enums (`shadow_intensity`, `border_treatment`, `border_radius`); replace with
  checks that apply to the new model (e.g. `card_style: outlined` with
  `border_width: 0` is contradictory → warning).

## Migration (breaking change)

- **No backward compatibility.** Bump the schema; old `design.json` fails
  schema + range/contrast validation.
- Migration path = **regenerate** `design.json` through the pipeline
  (`orchestrate.py` Step 6 / `ingest-design.md`). Manual edit is not supported.
- Document the removed fields mapping for humans reviewing diffs:
  `heading_size_scale` → `type_scale_ratio`; `shadow_intensity` →
  `elevation.shadow_strength`; `border_radius` → `radius.radius_base` (+overrides);
  `border_treatment` → `border.border_width`/`border_style`/`border_color`.
- `theme_constants.py` callers must handle optional `heading_weight` /
  `heading_letter_spacing` overrides.

## Acceptance criteria

- [ ] `design.schema.json` exposes the token shape in "Proposed new
      `design.schema.json` token shape" and is valid draft-07.
- [ ] `prompts/ingest-design.md` guides ranges + contrast and mentions the
      breaking change; an LLM following it produces schema-valid, in-range,
      contrast-passing `design.json`.
- [ ] `templates/style.css` contains no hardcoded brand-ignorant
      `rgba(0,0,0,x)`/`rgba(255,255,255,x)` overlays; defines and uses
      `--color-accent-rgb`; uses `--space-*`, `--radius-*`, `--shadow-*`; has no
      `transition: all`.
- [ ] `validate.py` rejects out-of-range values and WCAG-failing palettes with
      actionable messages; passes a known-good and a known-bad fixture.
- [ ] Existing `design.json` (old vocabulary) fails validation, confirming the
      breaking change.
- [ ] `theme_constants.py` honours `heading_weight` / `heading_letter_spacing`
      overrides and supplies correct font weights to the downloader.

## Open questions / risks

- **Small-model LLM-friendliness tension.** `data_design_split.md` eventually
  targets small local models. The richer vocabulary (more numeric fields) is
  harder for tiny models to satisfy than a few enums. Mitigation: keep every
  field optional with a sensible `default`; the prompt gives example values and
  bounded ranges so the model can omit-and-accept-default. Risk remains that
  small models emit out-of-range numbers — the range validator catches and the
  retry-with-feedback loop (from `data_design_split.md`) corrects them.
- **Build-time ramp generation cost/complexity.** `color-mix()` browser support
  vs a Python helper in `build.py`. Decide in implementation; either is
  acceptable per decision #5.
- **Dark mode derivation.** Should `dark` be fully LLM-specified or derived from
  levers via `dark.auto`? Recommend `auto: true` default with optional overrides.
- **Reduced-motion defaults.** Confirm `prefers-reduced-motion` disables
  transform/opacity transitions globally.

## Related specs

### Depends upon
- [refactors/data_design_split.md](data_design_split.md) – established the
  `design.json` file (and its schema) that this spec re-vocabularises. This spec
  is **complementary**: it does not re-split files, it redesigns the token
  content of the already-split `design.json`. Build/runtime must already merge
  `design.json` into the template context.

### Enables
- Future specs on theming/branding refinements, per-section theming, and
  user-editable theme tweaks (once a stable token contract exists).

### Extends
- (none)

### Supersedes
- (none — note: it *removes* fields `heading_size_scale`, `shadow_intensity`,
  `border_radius`, `border_treatment` from `design.schema.json`, but does not
  supersede `data_design_split.md` itself).
