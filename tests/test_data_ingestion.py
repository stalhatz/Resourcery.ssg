"""E2E test for data ingestion pipeline."""

import pytest
from pathlib import Path
from resourcery_ssg.validate import DataValidator
from resourcery_ssg.data_ingestion import run_ingestion


# Root of the test directory — used to locate fixtures and project dirs
_TEST_DIR = Path(__file__).parent
_FIXTURES_DIR = _TEST_DIR / "fixtures"
_PROJECT_DIR = _TEST_DIR.parent


@pytest.mark.e2e
def test_data_ingestion_e2e(tmp_path, pytestconfig):
    """Run the full ingestion pipeline and validate output against schemas.

    This test requires --model to be passed via pytest CLI.
    It is skipped by default (use `pytest -m e2e --model <name>`).
    """
    model = pytestconfig.getoption("--model")
    if not model:
        pytest.skip("use --model to run E2E test")

    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Pick a note and site prompt from test fixtures
    note = _FIXTURES_DIR / "markdown" / "notes" / "tech-links.md"
    site_prompt = _FIXTURES_DIR / "markdown" / "site_prompts" / "dev-portal.md"
    schemas_dir = _PROJECT_DIR / "schemas"
    prompt_path = _PROJECT_DIR / "prompts" / "data-ingestion.md"

    run_ingestion(
        note_path=note,
        site_prompt_path=site_prompt,
        schemas_dir=schemas_dir,
        prompt_path=prompt_path,
        model=model,
        output_dir=output_dir,
        opencode_bin=pytestconfig.getoption("--opencode-path"),
        debug=True,  # preserve workspace for debugging on failure
    )

    # Validate output files exist
    assert (output_dir / "links.json").exists(), "links.json missing"
    assert (output_dir / "site.config.json").exists(), "site.config.json missing"
    assert (output_dir / "design.json").exists(), "design.json missing"

    # Use DataValidator for schema + cross-validation
    validator = DataValidator(root_dir=str(_PROJECT_DIR))
    validator.data_dir = output_dir  # point to output, not default data/

    # Load schemas (from canonical schemas/ dir)
    assert validator.load_schemas(), "Failed to load schemas"

    # Load generated data
    validator.config_data = validator.load_json(output_dir / "site.config.json")
    validator.links_data = validator.load_json(output_dir / "links.json")
    validator.design_data = validator.load_json(output_dir / "design.json")
    assert validator.config_data, "site.config.json is empty/invalid"
    assert validator.links_data, "links.json is empty/invalid"
    assert validator.design_data, "design.json is empty/invalid"

    # Schema validation
    config_valid = validator.validate_schema(
        validator.config_data, validator.config_schema, "site.config.json"
    )
    links_valid = validator.validate_schema(
        validator.links_data, validator.links_schema, "links.json"
    )
    design_valid = validator.validate_schema(
        validator.design_data, validator.design_schema, "design.json"
    )

    assert config_valid, (
        f"site.config.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )
    assert links_valid, (
        f"links.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )
    assert design_valid, (
        f"design.json schema validation failed: "
        f"{validator.errors[-1] if validator.errors else 'unknown'}"
    )

    # Cross-validation
    cross_valid = validator.cross_validate()
    assert cross_valid, "Cross-validation failed"
    assert len(validator.errors) == 0, (
        f"Errors during validation: {validator.errors}"
    )
