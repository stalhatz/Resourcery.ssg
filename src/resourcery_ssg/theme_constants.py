"""
Single source of truth for heading style → font weight/spacing/download weights mapping.
Imported by both font_acquirer.py and build.py to ensure CSS and font downloads stay in sync.
"""

HEADING_STYLE_CONFIG = {
    "natural": {
        "heading_weight": 700,
        "letter_spacing": "0",
        "weights": [400, 600, 700],
    },
    "editorial": {
        "heading_weight": 800,
        "letter_spacing": "-0.03em",
        "weights": [400, 600, 800],
    },
    "elegant": {
        "heading_weight": 300,
        "letter_spacing": "0.07em",
        "weights": [300, 400, 600],
    },
    "uppercase": {
        "heading_weight": 700,
        "letter_spacing": "0.10em",
        "weights": [400, 600, 700],
    },
}

BODY_WEIGHTS = [400, 600]
DEFAULT_STYLE = "natural"


def get_heading_weight(heading_style: str) -> int:
    """Return the font weight integer for a given heading style name.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: integer font weight (e.g. 700).
    """

    return HEADING_STYLE_CONFIG.get(heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE])[
        "heading_weight"
    ]


def get_heading_letter_spacing(heading_style: str) -> str:
    """Return the letter-spacing CSS value for a given heading style name.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: CSS letter-spacing string (e.g. '0', '-0.03em').
    """

    return HEADING_STYLE_CONFIG.get(heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE])[
        "letter_spacing"
    ]


def get_required_weights(heading_style: str) -> list:
    """Return the sorted deduplicated list of font weights needed for a given heading_style.

    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE if missing.

    Returns: sorted list of integer weight values covering both body and heading.
    """

    style_weights = HEADING_STYLE_CONFIG.get(
        heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE]
    )["weights"]
    return sorted(set(BODY_WEIGHTS + style_weights))


# ============================================================================
# Override-aware heading resolution (new for design token system)
# ============================================================================


def resolve_heading(typography: dict, heading_style: str) -> dict:
    """Resolve effective heading weight and letter-spacing with overrides.

    typography: the 'typography' section from design.json theme. May contain
        heading_weight (int) and heading_letter_spacing (string like "0.05em").
    heading_style: key into HEADING_STYLE_CONFIG; falls back to DEFAULT_STYLE.

    Returns: dict with keys 'heading_weight' (int) and 'heading_letter_spacing' (str).
        Typography overrides take precedence over the enum-derived defaults.
    """

    style_config = HEADING_STYLE_CONFIG.get(
        heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE]
    )

    # Start with enum-derived defaults
    effective_weight = style_config["heading_weight"]
    effective_spacing = style_config["letter_spacing"]

    # Override with typography values if present
    if isinstance(typography, dict):
        if "heading_weight" in typography and typography["heading_weight"] is not None:
            effective_weight = typography["heading_weight"]
        if "heading_letter_spacing" in typography and typography["heading_letter_spacing"] is not None:
            effective_spacing = typography["heading_letter_spacing"]

    return {
        "heading_weight": effective_weight,
        "heading_letter_spacing": effective_spacing,
    }


def get_effective_weights(typography: dict, heading_style: str) -> list:
    """Return sorted set of all font weights needed, including overrides.

    Considers the enum-derived weights from heading_style AND any explicit
    heading_weight override in typography.

    typography: the 'typography' section from design.json.
    heading_style: key into HEADING_STYLE_CONFIG.

    Returns: sorted list of unique integer weight values.
    """

    heading = resolve_heading(typography, heading_style)
    override_weight = heading["heading_weight"]

    # Base weights from enum style
    style_weights = HEADING_STYLE_CONFIG.get(
        heading_style, HEADING_STYLE_CONFIG[DEFAULT_STYLE]
    )["weights"]

    all_weights = set(BODY_WEIGHTS + style_weights + [override_weight])
    return sorted(all_weights)


def weights_to_api_param(weights: list) -> str:
    """Convert a list of integer weights to a Google Fonts ital,wght parameter string.

    weights: list of integer font weights (e.g. [400, 600, 700]).

    Returns: semicolon-separated string of '0,<weight>' pairs.
    """

    return ";".join(f"0,{w}" for w in weights)
