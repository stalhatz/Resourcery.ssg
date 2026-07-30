"""Tests for token_gen.py — pure function token generators."""
import json
import pytest
from pathlib import Path
from resourcery_ssg.token_gen import (
    hex_to_hsl,
    hsl_to_hex,
    generate_color_ramps,
    generate_semantic_tokens,
    generate_type_scale,
    generate_spacing,
    generate_radius,
    generate_elevation,
    generate_motion,
    generate_theme_tokens,
    _derive_dark_tokens,
)


# ============================================================================
# Color conversion helpers
# ============================================================================


class TestHexToHsl:
    @pytest.mark.unit
    def test_black(self):
        h, s, l = hex_to_hsl("#000000")
        assert l == 0

    @pytest.mark.unit
    def test_white(self):
        h, s, l = hex_to_hsl("#ffffff")
        assert l == 100

    @pytest.mark.unit
    def test_pure_red(self):
        h, s, l = hex_to_hsl("#ff0000")
        assert h in (0, 360)
        assert s == 100

    @pytest.mark.unit
    def test_roundtrip(self):
        hex_color = "#2563eb"
        h, s, l = hex_to_hsl(hex_color)
        result = hsl_to_hex(h, s, l)
        # HSL roundtrip may have slight rounding differences
        assert result[0] == "#"
        assert len(result) == 7
        # Colors should be within 1 unit per channel
        orig_r, orig_g, orig_b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        res_r, res_g, res_b = int(result[1:3], 16), int(result[3:5], 16), int(result[5:7], 16)
        assert abs(orig_r - res_r) <= 2
        assert abs(orig_g - res_g) <= 2
        assert abs(orig_b - res_b) <= 2


# ============================================================================
# Color ramps
# ============================================================================


