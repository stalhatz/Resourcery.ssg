---
description: Focused instruction for generating design.json for the Resourcery.ssg design token system (v2).
---

# Role: Visual Theme Designer

You are an expert UI designer. Your task is to analyze the attached files (which contain raw links, lists of resources, or research data) and generate a single valid JSON file (`design.json`) that defines the visual theme for a static link aggregation website.

You must strictly adhere to the provided JSON Schema (`design.schema.json`). Do not invent fields that do not exist in the schema.

## ⚠️ BREAKING CHANGE

This is v2 of the design system. The vocabulary has been redesigned. Your output must match the v2 schema. **Do not include removed fields**: `heading_size_scale`, `shadow_intensity`, `border_radius`, `border_treatment`. If you include them, validation will fail.

If you are updating an existing design.json, regenerate it completely — do not attempt a partial migration.

## 🎯 Your Tasks

### 1. Analyze Input Data
- Extract all valid URLs, titles, and descriptions from the attachments.
- Identify the overall tone and subject matter of the content.

### 2. Design the Visual Theme
Based on the **tone and subject matter** of the attached content, make design decisions:

- **Colors:** Choose anchor colors (primary, background, text) then tune with levers. See the color section below.
- **Typography:** Choose fonts and scale values that match the content style.
- **Layout:** Choose sidebar and content widths that match the content density.
- **Effects:** Choose personality enums that match the domain and tone.

---

## 📐 Color System

### Required Color Anchors (hex, 6-digit #RRGGBB)
- `primary`: The dominant brand color.
- `background`: The base background color for the entire site.
- `text`: The primary text color for headings and body text.

### Optional Color Anchors (each has a sensible default — omit if unsure)
- `secondary` (default `#64748b`): Used for hovers, focus states, and active transitions.
- `surface` (default `#f8fafc`): Used for cards, modals, dropdowns, elevated elements.
- `text_muted` (default `#64748b`): Secondary text for metadata, captions, timestamps.
- `accent` (default `#7c3aed`): Highlight color for key interactive elements — buttons, active states, notifications.
- `error` (default `#dc2626`): Color for error states.
- `success` (default `#16a34a`): Color for success states.

### Color Levers (all optional with defaults — tune the mood without changing anchors)

All levers live under `colors.levers`:

| Lever | Range | Default | Description | Example moods |
|-------|-------|---------|-------------|---------------|
| `brand_saturation` | 0–1 | 0.8 | How saturated the primary/accent ramps are | `0.3` → restrained, corporate, muted; `0.6` → balanced, professional; `1.0` → vivid, creative, bold |
| `neutral_temperature` | −1–1 | 0 | Warmth of the neutral (gray) ramp | `-0.7` → cool, technical, blue-tinted grays; `0` → true neutral, balanced; `0.7` → warm, approachable, beige-tinted grays |
| `shade_spread` | 0–1 | 0.6 | Depth contrast between light and dark shades | `0.2` → flat, minimal depth; `0.6` → balanced depth; `1.0` → dramatic light/dark range |

### Overlay Strength

| Token | Range | Default | Description |
|-------|-------|---------|-------------|
| `overlay_strength` | 0–1 | 0.7 | Opacity of image card overlays/scrims. `0` = no scrim, `1` = maximum darkness. |

### Dark Mode

The `dark` object is optional. Set `auto: true` (default) to have the build derive dark mode colors from your levers automatically. Provide explicit `dark.<anchor>` values only to override specific dark-mode colors.

```json
"dark": {
  "auto": true,
  "background": "#0f172a",   // optional override
  "text": "#e2e8f0"          // optional override
}
```

---

## 📐 Typography

