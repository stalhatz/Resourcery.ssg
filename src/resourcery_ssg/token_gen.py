"""
Pure functions for generating CSS design tokens from a design.json theme configuration.
All functions are deterministic and testable — no side effects, no I/O.

Used by build.py at render time to produce a flat dict of CSS custom properties.
"""

import colorsys
import math
from typing import Dict, List, Optional


# ============================================================================
# Color conversion helpers
# ============================================================================


def hex_to_hsl(hex_color: str) -> tuple:
    """Convert a six-digit hex color to HSL.

    hex_color: e.g. "#2563eb".

    Returns: (hue 0-360, saturation 0-100, lightness 0-100) tuple.
    """

    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return (round(h * 360), round(s * 100), round(l * 100))


def _format_px(value: float) -> str:
    """Format a number as px string, stripping redundant .0."""

    if value == int(value):
        return f"{int(value)}px"
    return f"{round(value, 2)}px"


def hsl_to_hex(h: float, s: float, l: float) -> str:
    """Convert HSL values to a six-digit hex color.

    h: hue 0-360.
    s: saturation 0-100.
    l: lightness 0-100.

    Returns: hex string e.g. "#2563eb".
    """

    h_norm = (h % 360) / 360.0
    r_norm, g_norm, b_norm = colorsys.hls_to_rgb(h_norm, l / 100.0, s / 100.0)
    r = max(0, min(255, round(r_norm * 255)))
    g = max(0, min(255, round(g_norm * 255)))
    b = max(0, min(255, round(b_norm * 255)))
    return f"#{r:02x}{g:02x}{b:02x}"


# ============================================================================
# Color ramp generation
# ============================================================================


