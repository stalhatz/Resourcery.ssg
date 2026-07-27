"""Tests for validate.py design token validation (Package E)."""
import json
import pytest
from pathlib import Path
from resourcery_ssg.validate import DataValidator
from resourcery_ssg.validate import relative_luminance, contrast_ratio, parse_em


# ============================================================================
# Luminance and contrast helpers
# ============================================================================


class TestRelativeLuminance:
    @pytest.mark.unit
    def test_black(self):
        assert relative_luminance("#000000") == pytest.approx(0.0, abs=0.001)

    @pytest.mark.unit
    def test_white(self):
        assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=0.001)

    @pytest.mark.unit
    def test_mid_gray(self):
        lum = relative_luminance("#808080")
        assert 0.2 < lum < 0.25

    @pytest.mark.unit
    def test_blue(self):
        lum = relative_luminance("#2563eb")
        assert 0.07 < lum < 0.20


class TestContrastRatio:
    @pytest.mark.unit
    def test_black_white(self):
        assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.1)

    @pytest.mark.unit
    def test_black_on_white(self):
        # Same ratio regardless of order
        assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.1)

    @pytest.mark.unit
    def test_dark_text_on_light_bg(self):
        ratio = contrast_ratio("#1e293b", "#f8fafc")
        assert ratio > 4.5, f"Expected >4.5, got {ratio}"

    @pytest.mark.unit
    def test_low_contrast(self):
        ratio = contrast_ratio("#d4d4d4", "#ffffff")
        assert ratio < 3.0, f"Expected <3, got {ratio}"

    @pytest.mark.unit
    def test_good_fixture_passes(self):
        """The good.json fixture should pass all contrast checks."""
        fixture = Path(__file__).parent / "fixtures" / "design" / "good.json"
        design = json.loads(fixture.read_text())
        colors = design["theme"]["colors"]

        text_bg = contrast_ratio(colors["text"], colors["background"])
        assert text_bg >= 4.5, f"text/bg={text_bg}"

        muted_bg = contrast_ratio(colors["text_muted"], colors["background"])
        assert muted_bg >= 3.0, f"text_muted/bg={muted_bg}"


# ============================================================================
# parse_em
# ============================================================================


class TestParseEm:
    @pytest.mark.unit
    def test_zero(self):
        assert parse_em("0") == 0.0

    @pytest.mark.unit
    def test_positive(self):
        assert parse_em("0.10em") == pytest.approx(0.10)

    @pytest.mark.unit
    def test_negative(self):
        assert parse_em("-0.03em") == pytest.approx(-0.03)

    @pytest.mark.unit
    def test_no_em_unit(self):
        assert parse_em("0.05") == pytest.approx(0.05)

    @pytest.mark.unit
    def test_valid_boundary(self):
        # -0.04 is the lower bound
        assert parse_em("-0.04em") == pytest.approx(-0.04)
        # 0.12 is the upper bound
        assert parse_em("0.12em") == pytest.approx(0.12)

    @pytest.mark.unit
    def test_invalid_string_returns_none(self):
        assert parse_em("abc") is None

    @pytest.mark.unit
    def test_empty_returns_none(self):
        assert parse_em("") is None


# ============================================================================
# validate_design_tokens
# ============================================================================


class TestValidateDesignTokens:
    @pytest.mark.unit
    def test_good_fixture_passes(self):
        fixture = Path(__file__).parent / "fixtures" / "design" / "good.json"
        design = json.loads(fixture.read_text())

        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = design
        validator.errors = []

        # Import the function
        from resourcery_ssg.validate import validate_design_tokens
        validate_design_tokens(validator)

        assert len(validator.errors) == 0, f"Unexpected errors: {validator.errors}"

    @pytest.mark.unit
    def test_bad_range_fails(self):
        fixture = Path(__file__).parent / "fixtures" / "design" / "bad_range.json"
        design = json.loads(fixture.read_text())

        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = design
        validator.errors = []

        from resourcery_ssg.validate import validate_design_tokens
        validate_design_tokens(validator)

        assert len(validator.errors) >= 1, "Should have at least 1 error for out-of-range values"

        # At least one error should mention brand_saturation or heading_letter_spacing
        error_text = " ".join(validator.errors).lower()
        assert "brand_saturation" in error_text or "heading_letter_spacing" in error_text or "range" in error_text

    @pytest.mark.unit
    def test_bad_contrast_fails(self):
        fixture = Path(__file__).parent / "fixtures" / "design" / "bad_contrast.json"
        design = json.loads(fixture.read_text())

        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = design
        validator.errors = []

        from resourcery_ssg.validate import validate_design_tokens
        validate_design_tokens(validator)

        assert len(validator.errors) >= 1, f"Errors: {validator.errors}"
        error_text = " ".join(validator.errors).lower()
        assert "contrast" in error_text or "ratio" in error_text

    @pytest.mark.unit
    def test_old_vocabulary_fails_schema(self):
        """Old vocabulary design.json must fail schema validation."""
        fixture = Path(__file__).parent / "fixtures" / "design" / "old_vocabulary.json"
        design = json.loads(fixture.read_text())

        # Load the actual schema
        schemas_dir = Path(__file__).parent.parent / "schemas"
        design_schema = json.loads((schemas_dir / "design.schema.json").read_text())

        from jsonschema import validate as js_validate, ValidationError

        # This should raise a ValidationError because old_vocabulary.json
        # has heading_size_scale, shadow_intensity, border_radius, border_treatment
        # which are NOT in the new schema (additionalProperties: false)
        with pytest.raises(ValidationError):
            js_validate(instance=design, schema=design_schema)


# ============================================================================
# validate_effects (new model)
# ============================================================================


class TestValidateEffectsNew:
    @pytest.mark.unit
    def test_outlined_with_zero_border_warns(self):
        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = {
            "theme": {
                "effects": {"card_style": "outlined"},
                "border": {"border_width": 0},
                "colors": {},
            }
        }
        validator.validate_effects()
        # outlined + border_width 0 is contradictory
        assert any("border_width" in w or "outlined" in w for w in validator.warnings), \
            f"Expected warning about outlined + border_width 0, got: {validator.warnings}"

    @pytest.mark.unit
    def test_elevated_with_zero_shadow_warns(self):
        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = {
            "theme": {
                "effects": {"card_style": "elevated"},
                "elevation": {"shadow_strength": 0},
                "colors": {},
            }
        }
        validator.validate_effects()
        assert any("shadow_strength" in w or "elevated" in w for w in validator.warnings)

    @pytest.mark.unit
    def test_image_overlay_with_outline_warns(self):
        validator = DataValidator(data_dir=Path("."), schemas_dir=Path("."))
        validator.design_data = {
            "theme": {
                "effects": {
                    "card_style": "image-overlay",
                    "hover_effect": "outline",
                },
                "colors": {},
            }
        }
        validator.validate_effects()
        assert any("outline" in w for w in validator.warnings)