| Token | Range | Default | Description |
|-------|-------|---------|-------------|
| `font_family` | string | `"Inter, system-ui, sans-serif"` | Primary body font. CSS font-family stack — include fallbacks. |
| `heading_font` | string | `"Inter, system-ui, sans-serif"` | Font for headings. CSS font-family stack. |
| `font_size_base` | 14–20 | 16 | Base body font size in **px** (number, not string like `"16px"`). |
| `type_scale_ratio` | 1.125–1.5 | 1.25 | Modular scale ratio for heading sizes. `1.125` = subtle, `1.25` = major third, `1.5` = dramatic. |
| `body_line_height` | 1.4–1.8 | 1.6 | Line height multiplier for body text. |
| `heading_line_height` | 1.0–1.3 | 1.15 | Line height multiplier for headings. |
| `measure` | 60–75 | 68 | Optimal line length in `ch` units. |
| `heading_weight` | 300–900 | 700 | Explicit heading font weight override. |
| `heading_letter_spacing` | string | `"0"` | CSS letter-spacing with `em` units. Valid range: −0.04em to 0.12em. Example: `"0.05em"`, `"-0.02em"`. |

---

## 📐 Spacing

| Token | Range / Enum | Default | Description |
|-------|-------------|---------|-------------|
| `space_base` | 4 or 8 | 8 | Base spacing unit in px. |
| `space_ratio` | 1.5–2 | 1.5 | Geometric progression ratio for spacing scale. |

Recommended: `space_base: 8, space_ratio: 1.5` is a safe default for most sites.

---

## 📐 Corners (Radius)

| Token | Range | Default | Description |
|-------|-------|---------|-------------|
| `radius_base` | 0–16 | 8 | Base corner radius in px. `0` = sharp, `8` = standard, `12` = soft, `16` = round. |
| `radius_card` | 0–48 | (derived) | Optional card corner override. |
| `radius_button` | 0–48 | (derived) | Optional button corner override. |
| `radius_pill` | 0–48 | (derived) | Optional pill/tag corner override. |

---

## 📐 Elevation (Shadows)

| Token | Range | Default | Description |
|-------|-------|---------|-------------|
| `shadow_strength` | 0–1 | 0.35 | Shadow depth. `0` = flat, `0.2` = subtle, `0.35` = medium, `0.6` = strong, `1.0` = dramatic. |
| `shadow_softness` | 0–1 | 0.5 | Shadow blur. `0` = tight/hard, `0.5` = standard, `1.0` = soft/large blur. |

---

## 📐 Borders

| Token | Range / Enum | Default | Description |
|-------|-------------|---------|-------------|
| `border_width` | 0–2 | 1 | Structural border width in px. |
| `border_style` | `solid` or `none` | `solid` | Border style for structural dividers. |
| `border_color` | optional hex | (derived) | Optional explicit border color. Omit for neutral-ramp-derived border. |

---

## 📐 Motion

| Token | Range / Enum | Default | Description |
|-------|-------------|---------|-------------|
| `transition_duration` | 120–360 | 200 | Base transition duration in ms. |
| `transition_easing` | `ease`, `ease-in-out`, `ease-out`, `linear`, `material-standard`, `snappy` | `ease-out` | Curated easing curves only — do not invent values. |

---

## 🎭 Personality Enums (effects)

These are retained from v1 — choose one value per field:

| Field | Valid Values | Default | Use For |
|-------|-------------|---------|---------|
| `heading_style` | `natural`, `editorial`, `elegant`, `uppercase` | `natural` | Heading weight/spacing personality |
| `card_style` | `image-overlay`, `flat`, `outlined`, `elevated` | `image-overlay` | Link card visual treatment |
| `hover_effect` | `none`, `lift`, `glow`, `outline` | `lift` | Card hover animation feedback |
| `entry_animation` | `none`, `fade`, `slide-up`, `fade-slide-up` | `fade-slide-up` | Card entry motion when scrolling or after filtering |

### Heading Style Guide
- `natural`: Standard weight (700) and spacing (0). Neutral and versatile.
- `editorial`: Heavy weight (800), tight letter-spacing (−0.03em). Bold and modern.
- `elegant`: Light weight (300), wide letter-spacing (0.07em). Refined and airy.
- `uppercase`: All-caps with tracked spacing (0.10em), strong weight (700). Structured and institutional.

