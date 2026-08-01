import logging
import re
import sys
import pytest
from pathlib import Path
from resourcery_ssg.design_checks import is_valid_hex_color, validate_effects
from resourcery_ssg.validate import DataValidator
from resourcery_ssg.validate import main as validate_main


@pytest.fixture
def validator(testdata_dir: Path) -> DataValidator:
    return DataValidator(
        data_dir=testdata_dir,
        schemas_dir=testdata_dir.parent.parent / "schemas",  # project root schemas/
    )


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

    @pytest.mark.unit
    def test_missing_schema_file_returns_false_and_records_error(self, tmp_path: Path):
        validator = DataValidator(data_dir=tmp_path, schemas_dir=tmp_path / "noschemas")
        assert validator.load_schemas() is False
        assert any("site.config.schema.json" in e for e in validator.errors)


class TestLoadData:
    @pytest.mark.unit
    def test_loads_both_data_files(self, validator):
        assert validator.load_data() is True
        assert "site_info" in validator.config_data
        assert "links" in validator.links_data

    @pytest.mark.unit
    def test_missing_data_file_returns_false_and_records_error(self, tmp_path: Path):
        validator = DataValidator(
            data_dir=tmp_path,
            schemas_dir=tmp_path.parent.parent / "schemas",
        )
        assert validator.load_data() is False
        assert any("site.config.json" in e for e in validator.errors)

    @pytest.mark.unit
    def test_invalid_json_returns_false_and_records_error(self, tmp_path: Path):
        (tmp_path / "site.config.json").write_text("{bad", encoding="utf-8")
        (tmp_path / "links.json").write_text("{}", encoding="utf-8")
        (tmp_path / "design.json").write_text("{}", encoding="utf-8")
        validator = DataValidator(
            data_dir=tmp_path,
            schemas_dir=tmp_path.parent.parent / "schemas",
        )
        assert validator.load_data() is False
        assert any(
            "site.config.json" in e and "Failed to parse" in e
            for e in validator.errors
        )


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
    def test_no_effects_no_warnings(self):
        errors, warnings = validate_effects({"theme": {"colors": {}}})
        assert errors == []
        assert warnings == []

    @pytest.mark.unit
    def test_elevated_with_no_shadow_warns(self):
        design = {
            "theme": {
                "effects": {
                    "card_style": "elevated",
                },
                "elevation": {
                    "shadow_strength": 0,
                },
                "colors": {},
            }
        }
        errors, warnings = validate_effects(design)
        assert errors == []
        assert any("shadow_strength" in w or "elevated" in w for w in warnings)

    @pytest.mark.unit
    def test_image_overlay_with_outline_warns(self):
        design = {
            "theme": {
                "effects": {
                    "card_style": "image-overlay",
                    "hover_effect": "outline",
                }
            }
        }
        errors, warnings = validate_effects(design)
        assert errors == []
        assert any("hover_effect" in w for w in warnings)


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
            "resourcery_ssg.font_acquirer.extract_google_font_candidates", mock_extract
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
    def test_valid_codes(self):
        assert is_valid_hex_color("#1e40af") is True
        assert is_valid_hex_color("#FFFFFF") is True
        assert is_valid_hex_color("#000000") is True

    @pytest.mark.unit
    def test_invalid_codes(self):
        assert is_valid_hex_color("#FFF") is False
        assert is_valid_hex_color("1e40af") is False
        assert is_valid_hex_color("#GGGGGG") is False
        assert is_valid_hex_color("") is False
        assert is_valid_hex_color(123) is False


class TestValidateAll:
    @pytest.mark.unit
    def test_clean_data_succeeds(self, validator, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.extract_google_font_candidates", lambda s: []
        )
        assert validator.validate_all() is True

    @pytest.mark.unit
    def test_emits_operational_records(self, validator, monkeypatch, caplog):
        """INFO/DEBUG records document what a validation run actually did."""
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.extract_google_font_candidates", lambda s: []
        )
        caplog.set_level(logging.DEBUG)

        assert validator.validate_all() is True

        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Loaded 3 schemas$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.INFO
            and re.search(r"^Validated 3 data files \(\d+ links\)$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.INFO
            and re.search(r"^\d+ warnings, \d+ errors collected$", r.message)
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.DEBUG
            and re.search(r"^Loaded .*\.json \(\d+ records\)$", r.message)
            for r in caplog.records
        )

    @pytest.mark.unit
    def test_fails_on_missing_schema(self, testdata_dir):
        validator = DataValidator(data_dir=testdata_dir, schemas_dir=Path("/nonexistent"))
        assert validator.validate_all() is False


class TestIntegrationValidate:
    @pytest.mark.integration
    def test_validate_end_to_end(self, testdata_dir: Path, monkeypatch):
        monkeypatch.setattr(
            "resourcery_ssg.font_acquirer.extract_google_font_candidates", lambda s: []
        )
        validator = DataValidator(
            data_dir=testdata_dir,
            schemas_dir=testdata_dir.parent.parent / "schemas",  # project root schemas/
        )
        assert validator.validate_all() is True
        assert len(validator.errors) == 0


class TestValidateMain:
    """Entry-point exits of ``validate.main()`` (sys.exit(0/1))."""

    @staticmethod
    def _write_config(tmp_path: Path, testdata_dir: Path) -> Path:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "\n".join(
                [
                    "validate:",
                    f"  data_dir: {testdata_dir}",
                    f"  schemas_dir: {Path(__file__).resolve().parent.parent / 'schemas'}",
                ]
            ),
            encoding="utf-8",
        )
        return cfg

    @pytest.mark.unit
    def test_main_exits_1_on_failure(self, tmp_path, testdata_dir, monkeypatch):
        """Failed validation → SystemExit(1)."""
        cfg = self._write_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.validate.DataValidator.validate_all", lambda self: False
        )
        monkeypatch.setattr(sys, "argv", ["validate", "--config", str(cfg)])

        with pytest.raises(SystemExit) as exc_info:
            validate_main()

        assert exc_info.value.code == 1

    @pytest.mark.unit
    def test_main_exits_0_on_success(self, tmp_path, testdata_dir, monkeypatch):
        """Successful validation → SystemExit(0)."""
        cfg = self._write_config(tmp_path, testdata_dir)
        monkeypatch.setattr(
            "resourcery_ssg.validate.DataValidator.validate_all", lambda self: True
        )
        monkeypatch.setattr(sys, "argv", ["validate", "--config", str(cfg)])

        with pytest.raises(SystemExit) as exc_info:
            validate_main()

        assert exc_info.value.code == 0
