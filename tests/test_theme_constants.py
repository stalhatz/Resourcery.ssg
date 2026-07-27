import pytest
from resourcery_ssg.theme_constants import (
    HEADING_STYLE_CONFIG,
    get_heading_weight,
    get_heading_letter_spacing,
    get_required_weights,
    weights_to_api_param,
    resolve_heading,
    get_effective_weights,
)


class TestGetHeadingWeight:
    @pytest.mark.unit
    def test_valid_styles(self):
        assert get_heading_weight("natural") == 700
        assert get_heading_weight("editorial") == 800
        assert get_heading_weight("elegant") == 300
        assert get_heading_weight("uppercase") == 700

    @pytest.mark.unit
    def test_invalid_style_falls_back_to_default(self):
        assert get_heading_weight("nonexistent") == 700


class TestGetHeadingLetterSpacing:
    @pytest.mark.unit
    def test_valid_styles(self):
        assert get_heading_letter_spacing("natural") == "0"
        assert get_heading_letter_spacing("editorial") == "-0.03em"
        assert get_heading_letter_spacing("elegant") == "0.07em"
        assert get_heading_letter_spacing("uppercase") == "0.10em"

    @pytest.mark.unit
    def test_invalid_style_falls_back_to_default(self):
        assert get_heading_letter_spacing("nonexistent") == "0"


class TestGetRequiredWeights:
    @pytest.mark.unit
    def test_natural(self):
        assert get_required_weights("natural") == [400, 600, 700]

    @pytest.mark.unit
    def test_editorial(self):
        assert get_required_weights("editorial") == [400, 600, 800]

    @pytest.mark.unit
    def test_elegant(self):
        assert get_required_weights("elegant") == [300, 400, 600]

    @pytest.mark.unit
    def test_uppercase(self):
        assert get_required_weights("uppercase") == [400, 600, 700]

    @pytest.mark.unit
    def test_unknown_style(self):
        assert get_required_weights("bogus") == [400, 600, 700]


class TestWeightsToApiParam:
    @pytest.mark.unit
    def test_single_weight(self):
        assert weights_to_api_param([400]) == "0,400"

    @pytest.mark.unit
    def test_multiple_weights(self):
        assert weights_to_api_param([400, 600, 700]) == "0,400;0,600;0,700"

    @pytest.mark.unit
    def test_preserves_order(self):
        assert weights_to_api_param([800, 300]) == "0,800;0,300"


class TestHeadingStyleConfig:
    @pytest.mark.unit
    def test_has_expected_keys(self):
        assert set(HEADING_STYLE_CONFIG.keys()) == {
            "natural",
            "editorial",
            "elegant",
            "uppercase",
        }

    @pytest.mark.unit
    def test_each_entry_has_required_keys(self):
        for style, config in HEADING_STYLE_CONFIG.items():
            assert "heading_weight" in config, f"{style} missing heading_weight"
            assert "letter_spacing" in config, f"{style} missing letter_spacing"
            assert "weights" in config, f"{style} missing weights"
            assert isinstance(config["heading_weight"], int)
            assert isinstance(config["letter_spacing"], str)
            assert isinstance(config["weights"], list)


class TestResolveHeading:
    @pytest.mark.unit
    def test_enum_default_no_overrides(self):
        result = resolve_heading({}, "natural")
        assert result["heading_weight"] == 700
        assert result["heading_letter_spacing"] == "0"

    @pytest.mark.unit
    def test_weight_override(self):
        typography = {"heading_weight": 300}
        result = resolve_heading(typography, "natural")
        # Override should take precedence over enum default (700)
        assert result["heading_weight"] == 300
        # Letter spacing falls back to enum default
        assert result["heading_letter_spacing"] == "0"

    @pytest.mark.unit
    def test_letter_spacing_override(self):
        typography = {"heading_letter_spacing": "0.05em"}
        result = resolve_heading(typography, "uppercase")
        # Spacing override should beat enum default (0.10em)
        assert result["heading_letter_spacing"] == "0.05em"
        # Weight falls back to enum default
        assert result["heading_weight"] == 700

    @pytest.mark.unit
    def test_both_overrides(self):
        typography = {"heading_weight": 300, "heading_letter_spacing": "0.08em"}
        result = resolve_heading(typography, "editorial")
        assert result["heading_weight"] == 300
        assert result["heading_letter_spacing"] == "0.08em"

    @pytest.mark.unit
    def test_unknown_style_uses_default(self):
        result = resolve_heading({}, "nonexistent")
        assert result["heading_weight"] == 700  # natural default
        assert result["heading_letter_spacing"] == "0"


class TestGetEffectiveWeights:
    @pytest.mark.unit
    def test_includes_override_weight(self):
        typography = {"heading_weight": 900}
        weights = get_effective_weights(typography, "natural")
        assert 900 in weights
        # Should also include body weights
        assert 400 in weights
        assert 600 in weights

    @pytest.mark.unit
    def test_includes_enum_weights(self):
        typography = {}
        weights = get_effective_weights(typography, "elegant")
        assert 300 in weights  # elegant weight
        assert 400 in weights  # body weight
        assert 600 in weights  # body weight

    @pytest.mark.unit
    def test_deduplicates(self):
        typography = {"heading_weight": 700}
        weights = get_effective_weights(typography, "natural")
        # 700 should appear only once (already in natural weights)
        assert weights.count(700) == 1

    @pytest.mark.unit
    def test_returns_sorted(self):
        typography = {}
        weights = get_effective_weights(typography, "natural")
        assert weights == sorted(weights)
