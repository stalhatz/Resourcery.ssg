import json
import pytest
from pathlib import Path
from validate import DataValidator


@pytest.fixture
def validator(testdata_dir: Path) -> DataValidator:
    return DataValidator(root_dir=testdata_dir.parent.parent)


class TestLoadJson:
    @pytest.mark.unit
    def test_valid_json(self, validator, testdata_dir: Path):
        result = validator.load_json(testdata_dir / "site.config.json")
        assert isinstance(result, dict)
        assert "site_info" in result

    @pytest.mark.unit
    def test_file_not_found(self, validator, tmp_path: Path):
        result = validator.load_json(tmp_path / "nonexistent.json")
        assert result == {}
        assert any("not found" in e for e in validator.errors)

    @pytest.mark.unit
    def test_invalid_json(self, validator, tmp_path: Path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json}", encoding="utf-8")
        result = validator.load_json(bad_file)
        assert result == {}
        assert any("Invalid JSON" in e for e in validator.errors)


class TestLoadSchemas:
    @pytest.mark.unit
    def test_loads_both_schemas(self, validator):
        assert validator.load_schemas() is True
        assert "$schema" in validator.config_schema
        assert "$schema" in validator.links_schema

    @pytest.mark.unit
    def test_schema_has_required_top_keys(self, validator):
        validator.load_schemas()
        assert "title" in validator.config_schema
        assert "title" in validator.links_schema


class TestLoadData:
    @pytest.mark.unit
    def test_loads_both_data_files(self, validator):
        assert validator.load_data() is True
        assert "site_info" in validator.config_data
        assert "links" in validator.links_data


class TestValidateSchema:
    @pytest.mark.unit
    def test_valid_data_passes(self, validator):
        validator.load_schemas()
        validator.load_data()
        result = validator.validate_schema(
            validator.config_data, validator.config_schema, "site.config.json"
        )
        assert result is True

    @pytest.mark.unit
    def test_invalid_data_fails(self, validator):
        validator.load_schemas()
        bad_data = {"bad": "data"}
        result = validator.validate_schema(
            bad_data, validator.config_schema, "bad.json"
        )
        assert result is False


class TestValidateEffects:
    @pytest.mark.unit
    def test_no_effects_no_warnings(self, validator):
        validator.design_data = {"theme": {"colors": {}}}
        validator.validate_effects()
        assert len(validator.warnings) == 0

    @pytest.mark.unit
    def test_elevated_with_no_shadow_warns(self, validator):
        validator.design_data = {
            "theme": {
                "effects": {
                    "card_style": "elevated",
                    "shadow_intensity": "none",
                }
            }
        }
        validator.validate_effects()
        assert any("shadow_intensity" in w for w in validator.warnings)

    @pytest.mark.unit
    def test_image_overlay_with_outline_warns(self, validator):
        validator.design_data = {
            "theme": {
                "effects": {
                    "card_style": "image-overlay",
                    "hover_effect": "outline",
                }
            }
        }
        validator.validate_effects()
        assert any("hover_effect" in w for w in validator.warnings)


class TestValidateFonts:
    @pytest.mark.unit
    def test_no_fonts_no_error(self, validator, monkeypatch):
        validator.design_data = {
            "theme": {
                "typography": {
                    "font_family": "system-ui, sans-serif",
                    "heading_font": "Arial, sans-serif",
                }
            }
        }

        def mock_extract(stack):
            return []

        monkeypatch.setattr(
            "font_acquirer.extract_google_font_candidates", mock_extract
        )
        validator.validate_fonts()
        assert len(validator.errors) == 0


class TestCrossValidate:
    @pytest.mark.unit
    def test_valid_data_passes(self, validator, testdata_dir: Path):
        validator.load_data()
        validator.config_data["navigation"] = {
            "categories": [
                {
                    "id": "tech",
                    "label": "Tech",
                    "children": [{"id": "programming", "label": "Programming"}],
                }
            ],
            "menu_links": [],
        }
        result = validator.cross_validate()
        assert result is True

    @pytest.mark.unit
    def test_bad_category_warns(self, validator):
        validator.config_data = {
            "navigation": {
                "categories": [{"id": "tech", "label": "Tech", "children": []}],
                "menu_links": [],
            },
        }
        validator.links_data = {
            "links": [
                {
                    "id": "l1",
                    "category": "nonexistent",
                    "tags": ["x"],
                    "status": "active",
                    "url": "https://x.com",
                }
            ]
        }
        validator.cross_validate()
        assert any("nonexistent" in w for w in validator.warnings)

    @pytest.mark.unit
    def test_duplicate_ids_errors(self, validator):
        validator.config_data = {
            "navigation": {"categories": [], "menu_links": []},
        }
        validator.links_data = {
            "links": [
                {
                    "id": "dup",
                    "category": "",
                    "tags": ["a"],
                    "status": "active",
                    "url": "https://a.com",
                },
                {
                    "id": "dup",
                    "category": "",
                    "tags": ["b"],
                    "status": "active",
                    "url": "https://b.com",
                },
            ]
        }
        validator.cross_validate()
        assert any("Duplicate" in e for e in validator.errors)

    @pytest.mark.unit
    def test_inactive_link_can_omit_url(self, validator):
        validator.config_data = {
            "navigation": {"categories": [], "menu_links": []},
        }
        validator.links_data = {
            "links": [{"id": "l1", "category": "", "tags": ["x"], "status": "archived"}]
        }
        result = validator.cross_validate()
        assert result is True

    @pytest.mark.unit
    def test_active_link_missing_url_warns(self, validator):
        validator.config_data = {
            "navigation": {"categories": [], "menu_links": []},
        }
        validator.links_data = {
            "links": [{"id": "l1", "category": "", "tags": ["x"], "status": "active"}]
        }
        validator.cross_validate()
        assert any("missing URL" in w for w in validator.warnings)


class TestIsValidHexColor:
    @pytest.mark.unit
    def test_valid_codes(self, validator):
        assert validator._is_valid_hex_color("#1e40af") is True
        assert validator._is_valid_hex_color("#FFFFFF") is True
        assert validator._is_valid_hex_color("#000000") is True

    @pytest.mark.unit
    def test_invalid_codes(self, validator):
        assert validator._is_valid_hex_color("#FFF") is False
        assert validator._is_valid_hex_color("1e40af") is False
        assert validator._is_valid_hex_color("#GGGGGG") is False
        assert validator._is_valid_hex_color("") is False
        assert validator._is_valid_hex_color(123) is False


class TestValidateAll:
    @pytest.mark.unit
    def test_clean_data_succeeds(self, validator, monkeypatch):
        monkeypatch.setattr(
            "font_acquirer.extract_google_font_candidates", lambda s: []
        )
        assert validator.validate_all() is True

    @pytest.mark.unit
    def test_fails_on_missing_schema(self, validator):
        validator.schemas_dir = Path("/nonexistent")
        assert validator.validate_all() is False


class TestIntegrationValidate:
    @pytest.mark.integration
    def test_validate_end_to_end(self, testdata_dir: Path, monkeypatch):
        monkeypatch.setattr(
            "font_acquirer.extract_google_font_candidates", lambda s: []
        )
        validator = DataValidator(root_dir=testdata_dir.parent.parent)
        assert validator.validate_all() is True
        assert len(validator.errors) == 0