def generate_color_ramps(anchors: dict, levers: dict) -> dict:
    """Generate primary and neutral color ramps from anchor colors and levers.

    anchors: dict with at minimum 'primary', 'background', 'text' hex strings.
    levers: dict with brand_saturation (0-1), neutral_temperature (-1-1),
        shade_spread (0-1).

    Returns: flat dict mapping CSS custom property names to hex values.
    """

    primary_hex = anchors.get("primary", "#2563eb")
    brand_saturation = levers.get("brand_saturation", 0.8)
    neutral_temperature = levers.get("neutral_temperature", 0)
    shade_spread = levers.get("shade_spread", 0.6)

    h, s, l = hex_to_hsl(primary_hex)

    # --- Primary ramp (50 .. 900) ---
    # 500 = anchor; above = darker; below = lighter
    # shade_spread controls how far lightness deviates from 50%
    # brand_saturation controls chroma retention in tints

    primary_vars = {}
    primary_vars["--color-primary-500"] = primary_hex

    for step_val in [50, 100, 200, 300, 400, 600, 700, 800, 900]:
        if step_val < 500:
            # Tint: mix toward white as step decreases
            t = (500 - step_val) / 450.0  # 0 (at 500) → 1 (at 50)
            spread_factor = 0.3 + 0.7 * shade_spread
            new_l = l + (100 - l) * t * spread_factor
            # Saturation drops as we approach white; brand_saturation resists
            sat_factor = 1.0 - t * (1.0 - brand_saturation * 0.5)
            new_s = max(s * sat_factor, 0)
        else:
            # Shade: mix toward black as step increases
            t = (step_val - 500) / 400.0  # 0 (at 500) → 1 (at 900)
            spread_factor = 0.3 + 0.7 * shade_spread
            new_l = l - l * t * spread_factor
            # Saturation increases slightly in shades
            new_s = min(s * (1.0 + t * 0.3), 100)

        primary_vars[f"--color-primary-{step_val}"] = hsl_to_hex(h, new_s, new_l)

    # --- Neutral ramp (0 .. 1000) ---
    # neutral_temperature: -1 = cool (blue tint ~210°), 0 = pure gray, +1 = warm (beige ~30°)
    neutral_hue = 30 * neutral_temperature  # 0 at temp=0, -30..+30
    if neutral_temperature < 0:
        neutral_hue = 210 + (240 - 210) * abs(neutral_temperature)  # cool blue
    elif neutral_temperature > 0:
        neutral_hue = 30 * neutral_temperature  # warm beige

    neutral_vars = {}
    # Ramp goes 0 (near-white) through 500 (mid) to 1000 (near-black)
    for step_val in [0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
        t = step_val / 1000.0  # 0 → 1
        # Lightness: near-white at 0, mid at 500, near-black at 1000
        if step_val <= 500:
            l_val = 98 - (98 - 50) * (step_val / 500.0)
        else:
            l_val = 50 - 50 * ((step_val - 500) / 500.0)

        # Saturation: very low for neutrals, temperature controls chroma
        s_val = 2 + 6 * abs(neutral_temperature)  # 2%–8%

        neutral_vars[f"--color-neutral-{step_val}"] = hsl_to_hex(neutral_hue, s_val, l_val)

    return {**primary_vars, **neutral_vars}


# ============================================================================
# Semantic tokens
# ============================================================================


def generate_semantic_tokens(anchors: dict, levers: dict, dark: Optional[dict] = None) -> dict:
    """Generate semantic CSS tokens (borders, overlays, accent rgb, etc.).

    anchors: dict with color hex strings.
    levers: dict with overlay_strength.
    dark: optional dark mode anchor overrides dict (may contain auto: bool).

    Returns: flat dict of CSS custom properties.
    """

    overlay_strength = levers.get("overlay_strength", 0.7)
    primary_hex = anchors.get("primary", "#2563eb")
    accent_hex = anchors.get("accent", "#7c3aed")
    neutral_temperature = levers.get("neutral_temperature", 0)
    text_hex = anchors.get("text", "#0f172a")

    # Border colors from neutral ramp (derived from text + temperature)
    text_h, text_s, text_l = hex_to_hsl(text_hex)
    border_hue = text_h + 30 * neutral_temperature
    border_sat = 2 + 4 * abs(neutral_temperature)

    # --color-border: subtle structural borders
    border_l = 85 if text_l < 50 else 20
    border_color = hsl_to_hex(border_hue, border_sat, border_l)

    # --color-border-strong: visible borders (draws from text)
    border_strong_l = text_l * 0.8 if text_l < 50 else 100 - (100 - text_l) * 0.85
    border_strong_color = hsl_to_hex(text_h, text_s * 0.3, border_strong_l)

    # --color-overlay: scrim color (brand-aware)
    # Use either primary hue with low sat, or neutral
    ov_h, ov_s, ov_l = hex_to_hsl(primary_hex)
    overlay_alpha = overlay_strength
    overlay_color = hsl_to_hex(ov_h, ov_s * 0.3, 15)

    # --color-primary-subtle: light tint of primary for hover/focus bg
    p_h, p_s, p_l = hex_to_hsl(primary_hex)
    subtle_l = 90 if p_l < 50 else p_l + 30
    subtle_color = hsl_to_hex(p_h, p_s * 0.2, min(subtle_l, 95))

    # --color-on-primary: text on primary background (white or black)
    on_primary = "#ffffff" if p_l < 60 else "#000000"

    # --color-accent-rgb: r,g,b triplet for alpha composability
    accent_clean = accent_hex.lstrip("#")
    ar, ag, ab = int(accent_clean[0:2], 16), int(accent_clean[2:4], 16), int(accent_clean[4:6], 16)

    semantic = {
        "--color-border": border_color,
        "--color-border-strong": border_strong_color,
        "--color-overlay": overlay_color,
        "--color-primary-subtle": subtle_color,
        "--color-on-primary": on_primary,
        "--color-accent-rgb": f"{ar}, {ag}, {ab}",
    }

    return semantic


# ============================================================================
# Typographic scale
# ============================================================================


def generate_type_scale(font_size_base: float, type_scale_ratio: float) -> dict:
    """Generate modular type scale CSS variables.

    font_size_base: base font size in px (e.g. 16).
    type_scale_ratio: modular scale ratio (e.g. 1.25 → major third).

    Returns: flat dict with --font-size--1..6 and --font-size-base.
    """

    vars = {}
    base = font_size_base

    for n in range(-1, 7):
        size = round(base * (type_scale_ratio ** n), 2)
        vars[f"--font-size-{n}"] = _format_px(size)

    vars["--font-size-base"] = _format_px(base)

    return vars


# ============================================================================
# Spacing scale
# ============================================================================


def generate_spacing(space_base: int, space_ratio: float) -> dict:
    """Generate spacing scale CSS variables.

    space_base: base spacing unit in px (4 or 8).
    space_ratio: geometric ratio for progressive spacing.

    Returns: flat dict with --space-1..8.
    """

    vars = {}
    for n in range(1, 9):
        size = round(space_base * (space_ratio ** (n - 1)), 2)
        vars[f"--space-{n}"] = _format_px(size)

    return vars


# ============================================================================
# Radius scale
# ============================================================================


def generate_radius(radius_base: float, overrides: Optional[dict] = None) -> dict:
    """Generate border-radius CSS variables.

    radius_base: base corner radius in px.
    overrides: optional dict with radius_card, radius_button, radius_pill keys.

    Returns: flat dict with --radius-sm/md/lg/xl + per-element overrides.
    """

    overrides = overrides or {}
    r = radius_base

    vars = {
        "--radius-sm": _format_px(max(0, r * 0.5)),
        "--radius-md": _format_px(r),
        "--radius-lg": _format_px(r * 2),
        "--radius-xl": _format_px(r * 3),
    }

    # Per-element fallbacks (from scale)
    if "radius_card" in overrides and isinstance(overrides["radius_card"], (int, float)):
        vars["--radius-card"] = _format_px(overrides["radius_card"])
    else:
        vars["--radius-card"] = _format_px(r * 2)

    if "radius_button" in overrides and isinstance(overrides["radius_button"], (int, float)):
        vars["--radius-button"] = _format_px(overrides["radius_button"])
    else:
        vars["--radius-button"] = _format_px(r * 0.75)

    if "radius_pill" in overrides and isinstance(overrides["radius_pill"], (int, float)):
        vars["--radius-pill"] = _format_px(overrides["radius_pill"])
    else:
        vars["--radius-pill"] = "999px"

    return vars


# ============================================================================
# Elevation / shadows
# ============================================================================


def generate_elevation(shadow_strength: float, shadow_softness: float) -> dict:
    """Generate box-shadow CSS variables from strength and softness.

    shadow_strength: 0 = flat, 1 = maximum depth (drives alpha).
    shadow_softness: 0 = tight/hard, 1 = soft/large blur.

    Returns: flat dict with --shadow-1..4.
    """

    # Base alpha values multiplied by strength
    base_alphas = [0.06, 0.10, 0.15, 0.25]  # for shadow-1..4
    # Blur values: hard (tight) to soft (large)
    min_blurs = [2, 6, 10, 16]
    max_blurs = [8, 16, 30, 48]
    # Spread values
    min_spreads = [0, -1, -2, -4]
    max_spreads = [2, 2, 4, 8]
    # Y offset
    min_y = [1, 2, 4, 8]
    max_y = [2, 6, 12, 24]

    vars = {}
    for i in range(4):
        alpha = round(base_alphas[i] * shadow_strength, 3)
        blur = round(min_blurs[i] + (max_blurs[i] - min_blurs[i]) * shadow_softness, 1)
        spread = round(min_spreads[i] + (max_spreads[i] - min_spreads[i]) * shadow_softness, 1)
        y_offset = round(min_y[i] + (max_y[i] - min_y[i]) * shadow_softness, 1)

        vars[f"--shadow-{i+1}"] = f"0 {y_offset}px {blur}px {spread}px rgba(0, 0, 0, {alpha})"

    return vars


# ============================================================================
# Motion / transitions
# ============================================================================


def generate_motion(transition_duration: float, transition_easing: str) -> dict:
    """Generate transition CSS variables.

    transition_duration: base duration in ms.
    transition_easing: one of the curated easing keywords.

    Returns: flat dict with --transition-fast, --transition-base, --motion-duration, --motion-easing.
    """

    easing_map = {
        "ease": "ease",
        "ease-in-out": "ease-in-out",
        "ease-out": "ease-out",
        "linear": "linear",
        "material-standard": "cubic-bezier(0.4, 0.0, 0.2, 1)",
        "snappy": "cubic-bezier(0.2, 0.0, 0.0, 1)",
    }
    easing = easing_map.get(transition_easing, "ease-out")
    duration = int(transition_duration)
    fast_duration = max(int(duration * 0.5), 80)

    return {
        "--transition-fast": f"all {fast_duration}ms {easing}",
        "--transition-base": f"all {duration}ms {easing}",
        "--motion-duration": f"{duration}ms",
        "--motion-easing": easing,
    }


# ============================================================================
# Dark mode derivation
# ============================================================================


def _derive_dark_tokens(anchors: dict, levers: dict, dark_overrides: dict) -> dict:
    """Derive dark mode tokens from light anchors + levers.

    anchors: light mode color dict.
    levers: levers dict.
    dark_overrides: explicit dark.* anchor overrides (may contain auto: bool).

    Returns: dict of CSS custom property names to hex values for dark mode.
    """

    shade_spread = levers.get("shade_spread", 0.6)
    neutral_temperature = levers.get("neutral_temperature", 0)
    brand_saturation = levers.get("brand_saturation", 0.8)

    # Determine dark background from background or neutral
    bg_hex = anchors.get("background", "#ffffff")
    bg_h, bg_s, bg_l = hex_to_hsl(bg_hex)

    # Dark background: near-black tinted by temperature
    dark_bg_hue = 30 * neutral_temperature if neutral_temperature > 0 else (210 + 30 * abs(neutral_temperature))
    dark_bg_l = 8 + 4 * (1 - shade_spread)  # 8–12
    dark_bg_sat = 2 + 4 * abs(neutral_temperature)
    dark_bg = hsl_to_hex(dark_bg_hue, dark_bg_sat, dark_bg_l)

    # Dark surface: slightly lifted
    dark_surface = hsl_to_hex(dark_bg_hue, dark_bg_sat, dark_bg_l + 8)

    # Dark text: near-white
    dark_text_hue = dark_bg_hue
    dark_text = hsl_to_hex(dark_text_hue, 3, 90)

    # Dark text_muted: mid-gray
    dark_text_muted = hsl_to_hex(dark_text_hue, 3, 65)

    # Dark primary: retain hue, boost saturation slightly for dark mode
    primary_hex = anchors.get("primary", "#2563eb")
    p_h, p_s, p_l = hex_to_hsl(primary_hex)
    dark_primary_l = min(p_l + 15, 75)  # lighter for dark bg contrast
    dark_primary_s = min(p_s * (0.9 + 0.3 * brand_saturation), 90)
    dark_primary = hsl_to_hex(p_h, dark_primary_s, dark_primary_l)

    # Dark primary-subtle: very dark muted shade for hover/focus bg in dark mode
    dp_h, dp_s, dp_l = hex_to_hsl(dark_primary)
    dark_subtle_l = 15
    dark_subtle_s = dp_s * 0.15
    dark_subtle = hsl_to_hex(dp_h, dark_subtle_s, dark_subtle_l)

    # Dark accent: similar boost
    accent_hex = anchors.get("accent", "#7c3aed")
    a_h, a_s, a_l = hex_to_hsl(accent_hex)
    dark_accent_l = min(a_l + 15, 75)
    dark_accent_s = min(a_s * (0.9 + 0.3 * brand_saturation), 90)
    dark_accent = hsl_to_hex(a_h, dark_accent_s, dark_accent_l)

    # Dark secondary: muted
    dark_secondary = hsl_to_hex(dark_bg_hue, 3, 60)

    # Dark error/success: slightly lighter for dark bg
    error_hex = anchors.get("error", "#dc2626")
    e_h, e_s, e_l = hex_to_hsl(error_hex)
    dark_error = hsl_to_hex(e_h, e_s, min(e_l + 15, 75))

    success_hex = anchors.get("success", "#16a34a")
    s_h, s_s, s_l = hex_to_hsl(success_hex)
    dark_success = hsl_to_hex(s_h, s_s, min(s_l + 15, 75))

    dark_tokens = {
        "--color-primary": dark_primary,
        "--color-secondary": dark_secondary,
        "--color-background": dark_bg,
        "--color-surface": dark_surface,
        "--color-text": dark_text,
        "--color-text-muted": dark_text_muted,
        "--color-accent": dark_accent,
        "--color-error": dark_error,
        "--color-success": dark_success,
        "--color-primary-subtle": dark_subtle,
    }

    # Apply explicit overrides from dark.* anchors
    override_map = {
        "primary": "--color-primary",
        "secondary": "--color-secondary",
        "background": "--color-background",
        "surface": "--color-surface",
        "text": "--color-text",
        "text_muted": "--color-text-muted",
        "accent": "--color-accent",
        "error": "--color-error",
        "success": "--color-success",
    }
    for key, var_name in override_map.items():
        if key in dark_overrides and dark_overrides[key] is not None:
            dark_tokens[var_name] = dark_overrides[key]

    return dark_tokens


# ============================================================================
# Master token generator
# ============================================================================


def generate_theme_tokens(config_theme: dict) -> dict:
    """Generate all CSS custom property tokens from a theme configuration.

    config_theme: the 'theme' object from design.json (with colors, typography,
        spacing, radius, elevation, border, motion, effects sections).

    Returns: flat dict mapping "--<token-name>" to CSS values. All values
        are strings suitable for direct injection into a style.css template.
    """

    colors = config_theme.get("colors", {})
    typography = config_theme.get("typography", {})
    spacing_cfg = config_theme.get("spacing", {})
    radius_cfg = config_theme.get("radius", {})
    elevation_cfg = config_theme.get("elevation", {})
    border_cfg = config_theme.get("border", {})
    motion_cfg = config_theme.get("motion", {})

    # Extract levers with defaults
    levers = colors.get("levers", {})
    dark_cfg = colors.get("dark", {})

    # --- Color anchors ---
    tokens = {
        "--color-primary": colors.get("primary", "#2563eb"),
        "--color-secondary": colors.get("secondary", "#64748b"),
        "--color-background": colors.get("background", "#ffffff"),
        "--color-surface": colors.get("surface", "#f8fafc"),
        "--color-text": colors.get("text", "#0f172a"),
        "--color-text-muted": colors.get("text_muted", "#64748b"),
        "--color-accent": colors.get("accent", "#7c3aed"),
        "--color-error": colors.get("error", "#dc2626"),
        "--color-success": colors.get("success", "#16a34a"),
    }

    # --- Color ramps ---
    tokens.update(generate_color_ramps(colors, levers))

    # --- Semantic tokens ---
    tokens.update(generate_semantic_tokens(colors, levers, dark_cfg))

    # --- Typography ---
    tokens.update(generate_type_scale(
        typography.get("font_size_base", 16),
        typography.get("type_scale_ratio", 1.25),
    ))

    tokens["--font-family"] = typography.get("font_family", "Inter, system-ui, sans-serif")
    tokens["--heading-font"] = typography.get("heading_font", "Inter, system-ui, sans-serif")
    tokens["--body-line-height"] = str(typography.get("body_line_height", 1.6))
    tokens["--heading-line-height"] = str(typography.get("heading_line_height", 1.15))
    tokens["--measure"] = f"{typography.get('measure', 68)}ch"

    # --- Spacing ---
    tokens.update(generate_spacing(
        spacing_cfg.get("space_base", 8),
        spacing_cfg.get("space_ratio", 1.5),
    ))

    # --- Radius ---
    tokens.update(generate_radius(
        radius_cfg.get("radius_base", 8),
        radius_cfg,
    ))

    # --- Elevation ---
    tokens.update(generate_elevation(
        elevation_cfg.get("shadow_strength", 0.35),
        elevation_cfg.get("shadow_softness", 0.5),
    ))

    # --- Border ---
    tokens["--border-width"] = f"{border_cfg.get('border_width', 1)}px"
    tokens["--border-style"] = border_cfg.get("border_style", "solid")
    explicit_border = border_cfg.get("border_color")
    if explicit_border:
        tokens["--border-color"] = explicit_border
    else:
        tokens["--border-color"] = tokens.get("--color-border", "rgba(0,0,0,0.09)")

    # --- Motion ---
    tokens.update(generate_motion(
        motion_cfg.get("transition_duration", 200),
        motion_cfg.get("transition_easing", "ease-out"),
    ))

    # --- Layout ---
    layout = config_theme.get("layout", {})
    tokens["--sidebar-width"] = layout.get("sidebar_width", "280px")
    tokens["--max-width"] = layout.get("max_width", "1400px")

    # --- Dark mode tokens ---
    dark_auto = dark_cfg.get("auto", True)
    if dark_auto:
        dark_tokens = _derive_dark_tokens(colors, levers, dark_cfg)
    else:
        # Just use explicit dark values or fallback to light
        dark_tokens = {}
        override_map = {
            "primary": ("--color-primary", colors.get("primary", "#2563eb")),
            "secondary": ("--color-secondary", colors.get("secondary", "#64748b")),
            "background": ("--color-background", colors.get("background", "#ffffff")),
            "surface": ("--color-surface", colors.get("surface", "#f8fafc")),
            "text": ("--color-text", colors.get("text", "#0f172a")),
            "text_muted": ("--color-text-muted", colors.get("text_muted", "#64748b")),
            "accent": ("--color-accent", colors.get("accent", "#7c3aed")),
            "error": ("--color-error", colors.get("error", "#dc2626")),
            "success": ("--color-success", colors.get("success", "#16a34a")),
        }
        for key, (var_name, light_default) in override_map.items():
            dark_tokens[var_name] = dark_cfg.get(key, light_default)

        # Derive --color-primary-subtle for dark mode when auto=False
        dark_primary_for_subtle = dark_tokens.get("--color-primary", colors.get("primary", "#2563eb"))
        dp_h, dp_s, dp_l = hex_to_hsl(dark_primary_for_subtle)
        dark_tokens["--color-primary-subtle"] = hsl_to_hex(dp_h, dp_s * 0.15, 15)

    tokens["--dark-tokens"] = dark_tokens  # nested dict for template rendering

    return tokens