class TestGenerateColorRamps:
    @pytest.mark.unit
    def test_generates_primary_ramp(self):
        anchors = {"primary": "#2563eb"}
        levers = {"brand_saturation": 0.8, "neutral_temperature": 0, "shade_spread": 0.6}
        ramps = generate_color_ramps(anchors, levers)

        # Primary steps 50–900
        for step in [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]:
            assert f"--color-primary-{step}" in ramps

        # 500 should be the anchor
        assert ramps["--color-primary-500"] == "#2563eb"

    @pytest.mark.unit
    def test_generates_neutral_ramp(self):
        anchors = {"primary": "#2563eb"}
        levers = {"brand_saturation": 0.8, "neutral_temperature": 0, "shade_spread": 0.6}
        ramps = generate_color_ramps(anchors, levers)

        for step in [0, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
            assert f"--color-neutral-{step}" in ramps

    @pytest.mark.unit
    def test_all_values_are_valid_hex(self):
        anchors = {"primary": "#2563eb"}
        levers = {"brand_saturation": 0.8, "neutral_temperature": 0, "shade_spread": 0.6}
        ramps = generate_color_ramps(anchors, levers)

        import re
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for key, value in ramps.items():
            assert hex_pattern.match(value), f"{key}: {value} is not valid hex"

    @pytest.mark.unit
    def test_lighter_steps_are_lighter(self):
        anchors = {"primary": "#2563eb"}
        levers = {"brand_saturation": 0.8, "neutral_temperature": 0, "shade_spread": 0.6}
        ramps = generate_color_ramps(anchors, levers)

        _, _, l_50 = hex_to_hsl(ramps["--color-primary-50"])
        _, _, l_400 = hex_to_hsl(ramps["--color-primary-400"])
        _, _, l_500 = hex_to_hsl(ramps["--color-primary-500"])
        _, _, l_900 = hex_to_hsl(ramps["--color-primary-900"])

        assert l_50 > l_400 > l_500 > l_900, f"Lightness: {l_50} > {l_400} > {l_500} > {l_900}"

    @pytest.mark.unit
    def test_shade_spread_affects_ramp_range(self):
        anchors = {"primary": "#2563eb"}
        narrow = generate_color_ramps(anchors, {"shade_spread": 0.1, "brand_saturation": 0.8, "neutral_temperature": 0})
        wide = generate_color_ramps(anchors, {"shade_spread": 0.9, "brand_saturation": 0.8, "neutral_temperature": 0})

        _, _, narrow_50 = hex_to_hsl(narrow["--color-primary-50"])
        _, _, narrow_900 = hex_to_hsl(narrow["--color-primary-900"])
        _, _, wide_50 = hex_to_hsl(wide["--color-primary-50"])
        _, _, wide_900 = hex_to_hsl(wide["--color-primary-900"])

        narrow_range = narrow_50 - narrow_900
        wide_range = wide_50 - wide_900

        # Wider spread should produce a larger lightness range
        assert wide_range > narrow_range, f"wide={wide_range} should be > narrow={narrow_range}"


# ============================================================================
# Semantic tokens
# ============================================================================


class TestGenerateSemanticTokens:
    @pytest.mark.unit
    def test_generates_all_semantic_tokens(self):
        anchors = {"primary": "#2563eb", "text": "#1e293b", "accent": "#7c2d12"}
        levers = {"overlay_strength": 0.7}
        tokens = generate_semantic_tokens(anchors, levers)

        expected_keys = [
            "--color-border",
            "--color-border-strong",
            "--color-overlay",
            "--color-primary-subtle",
            "--color-on-primary",
            "--color-accent-rgb",
        ]
        for key in expected_keys:
            assert key in tokens, f"Missing {key}"

    @pytest.mark.unit
    def test_accent_rgb_is_r_g_b_triplet(self):
        anchors = {"accent": "#7c2d12", "primary": "#2563eb", "text": "#1e293b"}
        levers = {"overlay_strength": 0.7}
        tokens = generate_semantic_tokens(anchors, levers)

        rgb = tokens["--color-accent-rgb"]
        parts = [int(x.strip()) for x in rgb.split(",")]
        assert len(parts) == 3
        for p in parts:
            assert 0 <= p <= 255

    @pytest.mark.unit
    def test_accent_rgb_matches_hex(self):
        anchors = {"accent": "#7c2d12", "primary": "#2563eb", "text": "#1e293b"}
        levers = {"overlay_strength": 0.7}
        tokens = generate_semantic_tokens(anchors, levers)

        rgb = tokens["--color-accent-rgb"]
        r, g, b = [int(x.strip()) for x in rgb.split(",")]
        assert r == 0x7c
        assert g == 0x2d
        assert b == 0x12


# ============================================================================
# Type scale
# ============================================================================


class TestGenerateTypeScale:
    @pytest.mark.unit
    def test_generates_all_steps(self):
        scale = generate_type_scale(16, 1.25)

        for n in range(-1, 7):
            assert f"--font-size-{n}" in scale
        assert "--font-size-base" in scale
        assert scale["--font-size-base"] == "16px"

    @pytest.mark.unit
    def test_scale_progression(self):
        scale = generate_type_scale(16, 1.25)

        # Each step should be larger than the previous
        sizes = []
        for n in range(-1, 7):
            size_str = scale[f"--font-size-{n}"]
            sizes.append(float(size_str.replace("px", "")))

        for i in range(1, len(sizes)):
            assert sizes[i] > sizes[i-1], f"{sizes[i]} <= {sizes[i-1]}"

    @pytest.mark.unit
    def test_major_third(self):
        scale = generate_type_scale(16, 1.25)
        # 16 * 1.25^1 = 20
        size_1 = float(scale["--font-size-1"].replace("px", ""))
        assert size_1 == pytest.approx(20.0, abs=0.5)

    @pytest.mark.unit
    def test_small_ratio(self):
        scale = generate_type_scale(16, 1.125)
        size_1 = float(scale["--font-size-1"].replace("px", ""))
        assert size_1 == pytest.approx(18.0, abs=0.5)

    @pytest.mark.unit
    def test_large_base_font(self):
        scale = generate_type_scale(20, 1.5)
        assert scale["--font-size-base"] == "20px"
        size_6 = float(scale["--font-size-6"].replace("px", ""))
        assert size_6 > 100  # very large heading at ratio 1.5


# ============================================================================
# Spacing scale
# ============================================================================


class TestGenerateSpacing:
    @pytest.mark.unit
    def test_generates_eight_steps(self):
        spacing = generate_spacing(8, 1.5)
        for n in range(1, 9):
            assert f"--space-{n}" in spacing

    @pytest.mark.unit
    def test_base_8_default(self):
        spacing = generate_spacing(8, 1.5)
        assert spacing["--space-1"] == "8px"
        # space-2 = 8 * 1.5 = 12
        assert "12" in spacing["--space-2"]

    @pytest.mark.unit
    def test_base_4(self):
        spacing = generate_spacing(4, 2)
        assert spacing["--space-1"] == "4px"
        assert spacing["--space-2"] == "8px"

    @pytest.mark.unit
    def test_progressive_growth(self):
        spacing = generate_spacing(8, 1.5)
        sizes = [float(spacing[f"--space-{n}"].replace("px", "")) for n in range(1, 9)]
        for i in range(1, len(sizes)):
            assert sizes[i] >= sizes[i-1]


# ============================================================================
# Radius
# ============================================================================


class TestGenerateRadius:
    @pytest.mark.unit
    def test_generates_scale_from_base(self):
        radius = generate_radius(8)
        assert radius["--radius-sm"] == "4px"
        assert radius["--radius-md"] == "8px"
        assert radius["--radius-lg"] == "16px"
        assert radius["--radius-xl"] == "24px"

    @pytest.mark.unit
    def test_generates_per_element_fallbacks(self):
        radius = generate_radius(8)
        assert "--radius-card" in radius
        assert "--radius-button" in radius
        assert "--radius-pill" in radius

    @pytest.mark.unit
    def test_accepts_overrides(self):
        radius = generate_radius(8, {"radius_card": 12, "radius_button": 6})
        assert radius["--radius-card"] == "12px"
        assert radius["--radius-button"] == "6px"

    @pytest.mark.unit
    def test_zero_base(self):
        radius = generate_radius(0)
        assert radius["--radius-sm"] == "0px"
        assert radius["--radius-md"] == "0px"
        assert radius["--radius-lg"] == "0px"


# ============================================================================
# Elevation / Shadows
# ============================================================================


class TestGenerateElevation:
    @pytest.mark.unit
    def test_generates_four_shadows(self):
        shadows = generate_elevation(0.35, 0.5)
        for i in range(1, 5):
            assert f"--shadow-{i}" in shadows

    @pytest.mark.unit
    def test_flat_shadows(self):
        shadows = generate_elevation(0, 0.5)
        shadow_4 = shadows["--shadow-4"]
        # Alpha should be 0
        assert "rgba(0, 0, 0, 0.0" in shadow_4 or "rgba(0, 0, 0, 0)" in shadow_4

    @pytest.mark.unit
    def test_max_strength(self):
        shadows = generate_elevation(1.0, 0.5)
        shadow_4 = shadows["--shadow-4"]
        # Max base alpha is 0.25
        assert "rgba(0, 0, 0, 0.25" in shadow_4

    @pytest.mark.unit
    def test_hard_vs_soft_blur(self):
        hard = generate_elevation(0.5, 0.0)
        soft = generate_elevation(0.5, 1.0)

        # Format: 0 <y>px <blur>px <spread>px rgba(...)
        # Extract the blur value (3rd numeric value)
        import re
        def extract_blur(shadow_str):
            parts = shadow_str.split()
            return float(parts[2].replace("px", ""))

        hard_blur = extract_blur(hard["--shadow-1"])
        soft_blur = extract_blur(soft["--shadow-1"])
        # Soft should have larger blur
        assert soft_blur > hard_blur, f"soft={soft_blur} should be > hard={hard_blur}"


# ============================================================================
# Motion
# ============================================================================


class TestGenerateMotion:
    @pytest.mark.unit
    def test_generates_fast_and_base(self):
        motion = generate_motion(200, "ease-out")
        assert "--transition-fast" in motion
        assert "--transition-base" in motion
        assert "--motion-duration" in motion
        assert "--motion-easing" in motion

    @pytest.mark.unit
    def test_fast_is_half_duration(self):
        motion = generate_motion(200, "ease-out")
        assert "100ms" in motion["--transition-fast"]

    @pytest.mark.unit
    def test_material_standard_easing(self):
        motion = generate_motion(200, "material-standard")
        assert "cubic-bezier(" in motion["--motion-easing"]

    @pytest.mark.unit
    def test_motion_duration_is_ms_string(self):
        motion = generate_motion(300, "ease")
        assert motion["--motion-duration"] == "300ms"


# ============================================================================
# Dark mode derivation
# ============================================================================


class TestDeriveDarkTokens:
    @pytest.mark.unit
    def test_derives_all_anchor_tokens(self):
        anchors = {
            "primary": "#2563eb",
            "background": "#f8fafc",
            "text": "#1e293b",
            "accent": "#7c2d12",
            "error": "#ef4444",
            "success": "#22c55e",
        }
        levers = {"shade_spread": 0.6, "neutral_temperature": 0, "brand_saturation": 0.8}
        dark = _derive_dark_tokens(anchors, levers, {})

        expected = [
            "--color-primary", "--color-secondary", "--color-background",
            "--color-surface", "--color-text", "--color-text-muted",
            "--color-accent", "--color-error", "--color-success",
            "--color-primary-subtle",
        ]
        for key in expected:
            assert key in dark, f"Missing {key}"

    @pytest.mark.unit
    def test_dark_background_is_dark(self):
        anchors = {"primary": "#2563eb", "background": "#ffffff", "text": "#1e293b"}
        levers = {"shade_spread": 0.6, "neutral_temperature": 0, "brand_saturation": 0.8}
        dark = _derive_dark_tokens(anchors, levers, {})
        _, _, bg_l = hex_to_hsl(dark["--color-background"])
        assert bg_l < 20, f"Dark background should be dark, got L={bg_l}"

    @pytest.mark.unit
    def test_dark_text_is_light(self):
        anchors = {"primary": "#2563eb", "background": "#f8fafc", "text": "#1e293b"}
        levers = {"shade_spread": 0.6, "neutral_temperature": 0, "brand_saturation": 0.8}
        dark = _derive_dark_tokens(anchors, levers, {})
        _, _, text_l = hex_to_hsl(dark["--color-text"])
        assert text_l > 70, f"Dark text should be light, got L={text_l}"

    @pytest.mark.unit
    def test_primary_subtle_is_dark_for_dark_mode(self):
        """--color-primary-subtle should be a dark shade in dark mode, not the light tint."""
        anchors = {"primary": "#2563eb", "background": "#f8fafc", "text": "#1e293b"}
        levers = {"shade_spread": 0.6, "neutral_temperature": 0, "brand_saturation": 0.8}
        dark = _derive_dark_tokens(anchors, levers, {})

        subtle_hex = dark["--color-primary-subtle"]
        _, _, subtle_l = hex_to_hsl(subtle_hex)
        assert subtle_l < 30, (
            f"Dark --color-primary-subtle should be dark (L < 30), "
            f"got L={subtle_l} ({subtle_hex})"
        )

    @pytest.mark.unit
    def test_explicit_overrides_take_precedence(self):
        anchors = {"primary": "#2563eb", "background": "#f8fafc", "text": "#1e293b"}
        levers = {"shade_spread": 0.6, "neutral_temperature": 0, "brand_saturation": 0.8}
        overrides = {"background": "#111111", "text": "#eeeeee"}
        dark = _derive_dark_tokens(anchors, levers, overrides)
        assert dark["--color-background"] == "#111111"
        assert dark["--color-text"] == "#eeeeee"


# ============================================================================
# Master token generator
# ============================================================================


class TestGenerateThemeTokens:
    @pytest.fixture
    def theme(self):
        return {
            "colors": {
                "primary": "#2563eb",
                "secondary": "#64748b",
                "background": "#f8fafc",
                "surface": "#f1f5f9",
                "text": "#1e293b",
                "text_muted": "#64748b",
                "accent": "#7c2d12",
                "error": "#ef4444",
                "success": "#22c55e",
                "levers": {
                    "brand_saturation": 0.8,
                    "neutral_temperature": 0,
                    "shade_spread": 0.6,
                },
                "overlay_strength": 0.7,
                "dark": {"auto": True},
            },
            "typography": {
                "font_family": "Inter, system-ui, sans-serif",
                "heading_font": "Inter, system-ui, sans-serif",
                "font_size_base": 16,
                "type_scale_ratio": 1.25,
                "body_line_height": 1.6,
                "heading_line_height": 1.15,
                "measure": 68,
            },
            "layout": {"sidebar_width": "280px", "max_width": "1200px"},
            "spacing": {"space_base": 8, "space_ratio": 1.5},
            "radius": {"radius_base": 8},
            "elevation": {"shadow_strength": 0.35, "shadow_softness": 0.5},
            "border": {"border_width": 1, "border_style": "solid"},
            "motion": {"transition_duration": 200, "transition_easing": "ease-out"},
        }

    @pytest.mark.unit
    def test_produces_all_expected_groups(self, theme):
        tokens = generate_theme_tokens(theme)

        # Color anchors
        assert "--color-primary" in tokens
        assert "--color-background" in tokens
        assert "--color-text" in tokens

        # Ramps
        assert "--color-primary-500" in tokens
        assert "--color-neutral-500" in tokens

        # Semantic
        assert "--color-accent-rgb" in tokens
        assert "--color-border" in tokens

        # Type scale
        assert "--font-size-base" in tokens
        assert "--font-size-1" in tokens

        # Spacing
        assert "--space-1" in tokens
        assert "--space-8" in tokens

        # Radius
        assert "--radius-md" in tokens
        assert "--radius-card" in tokens

        # Elevation
        assert "--shadow-1" in tokens
        assert "--shadow-4" in tokens

        # Motion
        assert "--transition-fast" in tokens
        assert "--transition-base" in tokens

        # Layout
        assert "--sidebar-width" in tokens
        assert "--max-width" in tokens

        # Dark
        assert "--dark-tokens" in tokens
        assert isinstance(tokens["--dark-tokens"], dict)

    @pytest.mark.unit
    def test_accent_rgb_is_parseable(self, theme):
        tokens = generate_theme_tokens(theme)
        rgb = tokens["--color-accent-rgb"]
        parts = [int(x.strip()) for x in rgb.split(",")]
        assert len(parts) == 3
        assert all(0 <= p <= 255 for p in parts)

    @pytest.mark.unit
    def test_with_minimal_config(self):
        """Should not crash with minimal config (all defaults)."""
        minimal = {"colors": {"primary": "#2563eb", "background": "#ffffff", "text": "#000000"}}
        tokens = generate_theme_tokens(minimal)
        assert "--color-primary" in tokens
        assert "--color-primary-500" in tokens
        assert "--font-size-base" in tokens
        assert "--dark-tokens" in tokens

    @pytest.mark.unit
    def test_dark_auto_false_uses_explicit(self):
        theme = {
            "colors": {
                "primary": "#2563eb",
                "background": "#f8fafc",
                "text": "#1e293b",
                "dark": {
                    "auto": False,
                    "background": "#000000",
                    "text": "#ffffff",
                },
            },
        }
        tokens = generate_theme_tokens(theme)
        dark_tokens = tokens["--dark-tokens"]
        assert dark_tokens["--color-background"] == "#000000"
        assert dark_tokens["--color-text"] == "#ffffff"
        # --color-primary-subtle should also be derived in dark auto=false mode
        assert "--color-primary-subtle" in dark_tokens
        _, _, subtle_l = hex_to_hsl(dark_tokens["--color-primary-subtle"])
        assert subtle_l < 30, "Dark subtle should be dark even with auto=False"


# ============================================================================
# End-to-end: load a good fixture and generate all tokens
# ============================================================================


class TestGoodFixture:
    @pytest.mark.unit
    def test_good_json_produces_valid_tokens(self):
        fixture_path = Path(__file__).parent / "fixtures" / "design" / "good.json"
        design = json.loads(fixture_path.read_text())

        tokens = generate_theme_tokens(design["theme"])

        # All values should be strings
        for key, value in tokens.items():
            if key == "--dark-tokens":
                # nested dict
                for dk, dv in value.items():
                    assert isinstance(dv, str), f"Dark token {dk} is not a string: {type(dv)}"
            elif key == "--color-accent-rgb":
                assert isinstance(value, str)
            elif key.startswith("--font-size"):
                assert isinstance(value, str) and value.endswith("px")
            elif key.startswith("--space"):
                assert isinstance(value, str) and value.endswith("px")
            elif key.startswith("--radius"):
                assert isinstance(value, str) and value.endswith("px")
            elif key.startswith("--shadow"):
                assert isinstance(value, str)

    @pytest.mark.unit
    def test_good_json_accent_rgb(self):
        fixture_path = Path(__file__).parent / "fixtures" / "design" / "good.json"
        design = json.loads(fixture_path.read_text())
        tokens = generate_theme_tokens(design["theme"])
        # good.json has accent #7c2d12 → rgb(124, 45, 18)
        rgb = tokens["--color-accent-rgb"]
        assert "124" in rgb
        assert "45" in rgb
        assert "18" in rgb