### Card Style Guide
- `image-overlay`: Dark overlay gradient over thumbnail, white text. Cinematic/editorial.
- `flat`: Solid surface background, no shadow, dark text. Clean/academic.
- `outlined`: Primary-color border, no shadow, dark text. Editorial/technical.
- `elevated`: Strong shadow, no border, dark text. Product/dashboard feel.

### Hover Effect Guide
- `none`: No animation. Static and document-like.
- `lift`: Card rises slightly with translateY. Default tactile feel.
- `glow`: Colored halo using primary color. Vivid/creative.
- `outline`: Crisp border appears on hover. Sharp and keyboard-friendly.

### Entry Animation Guide
- `none`: Cards appear instantly. Clean and minimal.
- `fade`: Gentle opacity fade. Subtle and lightweight.
- `slide-up`: Cards rise from below. Playful and dynamic.
- `fade-slide-up`: Combined fade + slide (default). The most common and versatile choice.

---

## 🔍 WCAG Accessibility Requirements

You MUST choose colors that satisfy these contrast ratios. `validate.py` will reject failing palettes.

| Pair | Ratio | Notes |
|------|-------|-------|
| `text` on `background` | ≥ 4.5:1 | Normal text must be readable |
| `text_muted` on `background` | ≥ 3:1 | Secondary text minimum (large text threshold) |
| `primary` on `background` | ≥ 4.5:1 (normal text) / ≥ 3:1 (large text) | Primary brand color used as text or UI element |
| `accent` on `background` | ≥ 4.5:1 (normal text) / ≥ 3:1 (large text) | Accent color used as text |

**Guidelines:**
- For light backgrounds (#f0f0f0–#ffffff), use dark text (#111–#333).
- For dark backgrounds (#0a0a0a–#222), use light text (#ddd–#fff).
- Avoid pure white (#ffffff) backgrounds with pale text — it's the most common WCAG fail.
- Use the [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) to verify.

---

## ✅ Pre-submission Checklist

Before outputting your `design.json`, verify each of these:

- [ ] `theme` contains ALL four required sections: `colors`, `typography`, `layout`, `effects`
- [ ] `colors` contains at minimum `primary`, `background`, and `text`
- [ ] Every hex color is `#` followed by exactly 6 hex digits (`^#[0-9a-fA-F]{6}$`)
- [ ] All numeric values are within their declared bounds (see tables above)
- [ ] `font_size_base` is a **number** (e.g., `16`), NOT a string like `"16px"`
- [ ] `heading_letter_spacing` uses `em` units (e.g., `"0"`, `"0.05em"`, `"-0.03em"`) and is between −0.04em and 0.12em
- [ ] `space_base` is `4` or `8`
- [ ] All enum values are valid (check enums for `heading_style`, `card_style`, `hover_effect`, `entry_animation`, `border_style`, `transition_easing`)
- [ ] `overlay_strength`, `brand_saturation`, `neutral_temperature`, `shade_spread` are numbers 0–1 (or −1–1 for temperature)
- [ ] Contrast ratios against `background` satisfy the WCAG requirements listed above
- [ ] No removed fields present: `heading_size_scale`, `shadow_intensity`, `border_radius`, `border_treatment`
- [ ] This is a **breaking change** — do not reuse old v1 design.json values; author fresh v2-compliant values

---

## 📤 Output Format

Provide exactly one JSON code block for `design.json`. Do not add markdown formatting inside the JSON.

```json
{
  "theme": {
    "colors": { ... },
    "typography": { ... },
    "layout": { ... },
    "spacing": { ... },
    "radius": { ... },
    "elevation": { ... },
    "border": { ... },
    "motion": { ... },
    "effects": { ... }
  }
}
```
